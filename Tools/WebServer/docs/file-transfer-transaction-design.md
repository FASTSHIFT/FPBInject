# 文件传输事务性保证 —— 现状分析与整改方案

> 日期: 2026-04-XX
> 范围: `Tools/WebServer/app/routes/transfer.py`, `core/file_transfer.py`,
> `services/device_worker.py`, `core/serial_protocol.py`（上位机）+
> `App/func_loader/fl_file.c`, `fl.c`（固件）
> 议题: 上传/下载进行中，用户（或另一路 CLI/SDK 客户端）发起其他文件操作，
> 导致文件句柄错乱、数据写串、验证误判等一致性问题。

---

## 1. 问题背景

文件上传/下载是一个**多命令序列**（`fopen → fwrite/fread × N → fcrc → fclose`），
不是单条原子命令。在这个序列执行期间，如果穿插进其它文件操作，就可能破坏正在进行的
传输。用户视角的典型场景：

- 上传大文件时，在文件浏览器里点了另一个文件的「下载」；
- 下载进行中，右键「删除 / 重命名」了某个文件；
- 一台设备被多个客户端共享（README 明确宣传「一个 workbench 可被多名工程师共享，
  一个脚本可驱动多台设备」），GUI 在传输，另一个 CLI/SDK 同时发文件命令；
- 传输中触发了 flist 刷新目录。

---

## 2. 现状分析

### 2.1 固件端：全局唯一文件句柄

`fl_context_t` 内嵌**唯一**一个文件上下文（`App/func_loader/fl.h`）：

```c
typedef struct {
    ...
#if FL_USE_FILE
    struct fl_file_ctx_s file_ctx;   /* 只有一个 */
#endif
} fl_context_t;
```

设备**同一时刻只能打开一个文件**。更关键的是 `fl_file_open` 的行为
（`App/func_loader/fl_file.c`）：

```c
int fl_file_open(fl_file_ctx_t* file_ctx, const char* path, const char* mode) {
    ...
    /* Close any previously open file */
    if (file_ctx->fp) {
        fl_println("Warning: Closing previously open file: %s", file_ctx->path);
        fl_file_close(file_ctx);   /* 静默关掉正在传输的文件！ */
    }
    ...
}
```

也就是说，传输 A 正在进行（文件 A 处于 open 状态）时，任何一条新的 `fopen`（比如
下载 B 触发的 `fopen B`）都会**直接把文件 A 关掉**，且仅打印一条 warning，不返回错误。
之后传输 A 的 `fwrite/fread` 会因为 `ctx->file_ctx.fp` 已指向 B（或已被关闭）而写错
文件、读错文件，或直接 `FL_ERR_STATE`。

其它命令的穿插影响：

| 穿插命令 | 对进行中传输的影响 |
|---|---|
| `fopen`（另一个 upload/download 起手） | **句柄被顶替**，A 的后续读写落到 B 或失败 |
| `fclose` | A 的文件被提前关闭，后续 `fwrite/fread` 失败 |
| `fseek` | **文件偏移被改**，A 继续写/读时错位（数据写串） |
| `fread`/`fwrite`（裸命令） | 改变文件偏移，且和 A 的分块错位 |
| `fremove` 正在传输的文件 | 句柄悬空 / 数据丢失，且不可逆 |
| `frename` 正在传输的文件 | 路径与句柄不一致，close/校验语义混乱 |
| `fstat`/`flist`/`fmkdir` | 不持有/改动全局句柄，**相对安全**（只是抢串口时序） |

结论：固件层**没有任何互斥或事务概念**，谁最后 `fopen`/`fseek` 谁赢，先来的传输被
无声破坏。

### 2.2 上位机端：worker 串行，但保护粒度是「单条 worker 任务」

`DeviceWorker`（`services/device_worker.py`）是单线程，串口 I/O 都在这个线程里跑，
命令走一个 FIFO 队列（`_cmd_queue`）。这带来一个**部分**的保护：同一时刻只有一个
worker 任务在执行。

但保护粒度取决于「一个 worker 任务包了多少东西」：

- **上传/下载**：`transfer.py` 把整个 `fopen→循环→fcrc→fclose` 包进**一个**
  `do_upload`/`do_download` 函数，用 `run_in_device_worker(..., timeout=86400.0)`
  作为**单个** worker 任务提交。所以传输全程独占 worker 线程，期间其它 worker 任务
  排在队列里**等它结束**——这一条链本身不会被别的任务从中间插入。

