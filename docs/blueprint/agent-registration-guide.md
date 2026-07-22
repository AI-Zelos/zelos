# Agent Registration Guide

> How agents of every kind — LLM-based, traditional services, scripts, browsers — register and run on Zelos.

---

## 核心原则

Zelos 不关心你的 Agent 内部是什么。LLM Agent、传统 API 服务、Shell 脚本、浏览器自动化、数据库查询——对 Zelos 来说都一样。只要你能实现 5 个方法，你就是合法的 Zelos Agent。

```
┌─────────────────────────────────────────────────────────────┐
│                     ZELOS RUNTIME                           │
│                                                             │
│   只关心: 你注册了什么 Capability？你返回了 Artifact 吗？       │
│                                                             │
│   不关心: Claude / GPT / MySQL / curl / 你的内部逻辑          │
└─────────────────────────────────────────────────────────────┘
        ▲           ▲           ▲           ▲
        │           │           │           │
   ┌────┴────┐ ┌────┴────┐ ┌────┴────┐ ┌────┴────┐
   │ Claude  │ │ 传统 API │ │  Shell  │ │ Browser │  ...
   │  Agent  │ │   服务   │ │  脚本   │ │    Agent │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

---

## 0. 热加入和热退出（Hot-Join / Hot-Leave）

Agent 可以在 Runtime 运行时随时加入和退出，不需要重启任何东西。

### 热加入

```python
runtime = ZelosRuntime()
runtime.add_agent("Coder", entrypoint="...", capabilities=[...])
runtime.start()

# 运行中——突然发现需要一个新 Agent
runtime.add_agent(
    name="DataAnalyst",
    entrypoint="my_agents.analyst:SQLAgent",
    capabilities=[CapabilityDeclaration(name="data-query.sql", ...)],
)
# 无需重启。DataAnalyst 立即注册、心跳、进入调度候选池。
```

内部流程：`add_agent()` → 启动进程 → `Register()` → Capability Registry 更新 → 心跳 → 可被调度。全过程 < 3 秒。

### 热退出

```python
runtime.remove_agent("Coder")
# In-flight Tasks → 取消并重调度给其他 Agent
# Capability Registry → 移除全部 Capability
# Agent 进程 → shutdown
```

### 自动检测掉线

Agent 崩溃或网络断开 → heartbeat 超时（90s） → Agent → `disconnected` → In-flight Tasks 重调度 → 如果 `restart_policy="always"`，Runtime 自动重启 Agent。

---

## 1. 所有 Agent 的共同契约：5 个方法

不管你是谁，到 Zelos 注册必须实现这 5 个操作：

| 方法 | 方向 | 干什么 |
|------|------|--------|
| `register(capabilities)` | Agent → Runtime | "我上线了，我能做这些事情" |
| `heartbeat()` | Agent → Runtime | "我还活着"（每 30 秒一次） |
| `execute(task)` | Runtime → Agent | "给你一个任务，执行它" |
| `submitResult(task_id, result)` | Agent → Runtime | "任务做完了，这是结果" |
| `shutdown()` | Agent → Runtime | "我准备下线了" |

**就这么简单。不管是 Claude、一个 curl 脚本、还是一个 MySQL 查询服务——接口完全相同。**

---

## 2. 三种注册模式

Agent 和 Runtime 的通信方式有三种，你在注册时声明：

### 模式 A：HTTP 模式（最通用）

Agent 自己启动一个 HTTP Server，Runtime 通过 HTTP 推送 Task 给它。

```
Agent 端:
  1. 启动 HTTP Server (Flask/FastAPI/Express/任意)
  2. POST /api/v1/agents  → 注册
  3. 启动 heartbeat 循环
  4. 在自己端口上等待 Runtime 的 Execute 推送

Runtime 端:
  1. 收到注册 → 分配 agent_id
  2. 有任务时 → POST 到 Agent 的 endpoint
  3. Agent 完成后 → POST /api/v1/agents/{id}/tasks/{tid}/result
```

**适用：** LLM Agent（Claude/GPT 封装）、微服务、长期运行的 Agent 进程

### 模式 B：stdio 模式（最轻量）

Agent 是命令行程序，通过标准输入输出和 Runtime 通信。

```
Runtime 启动 Agent 子进程:
  Runtime  spawns  ./my-agent --capabilities code-gen
           │
           ├─ stdout → Agent 发送 JSON 消息给 Runtime
           └─ stdin  ← Runtime 发送 Task JSON 给 Agent
