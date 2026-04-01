# FL 协议 CRC 完整性与资源安全审计报告 (V2)

> 日期: 2026-04-01
> 范围: `App/func_loader/fl.c` (固件端) + `Tools/WebServer/core/serial_protocol.py`, `core/file_transfer.py` (上位机)
> 基线: 基于 `crc-integrity-audit.md` (2026-03-10) 整改后的代码现状

---

## 1. 问题总览

| # | 问题 | 严重度 | 影响 |
|---|------|:------:|------|
| P1 | `fcrc` / `fclose` 调用顺序不安全 | **高** | CRC 计算期间异常导致文件句柄泄漏 |
| P2 | `cmd_fcrc` 一次性全文件 CRC，大文件阻塞看门狗 | **高** | 嵌入式设备看门狗超时复位 |
| P3 | `cmd_alloc` 缺少 CRC 校验 | **中** | size 参数串口传输错误时静默分配错误大小 |
| P4 | `cmd_fopen` 缺少 CRC 校验 | **中** | path/mode 参数损坏时打开错误文件或错误模式 |
| P5 | `cmd_fremove` 缺少 CRC 校验 | **高** | path 参数损坏时误删文件，不可逆 |
| P6 | `cmd_frename` 缺少 CRC 校验 | **中** | path/newpath 损坏时文件被错误重命名 |

---

## 2. 问题详细分析

### P1: fcrc / fclose 调用顺序不安全

**现状**

`file_transfer.py` 中 `upload()` 和 `download()` 的流程：

```
fopen → fwrite/fread (循环) → fcrc (验证) → fclose
```

`fcrc` 在文件仍然打开时执行。如果 `fcrc` 过程中发生异常（串口超时、CRC 读取失败等），虽然外层有 `try/except` 兜底调用 `fclose()`，但存在以下风险：

1. `fcrc` 内部 seek 到文件头计算 CRC，如果中途失败，文件指针位置不确定
2. 固件端 `cmd_fcrc` 在读取失败时直接 return，未恢复文件指针位置
3. 上位机 `fcrc` 失败后仅打印 warning 继续执行，后续 `fclose` 可能操作在不确定状态的文件上

**整改方案**

将流程改为：先 `fclose`，再重新 `fopen` 只读模式做 CRC 校验，或者直接在 close 之后用独立的 fcrc 流程：

```
fopen("rw") → fwrite (循环) → fclose → fopen("r") → fcrc → fclose
```

更简洁的方案：在上位机侧调整顺序，先 close 再重新 open + fcrc + close：

```python
# file_transfer.py upload() 整改后
# 1. 写入完成后先关闭文件
self.fclose()

# 2. 重新打开只读模式做 CRC 校验
if total_size > 0:
    success, msg = self.fopen(remote_path, "r")
    if success:
        expected_crc = crc16(local_data)
        success, dev_size, dev_crc = self.fcrc(total_size)
        self.fclose()  # 无论 CRC 结果如何都关闭
        if not success:
            return False, "CRC verification failed"
        if dev_size != total_size or dev_crc != expected_crc:
            return False, f"CRC/size mismatch"
```

**优点**：
- 写入数据在 close 时被 flush 到存储，CRC 校验的是最终落盘数据
- 任何 CRC 异常不影响文件关闭
- 只读模式打开更安全

### P2: cmd_fcrc 大文件阻塞看门狗

**现状**

固件端 `cmd_fcrc` 实现（`fl.c:916`）：

```c
while (remaining > 0) {
    size_t to_read = FL_BUF_SIZE;  // 1024 bytes
    ssize_t nread = fl_file_read(&ctx->file_ctx, ctx->buf, to_read);
    crc = calc_crc16_base(crc, ctx->buf, nread);
    // ... 无任何 yield / 喂狗操作
}
```

虽然已经使用 `FL_BUF_SIZE` (1024) 分块读取并增量计算 CRC，但整个 while 循环是**不可中断的**。对于大文件（例如 1MB 固件文件），循环将持续执行数百毫秒甚至数秒，期间：
- 无法响应其他串口命令
- 无法喂看门狗
- 在 RTOS 环境下可能饿死低优先级任务

**整改方案**

方案 A：固件端分块 + 上位机多次调用（推荐）

新增 `--addr` 参数支持指定起始偏移，上位机分多次调用 fcrc，每次计算一个分块的 CRC，最终在上位机侧合并：

```c
// 固件端 cmd_fcrc 整改
static int cmd_fcrc(fl_context_t* ctx, const cmd_args_t* args) {
    off_t offset = (off_t)args->addr;   // 起始偏移
    off_t size = (off_t)args->len;      // 本次计算长度
    int init_crc = args->crc;           // 上次的 CRC 值，-1 表示初始

    uint16_t crc = (init_crc >= 0) ? (uint16_t)init_crc : 0xFFFF;

    // seek 到指定偏移
    fl_file_seek(&ctx->file_ctx, offset, FL_SEEK_SET);

    off_t total_read = 0;
    off_t remaining = size > 0 ? size : /* 单次最大限制 */ FL_FCRC_MAX_CHUNK;

    while (remaining > 0) {
        size_t to_read = FL_BUF_SIZE;
        if ((off_t)to_read > remaining) to_read = (size_t)remaining;
        ssize_t nread = fl_file_read(&ctx->file_ctx, ctx->buf, to_read);
        if (nread <= 0) break;
        crc = calc_crc16_base(crc, ctx->buf, nread);
        total_read += nread;
        remaining -= nread;
    }

    fl_response(true, "FCRC offset=%ld size=%ld crc=0x%04X",
                (long)offset, (long)total_read, (unsigned)crc);
    return 0;
}
```