- **短操作**（list/stat/delete/rename/mkdir）：各自是独立的短 worker 任务
  （`_run_serial_op`）。

看起来「单 worker 串行」似乎已经排他了，但实际存在以下**真实漏洞**：

**漏洞 A：传输链内部会主动让出，给了穿插窗口。**
`do_upload`/`do_download` 内部大量调用 `ft.fwrite/fread/fcrc`，这些最终走
`FPBProtocol.send_cmd`，而进入/退出还有 `enter_fl_mode/exit_fl_mode`。真正的排他仅在
「一条 worker 任务执行期间」。上传任务确实是一整条任务，但——

**漏洞 B：多客户端 / 多入口并发。**
worker 队列只保证**单台设备的 worker 线程**串行。但 README 宣传的共享场景里，
CLI/SDK 可以经 `server_proxy` 走 HTTP 打到同一个 server，最终也进同一个 worker，
排队即可；**然而** CLI 还能用 `Client.direct("/dev/ttyACM0")` **绕过 WebServer 直连串口**
（README 明示），此时两个进程各开各的串口会话，worker 队列**完全管不到**，
两条 `fopen/fwrite` 在物理串口上交错，必然错乱。

**漏洞 C：传输任务独占 worker 长达 86400s，短操作被「饿死」而非「被拒绝」。**
传输中用户点删除/重命名，该短任务被排到队列里，要等到整个传输结束（可能几分钟）才
执行。UI 上表现为「卡住无响应」，用户可能重试、叠更多任务，体验与语义都不清晰。理想
行为应是**明确拒绝并告知「传输进行中」**，而不是无限期排队。

**漏洞 D：传输链本身没有「开始即占用」的显式状态。**
没有任何 `transfer_active` 标志。cancel 用的是全局 `_transfer_cancelled` Event，
且**两个传输端点共用同一个全局 Event 与全局 worker**，若前端能同时发起两个 SSE 传输
（两次 fetch），第二个 `do_download` 会作为第二个 worker 任务排在第一个后面，但它们
**共享** `_transfer_cancelled`，cancel 语义会互相污染。

### 2.3 小结：现状能挡住什么、挡不住什么

| 场景 | 现状是否安全 | 原因 |
|---|:---:|---|
| 同一 server、传输中排队一个短操作 | ⚠️ 半安全 | 不会数据错乱（排在传输后），但会「假卡死」，语义差 |
| 同一 server、同时发两个传输 | ❌ 不安全 | 共享全局 cancel Event / 无互斥标志 |
| 多客户端经 server（都进 worker） | ⚠️ 半安全 | 靠 worker FIFO 意外兜底，非设计保证 |
| CLI `Client.direct` 直连串口旁路 | ❌ 不安全 | 完全绕过 worker，物理串口交错 |
| 固件层任意两条 `fopen`/`fseek` 交错 | ❌ 不安全 | 全局唯一句柄，后者静默顶替前者 |

核心判断：**当前的"安全"是 worker 单线程 FIFO 的副作用，不是显式的事务设计。**
一旦出现并发入口（多客户端 / 直连旁路 / 双传输），保证立即失效。需要在**上位机加显式
事务锁**，并在**固件加会话防护**做纵深防御。

---

## 3. 整改目标

1. **互斥**：任一时刻，整机文件系统的「有状态操作序列」（持有 open 句柄的传输）与其它
   文件写操作互斥，不允许交错。
2. **快速失败**：传输进行中，冲突的操作应**立即返回明确错误**（如 `409 Busy /
   transfer in progress`），而不是无限期排队或假卡死。
3. **纵深防御**：上位机加锁是主防线；固件加「会话令牌」防止旁路客户端 / 异常时序破坏
   正在进行的传输。
4. **可取消、可恢复**：传输可被显式取消并干净收尾（关闭句柄、释放锁）；异常/断连时锁
   不泄漏。
5. **向后兼容**：不引入不兼容的协议破坏性变更；固件会话令牌走「可选参数」，旧上位机
   不传时退化为当前行为。

---

## 4. 整改方案

### 4.1 P0 —— 上位机传输互斥锁（主防线，纯上位机）

