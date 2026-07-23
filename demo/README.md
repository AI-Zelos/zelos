# Zelos Demo 合集

21 个可运行的端到端示例，覆盖 v0.7.0 全部功能。只需配置 LLM API Key 即可运行需要 LLM 的 Demo。

## 快速开始

```bash
# 安装
pip install zelos-runtime

# 克隆仓库获取 Demo
git clone https://github.com/AI-Zelos/zelos.git
cd zelos/

# 配置 LLM（可选，Demo 13-21 无需 LLM）
export OPENAI_API_KEY="sk-your-key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"

# 运行 Demo
python3 demo/13_security.py        # ← 无需 LLM，可直接运行
python3 demo/20_hitl_approval_workflow.py
python3 demo/01_single_agent.py    # ← 需要 LLM API Key
```

## 支持的 LLM Provider

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | — | API Key（必填） |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | 兼容 OpenAI / DeepSeek / Ollama / vLLM |
| `OPENAI_MODEL` | `gpt-4o` | 模型名称 |

---

## Phase 1 Demo（核心编排）

| # | 文件 | 说明 | LLM |
|---|------|------|-----|
| 01 | `01_single_agent.py` | 单 Agent + LLM Planner 自动分解 + 阶梯容错 | ✅ |
| 02 | `02_multi_agent.py` | 4 个 Agent 协作，Scheduler 按能力自动分派 | ✅ |
| 03 | `03_http_api.py` | HTTP REST API 模式，curl 提交 → 自动完成 | ✅ |
| 04 | `04_custom_scoring.py` | 自定义评分策略（成本优先 vs 质量优先） | ✅ |
| 05 | `05_hot_join.py` | Agent 热加入 + 三层阶梯式容错 | ✅ |
| 06 | `06_full_pipeline.py` | 完整流水线：Planner → Scheduler → Agent → Verifier → Policy → Memory | ✅ |

## Phase 1 Demo（框架集成）

| # | 文件 | 说明 |
|---|------|------|
| 07 | `07_langchain_agent.py` | LangChain Agent 包装为 Zelos Agent，内部管理 Tools/Prompt |
| 08 | `08_crewai_agent.py` | CrewAI 3 角色 Crew 包装为 1 个 Zelos Agent |
| 09 | `09_autogen_agent.py` | AutoGen GroupChat 包装为 Zelos Agent |
| 10 | `10_mixed_frameworks.py` | LangChain + CrewAI + AutoGen + Native 混合编排 |

## Phase 2 Demo（新增功能）

| # | 文件 | 说明 |
|---|------|------|
| 11 | `11_verifier_pipeline.py` | 四级验证链：Schema → CodeReview → Security → FactCheck |
| 12 | `12_observability.py` | 结构化日志 + Prometheus 指标 + 分布式追踪 |

## Phase 3 Demo（Runtime Ecosystem）

| # | 文件 | 说明 |
|---|------|------|
| 13 | `13_security.py` | RBAC 权限控制 + 审计日志 + API Key 管理 |
| 14 | `14_multi_tenancy.py` | 命名空间隔离 + 资源配额 + 租户管理 |
| 15 | `15_advanced_execution.py` | 动态计划修改 + 子目标生成 + 人机协同审批 |
| 16 | `16_container_isolation.py` | Docker/Podman 容器配置 + 远程插件 |
| 17 | `17_hot_reload.py` | 零停机插件热重载（滚动/蓝绿/金丝雀升级） |
| 18 | `18_distributed.py` | 领导者选举 + 工作窃取 + 节点注册中心 |
| 19 | `19_cli_demo.sh` | CLI 命令行工具演示 |

## Phase 5 Demo（Production Hardening）

| # | 文件 | 说明 |
|---|------|------|
| 20 | `20_hitl_approval_workflow.py` | HITL 审批完整流程：单人/多人审批、拒绝、变更请求、超时、审计追踪（6 个场景） |
| 21 | `21_multi_tenant_isolation.py` | 多租户隔离：注册、配额强制、跨租户隔离、启停生命周期、用量报告（5 个场景） |

---

## 补充说明

### 无 LLM 依赖的 Demo（可直接运行）
下列 Demo 不依赖 LLM，无需配置 API Key 即可运行：
- `python3 demo/13_security.py`
- `python3 demo/14_multi_tenancy.py`
- `python3 demo/15_advanced_execution.py`
- `python3 demo/17_hot_reload.py`
- `python3 demo/18_distributed.py`
- `python3 demo/20_hitl_approval_workflow.py`
- `python3 demo/21_multi_tenant_isolation.py`

---

## 持久化存储配置

通过 zelos.yaml 一行切换存储后端，代码无需改动：

```yaml
# 开发/测试 — 内存（默认）
storage:
  type: "memory"

# 生产环境 — PostgreSQL
storage:
  type: "postgresql"
  url: "postgresql://user:pass@host:5432/zelos"

# 高并发 — Redis
storage:
  type: "redis"
  url: "redis://localhost:6379/0"
  prefix: "zelos"

# MySQL
storage:
  type: "mysql"
  url: "mysql://user:pass@host:3306/zelos"
```

```python
# 代码中使用 — 统一接口，不关心后端
from zelos.storage import create_storage_backend

backend = create_storage_backend({"type": "postgresql", "url": "..."})
backend.connect()
backend.append("task-events", [{"event_type": "task.created", ...}])
events = backend.read("task-events", 0, 100)
backend.set_state("goal-1", {"status": "executing"})
state = backend.get_state("goal-1")
```
