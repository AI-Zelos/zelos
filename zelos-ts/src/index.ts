/**
 * Zelos TypeScript SDK
 *
 * Build Agents and submit Goals on the Zelos Multi-Agent Orchestration Runtime.
 *
 * @packageDocumentation
 */

// Schema types
export type {
  CapabilityDeclaration,
  TaskConstraints,
  Task,
  Artifact,
  MemoryContext,
  GoalResult,
  TaskResult,
} from "./schema.js";

// Agent base class
export { BaseAgent, DemoAgent } from "./agent.js";

// HTTP Client
export {
  ZelosClient,
  ZelosError,
  AuthenticationError,
  ConnectionError,
} from "./client.js";
