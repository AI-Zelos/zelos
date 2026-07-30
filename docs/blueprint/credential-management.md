# Agent Credential Management — Design

> v1.1.0 候选特性。解决 Agent 执行时需要的身份凭据管理问题。

---

## 一、问题定义

### 场景 1：单个 Agent 执行需要凭据

Agent A 执行 Task：调用 GitHub API 创建 PR。需要 GitHub Personal Access Token。

当前做法：Agent 自己从环境变量或配置文件读。问题：
- Runtime 不知道 Agent 用了什么凭据
- 凭据泄漏后没有审计链路
- 凭据轮换需要重启 Agent

### 场景 2：多 Agent 各自独立凭据

Goal "实现 OAuth 登录 + 部署到 K8s" 拆成两个 Task：
- Task 1 → Agent Coder（需要 GitHub Token 提交代码）
- Task 2 → Agent Deployer（需要 K8s ServiceAccount Token 部署）

每个 Agent 的凭据不同，且**绝对不能互相看见**。

当前 Zelos 的两个 Task 天然独立 dispatch，不会串。但凭据管理缺失。

### 场景 3：凭据生命周期

- 凭据过期 → Agent 执行失败，需要 Retry 前刷新凭据
- 凭据轮换 → 不能中断正在跑的 Task
- 凭据撤销 → 立即阻止该凭据被注入新 Task

---

## 二、设计原则

| 原则 | 说明 |
|------|------|
| **凭据不属于 Agent** | Agent 只在注册时声明需要什么，不持有凭据 |
| **Runtime 是凭据的唯一持有者** | 存储、注入、轮换、撤销全部由 Runtime 管控 |
| **凭据是引用，不是值** | Task.constraints 存 `credential_ref`，Agent 执行时才解析 |
| **Agent 间零泄漏** | 每个 Task 独立 dispatch，凭据按 Task 隔离 |
| **插件化存储** | CredentialStore 支持多种后端，Agent 不感知 |

---

## 三、架构设计

```
Agent 注册
  │  required_credentials: ["github-token", "k8s-sa"]
  │
  ▼
CapabilityRegistry（已有）— 记录 Agent 需要什么凭据
  │
  ▼
Goal → Plan → Task DAG → Scheduler → Dispatch
                                │
                                ▼
                        CredentialInjector
                          │ 从 CredentialStore 取凭据
                          │ 注入 Task.constraints["credentials"]
                          │
                                ▼
                        Agent 执行
                          │ task.constraints["credentials"]["github-token"]
                          │ 用完即丢
```

### 新增模块

| 模块 | 文件 | 职责 |
|------|------|------|
| `CredentialStore` | `zelos/credential_store.py` | 凭据存储/读取/轮换/撤销，插件化 |
| `CredentialInjector` | `zelos/credential_injector.py` | 在 dispatch 时注入凭据到 Task |
| `Agent.required_credentials` | 修改 `execution_engine.py` / `runtime.py` | Agent 注册时声明凭据需求 |

### 修改模块

| 模块 | 改动 |
|------|------|
| `runtime.py: add_agent()` | 新增 `required_credentials` 参数 |
| `execution_engine.py: dispatch()` | 调用 CredentialInjector 注入凭据 |
| `runtime.py: _on_dispatch()` | 注入前做 Agent 资格校验 |

---

## 四、CredentialStore 设计

### 接口

```python
class CredentialStore(ABC):
    """凭据存储插件接口。"""

    @abstractmethod
    def get(self, credential_name: str, agent_id: str) -> dict | None:
        """获取 Agent 的某个凭据。返回包含 token 和元数据的 dict。"""
        ...

    @abstractmethod
    def validate(self, credential_name: str, agent_id: str) -> bool:
        """检查凭据是否有效（未过期、未被撤销）。"""
        ...

    def refresh(self, credential_name: str, agent_id: str) -> dict | None:
        """刷新凭据（如 OAuth token refresh）。默认不支持。"""
        return None

    def revoke(self, credential_name: str, agent_id: str) -> bool:
        """撤销凭据。"""
        return False
```