```

**适用：** CLI 工具封装、脚本型 Agent、不需要独立 HTTP Server 的简单 Agent

### 模式 C：gRPC 模式（高性能，Phase 2）

与 HTTP 模式类似，但使用 gRPC 二进制协议。

**适用：** 高频调用、需要流式传输的场景

---

## 3. 各种 Agent 怎么注册（实例）

### 3.1 LLM Agent（Claude Code 封装）

```python
# 用 Python SDK 最省事
from zelos_sdk.agent import Agent
from zelos_sdk.schema.task import Task
from zelos_sdk.schema.artifact import Artifact
from zelos_sdk.schema.capability import CapabilityDeclaration
import anthropic

class ClaudeCodeAgent(Agent):
    def declare_capabilities(self):
        return [
            CapabilityDeclaration(
                name="code-generation",
                version="1.0.0",
                description="Generates production code from specifications",
                input_schema={
                    "type": "object",
                    "properties": {"spec": {"type": "string"}},
                    "required": ["spec"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "language": {"type": "string"},
                        "explanation": {"type": "string"}
                    }
                },
                tags=["python", "typescript", "production"]
            ),
            CapabilityDeclaration(
                name="code-review",
                version="1.0.0",
                description="Reviews code for bugs, security, and style",
                input_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "review_focus": {"type": "string"}
                    },
                    "required": ["code"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "issues": {"type": "array"},
                        "score": {"type": "number"},
                        "summary": {"type": "string"}
                    }
                },
                tags=["security", "quality"]
            ),
        ]

    def execute(self, task: Task) -> Artifact:
        # 你决定用什么模型，什么 prompt
        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4000,
            messages=[{"role": "user", "content": task.description}]
        )
        return Artifact(
            content_type="application/json",
            content={"code": response.content[0].text, "language": "python"}
        )

# 注册到 Zelos
agent = ClaudeCodeAgent(
    name="ClaudeCode-v2",
    runtime_url="http://zelos-runtime:9876",
    api_key="zk-agent-xxxx",
    protocol="http",               # HTTP 模式
    endpoint="http://my-host:8080", # Runtime 来这个地址推送 Task
)
agent.run()  # 阻塞，自动处理注册+心跳+执行循环
```

---

### 3.2 传统 API 服务封装（无需 LLM）

假设你有一个已有的代码审查服务，跑在 `http://lint-service:3000/review`。

```python
class LintServiceAgent(Agent):
    """把已有的 lint 服务包装成 Zelos Agent"""

    def declare_capabilities(self):
        return [
            CapabilityDeclaration(
                name="code-review.lint",
                version="1.0.0",
                description="Static code linting via existing lint service",
                input_schema={
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "issues": {"type": "array"},
                        "error_count": {"type": "integer"},
                        "warning_count": {"type": "integer"}
                    }
                },
                tags=["lint", "static-analysis", "fast"]
            )
        ]

    def execute(self, task: Task) -> Artifact:
        import requests
        # 转发到已有的 lint 服务，不需要 LLM
        resp = requests.post(
            "http://lint-service:3000/review",
            json={"code": task.input.content["code"]},
            timeout=task.timeout_ms / 1000
        )
        data = resp.json()
        return Artifact(content_type="application/json", content=data)

# 注册
agent = LintServiceAgent(
    name="ESLint-Service",
    runtime_url="http://zelos-runtime:9876",
    api_key="zk-agent-xxxx",
)
agent.run()
```

---

### 3.3 Shell 脚本 Agent（stdio 模式）

```python
# 不对——stdio 模式下 Agent 不用开 HTTP Server
# Runtime 直接 spawn Agent 子进程，通过 stdin/stdout 通信

# 最简单的 Agent: 一个 JSON-in-JSON-out 的脚本
```

