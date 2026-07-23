# Temporal 可靠性模型分析 & Zelos 优化建议

> Temporal 是目前分布式工作流引擎的标杆。它的可靠性模型——Retry、Recovery、Event History、Deterministic Execution——是 Zelos 最值得学习的四项能力。
> 本文分析 Temporal 怎么做、Zelos 当前做了什么、差距在哪、怎么优化。

---

## 一、Retry（重试策略）

### Temporal 怎么做

Temporal 的重试不是一个简单的 `for` 循环，而是一套完整的策略体系：

```
RetryPolicy {
  InitialInterval:    1s       ← 第一次重试前的等待
  BackoffCoefficient: 2.0      ← 指数退避系数
  MaximumInterval:    100s     ← 最长退避上限
  MaximumAttempts:    10       ← 最多尝试次数（0 = 无限）
  NonRetryableErrors: [...]    ← 不可重试的错误（直接失败）
}
```

关键细节：
1. **Heartbeat Timeout** — 长时间执行的 Activity 必须定期心跳。如果超时无心跳 → 视为失败，触发重试。
2. **Retry State** — 每次重试记录 `attempt`, `last_failure`, `next_retry_time`，可以在 Dashboard 看到每笔重试的原因和时间。
3. **Different retry policies for different activities** — 一个 Workflow 内的不同 Activity 可以有不同重试策略。

### Zelos 当前做了什么

`zelos/scheduler.py` 的 `evaluate_retry()`:
```python
task.attempt += 1
if task.attempt <= task.max_retries:
    backoff_ms = task.backoff_base_ms * (2 ** (task.attempt - 1)) + random.randint(0, 500)
    task.status = TaskStatus.READY
    return f"retry_in_{backoff_ms}ms"
```

✅ 已有：指数退避 + jitter + max_retries
❌ 缺失：Heartbeat Timeout、NonRetryableErrors、不同 Task 不同策略、Retry 历史追踪

### 优化建议

```python
# 1. 添加 Heartbeat Timeout 检测
# zelos/execution_engine.py 已有 heartbeat 追踪，增加超时判定：
class InFlightTask:
    heartbeat_at: float = 0.0       # NEW
    heartbeat_timeout_ms: int = 30000

def check_heartbeat_timeouts(self) -> list[str]:
    """返回心跳超时的 task_id 列表 → Scheduler 触发重试"""
    now = time.time()
    timed_out = []
    for tid, t in self._in_flight.items():
        if t.heartbeat_at > 0 and (now - t.heartbeat_at) * 1000 > t.heartbeat_timeout_ms:
            timed_out.append(tid)
    return timed_out

# 2. 添加 NonRetryableError 类型
class TaskStatus:
    FATAL_FAILED = "fatal_failed"  # NEW: 不可重试的错误

# Task 增加字段：
#   non_retryable_errors: list[str] = []   # 如 ["ValidationError", "AuthError"]

# 3. Retry 历史追踪（写入 EventBus）
def _record_retry(self, task: Task, error: dict):
    self._event_bus.publish(Event(
        event_id=str(uuid.uuid4()),
        event_type="task.retry_scheduled",
        source="scheduler",
        timestamp=time.time(),
        correlation_id=task.plan_id,
        payload={
            "task_id": task.task_id,
            "attempt": task.attempt,
            "backoff_ms": self._compute_backoff(task),
            "previous_error": error,
        }
    ))
```

---

## 二、Recovery（崩溃恢复）

### Temporal 怎么做

Temporal 的恢复机制是它的核心能力：

1. **Workflow State 持久化** — 每次 Workflow 执行到一个 decision point（await/sleep/activity），状态自动序列化到持久存储。
2. **Replay from Event History** — Worker 重启后，Server 把完整的 Event History 发回 Worker，Worker 从第 0 个事件开始重放到最后一个，恢复到崩溃前的状态。
3. **Exactly-Once 语义** — 因为状态是从事件重建的，同一个 Activity 不会被重复执行。

### Zelos 当前做了什么

`zelos/event_bus.py` 的 `PersistentEventStore.recover()`:
```python
def recover(self) -> int:
    raw = self._backend.read(self._stream, 0, 100000)
    for r in raw:
        event = Event(...)
        self._memory.append(event)
    return len(raw)
```

