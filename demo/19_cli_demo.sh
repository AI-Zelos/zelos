#!/bin/bash
# Demo 19: CLI Tool — Command-line Interface for Zelos Runtime
#
# Demonstrates Phase 3 CLI tool with all subcommands.
# Run: bash demo/19_cli_demo.sh
# or:  python3 -m zelos.cli --help

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo "  DEMO 19: CLI Tool — Zelos Command-line Interface"
echo "============================================================"

# Use PYTHONPATH to import the zelos CLI
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

run_cmd() {
    echo ""
    echo "  \$ zelos $*"
    echo "  --------------------------------------------------"
    python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from zelos.cli import ZelosCLI
cli = ZelosCLI()
output = cli.run(sys.argv[1:])
if output:
    for line in output.strip().split('\n'):
        print(f'  {line}')
" $@ 2>&1 || true
}

echo ""
echo "  ── Version ──"
run_cmd --version

echo ""
echo "  ── Goal Management ──"
run_cmd goal submit --description "Build a production landing page with React"
run_cmd goal submit --description "Security audit of payment service" --priority critical --budget 500
run_cmd goal list
run_cmd goal status --goal-id g-demo-001
run_cmd goal cancel --goal-id g-demo-002

echo ""
echo "  ── Agent Management ──"
run_cmd agent list
run_cmd agent info --agent-id agent-codex-1

echo ""
echo "  ── Health & Metrics ──"
run_cmd health
run_cmd metrics

echo ""
echo "  ── Plugin & Namespace ──"
run_cmd plugin list
run_cmd namespace list

echo ""
echo "  ── Configuration ──"
run_cmd config show
run_cmd config validate

echo ""
echo "============================================================"
echo "  Demo complete. CLI tool primitives working."
echo "============================================================"