### 返回格式

```python
{
    "token": "ghp_xxxxxxxxxxxx",       # 凭据值
    "type": "bearer_token",            # bearer_token / api_key / jwt / mtls_cert / oauth2
    "expires_at": 1720000000.0,        # 过期时间戳，None = 永不过期
    "metadata": {                       # 附加信息
        "scopes": ["repo", "workflow"],
        "issued_at": 1719900000.0,
    }
}
```

### 内置实现

| 实现 | 适用场景 |
|------|---------|
| `EnvCredentialStore` | 开发环境，从 `ZELOS_CREDENTIAL_<NAME>` 环境变量读取 |
| `FileCredentialStore` | 简单部署，从 JSON/YAML 配置文件读取 |
| `VaultCredentialStore` | 生产环境，对接 HashiCorp Vault |
| `K8sSecretStore` | K8s 部署，从 K8s Secrets 读取 |

### 默认：EnvCredentialStore

```bash
# 开发环境
export ZELOS_CREDENTIAL_GITHUB_TOKEN='{"token":"ghp_xxx","type":"bearer_token","agent_ids":["agent-coder"]}'
export ZELOS_CREDENTIAL_K8S_SA='{"token":"eyJhbG...","type":"jwt","agent_ids":["agent-deployer"]}'
```

---

## 五、CredentialInjector 设计

### 注入时机

在 `ExecutionEngine.dispatch()` 中，`Task` 状态变为 `STARTED` **之前**。

### 注入逻辑

```python
class CredentialInjector:
    def __init__(self, store: CredentialStore):
        self._store = store

    def inject(self, task: Task, agent_id: str, required_credentials: list[str]) -> dict:
        """为 Task 注入凭据。返回注入的凭据引用映射。"""
        credentials = {}
        for cred_name in required_credentials:
            cred = self._store.get(cred_name, agent_id)
            if cred is None:
                raise CredentialNotFoundError(
                    f"Credential '{cred_name}' not available for agent '{agent_id}'"
                )
            if not self._store.validate(cred_name, agent_id):
                raise CredentialExpiredError(
                    f"Credential '{cred_name}' has expired for agent '{agent_id}'"
                )
            # 只存引用，不存明文在 Event 中
            task.constraints = task.constraints or {}
            task.constraints.setdefault("credential_refs", {})[cred_name] = cred

        return credentials
```

### 安全设计

- `Task.constraints["credential_refs"]` 存完整凭据对象（含 token）——**仅在 dispatch 内存中**
- `task.started` 事件的 `input_context` 中**不包含** token 值——EventBus 不过手明文凭据
- 凭据在 Agent 执行完毕、Task 生命周期结束后即从内存中清除

---

## 六、Agent 注册变更

### 当前

```python
runtime.add_agent("Coder", "agents.coder:CodingAgent", capabilities=[...])
```

### 新增

```python
runtime.add_agent(
    "Coder",
    "agents.coder:CodingAgent",
    capabilities=[...],
    required_credentials=["github-token"],  # NEW
)
```

`required_credentials` 存储在 `AgentState` 中，`ExecutionEngine` 维护。

### Agent 执行时使用

```python
class CodingAgent(BaseAgent):
    def execute(self, task: Task) -> ExecutionResult:
        # 从 task.constraints 获取凭据
        creds = task.constraints.get("credential_refs", {})
        github_cred = creds.get("github-token", {})
        token = github_cred.get("token")

        # 用 token 调用 GitHub API
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("https://api.github.com/user", headers=headers)
        ...
```

---

## 七、数据流：完整的 Task 生命周期

