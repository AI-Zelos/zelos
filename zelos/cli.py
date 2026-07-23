"""
Phase 3 CLI Tool — Command-line interface for Zelos Runtime.

Usage:
    zelos --version
    zelos --help
    zelos start [--config zelos.yaml]
    zelos stop
    zelos goal submit --description "..." [--priority high] [--budget 100]
    zelos goal status --goal-id <id>
    zelos goal list
    zelos goal cancel --goal-id <id>
    zelos agent list
    zelos agent info --agent-id <id>
    zelos health
    zelos metrics
    zelos plugin list
    zelos namespace list
"""

import argparse
import json
import sys

__version__ = "0.7.0"


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="zelos",
        description="Zelos — Open Multi-Agent Orchestration Runtime CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  zelos start --config zelos.yaml
  zelos goal submit --description "Build a landing page"
  zelos goal status --goal-id g-001
  zelos agent list
  zelos health
        """,
    )

    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--config", "-c", default="zelos.yaml", help="Path to configuration file (default: zelos.yaml)")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── start ──
    start_parser = sub.add_parser("start", help="Start the Zelos Runtime server")
    start_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    start_parser.add_argument("--port", type=int, default=9876, help="Bind port (default: 9876)")
    start_parser.add_argument("--daemon", action="store_true", help="Run as daemon (background)")

    # ── stop ──
    sub.add_parser("stop", help="Stop the Zelos Runtime server")

    # ── goal ──
    goal_parser = sub.add_parser("goal", help="Goal management")
    goal_sub = goal_parser.add_subparsers(dest="goal_command")

    goal_submit = goal_sub.add_parser("submit", help="Submit a new goal")
    goal_submit.add_argument("--description", "-d", required=True, help="Goal description (natural language)")
    goal_submit.add_argument(
        "--priority",
        "-p",
        default="medium",
        choices=["low", "medium", "high", "critical"],
        help="Goal priority (default: medium)",
    )
    goal_submit.add_argument("--budget", "-b", type=float, default=None, help="Maximum budget for this goal")
    goal_submit.add_argument("--deadline", default=None, help="Deadline (ISO 8601 format)")
    goal_submit.add_argument("--tenant", "-t", default=None, help="Tenant ID for multi-tenant deployments")

    goal_status = goal_sub.add_parser("status", help="Get goal status")
    goal_status.add_argument("--goal-id", "-g", required=True, help="Goal ID to query")

    goal_sub.add_parser("list", help="List all goals")

    goal_cancel = goal_sub.add_parser("cancel", help="Cancel a goal")
    goal_cancel.add_argument("--goal-id", "-g", required=True, help="Goal ID to cancel")

    # ── agent ──
    agent_parser = sub.add_parser("agent", help="Agent management")
    agent_sub = agent_parser.add_subparsers(dest="agent_command")

    agent_sub.add_parser("list", help="List all registered agents")

    agent_info = agent_sub.add_parser("info", help="Get agent details")
    agent_info.add_argument("--agent-id", "-a", required=True, help="Agent ID or name")

    # ── health ──
    sub.add_parser("health", help="Check Runtime health")

    # ── metrics ──
    sub.add_parser("metrics", help="Get Runtime metrics")

    # ── plugin ──
    plugin_parser = sub.add_parser("plugin", help="Plugin management")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command")
    plugin_sub.add_parser("list", help="List all loaded plugins")

    # ── namespace ──
    ns_parser = sub.add_parser("namespace", help="Namespace / tenant management")
    ns_sub = ns_parser.add_subparsers(dest="namespace_command")
    ns_sub.add_parser("list", help="List all namespaces")

    # ── config ──
    config_parser = sub.add_parser("config", help="Configuration management")
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_sub.add_parser("show", help="Show current configuration")
    config_sub.add_parser("validate", help="Validate configuration file")

    return parser


class ZelosCLI:
    """CLI command dispatcher for Zelos Runtime.

    In production, each command calls the Runtime API via HTTP.
    Phase 3 provides command parsing and dispatch infrastructure.
    In demo/standalone mode, returns formatted output strings.
    """

    def __init__(self, runtime=None):
        self.runtime = runtime
        self.parser = build_argument_parser()

    def run(self, args: list[str] | None = None) -> str:
        """Parse args and dispatch to the appropriate handler.

        Returns a formatted output string.
        """
        try:
            parsed = self.parser.parse_args(args or sys.argv[1:])
        except SystemExit:
            return ""

        # --version
        if parsed.version:
            return self._cmd_version()

        # No command
        if not parsed.command:
            self.parser.print_help()
            return ""

        # Dispatch
        handler = getattr(self, f"_cmd_{parsed.command}", None)
        if handler:
            return handler(parsed)
        return f"Unknown command: {parsed.command}"

    # ── Command Handlers ──

    def _cmd_version(self) -> str:
        return f"zelos version {__version__}"

    def _cmd_start(self, args) -> str:
        host = args.host
        port = args.port
        config = args.config if hasattr(args, "config") else "zelos.yaml"
        daemon = args.daemon if hasattr(args, "daemon") else False

        if self.runtime:
            self.runtime.start()
            return f"Zelos Runtime started on {host}:{port}\n  Config: {config}\n  Version: {__version__}"

        mode = "daemon" if daemon else "foreground"
        return (
            f"Zelos Runtime would start on {host}:{port}\n  Config: {config}\n  Mode: {mode}\n  Version: {__version__}"
        )

    def _cmd_stop(self, args) -> str:
        if self.runtime:
            self.runtime.shutdown()
            return "Zelos Runtime stopped."
        return "Zelos Runtime stopped (simulation)."

    def _cmd_goal(self, args) -> str:
        """Goal subcommand dispatcher."""
        subcmd = getattr(args, "goal_command", None)
        if subcmd == "submit":
            return self._goal_submit(args)
        elif subcmd == "status":
            return self._goal_status(args)
        elif subcmd == "list":
            return self._goal_list(args)
        elif subcmd == "cancel":
            return self._goal_cancel(args)
        return "Usage: zelos goal {submit|status|list|cancel}"

    def _goal_submit(self, args) -> str:
        desc = args.description
        priority = args.priority
        budget = args.budget

        if self.runtime:
            result = self.runtime.submit_goal(description=desc, priority=priority, budget=budget)
            return (
                f"Goal submitted\n"
                f"  Goal ID: {result.get('goal_id', 'N/A')}\n"
                f"  Status: {result.get('status', 'N/A')}\n"
                f"  Tasks: {result.get('task_count', 0)}"
            )

        return (
            f"Goal submitted (simulation)\n"
            f"  Description: {desc}\n"
            f"  Priority: {priority}\n"
            f"  Budget: {budget or 'unlimited'}"
        )

    def _goal_status(self, args) -> str:
        goal_id = getattr(args, "goal_id", None)
        if self.runtime:
            status = self.runtime.get_goal_status(goal_id)
            if status:
                progress = status.get("progress", {})
                return (
                    f"Goal: {goal_id}\n"
                    f"  Status: {status.get('status', 'N/A')}\n"
                    f"  Progress: {progress.get('percent_complete', 0):.0f}% "
                    f"({progress.get('completed_tasks', 0)}/"
                    f"{progress.get('total_tasks', 0)} tasks)"
                )
        return f"Goal: {goal_id}\n  Status: not found"

    def _goal_list(self, args) -> str:
        if self.runtime:
            goals = self.runtime._goals
            lines = [f"Goals ({len(goals)} total):"]
            for gid, g in list(goals.items())[:10]:
                lines.append(f"  {gid}: {g.get('status', 'unknown')} — {g.get('description', '')[:60]}")
            return "\n".join(lines)
        return "Goals (simulation):\n  No active goals"

    def _goal_cancel(self, args) -> str:
        goal_id = getattr(args, "goal_id", None)
        if self.runtime:
            result = self.runtime.cancel_goal(goal_id)
            if result:
                return f"Goal {goal_id}: {result.get('status', 'cancelled')}"
        return f"Goal {goal_id}: cancelled (simulation)"

    def _cmd_agent(self, args) -> str:
        """Agent subcommand dispatcher."""
        subcmd = getattr(args, "agent_command", None)
        if subcmd == "list":
            return self._agent_list(args)
        elif subcmd == "info":
            return self._agent_info(args)
        return "Usage: zelos agent {list|info}"

    def _agent_list(self, args) -> str:
        if self.runtime:
            agents = self.runtime.list_agents()
            lines = [f"Agents ({len(agents)} total):"]
            for a in agents:
                lines.append(
                    f"  {a.get('name', 'N/A')} ({a.get('agent_id', '')[:8]}...): "
                    f"{a.get('status', 'unknown')} — "
                    f"{a.get('current_tasks', 0)} tasks"
                )
            return "\n".join(lines)
        return "Agents (simulation):\n  No registered agents"

    def _agent_info(self, args) -> str:
        agent_id = getattr(args, "agent_id", None)
        if self.runtime:
            agent = self.runtime.get_agent(agent_id)
            if agent:
                caps = [c.get("name", c) for c in agent.get("capabilities", [])]
                return (
                    f"Agent: {agent.get('name', agent_id)}\n"
                    f"  ID: {agent.get('agent_id', 'N/A')}\n"
                    f"  Status: {agent.get('status', 'N/A')}\n"
                    f"  Capabilities: {', '.join(caps) if caps else 'none'}\n"
                    f"  Tasks: {agent.get('current_tasks', 0)} current / "
                    f"{agent.get('max_concurrent_tasks', 0)} max\n"
                    f"  Success Rate: {agent.get('historical_success_rate', 0):.0%}"
                )
        return f"Agent: {agent_id}\n  Status: not found (simulation)"

    def _cmd_health(self, args) -> str:
        if self.runtime:
            health = self.runtime.get_health()
            return (
                f"Zelos Runtime Health: {health.get('status', 'unknown')}\n"
                f"  Uptime: {health.get('uptime_seconds', 0):.0f}s\n"
                f"  Version: {health.get('version', 'N/A')}\n"
                f"  Kernel: {health.get('components', {}).get('kernel', 'N/A')}"
            )
        return "Zelos Runtime Health: healthy (simulation)\n  Version: 0.7.0"

    def _cmd_metrics(self, args) -> str:
        if self.runtime:
            metrics = self.runtime.get_metrics()
            goals = metrics.get("goals", {})
            tasks = metrics.get("tasks", {})
            agents = metrics.get("agents", {})
            events = metrics.get("events", {})
            return (
                f"Zelos Metrics:\n"
                f"  Goals: {goals.get('active', 0)} active, "
                f"{goals.get('completed_total', 0)} completed, "
                f"{goals.get('failed_total', 0)} failed\n"
                f"  Tasks: {tasks.get('in_flight', 0)} in-flight, "
                f"{tasks.get('completed_total', 0)} completed, "
                f"{tasks.get('failed_total', 0)} failed\n"
                f"  Agents: {agents.get('registered', 0)} registered, "
                f"{agents.get('connected', 0)} connected\n"
                f"  Events: {events.get('published_total', 0)} total"
            )
        return (
            "Zelos Metrics (simulation):\n"
            "  Goals: 0 active\n"
            "  Tasks: 0 in-flight\n"
            "  Agents: 0 registered\n"
            "  Events: 0 total"
        )

    def _cmd_plugin(self, args) -> str:
        subcmd = getattr(args, "plugin_command", None)
        if subcmd == "list":
            if self.runtime:
                plugins = self.runtime._plugin_manager.list_plugins()
                lines = [f"Plugins ({len(plugins)} total):"]
                for p in plugins:
                    lines.append(
                        f"  {p.manifest.plugin_id}: {p.manifest.plugin_type} "
                        f"({p.status.value if p.status else 'unknown'})"
                    )
                return "\n".join(lines)
            return "Plugins (simulation):\n  No active plugins"
        return "Usage: zelos plugin list"

    def _cmd_namespace(self, args) -> str:
        subcmd = getattr(args, "namespace_command", None)
        if subcmd == "list":
            return "Namespaces (simulation):\n  default — Default Namespace"
        return "Usage: zelos namespace list"

    def _cmd_config(self, args) -> str:
        subcmd = getattr(args, "config_command", None)
        if subcmd == "show":
            if self.runtime:
                return f"Configuration:\n{json.dumps(self.runtime.config, indent=2)}"
            return "Configuration (simulation):\n  zelos.yaml loaded"
        elif subcmd == "validate":
            return "Configuration valid (simulation)."
        return "Usage: zelos config {show|validate}"


def main():
    """Entry point for the zelos CLI."""
    cli = ZelosCLI()
    output = cli.run()
    if output:
        print(output)


if __name__ == "__main__":
    main()
