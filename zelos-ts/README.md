# Zelos TypeScript SDK

Build Agents and submit Goals on the Zelos Multi-Agent Orchestration Runtime.

## Install

```bash
npm install @zelos/sdk
```

## Quick Start

```typescript
import { ZelosClient, BaseAgent, DemoAgent } from "@zelos/sdk";
import type { CapabilityDeclaration, Task, TaskResult } from "@zelos/sdk";

// ── Remote Client ──
const client = new ZelosClient("http://localhost:9876", "zk-client-dev");
const health = await client.health();
const goal = await client.submitGoal("Build a landing page", { priority: "high" });

// ── Build an Agent ──
class MyCoder extends BaseAgent {
  declareCapabilities(): CapabilityDeclaration[] {
    return [
      { name: "code-generation.python", version: "1.0.0", tags: ["python"] },
    ];
  }

  async execute(task: Task): Promise<TaskResult> {
    return {
      status: "completed",
      artifact: { contentType: "text/plain", content: "Done!" },
    };
  }
}
```

## API

### ZelosClient

| Method | Description |
|--------|-------------|
| `submitGoal(desc, opts?)` | Submit a Goal to the Runtime |
| `getGoalStatus(id)` | Get current Goal status |
| `cancelGoal(id)` | Cancel a running Goal |
| `registerAgent(name, entry, caps)` | Register an Agent |
| `listAgents()` | List all registered Agents |
| `health()` | Check Runtime health |
| `metrics()` | Get Runtime metrics |

### BaseAgent

Extend and override:
- `declareCapabilities()` → `CapabilityDeclaration[]`
- `execute(task: Task)` → `Promise<TaskResult>`