```bash
#!/bin/bash
# my-script-agent — 一个被 Zelos 通过 stdio 调用的简单 Agent

# 注册消息（发给 Runtime）
echo '{"type":"register","name":"ShellRunner","capabilities":[{"name":"shell-exec","version":"1.0.0","description":"Executes shell commands","input_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]},"output_schema":{"type":"object","properties":{"stdout":{"type":"string"},"stderr":{"type":"string"},"exit_code":{"type":"integer"}}}}],"protocol_version":"1.0"}'

# 主循环：等 Runtime 发 Task
while IFS= read -r line; do
    msg=$(echo "$line" | jq -r '.type')

    if [ "$msg" = "heartbeat_request" ]; then
        echo '{"type":"heartbeat_response","status":"ok"}'

    elif [ "$msg" = "execute" ]; then
        task_id=$(echo "$line" | jq -r '.task_id')
        command=$(echo "$line" | jq -r '.input.content.command')

        # 执行命令
        result=$(eval "$command" 2>&1)
        exit_code=$?

        # 返回 Artifact
        echo "{\"type\":\"submit_result\",\"task_id\":\"$task_id\",\"agent_id\":\"shell-001\",\"result\":{\"status\":\"completed\",\"artifact\":{\"content_type\":\"application/json\",\"content\":{\"stdout\":$(echo "$result" | jq -Rs .),\"exit_code\":$exit_code}}}}"

    elif [ "$msg" = "cancel" ]; then
        task_id=$(echo "$line" | jq -r '.task_id')
        echo "{\"type\":\"cancel_response\",\"task_id\":\"$task_id\",\"status\":\"acknowledged\"}"

    elif [ "$msg" = "shutdown" ]; then
        echo '{"type":"shutdown_ack"}'
        exit 0
    fi
done
```

然后在 `zelos.yaml` 中配置 stdio Agent：

```yaml
plugins:
  - id: "shell-agent"
    type: "adapter"     # Agents go through Protocol Adapter
    ...

# stdio Agent 在 Agent 列表里配置
agents:
  - name: "ShellRunner"
    protocol: "stdio"
    command: "/usr/local/bin/my-script-agent"
    capabilities:
      - name: "shell-exec"
        version: "1.0.0"
```

---

### 3.4 浏览器自动化 Agent（Playwright 封装）

```python
class BrowserAgent(Agent):
    def declare_capabilities(self):
        return [
            CapabilityDeclaration(
                name="automation.browser",
                version="1.0.0",
                description="Automates browser interactions: navigate, click, screenshot, extract",
                input_schema={
                    "type": "object",
                    "properties": {
                        "actions": {"type": "array"},
                        "url": {"type": "string"}
                    },
                    "required": ["actions"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "screenshots": {"type": "array"},
                        "extracted_text": {"type": "string"},
                        "page_title": {"type": "string"}
                    }
                },
                tags=["browser", "automation", "web"]
            )
        ]

    def execute(self, task: Task) -> Artifact:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            # 执行 task.input 中指定的浏览器操作
            for action in task.input.content["actions"]:
                if action["type"] == "navigate":
                    page.goto(action["url"])
                elif action["type"] == "click":
                    page.click(action["selector"])
                elif action["type"] == "screenshot":
                    page.screenshot(path=f"/tmp/{task.task_id}.png")
                elif action["type"] == "extract":
                    text = page.inner_text(action["selector"])

            browser.close()
            return Artifact(
                content_type="application/json",
                content={"extracted_text": text, "page_title": page.title()}
            )
```

---

### 3.5 数据库查询 Agent

```python
class DatabaseAgent(Agent):
    def declare_capabilities(self):
        return [
            CapabilityDeclaration(
                name="data-query.sql",
                version="1.0.0",
                description="Executes SQL queries against configured databases",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "params": {"type": "array"},
                        "database": {"type": "string"}
                    },
                    "required": ["query"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "columns": {"type": "array"},
                        "rows": {"type": "array"},
                        "row_count": {"type": "integer"}
                    }
                },
                tags=["data", "sql", "read-only"]
            )
        ]

    def execute(self, task: Task) -> Artifact:
        import psycopg2
        conn = psycopg2.connect(self._db_url)
        cur = conn.cursor()
        cur.execute(task.input.content["query"], task.input.content.get("params", []))
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        conn.close()
        return Artifact(
            content_type="application/json",
            content={"columns": columns, "rows": rows, "row_count": len(rows)}
        )
```

---

## 4. 注册流程（Runtime 视角）

不管 Agent 是什么类型，Runtime 对它做完全相同的流程：

```
1. Agent 调用 register(name, capabilities, protocol, endpoint)
       │
       ▼
2. Runtime 验证:
   ├── Capability name 符合命名规范？
   ├── input_schema / output_schema 是合法 JSON Schema？
   ├── protocol 是支持的协议？
   └── 分配 agent_id (UUID)
       │
       ▼
3. 索引 Capability → Capability Registry
   "code-generation" → [agent_id_A, agent_id_B, agent_id_C]
   "code-review"     → [agent_id_D]
   "browser"         → [agent_id_E]
       │
       ▼
4. Agent 开始 heartbeat 循环
   Runtime 每 30s 检查一次 → 3 次未收到 → Agent disconnected
       │
       ▼
5. Agent → eligible for dispatch
   Scheduler 可以给它派 Task 了
```

