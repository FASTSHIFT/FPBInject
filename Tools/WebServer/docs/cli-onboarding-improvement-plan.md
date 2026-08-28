# CLI / Server / SDK 上手引导改进方案（面向首次使用的 AI）

> 日期: 2026-04-XX
> 范围: `Tools/WebServer/cli/fpb_cli.py`, `cli/server_proxy.py`,
> `core/arg_schema.py`, `core/config_schema.py`, `app/routes/transfer.py`,
> `client.py`(SDK), `main.py`(server), `Docs/CLI.md` / `Docs/SDK.md`
> 目标: 让第一次接触本工具的 AI（或人）从 help / 报错本身就能掌握规律、少踩坑，
> 而不是靠试错或读源码。

---

## 1. 背景

CLI 全部命令输出 JSON，本就是为 AI 集成设计的。但实测发现首次上手的 AI 反复踩同一批坑，
根因不是功能缺失，而是**引导缺失**：正确用法藏在 epilog 的 Notes 段、默认值不写在 help 里、
长耗时操作没有进度反馈、失败时报错不告诉下一步怎么办。本方案逐条给出证据与整改。

---

## 2. 问题清单（含代码证据）

### P1: AI 误以为"必须传 --port 和 --baudrate"

**现状**
- `--port` / `--baudrate` 由 `add_connection_args` 从 config schema 生成，help 文本只有
  `"Serial port device (e.g., /dev/ttyACM0, COM3)"` / `"Serial baud rate"`，**没有说明它们
  是可选的、以及何时才需要**。
- `baudrate` 默认 115200（`config_schema.py`），绝大多数场景无需设置；但 help 不显示默认值，
  AI 看到一个 `--baudrate` 选项就倾向于"补全"它。
- 正确的心智模型（"串口属于 server，不属于 CLI；proxy 模式下 server 已连设备就不用 --port"）
  只写在**主 help 的 epilog 末尾 Notes 段**，命令级 `--help` 和报错里都看不到。

**后果**：AI 对本可离线运行的 `analyze/search/disasm` 也硬塞 `--port`；或在 server 已连设备时
反复传 `--port` 触发不必要的重连。

**整改**
1. 在 `--port` help 里显式标注可选性与触发效果，在 `--baudrate` help 里显示默认值：
   - `--port`: `"Serial port (e.g. /dev/ttyACM0). OPTIONAL: only needed to open a port when no device is connected yet; ELF analysis and already-connected servers don't need it."`
   - `--baudrate`: `"Serial baud rate (default: 115200; rarely needs changing)."`
   - 让 `arg_schema._help_text()` 自动把 `default` 追加进 help（NUMBER/STRING 项统一受益）。
2. 在**每个** OFFLINE 命令（analyze/search/disasm/decompile/signature/compile）的 `--help`
   顶部加一行：`"Offline: no device or --port required."`
3. 无参运行 / `--help` 顶部加一段**三行决策树**（见 §4 的 "quickstart" 文本），把 epilog Notes
   的关键结论前置。

### P2: 文件上传/下载无进度反馈 → 看起来"卡死/超时"

**现状**
- CLI 的 `file_download` / `file_upload`（`fpb_cli.py`）是**同步阻塞**执行，中途无任何输出，
  只在结束时打印一坨 JSON。串口约 55KB/s，一个几百 KB 的文件就是数十秒静默。
- server 端其实有**带 SSE 进度**的 `/api/transfer/download` `/upload`（`transfer.py`，推送
  percent/speed/eta），但 CLI 走的是 `download-sync` / 一次性 multipart，**没用上 SSE**。

**后果**：AI 观察到长时间无输出，判定"工具挂了"或"超时了"，主动杀进程或重试，反而打断/叠加传输。

**整改**
1. CLI transfer 命令默认打印**进度到 stderr**（stdout 仍只输出最终 JSON，保持可管道）：
   - 直接模式：给 `FileTransfer.upload/download` 传 `progress_cb`，按 `已传/总量 + 速率`
     每 ~500ms 刷一行 `\r` 进度到 stderr。
   - proxy 模式：改用 SSE 端点，边收边把 progress 事件转成 stderr 进度行。
2. 传输开始时先打印一行预告到 stderr：
   `"[transfer] <file> <size> over serial (~55 KB/s), expect ~<eta>s; progress on stderr, JSON on stdout when done"`，
   让 AI 预期到耗时，不误判超时。
3. 增加 `--quiet` 关闭进度（脚本/CI 场景）。

### P3: proxy 传输 30s HTTP 超时会误伤大文件（真 bug，不只是引导）

