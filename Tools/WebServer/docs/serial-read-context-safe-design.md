# 串口读取「不丢数据、不爆上下文」设计方案（adb-logcat 式）

> 日期: 2026-04-XX
> 范围: `app/routes/logs.py`(`/api/logs`, `/api/raw_log`, SSE `/api/logs/stream`),
> `cli/fpb_cli.py`(`serial-read`/`serial-send`), `cli/server_proxy.py`(`serial_read`),
> `services/device_worker.py`(`raw_serial_log` 环形缓冲), `client.py`(SDK),
> `core/state.py`(缓冲配置)
> 痛点: AI 读串口时缓冲区可能积压海量数据，一次 `serial-read` 把整段 dump 出来，
> 直接把上下文窗口打爆；但又不能丢数据。目标是做成 adb（logcat/read）那样：
> 游标增量、按需窗口、字节预算可控、可跟随、可丢弃。

---

## 1. 现状分析

### 1.1 已有的正确骨架

设备端 worker 把每段串口 RX 存进**环形缓冲** `raw_serial_log`，每条带单调递增 `id`
（`device_worker._add_raw_serial_log`），上限 `raw_log_max_size = 5000` **条**
（`core/state.py`）。读取支持 `--since <cursor>` 增量（`raw_next` 作为下次游标），
这本质上就是 adb-logcat 的"按位置续读"模型——方向是对的。

### 1.2 会爆上下文的三个缺口

1. **读取无字节预算，整窗 dump。**
   `/api/logs` 把 `id >= raw_since` 的所有条目拼成一整个 `raw_data` 字符串返回
   （`logs.py`），不设任何长度上限。CLI proxy 分支
   （`fpb_cli.serial_read`）拿到后，虽然对**解析出的 `log` 数组**做了 `[-lines:]` 截断，
   却把**完整 `raw_data` 原文**照样塞进输出 JSON。也就是说 `--lines` 只截了一个字段，
   另一个字段仍是全量——这就是"一读就爆"的直接原因。

2. **游标默认 0 = 拉全量。**
   `--since` 默认 0，AI 首次 `serial-read` 会把环形缓冲里积压的**全部**（最多 5000 条）
   一次性取回。设备启动横幅、周期性日志、之前命令的回显全在里面。

3. **缓冲上限按"条数"而非"字节"。**
   5000 条里若有超长行（如一条几 KB 的 dump），总字节量不可控；且积压治理只能靠条数，
   无法回答"我最多愿意接收 N KB"。

结论：**不丢数据**这一半已经具备（环形缓冲 + 游标）；缺的是**读取侧的"上下文预算"与
"消费语义"**——让一次读取的产出大小可控、可预期。

---

## 2. 设计目标（对标 adb）

| adb 行为 | 本方案对应 |
|---|---|
| `logcat` 跟随输出，Ctrl-C 停 | `serial-read --follow`（SSE，带上限自动停） |
| `logcat -t N` 只看最近 N 行 | `serial-read --tail N`（默认就走 tail，不拉全量） |
| `logcat -c` 清缓冲 | 已有 `/api/raw_log/clear`；补 `serial-read --drop` |
| 增量续读（读过不再读） | 已有 `--since <cursor>` + `raw_next`，强化为默认工作方式 |
| 输出量可控、不撑爆终端 | **新增字节预算 `--max-bytes`（默认几 KB）+ 中间截断保留头尾** |

核心原则：**默认安全**——不带参数的一次 `serial-read` 永远只返回"有界的一小段"，
且始终回带游标，让 AI 可以增量把剩下的按需取走，全程零丢失。

---

## 3. 方案

### 3.1 服务端：读取按"字节预算 + 游标"返回，并给出积压元数据

改 `/api/logs` 与 `/api/raw_log`（或新增 `/api/serial/read`）接受：

- `since`（游标，默认 0）
- `max_bytes`（本次最多返回的字节数，默认如 4096）
- `tail`（可选：只要末尾 N 条/N 字节，忽略 since）
- `drop`（可选：不返回数据，仅把游标推进到最新——等价 adb `-c` 的"跳过积压"）

返回结构（关键是让 AI 知道"还剩多少没读"）：

```json
{
  "success": true,
  "data": "....(<= max_bytes, 可能被截断)....",
  "next": 4210,                // 下次 since：本次实际消费到的游标
  "returned_bytes": 4096,
  "pending_bytes": 81920,      // next 之后仍积压的字节数
  "pending_entries": 312,      // 仍积压的条目数
  "dropped": false,            // 是否因预算触发了中段截断
  "buffer_overflowed": false   // 环形缓冲是否已淘汰过更早的数据（真丢失信号）
}
```

要点：
- **截断保留头尾**：当 `since..最新` 的数据超过 `max_bytes`，不是简单砍尾，而是返回
  `头部 K 字节 + "…(<pending> bytes omitted)…" + 尾部 (max_bytes-K) 字节`，并把 `next`
  设为"尾部起始对应的游标"，保证 AI 顺着 `next` 继续读能补回中间被省略的部分（数据不丢，
  只是分页）。若 AI 只想要最新的，用 `--tail`。
- `pending_bytes/entries` 让 AI 明确"还有多少"，从而决定是继续分页读、还是 `--drop` 跳过。
- `buffer_overflowed`：只有当请求的 `since` 已经比环形缓冲最早保留的 `id` 还老时才为真——
  这是**唯一**真正"丢了数据"的情形，显式告知而不是静默。

### 3.2 缓冲：条数上限之外增加字节上限

`core/state.py` 增加 `raw_log_max_bytes`（如 1 MB），`_add_raw_serial_log` 在按条数淘汰之外
也按总字节淘汰。这样"积压治理"有确定的内存与字节上界，`pending_bytes` 也有意义。
（纯读取侧改动不依赖它，但配套能让上限语义完整。）

