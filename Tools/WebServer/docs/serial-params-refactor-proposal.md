# 串口传输参数重构方案

## 1. 现状分析

### 1.1 当前参数命名

| 参数名 | UI 标签 | 默认值 | 实际含义 |
|--------|---------|--------|----------|
| `chunk_size` | Chunk Size | 128 | 上传/下载共用的数据块大小 |
| `tx_chunk_size` | TX Chunk | 0 | PC→设备命令分片大小（workaround） |
| `tx_chunk_delay` | TX Delay | 5ms | 命令分片间延迟 |
| `transfer_max_retries` | Max Retries | 10 | 传输失败重试次数 |
| `wakeup_shell_cnt` | Wakeup Count | 3 | 进入 fl 模式前发送换行数 |
| `verify_crc` | Verify CRC | True | 传输后 CRC 校验（强制开启，不可配置） |

### 1.2 核心问题

#### 问题 1：命名混淆

- `chunk_size` vs `tx_chunk_size` 容易混淆，用户不清楚两者的区别
- `tx_chunk_size` 实际是一个 workaround（解决慢速串口驱动丢数据），不是常规传输参数
- `tx_chunk_delay` 依赖 `tx_chunk_size > 0` 才生效，但 UI 上没有明确关联

#### 问题 2：上传/下载共用 chunk_size

当前 `chunk_size` 同时控制两个方向：

```
上传 (PC → 设备):
  chunk_size=128 → base64 编码后 ~176 字节 → 加命令前缀 ~220 字节
  受限于: 设备 shell 接收缓冲区大小（通常 256-512 字节）

下载 (设备 → PC):
  chunk_size=128 → 设备 puts 输出 ~176 字节 base64
  受限于: PC 串口接收能力（通常远大于设备缓冲区）
```

**不对称性**：设备 shell 接收缓冲区通常很小（256-512B），但设备 `puts` 输出能力远大于此。PC 端接收能力几乎无限。因此下载方向可以使用远大于上传方向的 chunk_size，显著提升下载速度。

#### 问题 3：test_serial 只测单方向

当前 `test_serial_throughput` 只测试 PC→设备方向（发送 echo 命令），其 `recommended_chunk_size` 建议值直接用于全局 `chunk_size`，导致下载方向也被限制在较小的值。

### 1.3 数据流分析

