# FPBInject WebServer 重构计划

## 一、现状分析

### 1.1 当前代码结构

```
WebServer/
├── main.py              # 应用入口，Flask 初始化
├── state.py             # 全局状态管理 (AppState, DeviceState)
├── routes.py            # Flask API 路由 (~1800行，过于臃肿)
├── fpb_inject.py        # FPB 注入核心逻辑 (~2700行)
├── device_worker.py     # 设备工作线程
├── worker.py            # 通用工作线程 (未使用，与 device_worker 重复)
├── file_watcher.py      # 文件监控
├── serial_utils.py      # 串口工具函数
├── timer.py             # 定时器管理
├── patch_generator.py   # Patch 生成器
├── fpb_cli.py           # CLI 工具
└── config.json          # 配置文件
```

### 1.2 核心问题

#### 🔴 线程安全问题

| 问题 | 位置 | 严重程度 |
|------|------|----------|
| `DeviceState` 属性无锁访问 | `state.py` | 高 |
| `serial_log`/`raw_serial_log` 列表并发读写 | `device_worker.py`, `routes.py` | 高 |
| `_fpb_inject` 全局单例无保护 | `routes.py` | 中 |
| `auto_inject_*` 状态多线程更新 | `routes.py` | 中 |
| `symbols` 缓存并发访问 | `routes.py` | 低 |

#### 🟡 架构问题

1. **routes.py 过于臃肿** (~1800行)
   - 混合了路由定义、业务逻辑、辅助函数
   - 文件监控回调 `_trigger_auto_inject` 包含完整注入流程

2. **重复代码**
   - `worker.py` 和 `device_worker.py` 功能重叠
   - `serial_utils.py` 部分函数与 `device_worker.py` 重复

3. **全局状态滥用**
   - `state` 全局单例被多处直接访问
   - `_fpb_inject` 全局变量

4. **职责不清**
   - `FPBInject` 类承担过多职责 (编译、通信、解析、反汇编)
   - `DeviceState` 混合了配置、运行时状态、日志

---

## 二、重构目标

1. **线程安全**: 消除数据竞争，确保并发访问安全
2. **模块化**: 单一职责，降低耦合
3. **可测试性**: 依赖注入，便于单元测试
4. **可维护性**: 清晰的代码组织，合理的文件大小

---

## 三、重构方案

### 3.1 新目录结构

```
WebServer/
├── app/
│   ├── __init__.py          # Flask app 工厂
│   ├── config.py            # 配置管理
│   └── routes/
│       ├── __init__.py      # 路由注册
│       ├── connection.py    # 连接相关 API
│       ├── fpb.py           # FPB 操作 API
│       ├── symbols.py       # 符号查询 API
│       ├── patch.py         # Patch 管理 API
│       ├── watch.py         # 文件监控 API
│       ├── logs.py          # 日志 API
│       └── files.py         # 文件浏览 API
│
├── core/
│   ├── __init__.py
│   ├── device_state.py      # 设备状态 (线程安全)
│   ├── app_state.py         # 应用状态 (线程安全)
│   ├── fpb_inject.py        # FPB 注入核心
│   ├── compiler.py          # 编译相关 (从 fpb_inject 拆分)
│   ├── serial_comm.py       # 串口通信 (从 fpb_inject 拆分)
│   └── disassembler.py      # 反汇编 (从 fpb_inject 拆分)
│
├── services/
│   ├── __init__.py
│   ├── device_worker.py     # 设备工作线程
│   ├── file_watcher.py      # 文件监控服务
│   ├── auto_inject.py       # 自动注入服务 (从 routes 拆分)
│   └── timer.py             # 定时器管理
│
├── utils/
│   ├── __init__.py
│   ├── crc.py               # CRC 计算
│   └── logging.py           # 日志工具
│
├── cli/
│   └── fpb_cli.py           # CLI 工具
│
├── static/                  # 静态资源
├── templates/               # 模板
├── tests/                   # 测试
├── main.py                  # 入口
└── config.json              # 配置
```

### 3.2 线程安全改造 (队列模式)

现有的 `device_worker.py` 已经实现了队列模式，核心原则：

1. **所有设备状态修改都在 worker 线程执行** - 通过 `run_in_device_worker()` 提交
2. **Flask 路由只读取状态** - Python GIL 保证简单读取是安全的
3. **日志用 list.append** - Python GIL 保证 append 是原子操作

不需要额外的锁机制，保持代码简洁。

#### 3.2.1 自动注入状态机