**现状**
- `server_proxy._post` 默认 `_API_TIMEOUT = 30` 秒。`file_download` 走 `_post`，**沿用 30s**。
  按 55KB/s，>~1.6MB（或链路更慢时更小）就会 HTTP 读超时，CLI 报失败——**而 server 端传输
  可能仍在进行**。`file_upload` 硬编码 120s，同样对大文件不安全。

**后果**：这是"看起来超时"的**真实**来源之一，且是 client 侧误判，不是设备问题。

**整改**
1. 传输类 proxy 调用不使用固定 30s：
   - 迁移到 SSE 流式端点（无单请求整体超时，靠 §P2 的活跃度反馈判活）；或
   - 若保留同步端点，超时按 `size / 假定最低速率 + 富余`动态计算（参考 capture.sh 的
     `bytes/55000 + 20s` 经验公式），并设下限。
2. 在超时报错里明确区分"client 等待超时（传输可能仍在进行）"与"设备无响应"，给出
   `建议：改用流式端点 / 增大超时 / 见 §P4 调优`。

### P4: 丢包严重的设备缺乏"怎么调参"的引导

**现状**
- 工具其实齐备：`test-serial`（现已是可靠性压测，见 throughput 方案）、
  `--serial-tx-fragment-size` / `--serial-tx-fragment-delay`（慢驱动丢数的 workaround）、
  `--transfer-max-retries`（CRC 失败重试）、`--upload-chunk-size` / `--download-chunk-size`。
- 但这些散落在 `--help` 的 connection/transfer 组里，**没有任何命令或报错把它们串成一条
  "遇到丢包该怎么办"的处置路径**。AI 遇到 CRC/超时错误时无从下手。

**后果**：面对丢包设备，AI 要么放弃，要么盲目重试。

**整改**
1. 新增引导命令 `fpbinject doctor`（或 `diagnose`）：连上设备后自动跑 `test-serial`，
   根据结果输出**可直接复制的建议命令**，例如：
   - 检测到 TX 丢包 → 建议 `--serial-tx-fragment-size <N> --serial-tx-fragment-delay <d>`；
   - 下行不稳 → 建议下调 `--download-chunk-size`；
   - CRC 偶发 → 建议提高 `--transfer-max-retries`。
   输出同时给 JSON（机器可读）和 stderr 提示（人可读）。
2. 传输/CRC 类失败的 JSON 里统一加一个 `"hint"` 字段，指向 `doctor` 与相关参数，例如：
   `"hint": "serial loss? run 'fpbinject doctor', or retry with --serial-tx-fragment-size 64"`。
3. `test-serial` 结果里把 `recommended_*` 直接组织成一行"应用建议"的命令串（复制即用）。

### P5: 组合场景应引导到 SDK 二次开发

**现状**
- SDK（`from fpbinject import Client`）已提供 Proxy / Direct / Offline 三种入口和
  inject/file_upload/test_serial 等方法，但 CLI/README 很少提示"多步骤组合场景用 SDK 更合适"。
- 例如"扫描一批设备 → 逐个注入 → 校验 → 收集 JSON 结果"这类编排，用 shell 串 CLI 很别扭。

**整改**
1. 在主 help epilog 增加一节 "Scripting multiple steps? Use the Python SDK:" 附最小示例
   （discover → inject → verify）。
2. 在 `Docs/SDK.md` 增加"组合场景配方"（cookbook）：批量注入、下载并校验、失败自动调参重试、
   跨多设备并行。每个配方 20 行内可跑。
3. SDK 的 `file_upload/download` 增加可选 `progress` 回调参数，暴露与 §P2 同源的进度，
   便于二次开发做自己的 UI/日志。

### P6: CLI 传输终止后，server 端不会自动停（生命周期未绑定）

**现状**（代码追踪结论）
- **下载**：CLI proxy 走 `/api/transfer/download-sync`，server 端把整个 `ft.download()`
  丢进 `run_in_device_worker` 的**单个 worker 任务**里执行，而 `file_transfer.download()`
  这条同步路径**没有任何 cancel 检查点**。CLI 侧 Ctrl-C / 杀进程 / 30s HTTP 超时断开后，
  worker 线程仍会把整个文件读完、做完 CRC 才结束。
- **上传**：走 SSE upload 端点，`do_upload` 每个 chunk 前**确实**检查
  `cancel_event.is_set()`——但该 event **只有**显式 `POST /api/transfer/cancel` 才会被 set。
  SSE 生成器（`sse_generator`）只从队列取数据推给客户端，**不感知客户端断开**。CLI 的
  `file_upload/file_download` 也从不调用 `/transfer/cancel`——只发起、不取消。