上位机侧分块调用：

```python
# file_transfer.py fcrc 整改
FCRC_CHUNK = 32 * 1024  # 每次最多 32KB

def fcrc_chunked(self, total_size: int) -> Tuple[bool, int, int]:
    offset = 0
    crc = 0xFFFF
    total_read = 0

    while offset < total_size:
        chunk = min(FCRC_CHUNK, total_size - offset)
        cmd = f"fl -c fcrc -a {offset} -l {chunk} -r {crc}"
        success, response = self._send_cmd(cmd)
        if not success:
            return False, 0, 0
        # 解析返回的 crc 作为下次的 init_crc
        match = re.search(r"FCRC.*size=(\d+)\s+crc=0x([0-9A-Fa-f]+)", response)
        if not match:
            return False, 0, 0
        chunk_size = int(match.group(1))
        crc = int(match.group(2), 16)
        total_read += chunk_size
        offset += chunk_size

    return True, total_read, crc
```

**优点**：
- 每次 fcrc 调用耗时可控（32KB ≈ 几十毫秒）
- 调用间隙串口协议层可以处理其他事务
- RTOS 调度器有机会调度其他任务和喂狗
- 向后兼容：不传 `--addr` 和 `--crc` 时行为与旧版一致

方案 B：固件端内部 yield（备选）

在循环中每处理 N 个块后调用一次 `sched_yield()` 或喂狗函数。简单但不够通用，且依赖平台 API。

### P3: cmd_alloc 缺少 CRC 校验

**现状**

上位机 `serial_protocol.py:475`：

```python
def alloc(self, size: int) -> Tuple[Optional[int], str]:
    resp = self.send_cmd(f"-c alloc -s {size}")
```

固件端 `fl.c:371`：

```c
static int cmd_alloc(fl_context_t* ctx, const cmd_args_t* args) {
    if (args->size == 0) { ... }
    void* p = ctx->malloc_cb(args->size);
    // 无 CRC 校验
}
```

`alloc` 命令的 `--size` 参数没有 CRC 保护。如果串口传输中 size 值被损坏：
- size 变大：浪费内存，可能 OOM
- size 变小：后续 upload 写入超出分配范围，**堆溢出**
- size 变为 0：被拒绝（已有检查），但其他非零错误值无法检测

**整改方案**

CRC 覆盖 `size(4B)`：

```c
// 固件端
if (args->crc >= 0) {
    uint32_t size32 = (uint32_t)args->size;
    uint16_t calc = 0xFFFF;
    calc = calc_crc16_base(calc, &size32, sizeof(size32));
    if (calc != (uint16_t)args->crc) {
        fl_response(false, "CRC mismatch: 0x%04X != 0x%04X",
                    (unsigned)args->crc, (unsigned)calc);
        return 0;
    }
}
```

```python
# 上位机
crc = crc16_update(0xFFFF, struct.pack('<I', size))
cmd = f"-c alloc -s {size} -r 0x{crc:04X}"
```

### P4: cmd_fopen 缺少 CRC 校验

**现状**

`fopen` 的 `--path` 和 `--mode` 参数无 CRC 保护。path 损坏可能打开错误文件，mode 损坏可能以写模式打开只读文件。

**整改方案**

CRC 覆盖 `path + mode` 字符串：

```c
// 固件端
if (args->crc >= 0) {
    uint16_t calc = 0xFFFF;
    calc = calc_crc16_base(calc, args->path, strlen(args->path));
    calc = calc_crc16_base(calc, args->mode, strlen(mode));
    if (calc != (uint16_t)args->crc) {
        fl_response(false, "CRC mismatch");
        return 0;
    }
}
```

```python
# 上位机
crc = crc16_update(0xFFFF, path.encode('utf-8'))
crc = crc16_update(crc, mode.encode('utf-8'))
cmd = f'fl -c fopen --path "{path}" -m {mode} -r 0x{crc:04X}'
```

### P5: cmd_fremove 缺少 CRC 校验

**现状**

`fremove` 的 `--path` 参数无 CRC 保护。这是**破坏性操作**，path 损坏将导致误删文件，且不可逆。

**风险等级**：高。在所有缺少 CRC 的命令中，`fremove` 的后果最严重。

**整改方案**

CRC 覆盖 `path` 字符串：

```c
// 固件端
if (args->crc >= 0) {
    uint16_t calc = 0xFFFF;
    calc = calc_crc16_base(calc, args->path, strlen(args->path));
    if (calc != (uint16_t)args->crc) {
        fl_response(false, "CRC mismatch");
        return 0;
    }
}
```

