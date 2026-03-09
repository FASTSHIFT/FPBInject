# 注入与内存读取细粒度进度条设计

## 1. 现状分析

### 1.1 文件传输进度条（参考实现 ✅）

文件传输使用 **Thread + Queue + SSE generator** 三件套，实现了真正的实时逐包进度：

```
upload_task 线程                    SSE generator (主线程)
    │                                    │
    ├─ send chunk 1 ──► queue.put() ──► yield "data: {percent:12.5%}"
    ├─ send chunk 2 ──► queue.put() ──► yield "data: {percent:25.0%}"
    ├─ ...                               │
    └─ queue.put(None) ─────────────────► break (流结束)
```

关键设计点：
- `progress_callback` 在每个 chunk 发送成功后触发
- 通过 `queue.Queue` 实现线程间实时通信
- SSE generator 阻塞在 `queue.get(timeout=5.0)` 上，收到事件立即 yield
- 心跳保活 + 超时检测防止连接挂死

### 1.2 注入进度条现状

| 端点 | 方式 | 进度粒度 | 问题 |
|------|------|---------|------|
| `POST /fpb/inject/stream` | SSE | 逐包 | ✅ 已有，upload 阶段有逐包进度 |
| `POST /fpb/inject` | 同步 JSON | 无 | 无进度反馈 |
| `POST /fpb/inject/multi` | 同步 JSON | 无 | ❌ 多函数注入无任何进度 |

`/fpb/inject/stream` 的进度映射：

```
[0%─────20%] 编译阶段 (status: compiling)
[20%────30%] 编译完成 (status: compiled)
[30%────90%] 上传阶段 (progress: 逐包) ← 已有细粒度
[90%───100%] FPB 配置 (result)
```

**问题**：`/fpb/inject/multi` 需要依次注入多个函数，每个函数都经历 编译→上传→配置 流程，但目前是同步调用，前端无法知道当前进度。

### 1.3 变量内存读取进度条现状

| 端点 | 方式 | 进度粒度 | 问题 |
|------|------|---------|------|
| `POST /symbols/read` | 同步 JSON | 无 | ❌ 前端用假进度条 (width=100%) |
| `POST /memory/read/stream` | SSE | 伪实时 | ⚠️ events 先收集后批量 yield |

**`/symbols/read` 问题**：调用 `fpb.read_memory(addr, size)` 时未传递 `progress_callback`，底层已有逐包回调能力但未利用。

**`/memory/read/stream` 问题**：使用 `run_in_device_worker` 同步阻塞执行，progress events 收集到 list 中，等读取完成后才一次性 yield，不是真正的实时流。

### 1.4 底层能力盘点

| 底层方法 | progress_callback | 分块大小 |
|---------|-------------------|---------|
| `serial_protocol.upload()` | ✅ 每 chunk 回调 | ~128 bytes |
| `serial_protocol.read_memory()` | ✅ 每 chunk 回调 | ~128 bytes |
| `gdb_session.read_symbol_value()` | ❌ 无回调 | 单次 GDB 命令 |

**结论**：串口层的分块进度回调已经完备，只需在路由层正确连接到 SSE 即可。GDB 读取是单次命令，无需进度。

## 2. 设计方案

### 2.1 设计原则

- **复用文件传输的 Thread + Queue + SSE 模式**，不引入新的通信机制
- **不新增线程池或后台 worker**，每个 SSE 请求自带一个 daemon 线程
- **不新增 API 端点**，改造现有端点为 SSE 流式（通过请求参数或 Accept header 区分）
- **前端复用现有 SSE 解析逻辑**，统一 `processSSEStream()` 工具函数

### 2.2 改造点总览

```
改造项                          工作量    影响文件
─────────────────────────────  ────────  ──────────────────────
① /fpb/inject/multi → SSE     中        fpb.py, patch.js
② /symbols/read → SSE         中        symbols.py, symbols.js
③ /memory/read/stream 实时化   小        symbols.py
④ 前端 SSE 工具函数抽取        小        utils.js / transfer.js
```

### 2.3 方案①：多函数注入 SSE 进度