```python
# services/auto_inject.py

from enum import Enum, auto
from threading import Lock
from dataclasses import dataclass
from typing import List, Optional
import time

class AutoInjectStatus(Enum):
    IDLE = auto()
    DETECTING = auto()
    GENERATING = auto()
    COMPILING = auto()
    INJECTING = auto()
    SUCCESS = auto()
    FAILED = auto()

@dataclass
class AutoInjectState:
    status: AutoInjectStatus = AutoInjectStatus.IDLE
    message: str = ""
    source_file: str = ""
    modified_funcs: List[str] = None
    progress: int = 0
    last_update: float = 0
    result: dict = None

class AutoInjectService:
    """自动注入服务 (线程安全)"""
    
    def __init__(self, device_state, fpb_inject):
        self._lock = Lock()
        self._state = AutoInjectState()
        self._device = device_state
        self._fpb = fpb_inject
    
    def get_state(self) -> AutoInjectState:
        with self._lock:
            return AutoInjectState(
                status=self._state.status,
                message=self._state.message,
                source_file=self._state.source_file,
                modified_funcs=list(self._state.modified_funcs or []),
                progress=self._state.progress,
                last_update=self._state.last_update,
                result=self._state.result.copy() if self._state.result else None,
            )
    
    def _update_state(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)
            self._state.last_update = time.time()
    
    def trigger(self, file_path: str):
        """触发自动注入 (在后台线程执行)"""
        import threading
        thread = threading.Thread(
            target=self._do_inject,
            args=(file_path,),
            daemon=True
        )
        thread.start()
    
    def _do_inject(self, file_path: str):
        """执行注入流程"""
        try:
            self._update_state(
                status=AutoInjectStatus.DETECTING,
                message="Detecting markers...",
                source_file=file_path,
                progress=10
            )
            # ... 注入逻辑
        except Exception as e:
            self._update_state(
                status=AutoInjectStatus.FAILED,
                message=str(e),
                progress=0
            )
```

### 3.3 路由拆分

将 `routes.py` 按功能拆分为多个模块：

```python
# app/routes/__init__.py

from flask import Flask

def register_routes(app: Flask):
    from . import connection, fpb, symbols, patch, watch, logs, files
    
    # 注册蓝图
    app.register_blueprint(connection.bp, url_prefix='/api')
    app.register_blueprint(fpb.bp, url_prefix='/api/fpb')
    app.register_blueprint(symbols.bp, url_prefix='/api/symbols')
    app.register_blueprint(patch.bp, url_prefix='/api/patch')
    app.register_blueprint(watch.bp, url_prefix='/api/watch')
    app.register_blueprint(logs.bp, url_prefix='/api')
    app.register_blueprint(files.bp, url_prefix='/api')
```

```python
# app/routes/connection.py

from flask import Blueprint, jsonify, request
from core.device_state import DeviceState

bp = Blueprint('connection', __name__)

@bp.route('/ports', methods=['GET'])
def get_ports():
    """获取可用串口列表"""
    from core.serial_comm import scan_serial_ports
    ports = scan_serial_ports()
    return jsonify({'success': True, 'ports': ports})

@bp.route('/connect', methods=['POST'])
def connect():
    """连接串口"""
    # ... 实现
    pass

@bp.route('/disconnect', methods=['POST'])
def disconnect():
    """断开连接"""
    # ... 实现
    pass

@bp.route('/status', methods=['GET'])
def status():
    """获取连接状态"""
    # ... 实现
    pass
```

### 3.4 FPBInject 类拆分

将 `fpb_inject.py` 拆分为多个职责单一的模块：

```python
# core/compiler.py
class PatchCompiler:
    """Patch 编译器"""
    def compile(self, source: str, base_addr: int, elf_path: str) -> bytes:
        pass

# core/serial_comm.py
class SerialProtocol:
    """串口通信协议"""
    def send_command(self, cmd: str, timeout: float) -> str:
        pass
    
    def enter_fl_mode(self) -> bool:
        pass
    
    def exit_fl_mode(self) -> bool:
        pass

# core/disassembler.py
class Disassembler:
    """反汇编器"""
    def disassemble_function(self, elf_path: str, func_name: str) -> str:
        pass
    
    def decompile_function(self, elf_path: str, func_name: str) -> str:
        pass

# core/fpb_inject.py
class FPBInject:
    """FPB 注入协调器"""
    def __init__(self, compiler: PatchCompiler, protocol: SerialProtocol):
        self._compiler = compiler
        self._protocol = protocol
    
    def inject(self, source: str, target_func: str, ...) -> Tuple[bool, dict]:
        pass
```

### 3.5 删除冗余代码

