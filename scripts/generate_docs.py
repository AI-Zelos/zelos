#!/usr/bin/env python3
"""Generate the complete Zelos documentation site."""
import glob, hashlib, os, re, shutil, subprocess, sys
import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

if os.path.exists(PUBLIC):
    shutil.rmtree(PUBLIC)
os.makedirs(PUBLIC)

# ── Convert guide docs ──
for md_name in ["zelos-manual.md", "zelos-zh.md", "operations.md", "plugin-customization.md"]:
    src = os.path.join(ROOT, "docs", "guide", md_name)
    if not os.path.exists(src):
        continue
    with open(src) as f:
        body = markdown.markdown(f.read(), extensions=["tables", "fenced_code", "toc"])
    html_name = md_name.replace(".md", ".html")
    title = md_name.replace(".md", "").replace("-", " ").title()
    html = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
    html += f'<title>{title} - Zelos Documentation</title>\n'
    html += '<style>\n*{margin:0;padding:0;box-sizing:border-box}\n'
    html += 'body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:920px;margin:0 auto;padding:24px;background:#0d1117;color:#c9d1d9;line-height:1.65}\n'
    html += 'a{color:#58a6ff;text-decoration:none}a:hover{text-decoration:underline}\n'
    html += 'code{background:#161b22;padding:2px 6px;border-radius:4px;font-size:13px}\n'
    html += 'pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px}pre code{background:none;padding:0}\n'
    html += 'table{border-collapse:collapse;width:100%;margin:12px 0}\nth,td{border:1px solid #30363d;padding:8px 14px;text-align:left}\n'
    html += 'th{background:#161b22;font-weight:600}\nh1{font-size:32px;margin:24px 0 12px;color:#f0f6fc}\n'
    html += 'h2{font-size:22px;margin:28px 0 10px;color:#f0f6fc;padding-bottom:6px;border-bottom:1px solid #21262d}\n'
    html += 'h3{font-size:17px;margin:20px 0 8px;color:#f0f6fc}\nhr{border:none;border-top:1px solid #21262d;margin:24px 0}\n'
    html += '.back{margin-bottom:20px;font-size:14px}\n</style></head><body>\n'
    html += '<p class="back"><a href="./">Home</a></p>\n' + body + '\n</body></html>'
    with open(os.path.join(PUBLIC, html_name), "w") as f:
        f.write(html)
    print(f"  OK {html_name}")

# ── Generate API docs ──
subprocess.run(
    [sys.executable, "-m", "pdoc", "zelos", "zelos_sdk", "-o", PUBLIC, "--docformat", "google"],
    cwd=ROOT, check=True,
)
print("  OK API Reference (pdoc)")

# ── Papers: convert MD to HTML + copy PDFs ──
papers_dir = os.path.join(ROOT, "docs", "papers")
papers_rows = []
if os.path.isdir(papers_dir):
    for md_file in sorted(glob.glob(os.path.join(papers_dir, "*.md"))):
        bn = os.path.splitext(os.path.basename(md_file))[0]
        if "executive-summary" in bn.lower():
            continue
        # Preserve original filename, just replace spaces/underscores
        sn = re.sub(r'[_\s]+', '-', bn).lower()
        sn = re.sub(r'[：:]+', '-', sn)
        sn = re.sub(r'-+', '-', sn).strip('-')
        # If all non-ASCII was stripped and name is empty, use hash
        if not sn or len(sn) < 2:
            sn = hashlib.md5(bn.encode()).hexdigest()[:8]
        hname = f"{sn}.html"
        with open(md_file) as f:
            body = markdown.markdown(f.read(), extensions=["tables", "fenced_code"])
        html = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        html += f'<title>{bn[:60]}</title>\n<style>\n'
        html += '*{margin:0;padding:0;box-sizing:border-box}\nbody{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:920px;margin:0 auto;padding:24px;background:#0d1117;color:#c9d1d9;line-height:1.65}\n'
        html += 'a{color:#58a6ff}h1{color:#f0f6fc;margin:24px 0 12px}h2{color:#f0f6fc;margin:28px 0 10px;border-bottom:1px solid #21262d;padding-bottom:6px}h3{color:#f0f6fc;margin:20px 0 8px}\n'
        html += 'code{background:#161b22;padding:2px 6px;border-radius:4px;font-size:13px}pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px}pre code{background:none;padding:0}\n'
        html += 'table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #30363d;padding:8px 14px;text-align:left}th{background:#161b22;font-weight:600}\n'
        html += '.back{margin-bottom:20px;font-size:14px}strong{color:#f0f6fc}\n</style></head><body>\n'
        html += '<p class="back"><a href="./">Home</a> | <a href="papers.html">Papers</a></p>\n' + body + '\n</body></html>'
        with open(os.path.join(PUBLIC, hname), "w") as f:
            f.write(html)
        with open(md_file) as f:
            title = f.readline().strip().lstrip("#").strip()
        papers_rows.append(f'<tr><td><a href="{hname}">{title or bn}</a></td><td style="color:#8b949e">HTML</td></tr>')
        print(f"  OK {hname}")

    for pdf in sorted(glob.glob(os.path.join(papers_dir, "*.pdf"))):
        bn = os.path.basename(pdf)
        stem = os.path.splitext(bn)[0]
        sn = re.sub(r'[_\s]+', '-', stem).lower()
        sn = re.sub(r'[：:]+', '-', sn)
        sn = re.sub(r'-+', '-', sn).strip('-')
        if not sn or len(sn) < 2:
            sn = hashlib.md5(stem.encode()).hexdigest()[:8]
        cname = f"{sn}.pdf"
        shutil.copy2(pdf, os.path.join(PUBLIC, cname))
        papers_rows.append(f'<tr><td><a href="{cname}">{stem[:60]}</a></td><td style="color:#8b949e">PDF</td></tr>')
        print(f"  OK {cname}")

