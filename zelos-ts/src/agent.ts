/**
 * Zelos TypeScript SDK — Agent base class.
 *
 * Extend BaseAgent and override declareCapabilities() + execute().
 * The Runtime owns everything else.
 */
import type { CapabilityDeclaration, Task, TaskResult } from "./schema.js";

export abstract class BaseAgent {
  protected config: Record<string, unknown>;
  public agentId: string | null = null;
  public runtimeEndpoint: string | null = null;

  constructor(config?: Record<string, unknown>) {
    this.config = config ?? {};
  }

  /** Return the capabilities this Agent provides. */
  abstract declareCapabilities(): CapabilityDeclaration[];

  /** Execute a Task and return the result. */
  abstract execute(task: Task): Promise<TaskResult>;

  /** Hook: reject Tasks this Agent should not handle. */
  validateTask(_task: Task): boolean {
    return true;
  }

  /** Called after successful registration with the Runtime. */
  onRegistered(agentId: string): void {
    this.agentId = agentId;
  }

  /** Called before the Agent is shut down. */
  onShutdown(): void {
    // Override to clean up resources
  }

  /** Send a heartbeat. Override to call the Runtime API. */
  heartbeat(): Record<string, string> {
    return { status: "ok" };
  }
}

/** Simple demo Agent. */
export class DemoAgent extends BaseAgent {
  declareCapabilities(): CapabilityDeclaration[] {
    return [
      {
        name: "code-generation.python",
        version: "1.0.0",
        description: "Generates Python code from task descriptions",
        tags: ["python", "demo"],
      },
    ];
  }

  async execute(task: Task): Promise<TaskResult> {
    return {
      status: "completed",
      artifact: {
        contentType: "application/json",
        content: {
          code: `# Generated for: ${task.description}\ndef hello():\n    return 'Hello from Zelos!'`,
          language: "python",
        },
      },
    };
  }
}
