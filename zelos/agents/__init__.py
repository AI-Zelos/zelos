"""
Zelos Agent Providers — Built-in Agent implementations for various backends.

Each agent is a Zelos Runtime-compatible execution plugin:
  - Receive Task → Execute → Return Artifact → Exit

Available agents:
  - MiniSWEAgent: mini-SWE-agent integration (MIT, ~100 LOC core, 74%+ SWE-bench)
"""

from zelos.agents.mini_swe_agent import MiniSWEAgent

__all__ = ["MiniSWEAgent"]