**新增端点**：`POST /fpb/inject/multi/stream`

**SSE 事件流设计**：

```
← data: {"type":"status","stage":"start","total_functions":3}

← data: {"type":"status","stage":"compiling","index":0,"name":"func_a","total":3}
← data: {"type":"progress","index":0,"step":"upload","uploaded":128,"total":1024,"percent":12.5}
← data: {"type":"progress","index":0,"step":"upload","uploaded":256,"total":1024,"percent":25.0}
...
← data: {"type":"status","stage":"patched","index":0,"name":"func_a"}

← data: {"type":"status","stage":"compiling","index":1,"name":"func_b","total":3}
← data: {"type":"progress","index":1,"step":"upload","uploaded":128,"total":512,"percent":25.0}
...
← data: {"type":"status","stage":"patched","index":1,"name":"func_b"}

← data: {"type":"result","success":true,"results":[...]}
```

**进度条映射**（以 3 个函数为例）：

```
总进度 = Σ(每个函数的加权进度)
每个函数占 100/N %，内部再按阶段分配：
  [0%──20%] 编译
  [20%─90%] 上传（逐包细粒度）
  [90%-100%] FPB 配置

overall = (completed_funcs / total) * 100
        + (current_func_percent / total)
```

**后端实现要点**：

```python
# app/routes/fpb.py

@bp.route("/fpb/inject/multi/stream", methods=["POST"])
def api_inject_multi_stream():
    progress_queue = queue.Queue()

    def inject_task():
        for i, item in enumerate(functions):
            progress_queue.put({"type": "status", "stage": "compiling",
                                "index": i, "name": item["target"], "total": n})

            def upload_cb(uploaded, total):
                progress_queue.put({"type": "progress", "index": i,
                                    "step": "upload", "uploaded": uploaded,
                                    "total": total,
                                    "percent": round(uploaded/total*100, 1)})

            result = fpb.inject(..., progress_callback=upload_cb)
            progress_queue.put({"type": "status", "stage": "patched", "index": i})

        progress_queue.put({"type": "result", "success": True, ...})
        progress_queue.put(None)

    thread = threading.Thread(target=inject_task, daemon=True)
    thread.start()
    return Response(sse_generator(progress_queue), mimetype="text/event-stream", ...)
```

### 2.4 方案②：符号内存读取 SSE 进度

**新增端点**：`POST /symbols/read/stream`

**SSE 事件流设计**：

```
← data: {"type":"status","stage":"reading","symbol":"lv_global","size":616}
← data: {"type":"progress","read":128,"total":616,"percent":20.8}
← data: {"type":"progress","read":256,"total":616,"percent":41.6}
← data: {"type":"progress","read":384,"total":616,"percent":62.3}
← data: {"type":"progress","read":512,"total":616,"percent":83.1}
← data: {"type":"progress","read":616,"total":616,"percent":100.0}
← data: {"type":"result","success":true,"data":"base64...","size":616}
```

**后端实现要点**：

```python
# app/routes/symbols.py

@bp.route("/symbols/read/stream", methods=["POST"])
def api_read_symbol_stream():
    progress_queue = queue.Queue()

    def read_task():
        info = fpb.lookup_symbol(sym_name)  # 获取 addr + size
        progress_queue.put({"type": "status", "stage": "reading",
                            "symbol": sym_name, "size": info["size"]})

        def read_cb(offset, total):
            progress_queue.put({"type": "progress", "read": offset,
                                "total": total,
                                "percent": round(offset/total*100, 1)})

        raw, msg = fpb.read_memory(info["addr"], info["size"],
                                   progress_callback=read_cb)

        progress_queue.put({"type": "result", "success": True,
                            "data": base64.b64encode(raw).decode(), ...})
        progress_queue.put(None)

    thread = threading.Thread(target=read_task, daemon=True)
    thread.start()
    return Response(sse_generator(progress_queue), mimetype="text/event-stream", ...)
```

### 2.5 方案③：`/memory/read/stream` 实时化

当前问题：`run_in_device_worker` 同步阻塞，events 先收集后批量发送。

**改造方案**：改为与文件传输相同的 Thread + Queue 模式，替换 `run_in_device_worker`。

