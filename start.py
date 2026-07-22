#!/usr/bin/env python3
"""
Zelos Runtime — Quick Start

Starts the Zelos Runtime with the built-in Dashboard.
Open http://127.0.0.1:9876/ in your browser.

Usage:
    python3 start.py                          # Start with defaults
    python3 start.py --port 8080              # Custom port
    python3 start.py --config zelos.yaml      # With config file
    python3 start.py --host 0.0.0.0           # Listen on all interfaces

Options:
    --host HOST         Bind host (default: 127.0.0.1)
    --port PORT         Bind port (default: 9876)
    --config PATH       Path to zelos.yaml config file
    --no-dashboard      Don't start the HTTP adapter (CLI only)
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zelos.http_adapter import HTTPAdapter
from zelos.runtime import ZelosRuntime


def main():
    parser = argparse.ArgumentParser(description="Zelos Runtime — Open Multi-Agent Orchestration Runtime")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=9876, help="Bind port")
    parser.add_argument("--config", "-c", default=None, help="Path to zelos.yaml")
    parser.add_argument("--no-dashboard", action="store_true", help="Don't start HTTP adapter")
    args = parser.parse_args()

    # ── Create Runtime ──
    if args.config:
        rt = ZelosRuntime.from_yaml(args.config)
    else:
        rt = ZelosRuntime({"plugins": []})

    print("⚡ Starting Zelos Runtime...")
    rt.start()
    print("   Kernel: healthy")

    # ── Register a demo agent ──
    rt.add_agent(
        name="DemoAgent",
        entrypoint="builtin:Agent",
        capabilities=[
            {"name": "code-generation.python", "version": "1.0.0"},
            {"name": "code-review.security", "version": "1.0.0"},
            {"name": "automation.browser", "version": "1.0.0"},
        ],
    )
    print("   Agents: 1 registered (DemoAgent)")

    # ── HTTP Adapter + Dashboard ──
    if not args.no_dashboard:
        adapter = HTTPAdapter(rt, host=args.host, port=args.port)
        adapter.start()
        print(f"   Dashboard: {adapter.url}")

    print()
    print("=" * 55)
    print("  Zelos Runtime v0.5.0 — Ready")
    if not args.no_dashboard:
        print(f"  Dashboard: {adapter.url}")
        print(f"  API:       {adapter.url}/api/v1/health")
    print("  Press Ctrl+C to stop")
    print("=" * 55)
    print()

    # ── Keep alive ──
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        if not args.no_dashboard:
            adapter.stop()
        rt.shutdown()
        print("   Done.")


if __name__ == "__main__":
    main()
