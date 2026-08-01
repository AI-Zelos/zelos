# Zelos 架构反思与演进方向

> 编写日期：2026-08-01
>
> 目的：基于当前实现状态，诚实评估 Zelos 的架构问题，并给出务实的演进路径。这是一份内部技术讨论文档，不是对外宣传材料。

---

## 目录

1. [当前状态：做了什么，没做什么](#1-当前状态做了什么没做什么)
2. [六个设计问题](#2-六个设计问题)
   - [MPC 能解决什么、不能解决什么](#mpc-能解决什么不能解决什么)
3. [演进方向](#3-演进方向)
   - [P0：分阶段验证，先跑通核心调度闭环](#p0分阶段验证先跑通核心调度闭环)
   - [P1：从 DAG 执行模型升级为搜索/推理模型](#p1从-dag-执行模型升级为搜索推理模型)
   - [P2：把内部复杂度封装为简单 API](#p2把内部复杂度封装为简单-api)
   - [P3：可观测性是产品，不是运维工具](#p3可观测性是产品不是运维工具)
   - [P4：Agent 生态飞轮](#p4agent-生态飞轮p2-p3-完成后启动持续进行)
4. [最小核心闭环定义](#4-最小核心闭环定义)
5. [讨论要点](#5-讨论要点)
6. [接下来最应该做的事](#6-接下来最应该做的事)
7. [SWE-bench 与 Zelos 核心能力验证](#7-swe-bench-与-zelos-核心能力验证)

---

## 1. 当前状态：做了什么，没做了什么

### 已完成的（12 个 Phase，151 个测试全过）

| Phase | 内容 | 状态 |
|-------|------|------|
| Event Sourcing Engine | 不可变事件写入/回放 | ✅ |
| Goal State Persistence | Goal 状态持久化 | ✅ |
| Execution Trace | 执行追踪 | ✅ |
| Evidence Collection | 证据收集 | ✅ |
| Confidence Scoring | 置信度评分 | ✅ |
| Policy Gate v2 | 策略门 | ✅ |
| Change Approval Request (CAR) | 变更审批请求 | ✅ |
| Change Proposal (CP) | 变更提案 | ✅ |
| Diagnosis Engine | 诊断引擎 | ✅ |
| Failure Classifier | 故障分类器 | ✅ |
| Repair + Ranker | 修复 + 排序器 | ✅ |
| Credential Management | 凭证管理 | ✅ |

### 未验证的

- **SWE-bench v4**：17 个实例中只有 6 个产生了有效测试输出
- **Fixer Loop**：至今没有端到端验证过一个完整案例
- **真实负载**：所有功能没有在生产级负载下运行过
- **核心调度闭环**：Planner → Scheduler → Executor → Verifier 端到端链路未跑通

### 核心事实

**问题不是"功能不够"，是不知道哪些功能真正有用，哪些是过度设计。**

---

## 2. 六个设计问题

### 问题 1：验证顺序反了——核心未稳，外围已全量加载

**现象：**

Zelos 在 7 月完成了 12 个 Phase，从 Event Sourcing 到 CP Governance 到 Credential Management 到 Diagnosis Engine。151 个测试全过。

但一个事实是：**这些功能全量加载时，没有一个端到端的验证证明核心链路是正确的。** SWE-bench v4 只有 6/17 个实例产生了有效测试输出——而且分不清是哪一层的问题。

**真正的问题：不是"功能太多"，而是"所有功能同时跑，出问题无法定位根因"。**

12 个 Phase 全开时，一个失败的 Case 你看不到：

- 是 Planner 的 Plan 有问题？
- 是 Scheduler 选了不合适的 Agent？
- 是 Verifier Chain 太严格把好的产出拒掉了？
- 是 Policy Gate 拦住了应该放行的操作？
- 是 Diagnosis Engine 误判了失败原因？

**12 层叠加在一起，任何一个环节出问题，你都不知道该看哪里。**

**类比：**

Kubernetes 1.0 只有 Pod、Service、ReplicationController 三个核心抽象。RBAC、NetworkPolicy、CRD、Helm 的代码后来都写了——但它们是等核心在生产跑稳了之后，**逐层开启**的。

Zelos 目前是：12 层全部写完、全部开启，但最底层的核心调度链路还没端到端验证过。

**根因：**

我们被"规范先行"的理念推向了另一个极端。蓝图、RFC、Schema、Invariants 确保了架构的一致性，但也让我们在没有 feedback loop 的情况下把所有层都做了。

**解决思路不是"砍功能"，而是"分阶段验证"：**

```
验证阶段 A：只开核心调度闭环
  加载：Planner + Scheduler + Executor + 基础 Verifier
  目标：端到端跑通一个 Goal
  验证：调度链路正确，产出符合预期

验证阶段 B：叠加上一层
  加载：+ Event Sourcing + Execution Trace
  目标：验证审计链完整性
  验证：回放 Event Store 能重建状态

验证阶段 C
  加载：+ Evidence Collection + Confidence Scoring
  ...

验证阶段 D
  加载：+ Policy Gate + CAR/CP + Diagnosis Engine
  ...

验证阶段 E：全量
  加载：+ Credential Management + Failure Classifier + Repair + Ranker
  目标：全量功能集成验证
```

每一层验证通过，才开下一层。功能代码一行不动，只是用 feature flag 控制加载顺序。

---

### 问题 2：Planner → Executor 是一次性的，不是持续自适应的

**当前架构：**

```
Planner 产出 Execution Plan
  → Scheduler 调度 Task Graph
    → Executor 执行
      → Verifier 验证
```

这是瀑布模型。尽管有"dynamic plan modification"，但本质上是异常处理，不是原生自适应。

**具体问题：**

- Planner 在执行前就跑完了，执行中 Runtime 只在 Task 失败时介入
- 不会因为"置信度不够"主动插入一轮搜索
- 不会因为"中间结果暗示另一个方向更优"而切换策略
- "每一步重新评估下一步该做什么"——当前架构做不到

**这不是瀑布 vs 敏捷的问题。这是"一次性的 Plan-based 执行"vs"持续的 Belief-state 推理"的问题。**

---

### 问题 3：Agent 抽象过于单薄

**当前 Agent 接口：**

```
register()
heartbeat()
execute()
cancel()
shutdown()
metadata()
```

这个抽象适合"Agent 是完全可替换的执行单元"的模型。但当你需要考虑以下问题时，它不够用：

| 调度需要知道 | 当前抽象提供什么 | 差距 |
|-------------|----------------|------|
| 这个 Agent 擅长什么，不擅长什么（能力边界） | Capability 标签 | 标签是二元的，能力边界是谱系的 |
| 在这个特定任务类型上，它历史上的校准度如何 | QoS（笼统的 cost/latency/accuracy） | 没有按任务类型细分的校准历史 |
| 两个 Agent 有相同 Capability，在什么场景下选 A 不选 B | Scoring Strategy 的 7 因子加权 | 权重是静态配置的，不是从历史中学出来的 |

**需要的是更丰富的 Agent Profile：**
- Capability 不是布尔标签，是能力谱系（精确度/覆盖率/创造性/谨慎性）
- 按任务类型的校准历史（不是笼统的成功率，是"在这个子类上的表现"）
- 失败模式（这个 Agent 在什么情况下容易出错）

---

### 问题 4：验证是后置的，不是穿插的

**当前模型：**

```
所有 Tasks 执行完毕 → Verifier Chain 运行 → 发现错误 → 重新规划 → 重新执行
```

**问题：**

- 一个明显的错误要等全部任务跑完才被发现
- 中间产物没有增量验证
- 计算资源浪费在注定失败的下游任务上

**理想模型：**

```
Task A 完成 → 产出 Artifact A → 增量验证 A →
  ✅ 通过 → 下游 Task B、C 继续
  ❌ 失败 → 立即止损，触发重规划（只影响 A 及其下游）
  ⚠️ 置信度不足 → 插入补充验证 Task，不阻塞主线
```

**这里的核心变化不是"加更多 Verifier"，而是"Verifier 从执行后的门变成执行中的传感器"。**

---

### 问题 5：Task Graph 是 DAG，不是搜索树

**DAG 适合的场景：** 你知道所有依赖关系——"这个 Task 依赖那个 Task 的输出"。

**但真正的推理过程是搜索：**

- 你不确定哪个方案能走到终点
- 你需要同时探索多个假设
- 有的路径走不通需要回溯
- 有的路径走到一半发现更好需要加深
- 部分结果可能暗示新的方向

**当前 Task Graph 不支持：**

```
❌ 同一目标的多路径并行探索
   （不是"并行执行独立任务"，是"并行尝试不同方案解决同一个问题"）

❌ 回溯到上游换一个分支
   （当前 DAG 只向前传播，失败时重试同一个 Task，不会回退到上游
     Task 说"你那个输出不太好，换个方法重新生成"）

❌ 基于部分结果的动态路径选择
   （条件依赖是静态的，不能"中间结果暗示 X 方案更好，所以走 X"）
```

**这是"Reasoning Runtime"vs"Workflow Runtime"的本质区别。**

---

### 问题 6：对外 API 太重

**要让一个开发者跑起来，他目前需要理解：**

```
Event Bus → Capability Registry → Task Graph → Scheduler
→ Execution Engine → Plugin Lifecycle → Verifier Chain
→ Policy Engine → Memory → Storage Backend → ...
```

**理想体验：**

```bash
zelos run "fix this bug"
```

内部所有复杂度对开发者透明。目前 Python SDK 有 `BaseAgent` 和 `ZelosClient`，但"解决一个任务"的端到端 API 还不存在。

**这意味着 Zelos 目前是一个"给框架开发者用的框架"，不是"给应用开发者用的 Runtime"。**

---

### MPC 能解决什么、不能解决什么

上面六个问题中，问题 2（一次性 Plan）、问题 4（后置验证）、问题 5（DAG vs 搜索树）都涉及规划模型的改造。MPC 作为建议的 P0 方案，需要明确它到底能解决哪些、不能解决哪些。

**问题 2（一次性 Plan → 自适应）：✅ MPC 直接解决**

MPC 的核心循环就是"规划 N 步 → 执行 1 步 → 用新信息重规划"。这恰好把瀑布模型变成了自适应循环。不需要额外设计。

**问题 4（后置验证 → 穿插验证）：✅ MPC 提供了结构，验证逻辑本身还要设计**

MPC 在每一步执行后有一个自然的钩子点——"收集产出 → 评估 → 决定下一步"。增量验证可以插在这里。MPC 解决了"什么时候做验证"的问题（每一步之后，而不是全部跑完之后），但"验证什么、怎么判断"的逻辑仍然需要单独设计。

**问题 5（DAG → 搜索树）：❌ MPC 解决不了**

这是最关键的区分。MPC 改善的是**规划频次**（多久重新规划一次），不是**规划本体**（规划出来的东西是什么）。

```
MPC 每一轮重规划，Plan 还是 DAG：
  "Task A → Task B → Task C（依赖关系仍然存在）"

搜索模型每一轮，维护的是 Belief State：
  "H₁: 方案A 置信度 0.6  |  H₂: 方案B 置信度 0.3  |  H₃: 方案C 置信度 0.1"
                    ↓
  选择 H₁ 收集更多证据 → 更新 → H₁ 掉到 0.4, H₂ 升到 0.7 → 切换主攻方向
```

MPC 的 Planner 每次重规划可以产出**不同的 Task**，但它产出的东西仍然是"一个有序的 Task 列表 + 依赖关系"。它没有"同时持有多个竞争假设、根据证据更新各自置信度、动态分配探索资源"的能力。

**搜索树需要三个 MPC 没有的东西：**

| 搜索模型有 | MPC 没有 |
|-----------|---------|
| 多个并行假设（不同方案同时探索） | 每轮只有一个 Plan |
| 回溯（上一个 Task 的输出不好，换方法重新生成） | 重规划可以换 Task，但前一个 Task 的产出已经是事实，不会"换分支重新来" |
| 信息增益驱动的资源分配（下一单位算力投给哪个假设最值） | 按依赖关系调度（哪个 Task 前置满足就调哪个） |

**结论：**

```
MPC 解决：从"一次性瀑布" → "每步自适应"（问题 2 + 问题 4 的框架层面）
MPC 不解决：从"DAG 任务编排" → "搜索树推理"（问题 5）

P0（MPC + Rule-based replan）先验证自适应调度核心闭环
P1（Belief State 搜索模型）再解决多假设并行探索 + 回溯 + 信息增益分配
```

---

## 3. 演进方向

### 整体策略

```
当前状态                  目标状态
─────────                ─────────
12 层全开，无法定位根因    逐层验证，逐层开启
核心调度链路未端到端验证   端到端跑通核心闭环
模型偏静态                 自适应推理（MPC 模式 → Belief State 搜索）
API 暴露内部复杂度         zelos run "fix this bug"
```

**核心原则：功能代码不动，验证顺序调整——从核心向外围，逐层验证通过再开启下一层。**

---

### P0：分阶段验证核心调度闭环（约 4-6 周）

**目标：** 在关闭所有外围组件的前提下，端到端跑通至少一个多 Agent 协作的 Goal，定位核心链路的真实阻塞点。

**范围：** 只做验证和最小改造，不做大规模重构。MPC 重规划逻辑用最薄的方式实现，不推翻现有 Planner。

---

#### 阶段 A：核心调度闭环验证（第 1-3 周）

##### 做什么

**1.1 选择验证场景**

不碰 SWE-bench 全量。构造或选取一个**可控的、简化的**多 Agent 协作场景：

```
场景规格：
  输入：一个明确的代码任务描述（如 "在项目 X 中实现函数 Y，要求 Z"）
  所需 Agent：Researcher（分析） + Coder（实现） + Reviewer（审查）
  步数：3-5 步
  依赖：Reviewer 依赖 Coder 的产出，Coder 依赖 Researcher 的产出
  验证方式：自动化测试可判断产出正确性
```

场景选择标准：
- 能在本地环境 100% 复现（不依赖外部网络服务）
- 有明确的 pass/fail 判据（不是模糊的"好/不好"）
- Agent 可以是最简单的 mock 或 stub（先验证调度链路，再验证 Agent 质量）

**1.2 组件加载配置**

```
zelos.yaml（阶段 A 配置）:
  kernel:
    event_bus: true           # Kernel 核心，必须加载
    capability_registry: true # 调度依赖，必须加载
    task_graph_engine: true   # DAG 依赖，必须加载
    scheduler: true           # 核心
    execution_engine: true    # 核心

  plugins:
    planner: true             # 核心
    verifier: true            # 核心（基础模式，单步校验）
    policy: false             # 阶段 D 再开
    memory: false             # 阶段 C 再开
    storage: false            # 阶段 B 再开（先用内存实现）

  features:
    event_sourcing: false     # 阶段 B
    execution_trace: false    # 阶段 B
    evidence_collection: false # 阶段 C
    confidence_scoring: false  # 阶段 C
    policy_gate: false         # 阶段 D
    cp_governance: false       # 阶段 D
    car: false                 # 阶段 D
    diagnosis_engine: false    # 阶段 D
    credential_management: false # 阶段 E
    failure_classifier: false  # 阶段 E
    repair_ranker: false       # 阶段 E
```

**1.3 最薄 MPC 重规划实现**

不做新的 Planner 类。在现有 ExecutionEngine 的 Task 完成回调处加一个 `replan_check` 钩子：

```python
# zelos/kernel/execution_engine.py 新增

class ExecutionEngine:
    def __init__(self, ..., replan_rules: List[ReplanRule] = None):
        self.replan_rules = replan_rules or DEFAULT_REPLAN_RULES

    async def _on_task_completed(self, event: TaskCompleted):
        task_id = event.task_id
        artifact = event.artifact

        # 增量验证（穿插在每一步之后，非后置全量）
        verdict = await self.verifier.verify(artifact)
        await self.event_bus.publish(ArtifactVerified(
            task_id=task_id, verdict=verdict
        ))

        # 检查是否需要重规划
        for rule in self.replan_rules:
            if rule.should_replan(task_id, artifact, verdict, self._plan):
                new_plan = await self.planner.replan(
                    current_plan=self._plan,
                    trigger=rule.trigger_reason,
                    context={
                        "failed_task": task_id,
                        "verdict": verdict,
                        "completed_tasks": self._completed_tasks
                    }
                )
                self._plan = new_plan
                await self.event_bus.publish(ExecutionPlanModified(
                    plan=self._plan, reason=rule.trigger_reason
                ))
                break

# 默认重规划规则（Level 1: Rule-based）
DEFAULT_REPLAN_RULES = [
    VerdictRejectedRule(),      # Verifier 返回 rejected → 重规划
    ConfidenceLowRule(),        # Verifier 置信度 < 阈值 → 插入补充验证
    SchemaMismatchRule(),       # Artifact schema 不匹配预期 → 重规划
]
```

Planner 新增 `replan()` 方法（非抽象，有默认实现）：

```python
# zelos/plugins/planner.py 新增方法

class Planner(Plugin):
    async def replan(self, current_plan, trigger, context):
        """
        默认重规划策略：标记失败 Task，重新分解未完成路径。
        子类可覆盖实现更智能的策略。
        """

        # 1. 标记失败 Task 及其下游为 BLOCKED
        failed_task_id = context["failed_task"]
        downstream_ids = current_plan.get_downstream(failed_task_id)
        for tid in downstream_ids:
            current_plan.set_task_state(tid, TaskState.BLOCKED)

        # 2. 为被阻塞的路径生成替代 Task
        replacement_tasks = await self._decompose_path(
            goal=current_plan.goal,
            blocked_output=context.get("verdict"),
            context=context
        )

        # 3. 将新 Task 插入 Plan
        new_plan = current_plan.insert_tasks(
            after=failed_task_id,
            tasks=replacement_tasks
        )
        return new_plan
```

**关键设计约束：**
- `replan()` 必须返回一个合法的 Execution Plan（不破坏 DAG 拓扑）
- 重规划次数必须有上限（默认 5 次，防无限循环）
- 重规划 Event 必须记录 `trigger_reason`（审计用）

##### 怎么验证

**测试分层：**

```
Layer 1: 单元测试（每次提交跑）

  TestReplanRules:
    test_verdict_rejected_triggers_replan()         # Verdict.REJECTED → True
    test_verdict_accepted_does_not_trigger()         # Verdict.ACCEPTED → False
    test_confidence_below_50_triggers_replan()       # confidence=0.3, threshold=0.5 → True
    test_confidence_above_50_does_not_trigger()      # confidence=0.8 → False
    test_replan_max_5_times_then_fatal()             # 第 6 次触发 → FatalError

  TestPlannerReplan:
    test_replan_marks_failed_task_blocked()          # 失败 Task 状态 = BLOCKED
    test_replan_marks_downstream_blocked()           # 下游 Task 也都 BLOCKED
    test_replan_inserts_replacement_tasks()          # 新 Task 插入了 Plan
    test_replan_preserves_dag_topology()             # 新 Plan 的 DAG 仍然合法
    test_replan_emits_plan_modified_event()          # 发布了 ExecutionPlanModified

Layer 2: 集成测试（每个 Phase 跑，3-5 个场景）

  场景 1: 正常完成（无重规划）
    - 给定: Goal → 3 个 Task 的 Plan
    - Agent 全部成功 → Verifier 全部 Accepted
    - 验证: 所有 Task COMPLETED，Goal COMPLETED，0 次重规划触发

  场景 2: 单次重规划
    - 给定: Goal → Coder Task 失败（Verifier REJECTED）
    - 验证: 触发 1 次重规划 → 新的 Coder Task 插入 → 最终成功

  场景 3: 多次重规划直到成功
    - 给定: Coder Task 连续失败 2 次，第 3 次成功
    - 验证: 2 次重规划 Event 发布 → 第 3 个 Coder Task 成功

  场景 4: 超出重规划上限
    - 给定: Coder Task 连续失败 6 次
    - 验证: 第 5 次重规划后 → 第 6 次触发 → Goal FAILED (FATAL)

  场景 5: 下游被级联阻塞
    - 给定: A → B → C，A 失败
    - 验证: A 被替换 → B 和 C 重新关联到新 A' → 最终全部完成

Layer 3: 端到端验证（阶段 A 的最终目标）

  用 3 个真实 Agent（非 mock）完成一个完整案例：
    Researcher Agent → Coder Agent → Reviewer Agent

  验证记录（不是 pass/fail，是观察记录）：
    - Planner 产出了什么 Plan？Plan 的 Task 分解是否合理？
    - Scheduler 为每个 Task 选了哪个 Agent？选择依据是什么？
    - 每个 Agent 返回了什么？耗时多久？
    - Verifier 对每个产出给出了什么判断？
    - 有没有触发重规划？为什么？
    - 最终结果是否满足初始 Goal？
```

##### 成功标准

阶段 A 完成的标志是**一份完整的端到端执行记录**（不是"跑通了"），能回答：

> "在关闭所有外围组件的前提下，核心调度链路在哪个环节有问题？"

具体交付物：
1. 至少 1 个端到端案例的执行 Trace（包含上述所有验证记录字段）
2. 一份阻塞点分析：哪个环节（Plan/Schedule/Execute/Verify/Replan）是瓶颈
3. 如果跑通了：至少 3 个案例全部成功（证明不是侥幸）
4. 如果没跑通：精确到函数级别的根因定位

---

#### 阶段 B：审计链验证（第 4 周）

**前提：** 阶段 A 核心闭环跑通。

##### 做什么

**2.1 Feature Flag 打开：**

```yaml
features:
  event_sourcing: true
  execution_trace: true
```

**2.2 验证：Event Store 回放重建状态**

不需要改任何业务代码。只验证"Event 写入是正确的"和"回放能重建状态"：

```python
class TestEventSourcingReplay:
    async def test_replay_reconstructs_goal_state(self, event_store, goal_id):
        """回放 Goal 的所有 Event → 重建的状态与原始状态一致"""
        events = await event_store.replay(correlation_id=goal_id)
        reconstructed = reconstruct_state(events)
        original = await get_original_state(goal_id)
        assert reconstructed == original

    async def test_replay_at_timestamp(self, event_store, goal_id):
        """回放到某个时间点 → 状态与该时间点快照一致"""
        point = some_execution_midpoint_timestamp
        events = await event_store.replay(correlation_id=goal_id, to=point)
        mid_state = reconstruct_state(events)
        snapshot = await load_snapshot(goal_id, point)
        assert mid_state == snapshot

    async def test_causation_chain_is_complete(self, event_store, goal_id):
        """每个 Event 的 causation_id 指向的 Event 确实存在"""
        events = await event_store.replay(correlation_id=goal_id)
        event_ids = {e.event_id for e in events}
        for e in events:
            if e.causation_id:
                assert e.causation_id in event_ids, \
                    f"Event {e.event_id} claims caused by {e.causation_id}, not found"
```

##### 成功标准

- 3 个以上端到端案例的 Event Store 回放能精确重建最终状态
- causation chain 完整无断裂
- 0 个"不应该存在但存在"或"应该存在但不存在"的 Event

---

#### 阶段 C：置信度与证据验证（第 4-5 周）

**前提：** 阶段 B 审计链验证通过。

##### 做什么

**3.1 Feature Flag 打开：**

```yaml
features:
  evidence_collection: true
  confidence_scoring: true
plugins:
  memory: true
```

**3.2 置信度评分校准验证**

置信度是有校准意义的，不能是一个随意填的数字：

> "Verifier 给了 0.9 置信度的产出，最终确实有 90% 的比例被下游接受"

```python
class TestConfidenceCalibration:
    async def test_confidence_calibration(self, history):
        """统计校准曲线：声称的置信度 vs 实际通过率"""
        buckets = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
        for lo, hi in buckets:
            claimed = [h for h in history if lo <= h.confidence < hi]
            if len(claimed) < 5:
                continue  # 样本不够
            actual_pass_rate = sum(1 for h in claimed if h.accepted) / len(claimed)
            # 实际通过率应在声称区间的 ±15% 内
            assert lo - 0.15 <= actual_pass_rate <= hi + 0.15, \
                f"Calibration off: claimed {lo}-{hi}, actual {actual_pass_rate:.2f}"

    async def test_confidence_not_always_max(self, history):
        """置信度不能永远都是 1.0——那说明评分没用"""
        scores = [h.confidence for h in history]
        assert max(scores) - min(scores) > 0.3, \
            "Confidence scores show no discrimination"

    async def test_low_confidence_correlates_with_failure(self, history):
        """低置信度的产出确实比高置信度更容易失败"""
        low_conf = [h for h in history if h.confidence < 0.5]
        high_conf = [h for h in history if h.confidence > 0.8]
        if low_conf and high_conf:
            low_fail_rate = sum(1 for h in low_conf if not h.accepted) / len(low_conf)
            high_fail_rate = sum(1 for h in high_conf if not h.accepted) / len(high_conf)
            assert low_fail_rate > high_fail_rate
```

##### 成功标准

- 置信度评分的校准曲线在 ±15% 误差带内
- 低置信度产出确实有更高的下游失败率
- Evidence 对置信度的影响方向正确（positive evidence → 置信度上升，negative → 下降）

---

#### 阶段 D：治理层验证（第 5-6 周）

**前提：** 阶段 C 置信度评分校准通过。

##### 做什么

**4.1 Feature Flag 打开：**

```yaml
features:
  policy_gate: true
  cp_governance: true
  car: true
  diagnosis_engine: true
```

**4.2 治理层独家验证**

每个新增组件都有一个独立的验证维度：

```python
# Policy Gate: 不误拦、不漏拦
TestPolicyGate:
    test_low_risk_goal_allowed()           # 低风险 Goal → ALLOW
    test_high_risk_goal_blocked()          # 高风险 + 无审批 → REJECT
    test_high_risk_goal_delayed()          # 高风险 + 有审批 → DELAY（等审批）
    test_no_false_positive_on_20_cases()   # 20 个正常 Goal → 0 个误拦
    test_no_false_negative_on_10_risky()   # 10 个风险 Goal → 0 个漏拦

# Diagnosis Engine: 故障原因判断准确
TestDiagnosisEngine:
    test_agent_timeout_diagnosed()
    test_schema_mismatch_diagnosed()
    test_verification_failure_diagnosed()
    test_diagnosis_links_to_specific_event()

# CAR: 变更审批请求格式完整
TestCAR:
    test_car_contains_all_10_modules()
    test_car_evidence_links_to_artifacts()
```

##### 成功标准

- Policy Gate: 误拦率 = 0/20，漏拦率 = 0/10
- Diagnosis Engine: 已知故障类型 100% 正确归类
- CAR: 自动生成的 10 个模块全部有内容，Evidence 链接有效

---

#### 阶段 E：全量集成验证（第 6-7 周）

**前提：** 阶段 D 治理层验证通过。

##### 做什么

**5.1 所有 Feature Flag 全部打开**

**5.2 全量回归 + 压力测试**

```python
# 全量回归
TestFullIntegration:
    test_all_phase_a_cases_still_pass()     # 阶段 A 的案例全部重跑
    test_all_phase_b_cases_still_pass()
    test_all_phase_c_cases_still_pass()
    test_all_phase_d_cases_still_pass()

# 压力测试
TestStress:
    test_10_concurrent_goals()              # 10 个并发 Goal
    test_50_tasks_in_single_plan()          # 大 Plan
    test_long_running_goal_1hour()          # 长运行
    test_agent_join_mid_execution()         # 执行中途新 Agent 注册
    test_agent_disconnect_recovery()        # Agent 断连恢复
```

**5.3 SWE-bench 回归**

全量开启后，用 SWE-bench v4 重新跑一次，与阶段 A 的 baseline 对比：

```
阶段 A (bare core):     X/17 有效
阶段 E (full stack):    Y/17 有效

如果 Y < X：全量开启后性能退化，需要逐层排查
如果 Y ≈ X：外围组件没有拖累核心
如果 Y > X：外围组件起到了正向作用（如 Diagnosis 提高了重规划质量）
```

##### 成功标准

- 所有阶段 A-D 的测试案例仍然通过（功能叠加无回归）
- 10 个并发 Goal 全部完成（不超时、不死锁）
- SWE-bench 结果不比阶段 A 的 baseline 差

---

### P1：从 DAG 执行模型升级为搜索/推理模型（约 8-12 周，P0 全部完成后启动）

**前置条件：** P0 核心闭环跑通 + 阻塞点定位明确 + 确认 DAG 模型确实是瓶颈（而非 Agent 质量或 Verifier 判据问题）。

**目标：** Runtime 顶层执行模型从"执行一个 Plan（DAG）"升级为"引导一个搜索（Belief State）"。底层调度机制（Scheduler、Executor）保持不变。

---

#### 核心设计

##### 新增实体

```python
# zelos/kernel/belief_state.py

@dataclass
class Hypothesis:
    """一个可能的解法或部分结论"""
    id: str                          # 唯一标识
    description: str                 # 自然语言描述
    parent_id: Optional[str]         # 从哪个 Hypothesis 派生
    confidence: float                # 当前信念 (0.0 - 1.0)
    evidence: List[Evidence]         # 收集到的证据列表
    actions_completed: List[str]     # 已执行的 Action ID
    actions_planned: List[str]       # 计划但未执行的 Action ID
    status: HypothesisStatus         # ACTIVE / ACCEPTED / REJECTED / STALE

@dataclass
class Evidence:
    """支持或反对一个 Hypothesis 的证据"""
    id: str
    hypothesis_id: str
    source_action_id: str            # 哪个 Action 产出了这个 Evidence
    polarity: Polarity               # SUPPORTING / REFUTING / NEUTRAL
    strength: float                  # 证据强度 (0.0 - 1.0)
    summary: str                     # 自然语言摘要
    artifact_ref: str                # 关联的 Artifact ID

@dataclass
class BeliefState:
    """当前搜索状态"""
    goal_id: str
    hypotheses: List[Hypothesis]
    budget: Budget                   # 剩余计算预算
    iteration: int                   # 当前第几步

    @property
    def active_hypotheses(self):
        return [h for h in self.hypotheses if h.status == HypothesisStatus.ACTIVE]

    @property
    def best_hypothesis(self):
        return max(self.active_hypotheses, key=lambda h: h.confidence)
```

##### 新增 Kernel 组件：SearchController

```python
# zelos/kernel/search_controller.py

class SearchController:
    """
    替代 Planner 在搜索模型中的角色。
    不再"一次性产出 Plan"，而是"每一步决策下一个 Action"。
    """

    def __init__(self, strategy: SearchStrategy):
        self.strategy = strategy

    async def next_action(self, belief: BeliefState) -> Action:
        """
        核心决策函数：给定当前信念状态，选择收益最大的下一个 Action。
        这是 P1 最核心的算法点。
        """
        return await self.strategy.select(belief)

    async def update_belief(
        self,
        belief: BeliefState,
        action: Action,
        artifact: Artifact,
        verdict: Verdict
    ) -> BeliefState:
        """
        用执行结果更新信念状态：
        - 将 Artifact + Verdict 转化为 Evidence
        - 更新相关 Hypothesis 的置信度
        - 检查是否有 Hypothesis 达到接受/拒绝阈值
        """
        evidence = self._artifact_to_evidence(action, artifact, verdict)

        # 关联 Hypothesis
        target_h = belief.get_hypothesis(action.hypothesis_id)

        # 更新置信度：P(h | new_evidence)
        # 使用简单的贝叶斯更新（P1 先用这个，后续可换更复杂模型）
        if evidence.polarity == SUPPORTING:
            target_h.confidence = min(1.0, target_h.confidence * (1 + evidence.strength * 0.3))
        elif evidence.polarity == REFUTING:
            target_h.confidence = max(0.0, target_h.confidence * (1 - evidence.strength * 0.5))
            # 反证的惩罚力度更大（0.5 > 0.3），因为 1 个强反证应比 1 个强正证更有影响力

        target_h.evidence.append(evidence)
        belief.iteration += 1
        return belief
```

##### 搜索策略接口

```python
# zelos/kernel/search_strategy.py

class SearchStrategy(Plugin):
    """可替换的搜索策略。不同策略决定不同的探索/利用平衡。"""

    async def select(self, belief: BeliefState) -> Action:
        raise NotImplementedError

    async def initialize_hypotheses(self, goal: Goal) -> List[Hypothesis]:
        """给定 Goal，生成初始假设集合"""
        raise NotImplementedError


class EpsilonGreedyStrategy(SearchStrategy):
    """
    ε-greedy: 以 ε 概率探索（随机选），以 1-ε 概率利用（选置信度最高的）。
    最简单的 baseline，用于验证搜索框架是否正确。
    """

    def __init__(self, epsilon: float = 0.2):
        self.epsilon = epsilon

    async def select(self, belief: BeliefState) -> Action:
        if random.random() < self.epsilon:
            # 探索：随机选一个 active hypothesis
            h = random.choice(belief.active_hypotheses)
        else:
            # 利用：选置信度最高的
            h = belief.best_hypothesis

        # 为该 hypothesis 生成下一个待执行的 Action
        return Action(
            hypothesis_id=h.id,
            description=f"Collect more evidence for: {h.description}",
            expected_info_gain=self._estimate_info_gain(h, belief)
        )


class InfoGainStrategy(SearchStrategy):
    """
    信息增益策略：每步选择期望信息增益最大的 Action。
    这更接近 P1 的最终目标，但实现复杂度更高。
    建议 EpsilonGreedy 先跑通，再替换为 InfoGain。
    """

    async def select(self, belief: BeliefState) -> Action:
        candidates = []
        for h in belief.active_hypotheses:
            for action_template in h.actions_planned:
                info_gain = self._estimate_info_gain(h, action_template, belief)
                cost = self._estimate_cost(action_template)
                candidates.append((info_gain / cost, h, action_template))

        # 选 info_gain/cost 最大的
        best = max(candidates, key=lambda x: x[0])
        return Action(
            hypothesis_id=best[1].id,
            description=best[2].description,
            expected_info_gain=best[0]
        )
```

##### 与现有 DAG 层的关系

搜索模型不替代 DAG。它在上层做搜索决策，每个 Action 在执行时仍然经过 DAG 层：

```
搜索层（新增）                  执行层（复用现有）
─────────────                   ────────────────
BeliefState                     ExecutionPlan（动态生成，只含当前 Action + 下游依赖）
  → SearchController            TaskGraph（Action A → Task T → 子 Tasks）
    → next_action()               → Scheduler（匹配 Agent）
      → Action A                  → Executor（调用 Agent）
      → update_belief()           → Verifier（增量验证）
      → 循环                      → 结果返回搜索层
```

```python
class SearchController:
    async def execute_action(self, action: Action, belief: BeliefState) -> tuple[Artifact, Verdict]:
        """将 Action 转化为 DAG 层的 Execution Plan（只含当前探索步骤）"""

        # 动态生成一个极小 Plan（1 个 Action + 必要的下游）
        mini_plan = ExecutionPlan(
            goal_id=belief.goal_id,
            tasks=[
                Task(
                    id=action.id,
                    capability=action.capability,
                    input=action.description,
                    context={"hypothesis": action.hypothesis_id}
                )
            ]
        )

        # 走现有调度链路（复用 Scheduler + Executor + Verifier）
        result = await self.runtime.execute_plan(mini_plan)
        return result.artifact, result.verdict
```

---

#### 怎么验证

##### Layer 1: 单元测试

```python
TestBeliefState:
    test_initialize_hypotheses_from_goal()     # Goal → 至少 2 个 Hypothesis
    test_confidence_increases_with_support()    # positive evidence → 置信度上升
    test_confidence_decreases_with_refute()     # negative evidence → 置信度下降
    test_accept_threshold()                     # confidence > 0.9 → ACCEPTED
    test_reject_threshold()                     # confidence < 0.1 → REJECTED
    test_best_hypothesis_is_highest_confidence() # best_hypothesis 确实最高

TestEpsilonGreedyStrategy:
    test_exploit_chooses_best()                 # 1-ε 概率选最高置信度
    test_explore_chooses_random()               # ε 概率选随机 h
    test_greedy_converges_on_simple_case()      # 简单场景贪心能收敛

TestSearchController:
    test_update_belief_emits_event()            # 信念更新发布 Event
    test_action_creates_mini_plan()             # Action → 合法的 ExecutionPlan
    test_search_terminates_when_accepted()      # 有 Hypothesis 被接受 → 搜索结束
    test_search_terminates_when_budget_exhausted() # 算力耗尽 → 选 best_h 接受
    test_all_rejected_triggers_new_hypothesis() # 全拒绝 → 生成新 Hypothesis
```

##### Layer 2: 对比实验

最关键的不是"搜索模型能不能跑"，而是"搜索模型是否比 DAG 模型更好"。

在同一个场景上跑两种模式，对比：

| 指标 | DAG 模型（baseline） | 搜索模型（P1） | 期望方向 |
|------|---------------------|---------------|---------|
| 最终成功率 | X% | Y% | Y > X |
| 平均完成步数 | N steps | M steps | M ≤ N（搜索不该更慢） |
| 探索过但放弃的路径数 | 0（DAG 不探索） | K paths | K > 0（有探索行为） |
| 回溯次数 | 0（DAG 不回溯） | R rollbacks | R > 0（有回溯行为） |
| 被放弃路径中是否有更好的 | 无法知道 | 事后分析 | 至少 1 个案例中回溯 > 0 |

##### Layer 3: 审计链完整性

```python
TestSearchAuditTrail:
    test_every_exploration_has_event()      # 每个探索动作都有 Event
    test_rejected_hypothesis_events_preserved() # 被放弃的 H 的 Event 仍然在 Event Store
    test_exploration_id_links_branches()    # exploration_id 串起同一条探索路径
    test_correlation_id_links_all()         # correlation_id 串起整个 Goal
```

---

### P2：把内部复杂度封装为简单 API（约 3-4 周，P1 核心跑通后启动）

**前置条件：** P1 搜索模型核心逻辑跑通（EpsilonGreedy 即可，不需要 InfoGain）。

**目标：** 让应用开发者可以用一行命令使用 Zelos，内部复杂度完全透明。

---

#### 设计：两层 API

```python
# ── Layer 1: 一行命令（给应用开发者）──

import zelos

# 最简用法
result = zelos.run("fix bug #1234 in repo X")

# 带约束
result = zelos.run(
    "在 django 项目中修复 issue #1234，修复完要有测试验证",
    budget=10.0,        # 最大花费 $10
    deadline="1h",      # 1 小时超时
    agents=["claude-code", "gpt-engineer"],  # 可选：限制 Agent 池
)

# 查看结果
print(result.success)           # bool
print(result.artifact)          # 最终产出（PR / patch）
print(result.trace)             # 执行 Trace（可选展开）
print(result.cost)              # 实际花费
print(result.exploration_log)   # 搜索过程（探索了哪些方案、放弃了哪些）
```

```python
# ── Layer 2: 可编程 API（给框架开发者 / 高级用户）──

from zelos import ZelosRuntime, Goal

runtime = ZelosRuntime(config="zelos.yaml")

# 完整的控制权
goal = Goal(
    intent="fix bug #1234",
    repo="github.com/org/repo",
    constraints={
        "budget": 10.0,
        "deadline": "1h",
        "required_evidence": ["test_pass", "review_approved"]
    }
)

# 注册自定义 Agent
@runtime.agent(capability="code-review.security")
class MySecurityReviewer:
    async def execute(self, task):
        # 自定义审查逻辑
        return Artifact(...)

# 注册自定义 Verifier
@runtime.verifier
class MyVerifier:
    async def verify(self, artifact, criteria):
        return Verdict(accepted=True, confidence=0.95)

# 提交 + 观察
execution = runtime.submit(goal)
async for event in execution.stream():
    print(f"[{event.timestamp}] {event.type}: {event.summary}")

result = await execution.result()
```

---

#### 实现路径

**第 1 步：Goal 自然语言解析器**

```python
# zelos/api/goal_parser.py

class GoalParser:
    """
    将自然语言 Goal 转化为内部 Goal Schema。
    内部用一个轻量 LLM 调用（或模板匹配）做解析，不是核心逻辑。
    """

    async def parse(self, text: str, **kwargs) -> Goal:
        """
        "fix bug #1234 in repo X" →
          Goal(
            intent="fix bug",
            target=Target(repo="X", issue_id="1234"),
            constraints={"budget": kwargs.get("budget"), ...}
          )
        """
```

**第 2 步：zelos.run() 一行命令**

```python
# zelos/api/__init__.py

async def run(
    goal_text: str,
    *,
    budget: float = None,
    deadline: str = None,
    agents: List[str] = None,
    config: str = "zelos.yaml",
) -> RunResult:
    """
    一行命令入口。内部自动完成：
      1. 解析 Goal
      2. 初始化 Runtime（按 config 控制加载哪些组件）
      3. 初始化搜索（生成 Hypotheses）
      4. 搜索循环（P1 SearchController）
      5. 产出最终结果
    """

    # 1. 解析
    goal = await GoalParser().parse(goal_text, budget=budget, deadline=deadline)

    # 2. 初始化 Runtime
    runtime = ZelosRuntime.from_config(config)
    if agents:
        runtime.limit_agents(agents)

    # 3-5. 执行
    execution = await runtime.submit(goal)
    result = await execution.result()

    return RunResult(
        success=result.goal_completed,
        artifact=result.final_artifact,
        trace=result.event_trace,
        cost=result.total_cost,
        exploration_log=result.exploration_log,
    )
```

**第 3 步：CLI 入口**

```bash
# zelos/cli.py
$ zelos run "fix bug #1234 in repo X"
$ zelos run "fix bug #1234 in repo X" --budget 10 --deadline 1h
$ zelos run "fix bug #1234 in repo X" --verbose  # 显示执行过程
$ zelos dashboard                                 # 打开 Dashboard
```

---

#### 怎么验证

```python
TestZelosRunAPI:
    test_run_simple_goal_succeeds()           # 一行命令能完成简单任务
    test_run_returns_runresult()              # 返回结构完整
    test_run_with_budget_constraint()         # budget 约束生效
    test_run_with_deadline_constraint()       # deadline 约束生效
    test_run_result_trace_is_readable()       # trace 人类可读
    test_run_verbose_mode_output()            # verbose 输出有意义

TestCLI:
    test_zelos_run_command()                  # CLI 命令能启动
    test_zelos_run_with_flags()               # --budget --deadline 等 flag 生效
    test_zelos_dashboard_launches()           # dashboard 命令能启动
```

---

### P3：可观测性是产品，不是运维工具（约 4-6 周，与 P2 并行）

**目标：** 每一个 Runtime 决策都有可解释的输入、输出和理由。Dashboard 不是运维面板，是决策透明面板。

---

#### 设计：决策理由 Event 化

每个决策点发布一个专门的 "Decision" Event：

```python
# zelos/kernel/events/decision_events.py

@dataclass
class SchedulerDecision(Event):
    """Scheduler 为什么选了 Agent B 而不是 Agent A"""
    task_id: str
    capability: str
    candidates: List[ScoredCandidate]   # 所有候选 Agent 及其分数
    selected: str                        # 最终选择的 Agent ID
    selection_reason: str                # 自然语言理由
    # 例: "Agent B (score 0.89) selected over Agent A (0.72) because:
    #       - B 在此任务类型上历史校准度更高 (0.89 vs 0.72)
    #       - B 的当前负载更低 (2 vs 5 in-flight tasks)
    #       - B 的预估延迟更短 (15s vs 45s)"

@dataclass
class PlannerDecision(Event):
    """Planner 为什么产出这个 Plan"""
    goal_id: str
    hypotheses_considered: List[str]     # 考虑过的其他假设
    selected_hypothesis: str             # 选中的假设
    selection_reason: str                # 为什么选这个
    plan_summary: str                    # Plan 摘要

@dataclass
class VerificationDecision(Event):
    """Verifier 为什么给出这个判断"""
    artifact_id: str
    criteria: List[str]                  # 判据列表
    results: Dict[str, bool]             # 每个判据的结果
    confidence: float
    confidence_breakdown: str            # 置信度是怎么算的

@dataclass
class ReplanDecision(Event):
    """为什么触发了重规划"""
    trigger: str                         # 触发条件
    failed_task_id: str
    verdict: Verdict
    old_path: str                        # 被放弃的路径
    new_path: str                        # 新路径
    reason: str                          # 决策理由

@dataclass
class ExplorationDecision(Event):
    """搜索过程中为什么选择了这个 Hypothesis 来探索"""
    belief_state_snapshot: BeliefStateSnapshot  # 当时的信念状态
    selected_hypothesis: str
    selection_strategy: str              # epsilon-greedy / info-gain / ...
    estimated_info_gain: float           # 预估信息增益
    reason: str
```

#### 实现路径

**第 1 步：改造现有 Event 发布点**

在每个决策点插入 Decision Event 的发布。不改业务逻辑，只在决策后追加一个 Event：

```python
class Scheduler:
    async def _select_agent(self, task, candidates):
        scored = self.scoring_strategy.score(task, candidates)
        selected = scored[0]

        # 新增：发布决策理由
        await self.event_bus.publish(SchedulerDecision(
            task_id=task.id,
            capability=task.capability,
            candidates=scored,
            selected=selected.agent_id,
            selection_reason=self._explain_selection(scored, selected)
        ))

        return selected
```

**第 2 步：决策理由生成**

不是事后推断，是在决策时就记录计算过程：

```python
def _explain_selection(self, scored, selected):
    """生成人类可读的选择理由"""
    reasons = []
    runner_up = scored[1] if len(scored) > 1 else None

    if runner_up:
        reasons.append(
            f"Agent {selected.agent_id} (score {selected.score:.2f}) "
            f"selected over Agent {runner_up.agent_id} ({runner_up.score:.2f})"
        )

        # 逐因子比较
        for factor in selected.factor_scores:
            if factor.name in runner_up.factor_scores:
                delta = selected.factor_scores[factor.name] - runner_up.factor_scores[factor.name]
                if abs(delta) > 0.05:
                    reasons.append(
                        f"  {factor.name}: {selected.agent_id} ({selected.factor_scores[factor.name]:.2f}) "
                        f"vs {runner_up.agent_id} ({runner_up.factor_scores[factor.name]:.2f})"
                    )

    return "\n".join(reasons)
```

**第 3 步：Dashboard**

```python
# zelos/dashboard/ — 一个独立的 Web 应用

# 核心页面：
# 1. 执行 Timeline：每个 Goal 从创建到完成的完整 Event 时间线
# 2. 决策面板：每个 Decision Event 的展开视图
# 3. 搜索树可视化：所有 Hypothesis + 探索路径 + 置信度变化曲线
# 4. Agent 面板：每个 Agent 的历史校准度、当前负载、失败模式
```

---

#### 怎么验证

```python
TestDecisionEvents:
    test_scheduler_decision_emitted_on_dispatch()
    test_planner_decision_emitted_on_plan()
    test_verification_decision_emitted_on_verify()
    test_replan_decision_emitted_on_replan()
    test_exploration_decision_emitted_on_action_select()

TestDecisionExplainability:
    test_every_decision_has_non_empty_reason()    # 每个决策都有理由，不能空
    test_reason_references_specific_data()         # 理由引用具体数据（不能是"综合考虑"）
    test_reason_is_human_readable()               # 非技术人员能看懂
    test_same_input_same_reason()                  # 同样输入 → 同样解释（确定性）
```

---

### P4：Agent 生态飞轮（P2-P3 完成后启动，持续进行）

**核心问题：** P0-P3 做完后，Zelos 在技术上有本质性差异化。但搜索算法、MPC 调度、决策可解释性——一个足够强的团队（LangChain、Microsoft）看到这条路走通了，6-12 个月能追上。**飞轮是那个越用越强、别人追不上的东西。**

---

#### 飞轮模型

```
Agent 越多
  → 每个 Capability 的候选 Provider 越多
    → Scheduler 的选择空间越大
      → 每次调度的校准数据越多（Agent A 在任务类型 X 上到底准不准）
        → Scheduler 决策越准（真的知道什么时候选 A 不选 B）
          → 任务成功率越高
            → 更多用户愿意用 Zelos
              → 更多 Agent 开发者愿意注册到 Zelos
                → Agent 越多  ← 回到起点
```

每一圈，Scheduler 的校准精度就高一点，竞争者的追赶成本就大一点。

---

#### 为什么这个飞轮是 Zelos 独占的

LangGraph 和 CrewAI 拿不到这个数据，因为架构基因不同：

```
LangGraph / CrewAI / Harness：
  开发者写死 "这个 Task 给 Agent A 做"
  → 没有"选谁"的决策
  → 没有"选得对不对"的反馈
  → 没有跨 Agent 的校准数据积累
  → 飞轮根本不会转

Zelos：
  Scheduler 每次都要选——选 A 还是选 B
  → 每次选择都有结果（成功 / 失败 / Verifier 打分）
  → 这个结果自动变成 A 和 B 在这个任务类型上的历史校准记录
  → 100 次之后，Scheduler 真的知道选谁
  → 1000 次之后，任何新进入者要重新积累 1000 次的校准数据
```

**这个飞轮的三个前提条件，恰好都是 Zelos 的架构基因：**

| 前提条件 | 对应的 Zelos 设计 | 竞品状态 |
|---------|------------------|---------|
| Capability 分发，每次都有"选 A 还是选 B"的决策 | Invariant 5：Capability Before Agent | 竞品都是名称绑定（task.agent = xxx） |
| 每次决策的结果可追溯 | Event Bus + Execution Trace + Decision Event（P3） | 竞品最多有日志，没有结构化的跨 Agent 校准数据 |
| Agent 无状态、可热替换，对比才有意义 | Invariant 6：Agent is Stateless | 竞品 Agent 携带状态和记忆，替换成本高 |

LangGraph/CrewAI 要做这个飞轮，需要先把自己的架构基因改了——从"名称绑定"改成"Capability 分发"，从"Agent 有状态"改成"Agent 无状态"。**这不是加功能，是换骨架。**

---

#### 历史类比

| 产品 | 初期壁垒 | 长期壁垒 |
|------|---------|---------|
| Google 搜索 | PageRank 算法 | 越多搜索 → 越准 → 越多搜索（点击数据飞轮） |
| AWS | 虚拟化技术 | 越多负载 → 越好利用率 → 越低成本 → 越多负载（规模飞轮） |
| Uber | 叫车 App | 越多司机 → 越短等待 → 越多乘客 → 越多司机（双边网络飞轮） |
| **Zelos** | **搜索调度算法（P0-P1） + 决策可解释性（P3）** | **越多 Agent → 越准的调度 → 越高成功率 → 越多 Agent（校准数据飞轮）** |

算法是第一阶段的门票，飞轮才是长期的护城河。

---

#### 飞轮冷启动策略

飞轮最大的问题：**第一圈怎么转？** Agent 少 → 校准数据少 → 调度不够准 → 成功率不够高 → 没人来。

**冷启动方案：**

**阶段 1：人工策展（0 → 10 Agent）**

Zelos 自己提供一批高质量的参考 Agent，手动标注能力边界和初始校准值：

```python
# zelos/agents/curated/
# 预置的 Agent 池，每个 Agent 附带初始 Profile

curated_agents = [
    AgentProfile(
        id="claude-code",
        capability="code-generation.python",
        initial_calibration={
            "bug_fix": 0.85,       # 在这些任务类型上手动标注预期校准度
            "feature_impl": 0.80,
            "refactoring": 0.75,
        },
        failure_modes=["complex_async", "c_extensions"],  # 已知短板
    ),
    AgentProfile(
        id="gpt-engineer",
        capability="code-generation.python",
        initial_calibration={"bug_fix": 0.78, "feature_impl": 0.82, "refactoring": 0.72},
    ),
    # ... 至少 10 个，覆盖 3-5 个 Capability
]
```

**阶段 2：种子用户（10 → 100 Agent + 1000 案例）**

- 开源社区贡献 Agent（类似 VS Code 插件市场）
- Agent 注册即可跑，不需要审批
- 每完成一个 Task，自动更新该 Agent 在该任务类型上的校准值
- 1000 个案例后，Scheduler 的校准数据有统计意义

**阶段 3：飞轮自转（100+ Agent + 10000+ 案例）**

- Capability Registry 成为 Agent 发现入口
- Agent 开发者主动注册（"注册到 Zelos 就有任务可接"）
- Scheduler 的校准精度成为竞争壁垒

---

#### 怎么衡量飞轮是否在转

| 指标 | 冷启动时 | 飞轮转起来后 |
|------|---------|-------------|
| 每个 Capability 的平均 Agent 数量 | < 2 | > 5 |
| Scheduler 选择中"非默认 Agent"的比例 | < 10% | > 40%（说明有真正的选择空间） |
| 调度决策的"后悔值"（事后看选另一个会不会更好） | 高（不知道） | 持续下降 |
| Agent 校准数据的"置信区间宽度" | ±0.3（很宽，样本不够） | ±0.05（窄，样本够了） |
| 新 Agent 注册后获得首次调度的等待时间 | 不确定 | < 1 天（有探索机制推送新 Agent） |

---

## 4. 最小核心闭环定义

这是 P0 要跑通的东西。比现在的 Zelos 小很多，但它是整个系统的核心假设验证。

### 4.1 输入

```
一个自然语言 Goal
例："修复 django 项目中的 issue #1234，写代码 + 测试"
```

### 4.2 核心组件（只用这些）

| 组件 | 职责 | 当前状态 |
|------|------|---------|
| Goal Parser | 自然语言 → 内部 Goal 表示 | 需新建（或复用 Planner 的部分） |
| Adaptive Loop | 每一步决定下一步做什么 | 需从一次性 Planner 改为循环式 |
| Scheduler | 按 Capability 选 Agent | 已有，需简化 |
| Agent Runtime | 调用 Agent | 已有 |
| Incremental Verifier | 每步产出后评估 | 需从后置 Verifier Chain 改为增量式 |
| Result Builder | 聚合最终产出 | 需新建 |

### 4.3 分阶段开启策略

**所有代码保留，不删除。** 通过配置控制每阶段加载哪些组件：

```python
# zelos.yaml
runtime:
  phases:
    event_sourcing: false       # 阶段 B 开启
    execution_trace: false      # 阶段 B 开启
    evidence_collection: false  # 阶段 C 开启
    confidence_scoring: false   # 阶段 C 开启
    policy_gate: false          # 阶段 D 开启
    cp_governance: false        # 阶段 D 开启
    car: false                  # 阶段 D 开启
    diagnosis_engine: false     # 阶段 D 开启
    credential_management: false # 阶段 E 开启
    failure_classifier: false   # 阶段 E 开启
    repair_ranker: false        # 阶段 E 开启
```

**当前阶段（A）只开启：Planner / Scheduler / Executor / 基础 Verifier。** 其余组件代码仍在，单元测试仍在 CI 中运行，但不参与端到端验证——等核心跑稳后逐层开启。

### 4.4 成功标准

```
能端到端完成一个真实的 bug fix：
  issue 输入 → 理解 → 搜索 → 修复 → 验证 → PR 输出
```

不用 6/17 的 SWE-bench 通过率。**先跑通 1 个完整的案例，再谈 scale。**

---

## 5. 讨论要点

以下问题需要团队讨论决定：

### 5.1 Planner：一次性 Plan vs Adaptive Loop？（最关键的技术决策）

这是架构上最大的变化。一次性 Plan 是瀑布，Adaptive Loop 是持续推理。前者有明确的工程边界（好实现、好测试），后者在效果上更优但更难工程化。

**但两者不是二选一，中间有过渡方案：**

```
一次性 Plan（当前）
  Planner 提前规划全部 Task → Scheduler 按 DAG 顺序执行
  ✅ 好测试、好调试、确定性
  ❌ 不能中途调整、"过度规划"（后面的 Task 依赖前面的产出，提前规划是猜的）

─────────────────────────────────────────────────────────────

滑动窗口 Plan（MPC 模式，推荐 MVP 用这个）
  每执行 K 步，用最新的结果重新规划未来 N 步
  ✅ 兼顾可测试性（Plan 函数本身可独立测试）
  ✅ 有适应性（不会基于过时的假设继续执行）
  ⚠️ 需要定义 K 和 N，需要"重规划触发条件"

─────────────────────────────────────────────────────────────

纯 Adaptive Loop（理想态，P1 目标）
  每执行 1 步，重新评估全局状态，决定下一步
  ❌ 最难测试（决策是全局状态函数，状态空间不可穷举）
  ❌ 最容易"漂移"（没有 Plan 约束，可能偏离原始 Goal）
  ✅ 最大灵活性
```

**建议：MVP 做 MPC 模式，不是纯 Adaptive Loop。**

MPC（Model Predictive Control）是控制论里成熟的模式：
1. 基于当前状态，规划未来 N 步
2. 只执行第 1 步
3. 收集第 1 步的产出
4. 基于新状态，重新规划未来 N 步
5. 重复

**为什么 MPC 模式更工程化（可测试）：**

| 测试维度 | 怎么测 |
|---------|--------|
| Plan 函数本身 | 给固定状态（前置 Task 输出），验证产出的 Plan 是否合理。**确定性函数，可直接写单测。** |
| 重规划触发逻辑 | 给定"Task 失败 / 置信度不足 / 产出 schema 不匹配"的状态变化，验证触发了重规划。**条件有限，可枚举。** |
| 端到端不漂移 | 给定一个 Goal，验证最终产出符合 Goal 约束。**不需要验证中间每一步，只验证最终结果。** |
| 收敛性 | 给定有限的问题空间，验证 Loop 在有限步数内终止。**不会无限重规划。** |

纯 Adaptive Loop 每一步都是 `next_action = f(global_state)`，如果 `global_state` 包含所有历史 Event、所有 Artifact、所有 Agent 状态——输入空间不可穷举，你没法列举"所有可能的状态"来验证每一步决策的正确性。MPC 把问题拆开了：Plan 函数是确定性的（可测试），Loop 只是在"执行-重规划"之间循环（可验证收敛性）。

**重规划算法分三个复杂度级别：**

| Level | 算法 | 触发条件 | MVP 用？ |
|-------|------|---------|---------|
| Level 1：Rule-based | 硬编码规则触发重规划 | Task 失败 / 置信度 < 阈值 / 产出 schema 不匹配 | ✅ MVP |
| Level 2：Confidence-weighted | Verifier 产出置信度，按置信度区间决定：>0.9 继续 / 0.5-0.9 标记 / <0.5 重规划 | 同上，但阈值从 Verifier 来，不是硬编码 | P0.5 |
| Level 3：Information Gain | 每步选 argmax E[info_gain / cost]，更新 Belief State P(h｜evidence) | 不触发"重规划"，而是持续选择最优 action | P1 |

**MVP 只用 Level 1。** Level 3 是 P1 的事情，而且 Level 3 依赖 Level 1 作为 fallback——当 Belief State 模型不够好时，退回到规则决策。

---

### 5.2 DAG 要不要改为 Belief State 搜索模型？

这决定了 Zelos 是"Workflow Runtime"还是"Reasoning Runtime"。前者竞争激烈（Temporal + AI、LangGraph），后者目前无人做。

**建议：P0 不改，P1 改造。** MVP 先用 MPC + DAG 证明核心闭环，P1 再引入 Hypothesis/Evidence/Belief State 的搜索模型。DAG 作为底层执行机制仍然存在，只是顶层从"执行 Plan"变成"引导搜索"。

---

### 5.3 验证策略：功能全保留，按依赖顺序逐层开启

基本确认采用分阶段验证。需要具体决定的是：

- **阶段划分的粒度**：文档建议了 A-B-C-D-E 五个阶段，是否需要合并或拆分？
- **每阶段的验证标准**：什么算"通过"？多少个端到端案例？什么指标？
- **Feature flag 的实现方式**：配置文件 yaml？环境变量？编译时 feature flag？

---

### 5.4 MVP 用什么场景验证？

SWE-bench？一个自己的 demo？一个开源项目的真实 issue？

**建议：先跑通一个自己的可控场景，再碰 SWE-bench。** 自己的场景可以完全控制 Agent 行为、输入输出、验证条件。SWE-bench 引入了太多外部变量（Agent 质量、工具链稳定性、镜像环境），会在核心闭环还没验证之前就把问题淹没在噪音里。

**推荐 MVP 场景：** 一个简化的 bug fix 流程，3-4 步：
1. Researcher Agent 分析 issue → 产出理解
2. Coder Agent 写 fix → 产出 patch
3. Reviewer Agent 审查 patch → 产出 review（过 or 不过）
4. 如果不过 → 回到 Coder 重做（最多 3 轮）
5. Tester Agent 运行测试 → 产出 pass/fail

这个场景足够验证核心闭环（Plan → Execute → Verify → Replan），又不会像完整 SWE-bench 那样复杂。

---

### 5.5 `zelos run` 一行命令的体验要不要在 Mvp 就做？

还是先暴露内部 API，等核心稳定了再封装？

**建议：MVP 做两层的 API：**

```python
# Layer 1: 一行命令（给应用开发者）
result = zelos.run("fix this bug in repo X")

# Layer 2: 可编程 API（给框架开发者，内部调试用）
goal = Goal(intent="fix bug", context={...})
runtime = ZelosRuntime(config={...})
runtime.submit(goal)
runtime.watch(callback=my_observer)
```

Layer 1 是目标体验，Layer 2 是 MVP 开发期间我们调试用的。两个同时做，不冲突。Layer 1 一开始可能是 Layer 2 的薄封装，但随着成熟度提升，Layer 1 会逐步内置更多默认行为。

---

## 6. 接下来最应该做的事

基于以上所有分析，**最应该做的事只有一件：用最薄的组件，跑通一个端到端的案例。**

### 为什么是这一件

12 个 Phase 给了我们架构自信，但没有给实证信号。我们现在所有的讨论——MPC、搜索树、Agent Profile——都是基于"我们认为问题在哪"。只有端到端跑一遍，才能把"我们认为"变成"我们看到"。

而且跑通不是目的，**定位真正的阻塞点**才是目的。第一次跑大概率不会完全成功——但失败本身就是产出：它告诉你核心回路里到底哪个环节是瓶颈。

### 具体步骤

**第一步：选一个案例，只一个**

不碰 SWE-bench 全量。从一个 SWE-bench 实例里摘一个，或者自己构造一个更简单的。要求：
- 需要 2-3 个 Agent 协作（不要太简单，一个 Agent 搞定的测不出调度）
- 输入和预期输出明确（方便判断"算不算成功"）
- 能在本地环境稳定复现（不要依赖外部服务）

**第二步：组件只加载 Phase A**

```
Planner + Scheduler + Executor + 基础 Verifier
```

其余 8 个 Phase 的组件全部 feature flag 关闭。不是删代码，是关开关。

**第三步：跑，记录每一步**

不管结果成功还是失败。重点记录：
- Planner 产出了什么 Plan？
- Scheduler 选了谁？为什么？
- Agent 返回了什么？
- Verifier 判断了什么？
- 下一步怎么决定的？

**第四步：从结果倒推问题**

| 如果... | 说明核心问题在... |
|---------|-----------------|
| Plan 本身不合理 | Planner 需要改（MPC 也救不了错误的单次规划） |
| Plan 合理但执行结果差 | Agent 能力不够，或 Capability 匹配维度不够 |
| 执行 OK 但验证判断错误 | Verifier 的判据有问题 |
| 每一步都 OK 但整体没收敛 | 缺少全局协调——这就是 MPC 要解决的 |
| 全都 OK 了 | 加第二个案例，或开启下一层组件 |

### 这件事做完的标志

不是"跑通了"，而是**有了一份实证记录**，能回答：

> "在关闭所有外围组件的前提下，核心调度回路在哪个环节卡住了？"

这份记录就是我们接下来所有工作的基础。P0 的 MPC 改造、P1 的搜索模型、P2 的 API 封装——都应该基于真实阻塞点来做，而不是基于现在的推测。

---

## 7. SWE-bench 与 Zelos 核心能力验证

### Zelos 本身不是 Agent，也永远不会造 Agent

Zelos 的 Invariant 13 明确规定 Runtime 不知道 LLM 的存在。这意味着**所有 Agent 都来自外部**——SWE-bench 排行榜上的 live-SWE-agent、Sonar Foundation Agent、Claude Code 都可以包装一层适配器注册进 Zelos。

**关键思路：Agent 质量是常量，Runtime 质量是变量。** 用已经验证的顶尖 Agent，单独测 Runtime 的编排贡献。

---

### 一个 SWE-bench Task 能驱动 Zelos 全部核心路径

如果把一个 SWE-bench Task 按 Zelos 的架构拆开（而不是一个 Agent 从头做到尾），7 个步骤刚好压到 6 条核心路径：

```
SWE-bench Task 生命周期              验证的 Zelos 核心能力
─────────────────────               ─────────────────────

Step 1: Goal 提交                      Planner
  "修复 django issue #1234"            Goal → Plan [Search, Fix, Review, Test]
                                       分解是否合理？粒度是否合适？

Step 2: 定位代码                       Scheduler
  Search Agent 执行                    Capability "code-search"
                                       在 [Sonar定位, live-SWE定位, grep-agent] 中选最佳
                                       验证：选择依据是否有数据支撑？

Step 3: 生成 patch                     Scheduler（多 Agent 选择空间）
  Fix Agent 执行                       同一 Capability "code-generation" 有 2+ Agent 可选
                                       验证：Scheduler 是否选了对的那个？

Step 4: 审查 patch                     MPC 增量验证
  Reviewer Agent 执行                  Reviewer 产出置信度 0.7 → 低于阈值
                                       Runtime 决定：重做 / 切换 Agent / 继续
                                       验证：决策是否合理？

Step 5: 跑测试 + 诊断                  Diagnosis Engine + Failure Classifier
  Runtime 接管                         测试失败 → 结构化诊断
                                       → "AssertionError at line 42，期望 X 实际 Y"
                                       → Failure Classifier: "repair，值得修"
                                       验证：诊断准确率 + 分类准确率

Step 6: 重规划                         MPC Replan
  Runtime 基于诊断决定下一步：            触发规则：
    "定向修复这个断言"                      → 回到 Step 3，用诊断结论定向修复
    "全量爆炸，切方案"                      → 回到 Step 2，换 Search Agent 重新定位
    "当前方向好，继续加深"                  → 继续当前方向
                                       验证：回溯 + 动态路径选择是否正确

Step 7: 产出 patch + Evidence 链       Event Bus 审计
                                        完整 causation chain：
                                        "为什么选了 Agent B 而不是 Agent A？"
                                        "为什么在 Step 6 选择了回溯而不是重试？"
                                        每一个决策都有可追溯的理由
```

---

### 能验证什么、不能验证什么

| 核心能力 | SWE-bench 能验证吗 | 程度 |
|---------|-------------------|------|
| Planner（Goal → Task 分解） | ✅ | 拆 4-5 个子任务，够验证分解逻辑 |
| Scheduler（Capability 匹配 + 多 Agent 选择） | ✅ | 2-3 个 Capability，每个有 2+ Agent 候选 |
| MPC 增量验证（每步产出后评估） | ✅ | Reviewer 置信度 → 决定下一步 |
| MPC Replan（回溯 + 动态路径选择） | ✅ | 测试失败 → 诊断 → 切换方案 |
| Diagnosis Engine（Runtime 理解执行反馈） | ✅ | pytest 输出的结构化诊断 |
| Failure Classifier（工程决策） | ✅ | 修 / 重试 / 放弃 |
| Event Bus 审计链 | ✅ | 7 步完整 causation chain |
| Agent 热替换 / Fallback | ✅ | Fix Agent 失败 → 换同 Capability 的另一个 |
| Belief State 多假设探索（P1） | ⚠️ | 可设计成"并行 2 个 Fix Agent 用不同方案"，但不是必须 |
| Policy Gate（P0 阶段 D） | ❌ | SWE-bench 没有治理需求 |
| 大规模调度（10+ Agent 并发） | ❌ | SWE-bench 单题不需要 |

**结论：SWE-bench 恰好覆盖了 P0 阶段 A（核心调度闭环）需要验证的全部能力。** 不能验证的恰好是 P0 阶段 D、E 才需要的——这意味着 SWE-bench 作为 P0 阶段 A 的验证场景，和 Zelos 的迭代路线是完美对齐的。

---

### 下一阶段的三件事

基于以上分析，v1.2 测评结束后应做三件事，只做三件事：

**第一件：v1.2 测评实证复盘（1 周）**

逐题回答：
- Diagnosis Engine 的诊断结论和真人判断一致吗？
- Failure Classifier 的决策（修/重试/放弃）对吗？
- 失败案例里，是 Agent 写的 patch 不行，还是诊断/分类/修复流程有问题？
- 有没有 Runtime 的决策让情况变差（如放弃了本可修复的 patch）？

产出：一份数据，不是感想。**直接决定 P0 做什么、不做多少。**

**第二件：跑通最小核心闭环（2-3 周）**

P0 阶段 A。Agent 用 SWE-bench 排行榜已验证的那几个（live-SWE-agent / Sonar / Claude Code），单独测 Runtime：

```
Agent（常量）               Runtime（变量，我们要测的）
─────────────────────       ─────────────────────
live-SWE-agent 定位能力      Planner 拆解是否合理
Claude Code 生成能力         Scheduler Agent 匹配是否准确
Reviewer Agent 审查能力      MPC Verifier 增量验证是否有效
                             MPC Replan 重规划决策是否正确
                             Event Bus 审计链是否完整
```

**第三件：组合拳 PoC（2 周）**

挑 5 个 SWE-bench 题，每个题 3 种方式跑：

| 分组 | 做法 | 期望 |
|------|------|------|
| 基线 | live-SWE-agent 原生单打 | 排行榜 baseline |
| +Runtime | 包一层 adapter，加 Zelos Diagnosis + Classifier + Repair | 边际改善 |
| +编排 | 拆成定位/生成/审查三步，不同 Agent，Runtime 做决策 | **期望代际提升** |

如果第三组比第一组好——哪怕只好了 2 题——就证明了核心假设："Runtime 编排多 Agent 比单 Agent 好。"

这三件事加起来 5-6 周，产出三份数据。比继续加功能或继续盲测 SWE-bench 都有说服力——拿着第三份数据去跟投资人说，"我们没有自己造 Agent，我们把最好的 Agent 编排起来，组合拳超过了任何一个单体 Agent。"

---

### 回头看 v1.2 的教训

如果这个思路早想通了，v1.2 可能就不该是"加 Diagnosis Engine"，而是"先把一个 SWE-bench Task 拆开，验证核心闭环能不能端到端跑通"。

Diagnosis Engine 是对的——它是核心闭环上的一个组件，作为"Runtime 替代 LLM 做工程决策"的关键模块。但问题在于，它是作为独立功能开发的，没有嵌入到核心闭环中去验证。**组件先于闭环，验证顺序又反了。**

这个教训恰好印证了文档开头的问题 1：不是功能不对，是验证顺序反了。

> 📄 **此文档位置：** `docs/zelos-architecture-critique-and-evolution.md`