改动量最小，只需将现有的 events list 替换为 queue，generator 从 queue 实时读取。

### 2.6 前端 SSE 工具函数抽取

从 `transfer.js` 中抽取通用 SSE 流处理函数到 `utils.js`：

```javascript
// static/js/utils.js

/**
 * 通用 SSE 流消费器
 * @param {string} url - API 端点
 * @param {Object} options - fetch options (method, body, headers)
 * @param {Object} handlers - 事件处理器 {onProgress, onStatus, onResult, onError}
 * @param {AbortController} [abortCtrl] - 可选取消控制器
 */
async function consumeSSEStream(url, options, handlers, abortCtrl) {
    const response = await fetch(url, {
        ...options,
        signal: abortCtrl?.signal,
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = JSON.parse(line.slice(6));
            switch (data.type) {
                case 'progress': handlers.onProgress?.(data); break;
                case 'status':   handlers.onStatus?.(data);   break;
                case 'result':   handlers.onResult?.(data);   break;
                case 'heartbeat': break;
                default:         handlers.onOther?.(data);
            }
        }
    }
}
```

前端调用示例（符号读取）：

```javascript
// static/js/features/symbols.js

async function readSymbolFromDevice(symbolName) {
    showProgressBar();
    await consumeSSEStream('/api/symbols/read/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: symbolName }),
    }, {
        onProgress(data) {
            updateProgressBar(data.percent,
                `${data.percent.toFixed(1)}% (${data.read}/${data.total} bytes)`);
        },
        onResult(data) {
            hideProgressBar();
            if (data.success) applySymbolData(data.data);
        },
    });
}
```

## 3. 后端通用 SSE Generator 抽取

为避免每个路由重复编写 SSE generator + 心跳 + 超时逻辑，抽取公共函数：

```python
# app/utils/sse.py

def sse_generator(progress_queue, inactivity_timeout=120.0, poll_interval=5.0):
    """通用 SSE generator，从 queue 读取事件并 yield。

    - queue 中放入 dict → yield 为 SSE data 行
    - queue 中放入 None → 流结束
    - 超时无活动 → 发送超时错误并结束
    - 空轮询 → 发送心跳保活
    """
    last_activity = time.time()
    while True:
        try:
            item = progress_queue.get(timeout=poll_interval)
            if item is None:
                break
            last_activity = time.time()
            yield f"data: {json.dumps(item)}\n\n"
        except queue.Empty:
            if time.time() - last_activity > inactivity_timeout:
                yield f'data: {json.dumps({"type": "result", "success": False, "error": "Timeout"})}\n\n'
                break
            yield f'data: {json.dumps({"type": "heartbeat"})}\n\n'
```

## 4. 改造优先级与工作量

| 优先级 | 改造项 | 工作量 | 用户感知 |
|--------|--------|--------|---------|
| P0 | 抽取 `sse_generator` 公共函数 | 0.5h | 无（内部重构） |
| P0 | 抽取前端 `consumeSSEStream` | 0.5h | 无（内部重构） |
| P1 | `/symbols/read/stream` 端点 | 1h | 符号读取有真实进度条 |
| P1 | `/fpb/inject/multi/stream` 端点 | 1.5h | 多函数注入有逐函数+逐包进度 |
| P2 | `/memory/read/stream` 实时化 | 0.5h | 通用内存读取进度实时化 |
| P2 | 现有 `transfer.py` 迁移到公共 `sse_generator` | 0.5h | 无（内部统一） |

总计约 4.5h 工作量。

## 5. 不变的部分

- **不新增线程池**：每个 SSE 请求自带一个 daemon 线程，请求结束线程自动回收
- **不新增 WebSocket**：继续使用 SSE，与文件传输保持一致
- **不改变串口协议**：底层 `upload()` / `read_memory()` 的 `progress_callback` 已完备
- **不改变同步端点**：`/fpb/inject`、`/symbols/read` 保持不变，流式端点作为新增
- **GDB 读取不加进度**：`gdb_session.read_symbol_value()` 是单次 GDB 命令，无分块概念
