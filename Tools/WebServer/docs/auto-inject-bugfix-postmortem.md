# 自动注入功能 Bug 修复复盘

## 问题背景

2026-03-10 在实际使用自动注入功能时，发现两个严重问题导致注入全部失败。

## Bug 1: 符号查找性能问题 — GDB 太慢

### 现象

```
[INFO] lookup_symbol start: 'lv_obj_create'
[INFO] lookup_symbol done: 'lv_obj_create' -> 0x2C2DD780 (0.603s)
[INFO] lookup_symbol start: 'lv_obj_constructor'
[INFO] lookup_symbol done: 'lv_obj_constructor' -> 0x2C2DCA94 (0.613s)
...
```

9 个函数符号查找耗时 **~5.4 秒**（每个 ~0.6s），全部通过 GDB/MI 协议的 `info address` 命令逐个查询。

### 根因

`_resolve_symbol_addr()` 仅使用 GDB session 查找符号地址。GDB 启动了完整的调试会话，加载了整个 ELF 的调试信息，每次查询都需要通过 GDB/MI 协议往返通信。

但自动注入场景只需要 **符号名 → 地址** 的映射，不需要调试信息、类型信息或源码定位。

### 修复方案

改用 `nm` 工具（通过已有的 `elf_utils.get_symbols()`）作为快速路径：

```
_resolve_symbol_addr(sym_name)
  ├── 快速路径: nm 查找（一次 subprocess 调用加载全部符号，带 mtime 缓存）
  │   └── 命中 → 直接返回地址
  └── 慢速路径: GDB fallback（仅当 nm 未找到时）
```

- nm 一次调用加载所有符号到内存缓存（~0.3s）
- 后续查找为纯内存字典查找（~0μs）
- 缓存按 ELF 文件 mtime 自动失效

### 性能对比

| 方式 | 9 个符号总耗时 | 单符号耗时 |
|------|---------------|-----------|
| GDB (修复前) | ~5.4s | ~0.6s |
| nm + 缓存 (修复后) | ~0.3s (首次) / ~0s (缓存) | ~0s |

## Bug 2: 串口线程安全问题 — ThreadCheckedSerial 违规

### 现象

```
[ERROR] Inject failed for lv_obj_create: Failed to get device info:
  Serial.reset_input_buffer() called from thread 'Thread-496 (do_auto_inject)'
  (id=140669059319360), but owner is 'fpb-worker' (id=140669611779648)
```

所有 8 个注入操作全部因线程违规失败。

### 根因

`_trigger_auto_inject()` 在后台线程 `do_auto_inject` 中直接调用 `fpb.enter_fl_mode()` → 串口 I/O。但串口被 `ThreadCheckedSerial` 包装，绑定到 `fpb-worker` 线程，任何其他线程的 I/O 操作都会抛出 `SerialThreadViolation`。

调用链：

```
文件变更回调 (watchdog 线程)
  └── _trigger_auto_inject()
        └── threading.Thread(do_auto_inject)  ← 新线程
              └── fpb.enter_fl_mode()
                    └── serial.reset_input_buffer()  ← ❌ 非 owner 线程
```

### 修复方案

将所有串口 I/O 操作通过 `run_in_device_worker()` 派发到 `fpb-worker` 线程执行：

```
文件变更回调 (watchdog 线程)
  └── _trigger_auto_inject()
        └── threading.Thread(do_auto_inject)  ← 后台线程（非串口操作）
              ├── 文件 I/O: 检测 FPB_INJECT 标记 ← 安全
              └── run_in_device_worker(do_inject)
                    └── fpb-worker 线程执行:
                          ├── enter_fl_mode()  ← ✅ owner 线程
                          ├── inject_multi()   ← ✅ owner 线程
                          └── exit_fl_mode()   ← ✅ owner 线程
```

同样处理了 auto-unpatch 路径（标记移除时自动清除注入）。

## 修改文件

| 文件 | 修改内容 |
|------|---------|
| `fpb_inject.py` | `_resolve_symbol_addr()` 增加 nm 快速路径；新增 `_get_elf_symbols()` 带 mtime 缓存 |
| `services/file_watcher_manager.py` | `do_auto_inject` 和 `do_unpatch` 通过 `run_in_device_worker()` 派发串口操作 |
| `tests/test_fpb_inject.py` | 新增 `TestResolveSymbolAddr` 6 个测试（nm 快速路径、缓存失效、GDB fallback、边界条件） |
| `tests/test_file_watcher_manager.py` | 更新 `TestTriggerAutoInject` mock `run_in_device_worker`；新增 worker timeout 测试 |
| `tests/test_compile_inplace.py` | 更新 `test_inplace_flow_success` 和 `test_inplace_flow_auto_unpatch` mock worker |

## 测试验证

- 全部 Python 测试通过（含新增 7 个测试用例）
- 覆盖率达标（≥85%）

## 经验教训

1. **串口访问必须走 DeviceWorker**：`ThreadCheckedSerial` 是最后一道防线，但正确做法是在架构层面保证所有串口操作都通过 `run_in_device_worker()` 派发，而不是依赖运行时检测。

2. **能用离线工具就不要用在线工具**：符号查找只需要 `nm`（纯文件操作），不需要启动完整的 GDB 调试会话。选择最轻量的工具完成任务。

3. **后台线程 + 串口 = 必须审查**：任何新建线程中如果涉及串口操作，都需要检查是否通过 DeviceWorker 路由。