### 3.3 CLI：默认 tail + 字节预算，修掉"整窗 dump"

`serial-read` 参数重构（保持向后兼容，旧 `--lines/--since` 仍可用）：

- 默认（无参）：等价 `--tail 50 --max-bytes 4096`——**只回最近一小段**，绝不整窗 dump。
- `--since <cursor>`：增量续读，配合 `--max-bytes` 分页。
- `--follow`：走 SSE，边到边打印到 stderr，累计到 `--max-bytes` 或超时自动停（防跟随失控）。
- `--drop`：丢弃/跳过积压，只推进游标（返回新 `next`），用于"我不关心历史，只看接下来的"。
- `--max-bytes N`：本次产出硬上限（对 stdout JSON 的 `data` 字段生效）。

**关键修复**：proxy 分支不再把完整 `raw_data` 放进输出；`data` 一律受 `max_bytes` 约束，
并始终输出 `next` / `pending_bytes`。让"一次读取的输出大小"从不可控变成由参数决定、默认很小。

输出示例（默认调用）：
```json
{
  "success": true,
  "data": "...last ~4KB...",
  "next": 4210,
  "pending_bytes": 81920,
  "hint": "81920 bytes still buffered; read more with --since 4210, or skip with --drop"
}
```
`hint` 直接教 AI 下一步怎么做，避免它误以为"就这些了"或"卡住了"。

### 3.4 serial-send 的回显读取同样设预算

`serial_send(read_response=True)` 目前用 `serial_read(raw_since=0)` 抓回显——同样会拉全量
（`fpb_cli.py`）。改为：send 前先记录当前 `raw_next` 作为游标，send 后只读
`since=该游标 & max_bytes=<小预算>` 的**增量**，即"只拿这条命令产生的回显"，天然有界，
也更准确（不混入历史）。

### 3.5 SDK：暴露同样的游标/预算/跟随

`client.py` 的 `serial_read` 增加 `since / max_bytes / tail / follow / drop` 参数，返回同结构。
组合场景（等待某关键字、限时抓一段、跳过积压再交互）可在 SDK 里编排，配 §CLI 方案的 cookbook。

---

## 4. 典型用法（AI 视角，像 adb 一样）

```bash
# 只看最近一小段（默认安全，绝不爆上下文）
fpbinject serial-read

# 跳过历史积压，从现在开始（adb logcat -c 的效果）
fpbinject serial-read --drop            # -> 返回新的 next 游标

# 发命令并只取这条命令的回显（有界）
fpbinject serial-send "help\r\n"        # 内部按游标增量读

# 增量分页把积压读完，每次一小块
fpbinject serial-read --since 4210 --max-bytes 4096

# 跟随输出，累计 8KB 或 5s 自动停
fpbinject serial-read --follow --max-bytes 8192 --timeout 5
```

---

## 5. 优先级

| 优先级 | 事项 | 类型 | 涉及 |
|:---:|---|---|---|
| P0 | CLI 默认 tail + `--max-bytes`，修掉整窗 dump | **止血** | `fpb_cli.py` |
| P0 | 服务端读取支持 `max_bytes/tail/drop` + `pending_*`/`overflowed` 元数据 | 核心 | `logs.py`, `server_proxy.py` |
| P1 | `serial-send` 回显改增量游标读 | 体验 | `fpb_cli.py` |
| P1 | `--follow`（SSE + 上限自停） | 体验 | `fpb_cli.py`, SSE 复用 |
| P2 | 缓冲增加 `raw_log_max_bytes` 字节上限 | 完备性 | `state.py`, `device_worker.py` |
| P2 | SDK 暴露游标/预算/跟随 + cookbook | API | `client.py`, `Docs/SDK.md` |

> P0 两条一起做即可根治"一读爆上下文"：服务端能按预算切片，CLI 默认只取尾部一小段。

---

## 6. 兼容性

- `--since` / `raw_next` 语义不变，旧脚本继续可用；新增参数都有安全默认值。
- 服务端新增查询参数向后兼容（不传 `max_bytes` 时可保留旧行为或给一个较大的默认——建议
  即使不传也设一个上限，从根上杜绝整窗 dump；这属于"安全默认优先于严格兼容"的取舍，
  需在发布说明里注明）。
- 环形缓冲的 `id` 语义不变；`buffer_overflowed` 是新增的显式丢失信号，旧客户端忽略即可。

---

## 7. 测试计划

- 缓冲积压 1MB，`serial-read`（默认）返回 <= max_bytes，且带 `pending_bytes>0` 与可用 `next`。
- 顺着 `next` 分页读，拼接结果与原始积压**逐字节一致**（验证不丢数据）。
- 中段截断：超预算时返回头+尾+省略标记，`next` 指向尾部起点，续读能补回被省略中段。
- `--drop` 只推进游标、不返回数据；之后只读到新产生的数据。
- `--follow` 累计到 `--max-bytes` 或 `--timeout` 自动停。
- `since` 早于最早保留 id 时 `buffer_overflowed=true`。
- `serial-send` 回显只包含本次命令输出，不含历史。

---

## 8. 结论

现状已具备"不丢数据"的环形缓冲 + 游标骨架，缺的是"读取侧的上下文预算与消费语义"。
按 adb 心智补齐三件事——**默认 tail、字节预算 `max_bytes`、积压元数据（pending/overflow）+
`--drop`/`--follow`**——即可让 AI 读串口像 `adb logcat` 一样：默认只拿一小段、随时增量补齐、
想跳过就 drop、想跟随就 follow，全程不丢数据也不撑爆上下文。P0 的 CLI 默认 tail + 服务端
字节预算是止血关键，应优先落地。
