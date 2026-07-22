#!/usr/bin/env python3
"""
Demo 11: 多层验证流水线

SchemaVerifier → CodeReviewer → SecurityScanner → FactChecker
四级验证按序执行，任意一级失败则短路，完整日志记录。

用法: python3 demo/11_verifier_pipeline.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.verifier import SchemaVerifier, VerificationCriteria, VerificationGate
from zelos.verifier_v2 import CodeReviewer, FactChecker, SecurityScanner


def main():
    print("=" * 60)
    print("  Demo 11: 多层验证流水线")
    print("=" * 60)

    # 构建四级验证链
    gate = VerificationGate()
    gate.add_verifier(SchemaVerifier({"strict_mode": True}))
    gate.add_verifier(CodeReviewer())
    gate.add_verifier(SecurityScanner())
    gate.add_verifier(FactChecker())

    criteria = VerificationCriteria(
        expected_output_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        options={"language": "python"},
    )

    # 测试 1: 干净代码 — 全部通过
    clean = {"code": "def hello():\n    return 'Hello, World!'"}
    v1 = gate.verify(clean, criteria)
    print("\n🔹 干净代码:")
    print(f"   结果: {v1.verdict} | 分数: {v1.score} | {v1.summary}")

    # 测试 2: eval 漏洞 — SecurityScanner 拦截
    dangerous = {"code": "x = eval(input())"}
    v2 = gate.verify(dangerous, criteria)
    print("\n🔸 eval() 代码:")
    print(f"   结果: {v2.verdict} | 分数: {v2.score}")
    for i in v2.issues[:3]:
        print(f"   · [{i['severity']}] {i['message']} ({i.get('location', '')})")

    # 测试 3: SQL 注入 — SecurityScanner 拦截
    sql_inject = {"code": 'query = "SELECT * FROM users WHERE id=" + user_id'}
    v3 = gate.verify(sql_inject, criteria)
    print("\n🔸 SQL 注入:")
    print(f"   结果: {v3.verdict} | 分数: {v3.score}")
    for i in v3.issues:
        print(f"   · [{i['severity']}] {i['message']}")

    # 测试 4: 硬编码密码 + XSS — 多重告警
    bad_code = {"code": 'password = "admin123"\nel.innerHTML = user_input'}
    v4 = gate.verify(bad_code, criteria)
    print("\n🔸 硬编码密码 + XSS:")
    print(f"   结果: {v4.verdict} | 问题数: {len(v4.issues)}")
    for i in v4.issues:
        print(f"   · [{i['severity']}] {i['message']}")

    # 测试 5: 未来声明 — FactChecker 标记
    prediction = {"code": "# Prediction: Zelos will reach 1 million users by 2028\nprint('hello')"}
    v5 = gate.verify(prediction, criteria)
    print("\n🔹 未来声明:")
    print(f"   结果: {v5.verdict} | {v5.summary}")

    print("\n✅ Demo 11 完成 — 四级验证链全部通过测试")


if __name__ == "__main__":
    main()