```
1. Agent 注册
   Agent Coder → required_credentials: ["github-token"]
   Agent Deployer → required_credentials: ["k8s-sa"]

2. Goal 提交 → Task 创建
   Task A: "提交代码到 GitHub" → assigned to Agent Coder
   Task B: "部署到 K8s" → assigned to Agent Deployer

3. Dispatch Task A
   Runtime → CredentialStore.get("github-token", "agent-coder")
           → validate("github-token", "agent-coder") ✓
           → 注入 task.constraints["credential_refs"]["github-token"]
           → Agent Coder 收到 Task（含凭据）
           → Agent Coder 执行

4. Dispatch Task B（独立）
   Runtime → CredentialStore.get("k8s-sa", "agent-deployer")
           → validate("k8s-sa", "agent-deployer") ✓
           → 注入 task.constraints["credential_refs"]["k8s-sa"]
           → Agent Deployer 收到 Task（含凭据）
           → Agent Deployer 执行

   Agent Coder 的 Task 里只有 github-token
   Agent Deployer 的 Task 里只有 k8s-sa
   零泄漏。
```

---

## 八、凭据生命周期管理

### 过期处理

```python
# CredentialInjector.inject() 中
if not store.validate(cred_name, agent_id):
    # 尝试刷新（适用于 OAuth2 token）
    refreshed = store.refresh(cred_name, agent_id)
    if refreshed:
        return refreshed
    # 刷新失败 → Task FAILED → Scheduler 评估重试
    raise CredentialExpiredError(...)
```

### 轮换处理

轮换是 CredentialStore 内部的操作。Runtime 无感知：
- 新凭据写入 Store
- 旧凭据不立即删除（正在跑的 Task 不受影响）
- 新 dispatch 的 Task 自动拿到新凭据
- 旧凭据在所有使用它的 Task 结束后删除

### 撤销处理

```python
store.revoke("github-token", "agent-coder")
# → 正在运行的 Task 不受影响（已注入）
# → 新的 dispatch 会失败（validate = False）
# → 失败的 Task → Scheduler 评估是否重试
# → 重试时如果凭据已恢复 → 正常
# → 重试时如果凭据仍被撤销 → 超过 max_retries → FAILED
```

---

## 九、配置示例

### zelos.yaml

```yaml
credentials:
  store: "env"              # env | file | vault | k8s
  # vault 配置（store=vault 时）
  vault:
    url: "https://vault.example.com:8200"
    token: "${VAULT_TOKEN}"
    path: "secret/zelos/credentials"
  # file 配置（store=file 时）
  file:
    path: "/etc/zelos/credentials.json"
  # 全局策略
  policy:
    validate_on_dispatch: true       # dispatch 前必须验证
    refresh_before_expiry_seconds: 300  # 过期前 5 分钟自动刷新
    revoke_on_agent_remove: true     # Agent 被移除时自动撤销凭据
```

---

## 十、对 Agent SDK 的变更

### zelos_sdk/schema.py 新增

```python
class CredentialRequirement:
    name: str           # "github-token"
    type: str           # "bearer_token" / "api_key" / "jwt" / "mtls_cert" / "oauth2"
    description: str    # "GitHub Personal Access Token with repo scope"
    optional: bool = False  # False → 没有这个凭据禁止 dispatch
```

### zelos_sdk/agent.py

```python
class BaseAgent:
    # 新增类属性
    required_credentials: list[CredentialRequirement] = []

    def execute(self, task: Task) -> ExecutionResult:
        # 从 task.constraints 获取凭据（自动注入）
        creds = task.constraints.get("credential_refs", {})
        ...
```

---

## 十一、测试策略

| 测试 | 内容 |
|------|------|
| `test_credential_injection` | dispatch 时凭据正确注入 Task.constraints |
| `test_credential_isolation` | Agent A 的 Task 看不到 Agent B 的凭据 |
| `test_credential_expired` | 过期凭据 → Task FAILED → 触发重试 |
| `test_credential_refresh` | OAuth2 token 自动刷新 |
| `test_credential_revoke` | 撤销后新 dispatch 失败 |
| `test_env_store` | EnvCredentialStore 正确读取环境变量 |
| `test_task_started_event_no_token` | task.started 事件不含明文 token |

---

## 十二、里程碑

```
Day 1: CredentialStore 接口 + EnvCredentialStore + FileCredentialStore
Day 2: CredentialInjector + Agent.required_credentials 注册
Day 3: 过期/刷新/撤销生命周期
Day 4: 测试 + 文档
```

---

> 状态：Draft — 待 Review