**根因**：取消是"显式信令"模型（`/transfer/cancel` → set event），**没有绑定到连接
生命周期**。客户端消失 ≠ 取消。

**后果**
- AI 以为传输已停，实际设备仍在被读/写，串口仍被占用；
- P0 事务锁（见 `file-transfer-transaction-design.md`）仍被那次传输持有，紧接着的文件操作
  会吃 `409 busy`，直到 server 真正跑完才释放——AI 会误判"设备卡死/锁死"；
- 半截上传若最终失败，设备上残留半成品（正是事务方案 P2「临时文件 + 原子改名」的场景）。

**整改**（纯上位机）
1. CLI 捕获 `SIGINT`/`KeyboardInterrupt`，在 `finally` 里对 proxy 发一次
   `POST /api/transfer/cancel`，把"客户端放弃"翻译成 server 能识别的取消信令。
2. 给 `file_transfer.download()` 的同步路径补 `cancel_event` 检查点（上传已有，下载同步版缺）。
3. 更彻底：SSE 生成器感知客户端断开（Flask 下 `GeneratorExit` / 写异常）时自动
   `request_cancel(device)`，把"连接断开"直接绑定到"取消"，无需客户端显式调用。
4. 取消后 server 端务必 `fclose` + 释放事务锁（复用 P0 的 `finally`/`end_transaction` 路径），
   避免锁泄漏。

> 与 `file-transfer-transaction-design.md` 协同：那份负责"并发互斥"，本条负责"取消/生命周期"。
> 两者共用同一把事务锁与 `cancel_event`，应一并实现，避免"锁被一个已经没人接收的传输长期占住"。

---

## 3. 优先级

| 优先级 | 问题 | 类型 | 涉及 |
|:---:|---|---|---|
| P0 | P3 proxy 传输超时误伤 | **bug** | `server_proxy.py`（+ 走 SSE） |
| P0 | P2 传输无进度反馈 | 引导/体验 | `fpb_cli.py`, `file_transfer.py` |
| P0 | P6 终止后 server 不停（锁泄漏风险） | **bug** | `fpb_cli.py`, `transfer.py`, `sse.py`, `file_transfer.py` |
| P1 | P1 port/baud 可选性不清晰 | 引导 | `arg_schema.py`, `config_schema.py`, `fpb_cli.py` |
| P1 | P4 丢包调参无引导 | 引导 | 新增 `doctor`；失败 `hint` 字段 |
| P1 | 帮助信息密度过大（见 §5） | 引导 | `fpb_cli.py` help/epilog |
| P2 | P5 组合场景→SDK | 文档/API | `Docs/SDK.md`, epilog, `client.py` |

> P2/P3/P6 建议一起做：都围绕 SSE 流式端点 + `cancel_event` + 事务锁，一次改造同时解决
> "超时误判 / 无进度 / 终止不停 / 锁泄漏"四件事。

---

## 4. 帮助信息密度：分层 + 按功能引导

上面每条整改都倾向于"往 help 里加字"。若不加约束，主 `--help` 会膨胀成一堵墙——
信息密度过大同样会淹没 AI（它可能只截取前几行，或被无关细节带偏）。因此引导要**分层**，
按"当前想做什么"把信息就近投放，而不是全堆在顶层。

### 4.1 分层原则

1. **顶层 `--help` 只放"心智模型 + 命令清单"，不放参数细节。**
   顶层回答两个问题：*我该用哪个命令？* 和 *有哪几条我必须先知道的规律？* 参数细节下沉到
   命令级 `--help`。顶层的心智模型压到 **≤5 条**（见 §4.4），且每条一行。
2. **命令按功能分组展示**，而不是一个扁平的字母序长列表。argparse 支持
   `add_argument_group` / 子命令分组标题，让 AI 一眼看到"分析类 / 设备类 / 文件类 / 诊断类"。
3. **参数说明放到它所属的命令级 `--help`**，只有该命令相关的连接/传输参数才在那里出现，
   而不是所有命令都继承一大坨全局 connection/transfer flags 的 help。
4. **报错即引导（just-in-time）**：与其在 help 里预先解释所有坑，不如在**真的出错时**用
   `hint` 字段就地给出下一步。信息在需要的那一刻才出现，密度天然被摊薄（呼应 §P4 的
   `hint`、§P3 的超时文案分类）。