✅ 已有：事件持久化 + 内存恢复
❌ 缺失：**Goal 状态无法从事件重建**——这是最大的差距。Zelos 能恢复事件列表，但无法从事件重建 Goal 的运行状态（哪些 Task 完成了、哪些正在执行、当前进度）。

### 优化建议

```python
# 核心：添加 GoalState 的序列化/反序列化 + 事件重建

# Step 1: Task 添加 to_dict() / from_dict()
class Task:
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id, "plan_id": self.plan_id,
            "description": self.description, "status": self.status.value,
            "required_capability": self.required_capability,
            "dependencies": self.dependencies, "attempt": self.attempt,
            "assigned_agent_id": self.assigned_agent_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        t = cls(task_id=d["task_id"], plan_id=d["plan_id"],
                description=d["description"],
                required_capability=d["required_capability"])
        t.status = TaskStatus(d["status"])
        t.dependencies = d.get("dependencies", [])
        t.attempt = d.get("attempt", 0)
        t.assigned_agent_id = d.get("assigned_agent_id")
        return t

# Step 2: GoalState 快照（定期或在关键状态变更时）
class GoalState:
    goal_id: str
    status: str
    tasks: dict[str, Task]
    event_position: int  # EventBus 中的位置，对应最后一个已处理事件

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "GoalState": ...

# Step 3: Runtime 恢复
def restore_from_storage(self):
    """启动时从存储恢复所有未完成的 Goal"""
    for goal_id in self._storage.list_goals():
        saved = self._storage.get_state(f"goal-{goal_id}")
        if saved and saved["status"] not in ("completed", "failed", "cancelled"):
            state = GoalState.from_dict(saved)
            # 重放从快照位置之后的事件
            events = self._event_bus.store.replay_from(state.event_position)
            for e in events:
                self._apply_event(e, state)  # 事件溯源：逐事件重建状态
            self._restore_goal(state)  # 恢复到 Runtime 中继续执行
```

---

## 三、Event History（事件历史）

### Temporal 怎么做

Temporal 的核心数据模型是 **Event History** ——每个 Workflow Execution 有一条不可变的事件链：

```
WorkflowExecutionStarted  →  ActivityTaskScheduled  →  ActivityTaskStarted
→  ActivityTaskCompleted  →  TimerStarted  →  TimerFired  →  WorkflowExecutionCompleted
```

关键特性：
1. **事件是单一事实来源** — Workflow 的状态不从数据库读，而是从事件重放计算。
2. **Causally ordered** — 每个事件有 `event_id`（单调递增）+ `previous_event_id`，形成因果链。
3. **Query 不写入历史** — 查询操作（相当于 HTTP GET）不产生事件，只读当前状态。

### Zelos 当前做了什么

`zelos/event_bus.py`:
```python
class Event:
    event_id: str        # UUID
    event_type: str      # "task.created"
    correlation_id: str  # 关联到 Goal
    causation_id: str    # 关联到上一个事件 ← 已经有这个！
    timestamp: float
    payload: dict
```

✅ 已有：因果链（`causation_id`）、correlation_id 分组、Immutable Event
✅ 已有的 Event Taxonomy：runtime.*, goal.*, plan.*, task.*, agent.*, artifact.*, verification.*, plugin.*
❌ 缺失：
  - **事件不是状态唯一来源** — Goal 状态存在 `self._goals` dict 中，事件只是"日志"，不参与状态计算。
  - **没有 `event_id` 单调递增** — 用的是 UUID，无法做 `replay_from(event_id)`。
  - **Query 操作（get_goal_status）不经过事件系统** — 直接读内存 dict。

### 优化建议

