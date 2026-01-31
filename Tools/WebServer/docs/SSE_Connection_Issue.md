# SSE连接阻塞问题分析与解决

## 问题现象

在FPBInject WebServer中，执行代码注入后，点击Info按钮会卡住约20秒才响应。未注入代码时，Info按钮响应正常（约50ms）。

## 问题定位过程

### 1. 初步排查

通过在前后端关键路径添加时间戳日志，发现：

**前端日志：**
```
[TIMING] SSE: stream done                    // SSE读取完成
[TIMING] SSE: stream reading complete        // 准备调用fpbInfo
[TIMING] fpbInfo: START                      // 开始调用
[TIMING] fpbInfo: calling fetch...           // 发起请求
[TIMING] fpbInfo: fetch returned in 20056.9ms  // 20秒后才返回！
```

**后端日志：**
```
13:19:54,835 [INFO] SSE generate: END        // SSE结束
13:20:16,718 [INFO] api_fpb_info: START      // 22秒后才收到请求！
```

### 2. 根本原因

问题出在SSE（Server-Sent Events）的HTTP连接处理：

```python
return Response(
    generate(),
    mimetype="text/event-stream",
    headers={
        "Connection": "keep-alive",  # 问题根源！
    },
)
```

**关键发现：** 即使Python的generator函数已经执行完毕（`SSE generate: END`），Flask的Response对象配置了`Connection: keep-alive`，导致HTTP连接不会立即关闭。

## SSE机制详解

### 什么是SSE？

SSE（Server-Sent Events）是一种服务器向客户端推送数据的技术：

```
┌─────────┐                    ┌─────────┐
│  Client │ ──── HTTP请求 ──→  │  Server │
│         │ ←── 持续数据流 ──  │         │
└─────────┘                    └─────────┘
```

**特点：**
- 单向通信（服务器→客户端）
- 基于HTTP长连接
- 数据格式：`data: {json}\n\n`
- 自动重连机制

### SSE vs WebSocket

| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 通信方向 | 单向（服务器→客户端） | 双向 |
| 协议 | HTTP | WS/WSS |
| 复杂度 | 简单 | 较复杂 |
| 浏览器支持 | 广泛 | 广泛 |
| 连接数限制 | 受HTTP连接池限制 | 独立连接 |

### 浏览器连接池限制

**关键知识点：** 浏览器对同一域名的并发HTTP连接数有限制：

| 浏览器 | 最大并发连接数 |
|--------|---------------|
| Chrome | 6 |
| Firefox | 6 |
| Safari | 6 |
| Edge | 6 |

这意味着如果6个SSE连接没有关闭，新的HTTP请求会被排队等待！

## 问题的完整流程

```
时间线：
─────────────────────────────────────────────────────────────────→

[T0] 用户点击Inject按钮
     ↓
[T1] 前端发起 POST /api/fpb/inject/stream (SSE)
     浏览器连接池: [SSE占用1个] + [空闲5个]
     ↓
[T2] 后端处理注入，通过SSE推送进度
     data: {"type": "status", "stage": "compiling"}
     data: {"type": "progress", ...}
     data: {"type": "result", "success": true}
     ↓
[T3] 后端generator结束，打印 "SSE generate: END"
     但HTTP连接因为 Connection: keep-alive 没有关闭！
     浏览器连接池: [SSE仍占用1个] + [空闲5个]
     ↓
[T4] 前端收到 done=true，调用 await fpbInfo()
     ↓
[T5] 前端发起 GET /api/fpb/info
     但这个请求被浏览器排在SSE连接后面等待！
     ↓
[T5+20s] HTTP连接超时关闭，浏览器才发送info请求
     ↓
[T5+20s] 后端收到 api_fpb_info: START
```

## 解决方案

将SSE响应的`Connection`头从`keep-alive`改为`close`：

```python
# 修改前
return Response(
    generate(),
    mimetype="text/event-stream",
    headers={
        "Connection": "keep-alive",  # ❌ 连接不会立即关闭
    },
)

# 修改后
return Response(
    generate(),
    mimetype="text/event-stream",
    headers={
        "Connection": "close",  # ✅ generator结束后立即关闭连接
    },
)
```

## 修复后的效果

```
后端日志：
13:25:10,123 [INFO] SSE generate: END
13:25:10,156 [INFO] api_fpb_info: START    // 仅33ms后就收到请求！
```

## 经验总结

### 1. SSE使用注意事项

- **设置`Connection: close`**：除非明确需要保持连接，否则SSE结束后应关闭连接
- **及时发送结束标记**：确保generator在任务完成后立即退出
- **考虑连接池限制**：大量并发SSE连接会影响其他HTTP请求

### 2. 调试技巧

- **前后端时间戳对比**：确定延迟发生在哪一层
- **浏览器开发者工具**：Network面板可以看到请求的排队时间（Queueing）
- **Flask threaded模式**：确保`app.run(threaded=True)`以支持并发请求

### 3. 替代方案

如果需要真正的长连接推送，考虑：

1. **WebSocket**：独立于HTTP连接池
2. **轮询（Polling）**：定期请求更新
3. **长轮询（Long Polling）**：服务器有数据时才响应

## 相关代码位置

- SSE端点：`Tools/WebServer/app/routes/fpb.py` - `api_fpb_inject_stream()`
- 前端SSE读取：`Tools/WebServer/static/js/features/patch.js` - `performInjection()`

## 参考资料

- [MDN: Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [Flask Streaming](https://flask.palletsprojects.com/en/2.0.x/patterns/streaming/)
- [HTTP Connection Management](https://developer.mozilla.org/en-US/docs/Web/HTTP/Connection_management_in_HTTP_1.x)
