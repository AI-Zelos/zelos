#!/usr/bin/env python3
"""
Generate PoC experiment comparison report from result JSON files.

Usage:
  python report.py --results-dir logs/poc_results/ --output docs/swebench-poc-report.md
"""

import json
import os
import sys
from datetime import datetime

from metrics import (
    compute_group_summary,
    compute_orchestrated_details,
    compute_per_instance_comparison,
    load_results,
)

RESULTS_DIR = "logs/poc_results"
GROUPS = ["baseline", "runtime_diag", "orchestrated"]


def generate_report(results_dir: str, output_file: str) -> str:
    """Generate markdown comparison report."""
    # Load results
    baseline = load_results(results_dir, "baseline")
    diag = load_results(results_dir, "runtime_diag")
    orch = load_results(results_dir, "orchestrated")

    if not baseline and not diag and not orch:
        return "# PoC Experiment Report\n\n**No results found.** Run experiments first."

    # Compute summaries
    b_summary = compute_group_summary(baseline)
    d_summary = compute_group_summary(diag)
    o_summary = compute_group_summary(orch)
    per_instance = compute_per_instance_comparison(baseline, diag, orch)
    orch_details = compute_orchestrated_details(orch)

    # Hypothesis checks
    h1_supported = (
        o_summary.get("passed", 0) > b_summary.get("passed", 0)
    )
    h2_supported = (
        d_summary.get("total_tokens_estimate", float("inf"))
        < b_summary.get("total_tokens_estimate", 0)
    )

    lines = []
    lines.append("# SWE-bench PoC 实验结果报告")
    lines.append(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"实例数：{b_summary.get('count', 0)}")

    # ── Executive Summary ──
    lines.append("\n---\n")
    lines.append("## 摘要\n")
    lines.append("| 分组 | 通过率 | 总 Token (估算) | 平均重试 | 平均耗时 |")
    lines.append("|------|--------|----------------|---------|---------|")
    for name, s in [("基线组", b_summary), ("+诊断组", d_summary), ("+编排组", o_summary)]:
        lines.append(
            f"| {name} | {s.get('pass_rate', 'N/A')} | "
            f"{s.get('total_tokens_estimate', 'N/A'):,} | "
            f"{s.get('avg_retries_per_instance', 'N/A')} | "
            f"{s.get('avg_time_seconds', 'N/A')}s |"
        )

    # ── Hypothesis Results ──
    lines.append("\n## 假设验证\n")
    lines.append(f"- **H₁ (编排 > 单体)**: {'✅ 初步支持' if h1_supported else '❌ 未支持'}")
    lines.append(f"  - 编排组: {o_summary.get('pass_rate', 'N/A')}")
    lines.append(f"  - 基线组: {b_summary.get('pass_rate', 'N/A')}")
    lines.append(f"- **H₂ (诊断更省 Token)**: {'✅ 初步支持' if h2_supported else '❌ 未支持'}")
    lines.append(f"  - +诊断组 Token: {d_summary.get('total_tokens_estimate', 'N/A'):,}")
    lines.append(f"  - 基线组 Token: {b_summary.get('total_tokens_estimate', 'N/A'):,}")

    # ── Per-Instance Detail ──
    lines.append("\n## 逐实例对比\n")
    lines.append("| 实例 | 基线 | +诊断 | +编排 | 基线Token | 诊断Token | 编排Token |")
    lines.append("|------|------|------|------|----------|----------|----------|")
    for row in per_instance:
        def check(flag):
            return "✅" if flag else "❌"
        lines.append(
            f"| {row['instance_id'][:40]} | {check(row['baseline_pass'])} | "
            f"{check(row['diag_pass'])} | {check(row['orch_pass'])} | "
            f"{row['baseline_tokens']:,} | {row['diag_tokens']:,} | "
            f"{row['orch_tokens']:,} |"
        )

    # ── Orchestrated Details ──
    if orch:
        lines.append("\n## 编排组专项\n")
        lines.append(f"- MPC 决策总数: {orch_details['total_mpc_decisions']}")
        lines.append(f"- Replan 触发次数: {orch_details['total_replans']}")
        lines.append(f"- 触发 Replan 的实例数: {orch_details['instances_with_replan']}")
        lines.append(f"- Reviewer 通过率: {orch_details['review_pass_rate']:.0%}")

        lines.append("\n### 决策详情\n")
        for r in orch:
            decisions = r.get("metrics", {}).get("decisions", [])
            if decisions:
                lines.append(f"**{r['instance_id']}**")
                for d in decisions:
                    lines.append(
                        f"- Attempt {d.get('attempt', '?')}: "
                        f"action={d.get('action', '?')}, "
                        f"trigger={d.get('trigger', '?')}"
                    )
                lines.append("")

    # ── Qualitative Analysis Template ──
    lines.append("\n## 定性分析\n")
    lines.append("> **逐实例填写（实验完成后）**\n")
    for row in per_instance:
        lines.append(f"### {row['instance_id']}\n")
        lines.append("- **为什么失败/成功？** ")
        lines.append("- **Runtime 介入了吗？** ")
        lines.append("- **Runtime 的决策对吗？** ")
        lines.append("- **哪一步最耗时？** ")
        lines.append("")

    # ── Conclusion ──
    lines.append("\n## 结论与下一步\n")
    if h1_supported:
        lines.append("H₁ 被初步支持：编排组通过率高于基线组。")
        lines.append("**建议**: 扩大样本到 20-30 题做正式评测。")
    elif not baseline:
        lines.append("**实验尚未执行。** 请先运行各组实验脚本。")
    else:
        lines.append("H₁ 未被支持：编排组未超越基线组。")
        lines.append("**建议**: 逐实例分析 Runtime 瓶颈（Planner/Agent/Diagnosis）。")

    report = "\n".join(lines)

    # Write to file
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w") as f:
        f.write(report)
    print(f"Report saved to {output_file}")

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate PoC experiment report"
    )
    parser.add_argument(
        "--results-dir", default=RESULTS_DIR,
        help=f"Directory with result JSONs (default: {RESULTS_DIR})"
    )
    parser.add_argument(
        "--output", default="docs/swebench-poc-report.md",
        help="Output markdown file"
    )
    args = parser.parse_args()

    report = generate_report(args.results_dir, args.output)
    print(report)


if __name__ == "__main__":
    main()
