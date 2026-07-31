# Fixer Loop Integration — Design & Verification Plan

> 目标：接通 Diagnosis Engine → Failure Classifier → Repair Orchestrator → Docker eval 的完整闭环。
> 状态：所有模块已实现（v1.2.0），待接入 SWE-bench 评测链路。

---

## 一、架构

```
SWE-bench 评测结果
    │
    ├── passed → 完成，提交
    │
    └── failed
          │
          ▼
    Diagnosis Engine（读评测日志 → 提取失败测试、断言值、文件行号）
          │
          ▼
    Failure Classifier（分类：repair / retry / abandon）
          │
          ├── abandon → 放弃，记录原因
          │
          └── repair → 构建 RepairContext
                │
                ▼
          Fixer Agent（Claude Code，拿精确诊断信息）（上限 3 轮）
                │
                ▼
          Docker eval（重新评测）
                │
                ├── passed → 完成
                └── failed → 回到 Diagnosis（最多 3 轮）
```

---

## 二、接入点

在当前 `scripts/swebench_v3.py`（v4）的评测结果基础上，加后处理步骤：

```python
# 伪代码
for instance in failed_instances:
    diagnosis = engine.diagnose(instance.test_output)
    classification = classifier.classify(diagnosis)

    if classification.action == "abandon":
        continue  # 不值得修

    for round in range(3):
        ctx = repair_orch.build_context(
            issue=instance.issue,
            patch=instance.patch,
            diagnosis=diagnosis,
            previous_hypotheses=previous_hypotheses,
        )
        new_patch = claude(ctx.build_fixer_prompt())
        test_output = run_docker_eval(instance.id, new_patch)

        if test_output_contains_all_passed(test_output):
            instance.patch = new_patch
            instance.resolved = True
            break

        diagnosis = engine.diagnose(test_output)
        classification = classifier.classify(diagnosis)
```

---

## 三、验证方案

### 第一步：1 题验证链路通

选取评测中**单个失败但 salvageable** 的实例（断言错误、单模块影响）。

手动跑 Fixer Loop 1 轮：
- 输入：评测日志 + Claude 生成的新 patch
- 验证：新 patch 在 Docker 里重新评测
- 判定：通过的测试数是否增加

### 第二步：1 题验证边界

选取评测中**明确 abandon** 的实例（全量爆炸、方向根本错误）。

验证 Failure Classifier 正确判定为 abandon，**不触发 Fixer**。

### 第三步：全量验证

如果两步都通，在 10 题上跑完整 Fixer Loop，统计：
- Fixer 触发次数
- 修复成功率
- 最终解决率提升

---

## 四、成功标准

| 指标 | 目标 | 说明 |
|------|------|------|
| Fixer 触发正确性 | 100% | salvageable 才触发，abandon 不触发 |
| Fixer 1 轮成功率 | >30% | 第一轮修复成功率 |
| Fixer 3 轮成功率 | >50% | 三轮后总修复成功率 |
| 整体解决率提升 | +5pp | 10 题上对比 v4 基线 |

---

## 五、风险

| 风险 | 应对 |
|------|------|
| Docker eval 慢（每轮 80s） | 先跑 1 题验证，确认通再跑 10 题 |
| Fixer 产出格式不对 | 用和 v4 一样的清洗逻辑 |
| Fixer 越修越差 | Failure Classifier 拦掉 abandon，最多 3 轮止损 |

---

## 六、实施计划

1. 当前 v4 评测结束 → 得到失败实例列表 + 评测日志
2. 选 1 个 salvageable + 1 个 abandon 做验证
3. 接 Fixer Loop → 跑 10 题
4. 对比 v4 vs v4+Fixer 解决率