1. **删除 `worker.py`**: 功能与 `device_worker.py` 重复
2. **合并 `serial_utils.py`**: 移入 `core/serial_comm.py`
3. **清理 `routes.py` 中的辅助函数**: 移入对应服务模块

---

## 四、实施计划

### Phase 1: 线程安全 (优先级: 高)

| 任务 | 预计工时 | 风险 |
|------|----------|------|
| 实现 `ThreadSafeLog` | 2h | 低 |
| 重构 `DeviceState` | 4h | 中 |
| 重构 `AutoInjectState` | 3h | 中 |
| 添加单元测试 | 4h | 低 |

### Phase 2: 路由拆分 (优先级: 中)

| 任务 | 预计工时 | 风险 |
|------|----------|------|
| 创建路由蓝图结构 | 2h | 低 |
| 拆分 connection 路由 | 2h | 低 |
| 拆分 fpb 路由 | 3h | 低 |
| 拆分 symbols 路由 | 2h | 低 |
| 拆分 patch 路由 | 2h | 低 |
| 拆分 watch 路由 | 2h | 低 |
| 拆分 logs 路由 | 2h | 低 |
| 拆分 files 路由 | 1h | 低 |
| 集成测试 | 4h | 中 |

### Phase 3: 核心模块重构 (优先级: 中)

| 任务 | 预计工时 | 风险 |
|------|----------|------|
| 拆分 `PatchCompiler` | 4h | 中 |
| 拆分 `SerialProtocol` | 4h | 中 |
| 拆分 `Disassembler` | 3h | 低 |
| 重构 `FPBInject` | 4h | 高 |
| 集成测试 | 6h | 中 |

### Phase 4: 清理与优化 (优先级: 低)

| 任务 | 预计工时 | 风险 |
|------|----------|------|
| 删除 `worker.py` | 0.5h | 低 |
| 合并 `serial_utils.py` | 1h | 低 |
| 更新文档 | 2h | 低 |
| 性能优化 | 4h | 中 |

---

## 五、测试策略

### 5.1 单元测试

```python
# tests/test_thread_safe_log.py

import pytest
import threading
from utils.thread_safe import ThreadSafeLog

def test_concurrent_append():
    """测试并发写入"""
    log = ThreadSafeLog(max_size=1000)
    threads = []
    
    def append_entries(n):
        for i in range(100):
            log.append({'data': f'thread-{n}-{i}'})
    
    for i in range(10):
        t = threading.Thread(target=append_entries, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # 验证所有条目都被正确添加
    assert log.next_id == 1000

def test_concurrent_read_write():
    """测试并发读写"""
    log = ThreadSafeLog(max_size=100)
    errors = []
    
    def writer():
        for i in range(50):
            log.append({'data': i})
    
    def reader():
        for _ in range(50):
            try:
                entries = log.get_since(0)
                # 验证返回的是列表副本
                assert isinstance(entries, list)
            except Exception as e:
                errors.append(e)
    
    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0
```

### 5.2 集成测试

```python
# tests/test_auto_inject.py

import pytest
from unittest.mock import Mock, patch
from services.auto_inject import AutoInjectService, AutoInjectStatus

@pytest.fixture
def mock_device():
    device = Mock()
    device.config.elf_path = '/path/to/elf'
    device.ser = Mock()
    return device

@pytest.fixture
def mock_fpb():
    return Mock()

def test_auto_inject_success(mock_device, mock_fpb):
    """测试自动注入成功流程"""
    service = AutoInjectService(mock_device, mock_fpb)
    
    mock_fpb.inject_multi.return_value = (True, {
        'successful_count': 2,
        'total_count': 2,
        'injections': [
            {'success': True, 'target_func': 'func1'},
            {'success': True, 'target_func': 'func2'},
        ]
    })
    
    # 触发注入并等待完成
    service.trigger('/path/to/source.c')
    # ... 等待和验证
```

---

## 六、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重构引入新 Bug | 高 | 增量重构，每步都有测试覆盖 |
| 线程安全改造影响性能 | 中 | 使用细粒度锁，避免全局锁 |
| API 兼容性问题 | 中 | 保持 API 接口不变，只重构内部实现 |
| 前端依赖特定响应格式 | 低 | 添加 API 响应格式测试 |

---

## 七、验收标准

1. ✅ 所有现有功能正常工作
2. ✅ 无线程安全警告 (使用 ThreadSanitizer 验证)
3. ✅ 单元测试覆盖率 > 80%
4. ✅ 单个文件不超过 500 行
5. ✅ 无循环依赖
6. ✅ 文档更新完成