在 `DeviceState` 上引入一把**可重入区分的传输锁 + 忙标志**，语义为「文件事务锁」：

```python
# core/state.py (DeviceState)
self.file_txn_lock = threading.Lock()   # 保护"有状态文件序列"的排他执行
self.file_txn_active = None             # None 或 {"op": "upload", "path": ..., "since": ts, "id": ...}
```

约定：**所有**文件类端点在进入前都要经过一个统一的门禁装饰器/上下文管理器
`file_transaction(op, path)`：

```python
# 伪代码
@contextmanager
def file_transaction(op, path, exclusive=True):
    acquired = state.device.file_txn_lock.acquire(blocking=False)
    if not acquired:
        raise TransferBusy(state.device.file_txn_active)   # -> HTTP 409
    try:
        state.device.file_txn_active = {"op": op, "path": path,
                                        "since": time.time(), "id": uuid4()}
        yield
    finally:
        state.device.file_txn_active = None
        state.device.file_txn_lock.release()
```

各端点接入策略：

| 端点 | 锁策略 |
|---|---|
| `upload` / `download` | **持锁全程**（从 fopen 到 fclose+校验），`blocking=False`，抢不到即 409 |
| `delete` / `rename` / `mkdir` | 需要持锁（写操作），抢不到即 409 |
| `stat` / `list` | **只读**，可不阻塞传输；但为简化可用「读时快速尝试锁，抢不到就返回 busy 提示或降级为缓存」。首版建议也要求持锁，保证一致 |
| `fseek` / 裸 `fread`/`fwrite`（若暴露） | 必须在持锁的传输上下文内部调用，不单独开放 |

要点：
- 用 **`blocking=False` + 立即 409**，实现「快速失败」目标，杜绝 86400s 假卡死。
- 前端收到 409 时提示「设备正忙：<op> <path> 进行中」，禁用冲突按钮。
- 锁在 `finally` 释放，覆盖异常/取消路径，避免锁泄漏。
- 传输的 cancel Event 改为**每次传输独立**（放进 `file_txn_active`，不再全局共享），
  修掉 2.2 漏洞 D 的 cancel 污染。

> 该项修复 2.2 漏洞 A/B(经 server 部分)/C/D，是收益最高、代价最低的一步。

### 4.2 P0 —— 传输独占不再垄断 worker 语义

保持传输是「单条 worker 任务」不变（数据链原子性靠它），但：
- 冲突判定放在**进入 worker 之前**（HTTP 处理线程里先试 `file_txn_lock`），
  这样短操作在传输中能**立刻**拿到 409，而不是进队列干等。
- worker 队列积压告警（现有 `QUEUE_WARN_THRESHOLD`）之外，补充：传输持锁期间拒绝把
  冲突写任务入队。

### 4.3 P1 —— 固件会话令牌（纵深防御，防旁路 / 防错乱）

上位机锁挡不住 `Client.direct` 旁路直连和物理层交错（2.2 漏洞 B 的直连部分 + 2.1）。
在固件侧增加**文件会话令牌**，让被顶替的旧会话「有感」并能拒绝危险操作：

设计（向后兼容）：
- `fl_file_ctx_t` 增加 `uint32_t session_id;`
- `fopen` 成功时生成/接收一个 `session_id`，响应里回带：`[FLOK] FOPEN ... sid=0xXXXX`。
- 后续 `fwrite/fread/fseek/fcrc/fclose` 支持**可选**参数 `--sid 0xXXXX`：
  - 传了 `--sid` 且与当前 `ctx->file_ctx.session_id` 不符 → 返回
    `FL_ERR_STATE`（"session superseded"），**不执行**危险操作；
  - 未传 `--sid`（旧上位机）→ 保持当前行为（向后兼容）。
- `fopen` 顶替旧句柄时，递增 `session_id`；旧会话后续带着旧 `sid` 的命令会被拒绝，
  从而把「静默顶替」变成「显式失败」，上位机可据此报错并让用户知晓冲突。

可选增强：`fopen` 增加 `--exclusive` 语义——若已有文件打开，返回
`FL_ERR_BUSY` 而不是顶替。是否采用取决于是否希望「后来者失败」而非「先到者失败」。

