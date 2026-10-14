# fl 模式退出集中化 架构优化复盘

## 背景

NuttX 平台下，任何一条设备命令都会隐式进入 `fl` 交互模式（提示符 `fl>`）。
操作完成后必须显式退出，否则设备卡在 `fl>`，下一个工具（甚至控制台前的人）都无法正常使用。

进入 `fl` 模式是幂等的，退出才是那个"必须做且容易忘"的横切关注点。旧代码把
`enter_fl_mode()` / `exit_fl_mode()` 的配对**手写**在每一个调用点，散落在路由、
CLI、SDK、GDB 桥接多处，形成了典型的"配对易漏"反模式。

## 问题

### 1. 退出散乱、易漏

同一段 `enter → try → finally: exit` 模板在以下位置各写一遍：

- `app/routes/fpb.py`：inject / inject_multi / mem_read / mem_write / info
- `app/routes/transfer.py`：list / stat / mkdir / delete / rename / download
- `cli/commands_file_mem.py`：read / write / dump
- `cli/fpb_cli.py`：inject / unpatch / info / test_serial
- `client.py`：direct read / write

任何一处漏写 `exit_fl_mode()`，设备就会卡在 `fl>`。已经发现的两个真实缺陷：

- **GDB 内存读写**：走内存指令但没有退出，每次 GDB 访问后设备卡在 `fl>`。
- **route info**：手动 exit 位置不统一，异常路径下可能漏退。

### 2. 每块反复进出的担忧

文件传输是"多命令组合操作"（下载 = `fstat` → `fopen` → `fread` × N → `fcrc` → `fclose`）。
若在每个子命令里各自 enter/exit，会产生大量无意义的进出抖动。

## 优化方案

把"退出"这一个横切关注点**集中到一处**，进入保持幂等由协议层自理。

### 服务端路由：`with_fl_exit` 包装器

新增 `app/utils/device_op.py`：

```python
def with_fl_exit(func, keep_fl=False, fpb=None):
    def wrapped():
        try:
            return func()
        finally:
            if not keep_fl:
                target = fpb or get_fpb_inject()
                target.exit_fl_mode()   # 异常也不吞掉 func 的结果
    return wrapped
```

各路由的 `_run_serial_op` 统一接受 `keep_fl` / `fpb` 参数，用 `with_fl_exit` 包住业务函数。
业务函数 `do_*` 里**不再手写** enter/exit，只写纯业务逻辑。

关键点：`_run_serial_op` 仍保留各模块自己的 `run_in_device_worker` 派发（保证按模块 mock
worker 的测试不受影响），只是把工作函数换成被包装过的版本。

### CLI / SDK / GDB：`fl_session()` 上下文管理器

不走路由 `_run_serial_op` 的调用方（CLI 直连、SDK、GDB 桥接），用
`FPBInject.fl_session()` 上下文管理器：

```python
with fpb.fl_session():
    fpb.unpatch(...)
# 离开作用域时自动 exit_fl_mode()，异常也保证
```

### 流式 / worker-direct 路径

一部分操作因为要推送 SSE 进度，不经过 `_run_serial_op`，而是自建一个函数直接丢给
`run_in_device_worker`：

- 读：`/symbols/read/stream`、`/memory/read/stream`
- 注入：`/fpb/inject/stream`、`/fpb/inject-multi/stream`
- 传输：`/transfer/upload-sync`、`/transfer/download-sync`
- 自动注入：`file_watcher_manager` 的 auto-inject / auto-unpatch

这些是最初"退出散乱、易漏"的重灾区（读内存流式路径就曾整段漏掉退出，导致点击读内存后
设备卡在 `fl>`）。现在统一处理：

- 派发给 worker 的函数用 `with_fl_exit(fn, fpb=...)` 包一层，退出仍落在 worker 线程；
- `file_watcher_manager` 这类持有 fpb 实例的，直接用 `with fpb.fl_session():`。

SSE 的结束信号 `progress_queue.put(None)` 属于传输协议、不属于 fl 退出，保留在各自的
`finally` 里，与退出解耦。

### 一次进入、一次退出