5. **渐进式披露**：`--help`（简）→ `<cmd> --help`（该命令详解）→ `doctor` / `Docs/*`（深）。
   每一层只承载本层该有的信息量。

### 4.2 命令分组（顶层 help 的呈现）

按功能给子命令分组，标题化展示（示意）：

```
Analysis (offline, no device):   analyze  search  disasm  decompile  signature  compile
Device / patching:               info  connect  inject  unpatch  mem-read  mem-write ...
Files on device:                 file-list  file-stat  file-download  file-upload  file-remove ...
Serial console:                  serial-send  serial-read
Diagnostics / tuning:            test-serial  doctor
Discovery / server:              discover  server-stop  vserial-*
```

AI 先按"我要做的事"定位到组，再进对应命令看细节——顶层不再是一长串无结构命令名。

### 4.3 每组一句"入门提示"（就近投放，而非集中堆叠）

把原本想塞进顶层的规律，拆散成**每组一句**，放在该组/该命令的 help 开头：

| 功能组 | 就近提示（放在组或命令 help 顶部） |
|---|---|
| Analysis | `Offline: no device or --port required.` |
| Device | `--port only needed to open a port the first time; else omit it.` |
| Files | `Serial is slow (~55 KB/s); progress on stderr, JSON on stdout. Not a hang.` |
| Serial console | `Reads are windowed & cursored (like adb logcat); default returns only a small tail.` |
| Diagnostics | `Serial dropping data? run 'doctor' for copy-paste tuning commands.` |

这样每条信息只在"用户正在这个功能里"时出现，顶层保持清爽，命令级也不过载。

### 4.4 顶层心智模型（压缩到 ≤5 行，仅放顶层）

```
FPBInject CLI — before you start:
  1. Analysis (analyze/search/disasm) is OFFLINE — no device, no --port.
  2. The serial port belongs to the WebServer; once a device is connected,
     device commands need NO --port (and --baudrate defaults to 115200).
  3. Serial transfers/reads are slow & windowed: progress on stderr, small
     tail by default — a long-but-progressing op is NOT a hang.
  4. Stuck on serial loss? run `fpbinject doctor`.
  5. Multi-step automation? use the Python SDK (see `<cmd> --help` / Docs/SDK.md).
```

细节一律下沉：port/baud 的完整说明进 Device 组命令 help；传输耗时/进度进 Files 组；
调参进 `doctor`；SDK 配方进 `Docs/SDK.md`。顶层只留"指路"。

---

## 5. 测试计划

- **P1**: `--help` / 各 OFFLINE 命令 `--help` 含可选性说明；`--baudrate` help 含默认值；
  快照测试断言 quickstart 文本存在。
- **P2**: 直接模式与 proxy 模式传输都产生 stderr 进度行、stdout 仍是单一 JSON；`--quiet` 抑制进度。
- **P3**: 模拟慢传输（sleep 的 mock 端点）超过旧 30s 阈值仍成功；超时报错文案区分两类原因。
- **P4**: `doctor` 在给定 `test-serial` 结果下产出预期建议命令；传输失败 JSON 含 `hint`。
- **P5**: `Docs/SDK.md` cookbook 示例可导入运行（至少 offline 部分进 CI）；SDK `progress` 回调被调用。
- **P6**: CLI SIGINT 时对 proxy 发 `/transfer/cancel`；download 同步路径响应 `cancel_event`；
  客户端断开后事务锁最终被释放（无泄漏）；取消后设备句柄被 `fclose`。
- **帮助密度**: 顶层 `--help` 心智模型 ≤5 行；子命令按功能分组标题存在；OFFLINE 命令 help
  不出现设备相关 flags 的噪音（快照测试）。

---

## 6. 结论

首次上手的 AI 踩的坑几乎都能归到"**正确规律没有出现在它读得到的地方**"，或"**信息都在，
但堆成一堵墙、找不到重点**"。对策是两条腿：

1. **把规律补到 AI 读得到的地方**——help、报错 `hint`、进度反馈、`doctor` 命令；
2. **按功能分层投放，控制密度**——顶层只给心智模型 + 分组命令清单，参数细节下沉到命令级，
   处置建议延迟到出错时就近给出（just-in-time）。

其中 P3（超时）、P6（终止不停）是真实 bug，且与 P2（进度）同源，建议围绕 SSE 流式端点 +
`cancel_event` + 事务锁一次性改造；随后做 P1/P4 的 help/`doctor` 引导与 §4 的分层重排，
最后补 P5 的 SDK cookbook。落地顺序：**P0（P2+P3+P6）→ P1/P4 + §4 分层 → P5**。