```
┌──────────────────────────────────────────────────────────┐
│                    上传 (PC → 设备)                        │
│                                                          │
│  PC 发送命令:                                             │
│  "fl -c upload -a 0x{addr} -d {base64} -r 0x{crc}\n"    │
│       ↑                        ↑                         │
│       命令前缀 ~40B             chunk_size 经 base64 膨胀  │
│                                                          │
│  总命令长度 ≈ 40 + chunk_size * 4/3                       │
│  受限于: 设备 shell 接收缓冲区 (CONFIG_NSH_LINELEN)        │
│                                                          │
│  serial_tx_fragment 在此层再次分片发送                     │
│  (workaround: 某些串口驱动一次写入太多会丢数据)            │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    下载 (设备 → PC)                        │
│                                                          │
│  PC 发送请求:                                             │
│  "fl -c fread --len {chunk_size}\n"  (~30B, 很短)         │
│                                                          │
│  设备响应:                                                │
│  "FREAD {n} bytes crc=0x{crc} data={base64}\n"           │
│       ↑                              ↑                   │
│       响应前缀 ~30B                   chunk_size 经 base64 │
│                                                          │
│  总响应长度 ≈ 30 + chunk_size * 4/3                       │
│  受限于: 设备 puts 输出能力 (通常无限制)                    │
│         PC 串口接收能力 (通常无限制)                        │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 重构方案

### 2.1 参数重命名

| 旧名称 | 新名称 | 新 UI 标签 | 说明 |
|--------|--------|-----------|------|
| `chunk_size` | `upload_chunk_size` | Upload Chunk | 上传方向数据块大小 |
| _(新增)_ | `download_chunk_size` | Download Chunk | 下载方向数据块大小 |
| `tx_chunk_size` | `serial_tx_fragment_size` | TX Fragment | 串口发送分片大小（0=禁用） |
| `tx_chunk_delay` | `serial_tx_fragment_delay` | TX Fragment Delay | 分片间延迟 |
| `transfer_max_retries` | `transfer_max_retries` | Max Retries | 不变 |
| `wakeup_shell_cnt` | `wakeup_shell_cnt` | Wakeup Count | 不变 |
| `verify_crc` | _(删除)_ | — | CRC 校验强制开启，移除配置项 |

**命名原则**：
- `upload/download` 明确方向，消除歧义
- `fragment` 区别于 `chunk`：chunk 是应用层数据分块，fragment 是传输层命令分片（workaround）
- 不做旧参数迁移，用户重新执行一次串口连通性测试即可自动获得最优参数

### 2.2 参数默认值

| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| `upload_chunk_size` | 128 | 16-512, step=16 | 受限于设备 shell 缓冲区 |
| `download_chunk_size` | 1024 | 128-8192, step=128 | 设备 puts 通常无限制 |
| `serial_tx_fragment_size` | 0 | 0-256, step=8 | 0=禁用 |
| `serial_tx_fragment_delay` | 2ms | 1-100ms, step=1 | 仅 fragment > 0 时生效 |

### 2.3 串口连通性测试（test_serial）重构

将现有的单向测试扩展为三阶段双向探测，集成在现有的 "串口连通性测试" 功能中：

```
┌─────────────────────────────────────────────────────┐
│           串口连通性测试 (test_serial) 流程            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Phase 1: TX Fragment 探测                           │
│  ─────────────────────                              │
│  目的: 检测 PC→设备 是否需要分片发送                   │
│                                                     │
│  1. 发送一条中等长度命令 (256B echo)                   │
│  2. 如果成功 → fragment 不需要, 设为 0                │
│  3. 如果失败 → 启用 fragment, 二分法找最大可靠值       │
│     - 从 128 开始, 逐步缩小直到稳定                   │
│     - 设置 fragment_delay = 2ms (保守值)              │
│                                                     │
│  Phase 2: Upload Chunk 探测                          │
│  ─────────────────────                              │
│  目的: 找到设备 shell 接收缓冲区的安全上限             │
│  (与现有 test_serial_throughput 逻辑一致)              │
│                                                     │
│  1. 从 start_size (16B) 开始                         │
│  2. 生成 test_size 字节数据, 构造 echo 命令           │
│  3. 发送并验证 CRC                                   │
│  4. 逐步增大 (×1.4), 直到失败                        │
│  5. upload_chunk_size = last_success × 75%           │
│                                                     │
│  Phase 3: Download Chunk 探测 (新增)                  │
│  ─────────────────────────                          │
│  目的: 找到设备→PC 方向的最大可靠传输块               │
│                                                     │
│  1. 在设备 RAM 中写入测试数据 (使用 Phase 2 的参数)    │
│  2. 从 start_size (256B) 开始                        │
│  3. 发送 "fl -c read --addr {addr} --len {size}"     │
│  4. 验证返回数据的 CRC                               │
│  5. 逐步增大 (×1.5), 直到失败或达到上限 (8192B)       │
│  6. download_chunk_size = last_success × 85%         │
│     (下载方向更稳定, 安全余量可以更小)                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 2.4 测试结果弹窗展示

测试完成后，通过弹窗（Modal Dialog）展示结果，用户确认后自动应用：

```
┌─────────────── 串口连通性测试结果 ───────────────┐
│                                                 │
│  ✅ 测试完成                                     │
│                                                 │
│  ┌─ 推荐参数 ─────────────────────────────────┐ │
│  │  Upload Chunk:       128 B                 │ │
│  │  Download Chunk:     2048 B                │ │
│  │  TX Fragment:        disabled              │ │
│  │  TX Fragment Delay:  2 ms                  │ │
│  └────────────────────────────────────────────┘ │
│                                                 │
│  ┌─ 测试详情 ─────────────────────────────────┐ │
│  │  Upload 最大成功:    170 B                  │ │
│  │  Upload 首次失败:    238 B                  │ │
│  │  Download 最大成功:  2412 B                 │ │
│  │  Download 首次失败:  3618 B                 │ │
│  │  测试耗时:           3.2 s                  │ │
│  └────────────────────────────────────────────┘ │
│                                                 │
│           [应用参数]     [取消]                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

点击 "应用参数" 后自动写入配置并持久化。

---

## 3. CLI / MCP 适配

### 3.1 CLI 参数更新

`fpb_cli.py` 参数直接使用新名称，不保留旧名称：

```bash
# 连通性测试（自动探测所有参数）
fpb_cli.py test-serial