因为进入幂等，整个多命令操作只在第一条命令时真正进入 `fl`，靠这里唯一的一次退出离开，
**不会出现每块反复进出**。传输一个大文件全程只有 1 次 enter + 1 次 exit。

### 架构对比

```mermaid
graph TD
    subgraph Before["旧: 退出散落各处"]
        A1["route do_inject<br/>enter/try/finally exit"] --> W1[DeviceWorker]
        A2["route do_download<br/>enter/try/finally exit"] --> W1
        A3["cli read_memory<br/>enter/try/finally exit"] --> S1[serial]
        A4["gdb read/write<br/>❌ 漏 exit"] --> W1
    end

    subgraph After["新: 退出集中一处"]
        B1["route _run_serial_op<br/>纯业务"] --> WFE[with_fl_exit 包装]
        B2["流式 read/inject/传输<br/>纯业务"] --> WFE
        WFE --> W2[DeviceWorker]
        B3["cli read_memory<br/>纯业务"] --> FS[fl_session 上下文]
        B4["gdb read/write ✅<br/>纯业务"] --> FS
        B5["auto-inject/unpatch<br/>纯业务"] --> FS
        FS --> W2
    end
```

## 线程安全分析

结论：**没有引入线程安全问题。**

### 单一属主线程模型

所有串口访问都汇聚到唯一的 `DeviceWorker`（线程名 `fpb-worker`，`daemon=True`）。
它内部是一个 FIFO 命令队列 `_cmd_queue`，`_worker_loop` 串行取出并执行：

```mermaid
sequenceDiagram
    participant Route as Flask 请求线程
    participant Q as _cmd_queue (FIFO)
    participant W as fpb-worker 线程
    participant Ser as 串口

    Route->>Q: enqueue_and_wait(wrapper)
    Note over Route: 阻塞等待 done_event
    W->>Q: get()
    W->>Ser: func() 业务 I/O
    W->>Ser: exit_fl_mode() 退出
    Note over W: enter/退出都在同一线程
    W-->>Route: done_event.set()
```

要点：

1. **退出发生在 worker 线程内**。`with_fl_exit` 的 `wrapped()` 是作为 `run_in_device_worker`
   的 `func` 提交进队列的，它的 `finally: exit_fl_mode()` 在 worker 线程里执行，
   和业务 I/O 是**同一个线程、同一次出队**，没有新增任何跨线程串口访问。

2. **`_in_fl_mode` 状态只在 worker 线程翻转**。`enter_fl_mode` / `exit_fl_mode` 读写
   `_protocol._in_fl_mode` 全部在 worker 线程串行发生，不存在竞态。

3. **请求线程只阻塞等待**。Flask 请求线程通过 `enqueue_and_wait` 提交后阻塞在
   `done_event` 上，不触碰串口。多个并发请求会在队列里排队，天然串行化。

4. **GDB 路径同理**。GDB 的 `read_memory_fn` / `write_memory_fn` 里的 `fl_session()`
   位于 `do_read` / `do_write` 内，而这两个函数经 `run_in_device_worker` 派发，
   退出同样落在 worker 线程。

即：新架构没有增加任何新的共享可变状态，也没有新增跨线程访问路径，
只是把"退出"从"每个调用点各写一遍"变成"包装器/上下文里写一遍"，执行时机和线程都不变。

## 对 fpb_cli 的影响

无负面影响。

- **CLI 直连模式**：单进程、单线程，`fl_session()` 就是普通的 try/finally 语法糖，
  行为与旧的手写 `enter/try/finally: exit` 完全等价。
- **CLI 代理模式（连服务端）**：CLI 只发 HTTP 请求，实际串口操作仍由服务端的
  `fpb-worker` 串行完成，退出策略与 GUI 路由共用同一套 `with_fl_exit`，一致且可靠。

CLI 各命令（inject / unpatch / info / test_serial / read / write / dump）均已改用
`fl_session()`，语义不变但保证了退出配对。

## 测试

- 新增 `tests/test_device_op.py`：覆盖 `with_fl_exit` 的正常返回、异常透传、`keep_fl`、
  显式 `fpb` 与默认 `get_fpb_inject()` 解析等场景。