```python
# 1. 事件改为单调递增 ID
class InMemoryEventStore:
    def append(self, event: Event) -> None:
        event.sequence_id = self._next_id  # NEW: 单调递增
        self._next_id += 1
        ...

# 2. 事件溯源（Event Sourcing）—— Goal 状态从事件计算
def _apply_event(self, event: Event, state: GoalState) -> None:
    """纯函数：根据事件类型更新 GoalState，无副作用"""
    handlers = {
        "goal.submitted": lambda s, e: setattr(s, "status", "accepted"),
        "plan.created": lambda s, e: setattr(s, "plan_id", e.payload["plan_id"]),
        "task.created": lambda s, e: s.tasks.__setitem__(e.payload["task_id"], Task.from_dict(e.payload)),
        "task.completed": lambda s, e: s.tasks[e.payload["task_id"]].__setattr__("status", TaskStatus.COMPLETED),
        "task.failed": lambda s, e: s.tasks[e.payload["task_id"]].__setattr__("status", TaskStatus.FAILED),
        "goal.completed": lambda s, e: setattr(s, "status", "completed"),
    }
    handler = handlers.get(event.event_type)
    if handler:
        handler(state, event)

# 3. 重放恢复
def restore_goal(self, goal_id: str) -> GoalState:
    state = GoalState(goal_id=goal_id, tasks={})
    events = self._event_bus.replay_correlation(goal_id)
    for e in events:
        self._apply_event(e, state)
    return state
```

---

## 四、Deterministic Execution（确定性执行）

### Temporal 怎么做

Temporal 要求 Workflow 代码必须是**确定性的**：

- 禁止 `random()`、`time.now()`、`uuid()`、HTTP 调用、文件 IO 在工作流代码中直接使用
- 所有非确定性操作必须通过 Activity（副作用隔离）
- 因为要支持 Replay：从事件历史重放时，Workflow 代码必须产生完全相同的决策序列

### Zelos 的做法

Zelos **刻意不需要确定性**——这是设计选择，不是缺陷。

原因：
- Agent 是外部进程，不是 Zelos 内的代码。Agent 的行为天然是非确定性的。
- Zelos 不执行 Agent——它调度 Agent。Temporal 的 Workflow 是 Zeit 自己执行的确定性代码。
- Zelos 的三权分立（Planner ≠ Scheduler ≠ Verifier）已经内置了"不可信 Agent"的防护。

✅ Zelos 的做法是合理的。不需要像 Temporal 一样限制确定性。

但 Temporal 有一个值得学的思想：**副作用隔离**。

### 优化建议

```python
# 将非确定性操作显式隔离到 SideEffect 接口
class SideEffect(ABC):
    """Temporal 风格：所有外部调用通过 SideEffect，可 mock 用于测试"""
    @abstractmethod
    def execute(self) -> Any: ...

class AgentCall(SideEffect):
    """Agent 调用是一个 SideEffect——结果可能不同，但调用本身是确定性的"""
    def __init__(self, agent_id: str, task: Task):
        self.agent_id = agent_id
        self.task = task
    def execute(self) -> dict:
        return self._agent.execute(self.task)

# 好处：测试时可以注入 Mock SideEffect，完整重放 Goal 执行
class TestMode:
    def __init__(self):
        self._side_effect_results: dict[str, Any] = {}

    def record(self, key: str, result: Any):
        self._side_effect_results[key] = result

    def replay(self, key: str) -> Any:
        return self._side_effect_results[key]  # 确定性重放
```

---

## 五、优先级排序

| 优先级 | 优化项 | 影响 | 工作量 |
|:--:|------|------|:--:|
| P0 | Goal 状态序列化 + 事件溯源恢复 | 🔴 当前重启丢 Goal 状态 | 3-5 天 |
| P1 | Heartbeat Timeout + NonRetryableErrors | 🟡 长时间卡住的 Task 无法自动恢复 | 1-2 天 |
| P2 | 事件单调递增 ID + Query 不写入历史 | 🟡 无法按顺序精确重放 | 1 天 |
| P3 | SideEffect 接口隔离 + TestMode | 🟢 测试便利性提升 | 2 天 |

---

## 六、总结

> Zelos 和 Temporal 的核心差异不在技术，在**设计目标**：
>
> - **Temporal 管理确定性工作流** → 要求 Replay 一致性，所以需要确定性执行 + 事件是唯一状态源。
> - **Zelos 管理非确定性 Agent** → Agent 天然不可预测，所以不需要确定性执行，但可以从 Temporal 学到**事件溯源**和**崩溃恢复**。
>
> **最大的 gap 不是功能缺失，是哲学不一致**：Zelos 目前把 EventBus 当"审计日志"，Temporal 把它当"状态计算引擎"。  
> **优化方向**：不改变 Zelos 的非确定性本质，但让它的 Goal 状态变成从事件可重建的。这样重启后可以完整恢复，而不是在内存 dict 里丢了一半的进度。
