"""
Demo 17: Hot Reload — Plugin Upgrade without Runtime Restart

Demonstrates Phase 3 hot reload features:
  - File watching for plugin changes
  - Version management and tracking
  - Rolling / Blue-Green / Canary upgrade strategies
  - Version drain, rollback, and history

Run: python3 demo/17_hot_reload.py
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.hot_reload import (
    FileWatcher,
    HotReloadManager,
    UpgradeStrategy,
)


def main():
    print("=" * 60)
    print("  DEMO 17: Hot Reload — Zero-Downtime Plugin Upgrades")
    print("=" * 60)

    # ── 1. File Watcher ──
    print("\n👁️  1. File Watcher — Detect Plugin Changes")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial plugin files
        plugin_a = os.path.join(tmpdir, "plugin_a.py")
        plugin_b = os.path.join(tmpdir, "plugin_b.py")

        with open(plugin_a, "w") as f:
            f.write("# Plugin A v1.0.0\ndef execute(): return 'a:v1'")
        with open(plugin_b, "w") as f:
            f.write("# Plugin B v1.0.0\ndef execute(): return 'b:v1'")

        fw = FileWatcher(tmpdir, patterns=["*.py"], poll_interval_ms=200)
        fw.start()
        time.sleep(0.2)

        print(f"   Watching: {tmpdir}")
        print("   Initial files: plugin_a.py, plugin_b.py")

        # Modify plugin_a
        time.sleep(0.1)
        with open(plugin_a, "w") as f:
            f.write("# Plugin A v1.1.0\ndef execute(): return 'a:v2'")
        time.sleep(0.8)

        changes = fw.get_changes()
        print(f"   Changes detected: {len(changes)}")
        for c in changes:
            print(f"     - [{c['type']}] {c['filename']}")

        fw.stop()

    # ── 2. Hot Reload Manager — Version Lifecycle ──
    print("\n🔄 2. Hot Reload Manager — Version Lifecycle")

    hrm = HotReloadManager()

    # Register versions over time
    print("\n   Timeline:")
    versions = [
        ("verifier-plugin", "1.0.0", "zelos.verifier:SchemaVerifier", "sha256:a1b2"),
        ("verifier-plugin", "1.1.0", "zelos.verifier_v2:CodeReviewer", "sha256:c3d4"),
        ("verifier-plugin", "1.2.0", "zelos.verifier_v2:SecurityScanner", "sha256:e5f6"),
        ("verifier-plugin", "2.0.0", "zelos.verifier_v3:FullVerifier", "sha256:g7h8"),
    ]

    for plugin_id, ver, entry, checksum in versions:
        hrm.register_version(plugin_id, ver, entry, checksum)
        active = hrm.get_active_version(plugin_id)
        print(f"   Registered {plugin_id}@{ver} → active: {active.version}")

    # Show version history
    print("\n   Version history for verifier-plugin:")
    for v in hrm.get_version_history("verifier-plugin"):
        print(f"     {v.version:8s} [{v.status:12s}] {v.entrypoint} ({v.checksum})")

    # Drain old versions
    print("\n   Drain old versions:")
    for old_ver in ["1.0.0", "1.1.0"]:
        hrm.drain_version("verifier-plugin", old_ver)
        drained = hrm.get_version("verifier-plugin", old_ver)
        print(f"     {old_ver}: {drained.status}")

    # Rollback
    print("\n   ⚠️  Rollback: 2.0.0 has a bug → rolling back to 1.2.0")
    hrm.rollback("verifier-plugin", "1.2.0")
    active = hrm.get_active_version("verifier-plugin")
    print(f"   Active after rollback: {active.version} ({active.status})")

    # ── 3. Upgrade Strategies ──
    print("\n📊 3. Upgrade Strategies")

    strategies = [
        (UpgradeStrategy.ROLLING, "One instance at a time"),
        (UpgradeStrategy.BLUE_GREEN, "Spin up new, cut over all at once"),
        (UpgradeStrategy.CANARY, "Route X% traffic to new version"),
        (UpgradeStrategy.INSTANT, "Immediate cut-over (for hotfixes)"),
    ]

    for strat, desc in strategies:
        hrm.set_upgrade_strategy(strat)
        print(f"   {strat.value:12s} — {desc}")

    # Canary deployment
    print("\n   Canary deployment example:")
    hrm.set_upgrade_strategy(UpgradeStrategy.CANARY)
    hrm.register_version("api-gateway", "3.0.0", "gateway:v3", "sha256:xxx", canary_percent=5)
    v3 = hrm.get_version("api-gateway", "3.0.0")
    print(f"     api-gateway@3.0.0: {v3.canary_percent}% traffic → new version")
    print(f"     api-gateway@2.0.0: {100 - v3.canary_percent}% traffic → old version")
    print("     (ramp up canary_percent gradually, then full cut-over)")

    # ── 4. Plugin Summary ──
    print("\n📋 4. Plugin Summary")
    for p in hrm.list_plugins():
        print(f"   {p['plugin_id']}: {p['active_version']} ({p['version_count']} versions, {p['strategy']})")

    # Upgrade history
    history = hrm.get_upgrade_history()
    print(f"\n   Upgrade events: {len(history)}")
    for h in history[-5:]:
        print(f"     [{h['action']:12s}] {h['plugin_id']}@{h['version']}")

    print(f"\n{'=' * 60}")
    print("  Demo complete. Hot reload primitives working.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
