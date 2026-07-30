# Zelos Runtime Benchmark Plan

> 证明 Runtime 的价值：和裸 Python、LangGraph、CrewAI 比，Zelos 能不能让多 Agent 执行更快、更稳、更可靠。

---

## 一、测什么（不测什么）

**测的：Runtime 的核心能力**

| 能力 | 为什么重要 |
|------|-----------|
| **调度吞吐** | 100 个 Task 来了，多快能派出去？ |
| **故障恢复** | Agent 挂了，Runtime 能不能自动重试、切到备用 Agent？ |
| **伸缩性** | Agent 数量从 10 → 100 → 500，性能怎么变？ |
| **资源开销** | 每多一个 Agent，Runtime 多吃多少 CPU/内存？ |
| **冷启动** | Agent 注册到能接 Task，要多久？ |

**不测的：CP/治理层的能力**

Evidence、Confidence、PolicyGate 是 v0.9+ 的治理能力，不是 Runtime 的核心价值。本次 benchmark 不涉及。

---

## 二、对比对象

| 方案 | 是什么 | 为什么比 |
|------|--------|---------|
| **裸 Python**（threading.Queue + 手动管理） | 没有 Runtime 的基线 | 证明 Runtime 有存在的价值 |
| **LangGraph** | Agent 工作流框架 | 目前最火的 Agent 编排工具 |
| **CrewAI** | 多 Agent 协作框架 | 另一个热门选择 |
| **Zelos** | 我们的 Runtime | 实验组 |

---

## 三、实验场景

### 场景 1：吞吐压力测试

```
100 个独立 Task，每个 100ms work，10 个 Agent 可调度
```

**测什么**：从第一个 Task 提交到最后一个 Task 完成的总耗时。

| 方案 | 预期 |
|------|------|
| 裸 Python | 最快（无框架开销），但无故障恢复 |
| LangGraph | 中等（有编排开销） |
| CrewAI | 中等 |
| **Zelos** | 接近裸 Python（核心零依赖），显著优于框架 |

### 场景 2：故障恢复测试

```
20 个 Task，其中第 5、10、15 个 Task 的目标 Agent 在执行中途崩溃。
```

**测什么**：Runtime 检测到 Agent 失联（心跳超时）→ 标记 Task FAILED → 自动重试或切到备用 Agent → 最终成功率。

| 方案 | 预期 |
|------|------|
| 裸 Python | **失败**，需要人手动介入 |
| LangGraph | 有限支持（需手动配置 retry） |
| CrewAI | 有限支持 |
| **Zelos** | **自动恢复**，心跳检测 + 调度器重试 + fallback 机制 |

### 场景 3：伸缩性测试

```
Agent 数量：10 → 50 → 100 → 500
每个 Agent 注册 3 个 Capability
Capability 查询：随机查找匹配的 Capability
```

**测什么**：Capability 匹配延迟、Scheduler 评分延迟随 Agent 数量的增长曲线。

| 方案 | 预期 |
|------|------|
| Zelos（已有 benchmark） | Capability 匹配 37M queries/s，500 Agent 下 <1ms |

### 场景 4：资源开销测试

```
100 个 Agent 注册后，Runtime 的内存占用和 CPU 消耗。
对比：裸 Python 管理同等数量的 worker thread。
```

**测什么**：Runtime 本身的开销占多少。

---

## 四、核心指标

| 指标 | 定义 | 目标 |
|------|------|------|
| **调度延迟** | Task READY → dispatch 的时间 | <10ms (p99) |
| **吞吐量** | Tasks/秒（100 Task 并发） | >500 tasks/s |
| **故障恢复率** | Agent 崩溃后 Task 最终成功比例 | >99% |
| **恢复时间** | Agent 崩溃 → Task 重新 dispatch | <3s（心跳间隔 × 3） |
| **内存开销** | 500 Agent 注册后 Runtime 内存 | <200MB |
| **冷启动** | Agent 注册 → 可接 Task | <1s |

---

## 五、实验环境

| 项目 | 规格 |
|------|------|
| CPU | 8 核 |
| 内存 | 16 GB |
| OS | macOS 14 / Ubuntu 22.04 |
| Python | 3.12 |
| Zelos | v1.1.0 |

---

## 六、实施

### Phase 1：已有 Benchmark（已完成）

```
test_benchmark.py (5 tests)
  EventBus: 890,000 events/s
  TaskGraph: 2,250,000 transitions/s
  Capability: 37,500,000 queries/s
  Scheduler: 570,000 scores/s
  Ring Buffer: 200 events → cap 100, correct
```

### Phase 2：对比 Benchmark（需实施）

```python
# benchmark_runtime.py — 骨架
import time, threading, queue
from zelos.runtime import ZelosRuntime

def bench_throughput():
    """100 tasks, 10 agents, measure total time."""
    rt = ZelosRuntime()
    for i in range(10):
        rt.add_agent(f"agent-{i}", f"test:Agent", [cap("code")])
    rt.start()

    t0 = time.perf_counter()
    goal = rt.submit_goal("Throughput test")
    rt.wait_for_goal(goal["goal_id"], timeout_seconds=60)
    elapsed = time.perf_counter() - t0

    rt.shutdown()
    return elapsed

def bench_fault_recovery():
    """20 tasks, kill agent at task 5/10/15, measure recovery."""
    ...

def bench_scaling():
    """10 → 500 agents, measure capability matching latency."""
    ...
```

### Phase 3：出报告

输出：
- 一张对比表（Zelos vs LangGraph vs CrewAI vs 裸 Python）
- 一篇博客：**"We benchmarked 4 ways to run 100 agents. Here's what happened."**
- README 更新：核心 benchmark 数据放首页

---

## 七、对比表模板

| 指标 | 裸 Python | LangGraph | CrewAI | **Zelos** |
|------|----------|-----------|--------|----------|
| 100 Task 耗时 | ?ms | ?ms | ?ms | ?ms |
| 故障自动恢复 | ❌ | 手动配置 | 手动配置 | ✅ 自动 |
| Capability 匹配延迟 | N/A | 无此能力 | 无此能力 | <1ms |
| 内存开销 (500 Agent) | ?MB | ?MB | ?MB | ?MB |
| 外部依赖 | 0 | N | N | **0** |

---

> 下一步：先跑裸 Python baseline，再跑 LangGraph/CrewAI，出第一版数据。