- `tests/test_fpb_inject.py`：新增 `fl_session` 正常/异常退出用例，以及
  退出校验（bare-Enter 探测 `fl>` 是否仍在）用例。
- 路由测试去掉了对 `enter_fl_mode.assert_called` 的断言（进入现在由包装器隐式处理）。
- 后端全量套件通过，`./format.sh --lint` 干净。

## 收益

- 退出策略从 N 个调用点收敛到 2 个入口（`with_fl_exit` + `fl_session`），
  杜绝"漏写 exit"类缺陷。
- 修复了 GDB 内存访问后卡 `fl>` 的真实 bug。
- 多命令操作保持"一次进、一次出"，无进出抖动。
- 线程模型未变，无并发风险。

## 后续更新：用 `info` 的 `Mode:` 和 `[FLEXIT]` 简化 fl 模式管理

上面描述的是当时的设计。固件后来提供了两个明确信号，上位机据此删掉了大部分猜测逻辑。

固件信号：

- `info` 输出 `Mode: interactive|oneshot` 和 `Platform: <描述>`。`interactive` 表示命令执行后设备停在 `fl>` 循环里（NuttX），`oneshot` 表示没有循环。
- 离开循环时固件一定打印 `[FLEXIT]`（所有退出路径）。

上位机的现在的做法（`core/serial_protocol.py`）：

| 项目 | 以前 | 现在 |
|------|------|------|
| 进入 | `enter_fl_mode`：清缓冲、发换行唤醒、发 `fl\n`、等横幅 `FPBInject Function Loader` | 没有显式进入。NuttX 上任何 `fl ...` 命令本身就会启动循环 |
| 能力判断 | 靠进入握手的副作用推断，`BARE_METAL` 从未被赋值，裸机每条命令都白走一遍握手 | 每个串口对象第一次通信时发 `fl -c info`，读 `Mode:` / `Platform:`，之后缓存（`ensure_mode`）；换串口对象自动重新探测 |
| oneshot 设备 | 同上 | 不进入也不退出，`exit_fl_mode` 直接返回 True，`with_fl_exit`、`fl_session`、GDB 空闲退出自动变成空操作 |
| 退出 | 每轮连发 `q` 和假命令 `fldet`，最多 5 轮，靠 `[FLEXIT]` / `fl_error` / `command not found` 判断 | 发一个 `q`，等 `[FLEXIT]`；最多 3 次。没有 `fldet`，也不再往 nsh 里多打一行 `command not found` |
| 状态同步 | `_in_fl_mode` 只是宿主的猜测 | 所有读串口的地方（协议自己的读、`DeviceWorker` 的后台读）把 `[FLEXIT]` 计数到 `device.fl_exit_seen`；用户在终端自己敲了 `q`，下次退出直接跳过 |
| exec 卡死之后 | 退出照常连发多轮 | 只发一次 `q`，设备正忙于执行命令读不到，不留一堆 `q` 在 shell 里 |

`wakeup_shell_cnt` 保留，含义改为“连接后发送第一条 `fl` 命令（模式探测）之前发多少个换行”。

删除的东西：`enter_fl_mode`、`try_enter_fl_mode`、`Platform` 枚举和 `get_platform()`、横幅依赖、`send_cmd` 里的 “Enter … interactive mode / Missing --cmd 再进入” 分支、`send_cmd` 的 `retry_on_missing_cmd` 参数。

漂移处理：宿主以为在循环里、设备其实已经在 shell（复位、用户手敲 `q`）时，下一次 `exit_fl_mode` 发出的 `q` 会收到 `command not found`，据此清掉标志。反方向（设备在循环里、宿主以为不在）无害：下一条 `fl ...` 命令照常执行，执行成功后标志重新置位，退出时正常离开。

局限：`[FLEXIT]` 被串口驱动拆成两段到达时，被动计数会漏掉一次，这时退回到“发 `q`、读回复”的路径，结果仍然正确，只是多一次往返。

实机验证（NuttX 设备，921600 波特，串口上有大量其他日志输出）：`info`、`exec`、文件列表/下载、重连、手动 `fl -c ping` 把设备留在循环里后再发 `info`、exec 超时后的恢复，每次操作后控制台都回到 nsh，没有多余的 `q` 或 `fldet` 行。