> 该项把固件从「任由顶替」升级为「会话可辨识、危险操作可拒绝」，即便上位机锁被绕过，
> 也不会把正在进行的传输数据写串到静默错误。

### 4.4 P2 —— 上传采用「临时文件 + 原子改名」提交（防半成品）

即使加了锁，上传中途失败/取消/断电仍会在设备上留下**半截文件**，其它读者可能读到不
完整数据。引入经典的「写临时文件 + rename 提交」：

1. 上传写入 `remote_path + ".part"`（或隐藏临时名）；
2. 写完 + `fcrc` 校验通过后，`frename(".part" → remote_path)` 原子提交；
3. 失败/取消则删除 `.part`，`remote_path` 保持旧内容不变。

前提：确认目标文件系统的 `rename` 是同目录原子替换（FatFS `f_rename` 不允许覆盖已存在
目标，需先 `fremove` 目标再 rename，或用 backend 能力探测）。这一点要按 backend 分别
验证：POSIX rename 覆盖语义 OK；FatFS 需要「删旧→改名」两步，存在窗口，需在文档中标注
局限。

### 4.5 P2 —— 只读快照一致性（可选）

`download` 期间目标文件被本机其它端点改动已被 P0 锁挡住；跨旁路的改动靠 P1 会话令牌
兜底。若需更强保证，可在 `download` 完成时用 `fstat` 的 `mtime/size` 做「传输前后一致
性校验」，发现文件在传输窗口内被改动则告警。

---

## 5. 优先级与工作量

| 优先级 | 事项 | 涉及文件 | 兼容性 |
|:---:|---|---|---|
| P0 | 传输互斥锁 + 忙即 409 + 独立 cancel | `state.py`, `app/routes/transfer.py`（+ 其余文件端点） | 纯上位机，兼容 |
| P0 | 冲突判定前置到 worker 入队之前 | `app/routes/transfer.py`, `device_worker.py` | 纯上位机，兼容 |
| P1 | 固件会话令牌 `--sid`（可选参数） | `fl_file.{h,c}`, `fl_cmd_file.c`, `fl_cmd.h`, `serial_protocol.py`/`file_transfer.py` | 可选参数，旧上位机兼容 |
| P2 | 上传临时文件 + 原子改名提交 | `file_transfer.py`, `app/routes/transfer.py` | 兼容（backend 差异需标注） |
| P2 | 下载前后 `mtime/size` 一致性校验 | `file_transfer.py` | 兼容 |

---

## 6. 测试计划

上位机（pytest）：
- 传输持锁期间，`delete/rename/mkdir/upload/download` 立即返回 409（不阻塞）。
- 传输结束后锁释放，冲突操作恢复成功。
- 传输异常（写失败 / 抛异常 / cancel）后锁必被释放（`finally` 覆盖），无死锁。
- 两个并发传输：第二个被拒；各自 cancel 互不影响（独立 Event）。
- 只读 `stat/list` 的并发策略符合选定语义。

固件（cmocka/host 测试）：
- `fopen` 顶替旧句柄后 `session_id` 递增；旧 `--sid` 的 `fwrite/fseek/fcrc/fclose`
  被拒绝返回 `FL_ERR_STATE`；不带 `--sid` 保持兼容。
- （若实现 `--exclusive`）已有文件打开时 `fopen --exclusive` 返回 `FL_ERR_BUSY`。

集成：
- 上传中途 cancel/失败后，目标路径保持旧内容，`.part` 被清理（P2）。
- FatFS 与 POSIX 两种 backend 的 rename 提交路径分别验证。

---

## 7. 结论与建议落地顺序

现状的一致性「保证」只是单线程 worker FIFO 的**副作用**，在多客户端、直连旁路、双传输
等并发入口下会失效，固件层更是「后 `fopen`/`fseek` 者静默顶替」，无任何事务概念。

建议落地顺序：
1. 先做 **P0 上位机传输锁 + 忙即 409 + 独立 cancel**（小改动、大收益，立即消除大部分
   用户可感知的错乱与假卡死）；
2. 再做 **P1 固件会话令牌**（纵深防御，覆盖旁路与物理交错）；
3. 视需求做 **P2 临时文件原子提交 / 一致性校验**（防半成品与传输窗口内改动）。

P0 完成即可对外宣称「文件操作具备互斥事务保证」；P1/P2 提供更强的纵深与原子提交语义。