**关键：Runtime 从来没看过 Agent 内部。它只知道 Agent 注册了哪些 Capability。Agent 是 Claude、是 curl、是 MySQL——对 Runtime 来说都一样。**

---

## 5. 一个 Agent 注册多个 Capability

一个 Agent 可以同时注册多个能力：

```python
class FullStackAgent(Agent):
    def declare_capabilities(self):
        return [
            CapabilityDeclaration(name="code-generation.python", ...),
            CapabilityDeclaration(name="code-generation.typescript", ...),
            CapabilityDeclaration(name="code-review", ...),
            CapabilityDeclaration(name="design.architecture", ...),
            CapabilityDeclaration(name="automation.browser", ...),
        ]
```

Scheduler 会根据 Task 需要的能力来匹配：
- 如果一个 Task 需要 `code-generation.python`→ 这个 Agent 可以
- 如果另一个 Task 需要 `data-query.sql` → 这个 Agent 不行，调度器去找别的

---

## 6. 同一个 Capability 多个 Agent 竞争

可以有多个 Agent 注册同一个 Capability：

```
Capability: code-generation.python
Providers:
  ├── ClaudeCode-v2    (success: 0.95, cost: $0.05, latency: 5s)
  ├── Codex-v1         (success: 0.90, cost: $0.03, latency: 8s)
  ├── Gemini-v3        (success: 0.85, cost: $0.02, latency: 3s)
  └── LocalCodeAgent   (success: 0.80, cost: $0.00, latency: 15s)
```

Scheduler 每次选择一个最合适的。Agent 之间形成了竞争市场——质量高、成本低、速度快的自然获得更多的 Task。

---

## 7. 注册后发生了什么？（真实流程示例）

```
时间线：

T+0s:    ClaudeCodeAgent 启动
T+1s:    POST /api/v1/agents → register("ClaudeCode", [code-generation, code-review])
T+2s:    Runtime 验证通过，分配 agent_id = "agt-001"
T+2s:    Capability Registry 更新：
           code-generation → [agt-001]
           code-review     → [agt-001]
T+3s:    Agent 开始 heartbeat 循环 (每 30s)
T+5s:    用户提交 Goal: "Build an e-commerce website"
T+8s:    Planner 产出 Execution Plan，其中 Task #3 需要 code-generation.python
T+9s:    Task #3 → Ready
T+10s:   Scheduler 查询 Capability Registry → 找到 agt-001
T+11s:   Scheduler 评分: agt-001 score = 0.87 → 选中
T+12s:   Execution Engine → POST http://my-agent:8080/execute {task_id, ...}
T+13s:   agt-001 收到 Task，调用 Claude API 生成代码
T+25s:   代码生成完毕
T+26s:   POST /api/v1/agents/agt-001/tasks/task-3/result → {status: completed, artifact: {...}}
T+27s:   Verifier 验证代码质量 → Passed
T+28s:   Task #3 → Completed → 下游 Task 解锁
```

**全程 Runtime 不知道 agt-001 内部用的是 Claude 还是 Gemini。它只知道 agt-001 注册了 `code-generation.python`，被调度了，返回了 Artifact。**

---

## 8. 一句话总结

> **Agent 开发者做三件事：构建 Agent → 声明 Capabilities → 注册到 Zelos。**
> **Zelos 做剩下的所有事：Plan, Schedule, Dispatch, Retry, Verify, Memory, Observe。**
> **Agent 是 Claude 还是 curl——Zelos 不知道，也不需要知道。**

---

## 9. References

- [Runtime API §4: Agent API](./runtime-api.md#4-agent-api) — Register / Heartbeat / Execute / SubmitResult 完整契约
- [Python SDK](./python-sdk.md) — SDK 帮你处理注册和心跳，你只写 `execute()`
- [RFC-0002: Agent Registration Protocol](../rfc/rfc-0002-agent-registration-protocol.md)
- [Capability Registry](./capability-registry.md) — 能力注册、索引、匹配
- [Scheduler](./scheduler.md) — 评分、筛选、选择最佳 Agent