# ── Papers index page ──
phtml = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Papers - Zelos</title>\n<style>\n'
phtml += '*{margin:0;padding:0;box-sizing:border-box}\nbody{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:780px;margin:0 auto;padding:48px 24px;background:#0d1117;color:#c9d1d9;line-height:1.65}\n'
phtml += 'a{color:#58a6ff;text-decoration:none}a:hover{text-decoration:underline}\nh1{color:#f0f6fc;font-size:32px;margin-bottom:8px}\n'
phtml += '.subtitle{color:#8b949e;font-size:15px;margin-bottom:32px}\ntable{width:100%;border-collapse:collapse}\n'
phtml += 'td{padding:12px 14px;border-bottom:1px solid #21262d;font-size:15px}tr:hover{background:#161b22}\n.back{margin-bottom:24px;font-size:14px}\n</style></head><body>\n'
phtml += '<p class="back"><a href="./">Home</a></p>\n<h1>Papers</h1>\n<p class="subtitle">Research papers from the Zelos project.</p>\n<table>\n'
phtml += '\n'.join(papers_rows) + '\n</table>\n</body></html>'
with open(os.path.join(PUBLIC, "papers.html"), "w") as f:
    f.write(phtml)
print("  OK papers.html")

# ── Landing page ──
index = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Zelos Documentation</title>\n<style>\n'
index += '*{margin:0;padding:0;box-sizing:border-box}\nbody{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}\n'
index += 'main{max-width:780px;padding:48px 24px;text-align:center}\nh1{font-size:52px;margin-bottom:4px;color:#f0f6fc}h1 span{color:#58a6ff}\n'
index += '.subtitle{color:#8b949e;font-size:18px;margin-bottom:44px}\n.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:620px;margin:0 auto}\n'
index += '.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:26px 22px;text-align:left;text-decoration:none;transition:border-color .2s,transform .1s}\n'
index += '.card:hover{border-color:#58a6ff;transform:translateY(-2px)}\n.card h3{color:#f0f6fc;font-size:18px;margin-bottom:6px}\n'
index += '.card p{color:#8b949e;font-size:14px;line-height:1.5}\n.footer{margin-top:48px;color:#484f58;font-size:13px}.footer a{color:#484f58}\n'
index += '.badge{display:inline-block;background:rgba(88,166,255,.12);color:#58a6ff;padding:3px 10px;border-radius:12px;font-size:12px;margin-bottom:18px}\n</style></head><body>\n'
index += '<main>\n<h1>Zel<span>os</span></h1>\n<p class="subtitle">Open Multi-Agent Orchestration Runtime</p>\n'
index += '<p class="badge">v1.0.0 &middot; 10 Phases Complete &middot; Apache 2.0</p>\n<div class="cards">\n'
index += '<a class="card" href="zelos.html"><h3>API Reference</h3><p>Complete API docs for all 37 modules - runtime, kernel, plugins, SDK</p></a>\n'
index += '<a class="card" href="zelos-manual.html"><h3>User Manual</h3><p>Getting started, architecture deep dive, configuration, and full API walkthrough</p></a>\n'
index += '<a class="card" href="zelos-zh.html"><h3>中文手册</h3><p>Zelos 全面技术手册 - 为什么存在、怎么用、每个模块详解、部署指南、FAQ</p></a>\n'
index += '<a class="card" href="plugin-customization.html"><h3>Plugin Guide</h3><p>Customize Verifier, ConfidenceScorer, PolicyGate, Planner with code examples</p></a>\n'
index += '<a class="card" href="operations.html"><h3>Operations Guide</h3><p>Deployment (bare-metal/Docker/K8s), multi-node cluster, monitoring, troubleshooting</p></a>\n'
index += '<a class="card" href="papers.html"><h3>Papers</h3><p>Research papers and academic publications from the Zelos project</p></a>\n'
index += '<a class="card" href="https://github.com/AI-Zelos/zelos"><h3>GitHub</h3><p>Source code &middot; 151 tests &middot; 21 demos &middot; Python/TS/Go SDKs</p></a>\n'
index += '</div>\n<p class="footer">Apache 2.0 &middot; <a href="https://github.com/AI-Zelos/zelos">AI-Zelos/zelos</a></p>\n</main></body></html>'
with open(os.path.join(PUBLIC, "index.html"), "w") as f:
    f.write(index)
print("  OK index.html")

print(f"\nDone: {PUBLIC}/")
print(f"   open {PUBLIC}/index.html")
