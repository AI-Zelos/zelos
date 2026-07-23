#!/usr/bin/env python3
"""Generate the complete Zelos documentation site.

Produces public/ with:
  - index.html (landing page)
  - zelos-manual.html (from docs/guide/zelos-manual.md)
  - operations.html (from docs/guide/operations.md)
  - zelos.html + zelos/ + zelos_sdk.html (pdoc API reference)
"""
import os
import shutil
import subprocess
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

# Clean
if os.path.exists(PUBLIC):
    shutil.rmtree(PUBLIC)
os.makedirs(PUBLIC)

# ── Convert guide docs ──
for md_name in ["zelos-manual.md", "zelos-zh.md", "operations.md"]:
    src = os.path.join(ROOT, "docs", "guide", md_name)
    if not os.path.exists(src):
        continue
    with open(src) as f:
        body = markdown.markdown(f.read(), extensions=["tables", "fenced_code", "toc"])

    html_name = md_name.replace(".md", ".html")
    title = md_name.replace(".md", "").replace("-", " ").title()
    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Zelos Documentation</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:920px;margin:0 auto;padding:24px;background:#0d1117;color:#c9d1d9;line-height:1.65}}
a{{color:#58a6ff;text-decoration:none}}a:hover{{text-decoration:underline}}
code{{background:#161b22;padding:2px 6px;border-radius:4px;font-size:13px}}
pre{{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px}}
pre code{{background:none;padding:0}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #30363d;padding:8px 14px;text-align:left}}
th{{background:#161b22;font-weight:600}}
h1{{font-size:32px;margin:24px 0 12px;color:#f0f6fc}}
h2{{font-size:22px;margin:28px 0 10px;color:#f0f6fc;padding-bottom:6px;border-bottom:1px solid #21262d}}
h3{{font-size:17px;margin:20px 0 8px;color:#f0f6fc}}
hr{{border:none;border-top:1px solid #21262d;margin:24px 0}}
.back{{margin-bottom:20px;font-size:14px}}
</style></head><body>
<p class="back"><a href="./">← Documentation Home</a></p>
{body}
</body></html>"""

    with open(os.path.join(PUBLIC, html_name), "w") as f:
        f.write(html)
    print(f"  ✅ {html_name}")

# ── Generate API docs ──
subprocess.run(
    [sys.executable, "-m", "pdoc", "zelos", "zelos_sdk", "-o", PUBLIC, "--docformat", "google"],
    cwd=ROOT,
    check=True,
)
print("  ✅ API Reference (pdoc)")

# ── Landing page ──
index = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zelos Documentation</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
main{max-width:780px;padding:48px 24px;text-align:center}
h1{font-size:52px;margin-bottom:4px;color:#f0f6fc}h1 span{color:#58a6ff}
.subtitle{color:#8b949e;font-size:18px;margin-bottom:44px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:620px;margin:0 auto}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:26px 22px;text-align:left;text-decoration:none;transition:border-color .2s,transform .1s}
.card:hover{border-color:#58a6ff;transform:translateY(-2px)}
.card h3{color:#f0f6fc;font-size:18px;margin-bottom:6px}
.card p{color:#8b949e;font-size:14px;line-height:1.5}
.footer{margin-top:48px;color:#484f58;font-size:13px}.footer a{color:#484f58}
.badge{display:inline-block;background:rgba(88,166,255,.12);color:#58a6ff;padding:3px 10px;border-radius:12px;font-size:12px;margin-bottom:18px}
</style></head><body>
<main>
<h1>&#9889; Zel<span>os</span></h1>
<p class="subtitle">Open Multi-Agent Orchestration Runtime</p>
<p class="badge">v0.7.0 &middot; 7 Phases Complete &middot; Apache 2.0</p>
<div class="cards">
<a class="card" href="zelos.html"><h3>&#128218; API Reference</h3><p>Complete API docs for all 28 modules &mdash; runtime, kernel, plugins, SDK</p></a>
<a class="card" href="zelos-manual.html"><h3>&#128214; User Manual</h3><p>Getting started, architecture deep dive, configuration, and full API walkthrough</p></a>
<a class="card" href="zelos-zh.html"><h3>&#127471;&#127477; 中文手册</h3><p>Zelos 全面技术手册 — 为什么存在、怎么用、每个模块详解、部署指南、FAQ</p></a>
<a class="card" href="operations.html"><h3>&#128640; Operations Guide</h3><p>Deployment (bare-metal/Docker/K8s), multi-node cluster, monitoring, troubleshooting</p></a>
<a class="card" href="https://github.com/AI-Zelos/zelos"><h3>&#128187; GitHub</h3><p>Source code &middot; 78 tests &middot; 21 demos &middot; Python/TS/Go SDKs</p></a>
</div>
<p class="footer">Apache 2.0 &middot; <a href="https://github.com/AI-Zelos/zelos">AI-Zelos/zelos</a></p>
</main></body></html>"""

with open(os.path.join(PUBLIC, "index.html"), "w") as f:
    f.write(index)
print("  ✅ index.html")

print(f"\n✅ Documentation site generated: {PUBLIC}/")
print(f"   open {PUBLIC}/index.html")