# 手动指定参数
fpb_cli.py inject --upload-chunk-size 128
fpb_cli.py download --download-chunk-size 2048
fpb_cli.py inject --serial-tx-fragment-size 64 --serial-tx-fragment-delay 0.002
```

### 3.2 MCP 工具更新

`test_serial` MCP 工具返回值扩展为包含双向结果：

```json
{
  "upload_chunk_size": 128,
  "download_chunk_size": 2048,
  "serial_tx_fragment_size": 0,
  "serial_tx_fragment_delay": 0.002,
  "upload_max_working_size": 170,
  "upload_failed_size": 238,
  "download_max_working_size": 2412,
  "download_failed_size": 3618,
  "tests": {
    "fragment": [...],
    "upload": [...],
    "download": [...]
  }
}
```

各 MCP 工具（`inject`、`mem_read`、`mem_write`、`mem_dump` 等）不接受单次调用的 chunk 参数覆盖，统一使用全局串口配置。串口参数通过以下方式设置：

1. 连接设备后执行 `test_serial`，自动探测并应用最优参数
2. 通过 `connect` 工具的参数手动指定全局默认值

| 全局配置参数 | 影响的 MCP 工具 |
|-------------|----------------|
| `upload_chunk_size` | `inject`, `mem_write` |
| `download_chunk_size` | `mem_read`, `mem_dump`, 文件下载 |
| `serial_tx_fragment_size` | 所有串口通信 |
| `serial_tx_fragment_delay` | 所有串口通信 |

---

## 4. 实施计划

### Phase 1: 参数重命名 + 拆分

1. `core/config_schema.py`: 重命名参数，新增 `download_chunk_size`
2. `core/state.py`: 删除旧参数，使用新默认值
3. `core/serial_protocol.py`: 区分 upload/download chunk_size，重命名 tx_chunk 引用
4. `core/file_transfer.py`: 构造时接收两个 chunk_size
5. 前端 UI: 更新配置面板标签

### Phase 2: 串口连通性测试扩展

1. `core/serial_protocol.py`: 扩展 `test_serial_throughput()` 为三阶段
2. `app/routes/connection.py`: 更新 API 返回值
3. 前端: 测试完成后弹窗展示结果，点击 "应用参数" 写入配置

### Phase 3: CLI / MCP 适配

1. `cli/fpb_cli.py`: 更新 CLI 参数名
2. `fpb_mcp_server.py`: 更新 MCP 工具参数和返回值
3. 更新所有相关测试

### 涉及文件

| 文件 | 改动内容 |
|------|---------|
| `core/config_schema.py` | 重命名参数，新增 download_chunk_size |
| `core/state.py` | 删除旧参数 |
| `core/serial_protocol.py` | 拆分 chunk_size，扩展 test_serial，重命名 tx_chunk |
| `core/file_transfer.py` | 接收两个 chunk_size |
| `cli/fpb_cli.py` | 更新 CLI 参数名 |
| `fpb_mcp_server.py` | 更新 MCP 工具参数 |
| `app/routes/connection.py` | 更新 test_serial API |
| `static/js/features/connection.js` | 弹窗展示测试结果 |
| `tests/test_*.py` | 更新相关测试 |

---

## 5. 预期收益

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| 下载速度 | chunk_size=128 → ~10 KB/s | download_chunk=2048 → ~80 KB/s |
| 参数可理解性 | 3 个易混淆参数 | 语义清晰的命名 |
| 配置复杂度 | 手动调参 | 连通性测试自动探测 + 弹窗一键应用 |
| 上传速度 | 不变 | 不变（受限于设备缓冲区） |
