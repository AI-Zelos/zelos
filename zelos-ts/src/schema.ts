/**
 * Zelos TypeScript SDK — Schema types.
 *
 * Mirrors the Python zelos_sdk/schema.py definitions.
 * Matches JSON Schemas in docs/schema/.
 */

/** Capability declaration when registering an Agent. */
export interface CapabilityDeclaration {
  name: string;
  version: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
  outputSchema?: Record<string, unknown>;
  qos?: Record<string, unknown>;
  tags?: string[];
  requiredResources?: Record<string, unknown>;
  capacity?: number;
}

/** Task constraints for scheduler dispatch. */
export interface TaskConstraints {
  preferredAgentId?: string;
  excludedAgentIds?: string[];
  requiredTags?: string[];
  minSuccessRate?: number;
  timeoutMs?: number;
  maxRetries?: number;
}

/** A single unit of work within an Execution Plan. */
export interface Task {
  taskId: string;
  planId: string;
  description: string;
  requiredCapability: string;
  input?: Record<string, unknown>;
  expectedOutputSchema?: Record<string, unknown>;
  dependencies?: string[];
  constraints?: TaskConstraints;
  fallbackCapability?: string;
  priority?: string;
}

/** Artifact produced by an Agent after executing a Task. */
export interface Artifact {
  artifactId: string;
  taskId: string;
  agentId: string;
  contentType?: string;
  content?: unknown;
  contentRef?: string;
  sizeBytes?: number;
  verificationStatus?: string;
  executionMetadata?: Record<string, unknown>;
}

/** Context assembled from 6-layer Memory before Task dispatch. */
export interface MemoryContext {
  session: Record<string, unknown>;
  project: Record<string, unknown>;
  user: Record<string, unknown>;
  knowledge: Record<string, unknown>;
  execution: Record<string, unknown>;
  skill: Record<string, unknown>;
}

/** Result of a completed Goal. */
export interface GoalResult {
  goalId: string;
  status: string;
  progress: Record<string, unknown>;
  artifacts: Artifact[];
  events: Record<string, unknown>[];
}

/** Result of a Task execution (returned by Agent.execute). */
export interface TaskResult {
  status: "completed" | "failed";
  artifact?: {
    contentType: string;
    content: unknown;
  };
  error?: {
    code: string;
    message: string;
  };
}