### P6: cmd_frename 缺少 CRC 校验

**现状**

`frename` 的 `--path` 和 `--newpath` 参数无 CRC 保护。

**整改方案**

CRC 覆盖 `path + newpath`：

```c
if (args->crc >= 0) {
    uint16_t calc = 0xFFFF;
    calc = calc_crc16_base(calc, args->path, strlen(args->path));
    calc = calc_crc16_base(calc, args->newpath, strlen(args->newpath));
    if (calc != (uint16_t)args->crc) {
        fl_response(false, "CRC mismatch");
        return 0;
    }
}
```

---

## 3. 各命令 CRC 覆盖现状与整改目标

| 命令 | 当前 CRC 状态 | CRC 覆盖参数 | 整改目标 |
|------|:---:|------|------|
| `write` | ✅ 已有 | addr + len + data | 无需改动 |
| `upload` | ✅ 已有 | offset + len + data | 无需改动 |
| `read` (请求) | ✅ 已有 | addr + len | 无需改动 |
| `read` (响应) | ✅ 已有 | addr + len + data | 无需改动 |
| `patch` | ✅ 已有 | comp + orig + target | 无需改动 |
| `tpatch` | ✅ 已有 | comp + orig + target | 无需改动 |
| `dpatch` | ✅ 已有 | comp + orig + target | 无需改动 |
| `fwrite` | ✅ 已有 | data | 无需改动 |
| `fread` (响应) | ✅ 已有 | data | 无需改动 |
| `alloc` | ❌ **缺失** | — | 🔧 增加 size CRC |
| `fopen` | ❌ **缺失** | — | 🔧 增加 path + mode CRC |
| `fremove` | ❌ **缺失** | — | 🔧 增加 path CRC |
| `frename` | ❌ **缺失** | — | 🔧 增加 path + newpath CRC |
| `fclose` | N/A | 无参数 | 无需改动 |
| `fcrc` | N/A | 无需 CRC | 🔧 增加分块支持 |
| `fseek` | ✅ 已有 | addr(4B) | 🔧 本次新增 |
| `fstat` | ✅ 已有 | path | 🔧 本次新增 |
| `flist` | ✅ 已有 | path | 🔧 本次新增 |
| `fmkdir` | ✅ 已有 | path | 🔧 本次新增 |
| `ping` | N/A | 无参数 | 无需改动 |
| `echo` | N/A | 测试命令 | 无需改动 |
| `info` | N/A | 无参数 | 无需改动 |
| `unpatch` | ✅ 已有 | comp(4B) | 🔧 本次新增 |
| `enable` | ✅ 已有 | comp(4B) + enable(4B) | 🔧 本次新增 |

---

## 4. 整改优先级

| 优先级 | 问题 | 理由 |
|:------:|------|------|
| P0 | P1: fcrc/fclose 顺序 | 资源泄漏 + 数据完整性风险，纯上位机改动，无需固件配合 |
| P0 | P2: fcrc 分块 | 看门狗复位是生产环境致命问题 |
| P1 | P3: alloc CRC | 堆溢出风险，影响注入安全性 |
| P1 | P5: fremove CRC | 破坏性操作，不可逆 |
| P2 | P4: fopen CRC | 打开错误文件风险 |
| P2 | P6: frename CRC | 文件重命名错误风险 |

---

## 5. 涉及文件

| 文件 | 改动内容 |
|------|------|
| `App/func_loader/fl.c` | `cmd_fcrc` 增加分块参数支持；`cmd_alloc` 增加 CRC 校验；`cmd_fopen`/`cmd_fremove`/`cmd_frename` 增加 CRC 校验 |
| `Tools/WebServer/core/file_transfer.py` | `upload()`/`download()` 调整 fcrc/fclose 顺序；`fcrc()` 改为分块调用；`fopen()`/`fremove()`/`frename()` 发送 CRC |
| `Tools/WebServer/core/serial_protocol.py` | `alloc()` 发送 CRC |

---

## 6. 向后兼容性

本次整改**不兼容旧版固件**，需上下位机同步升级。

| 场景 | 行为 | 说明 |
|------|------|------|
| 新上位机 + 新固件 | ✅ 正常工作 | 所有 CRC 校验生效 |
| 新上位机 + 旧固件 | ❌ 不兼容 | `fcrc` 响应格式不匹配（缺少 `offset=`），分块 CRC 链式计算结果错误 |
| 旧上位机 + 新固件 | ✅ 兼容 | 旧上位机不传 CRC（`-1`），新固件跳过校验；`fcrc` 不传 `--addr`/`--crc` 时退化为 offset=0 全文件 CRC |

不兼容原因：
- `fcrc` 响应格式从 `FCRC size=N crc=0xXXXX` 改为 `FCRC offset=N size=N crc=0xXXXX`
- 分块 `fcrc` 依赖新固件的 `--addr`（偏移）和 `--crc`（链式初始值）参数支持

建议：升级上位机时同步升级固件版本号。
