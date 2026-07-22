# Planner Module — Acceptance Test Specification

## Module: LLM-based Planner

### PLNR-01: Basic Goal → ExecutionPlan Decomposition
- **Given:** Goal "Write a Python hello world function"
- **When:** Planner.plan(goal) is called with a mock LLM returning valid task JSON
- **Then:** Returns an ExecutionPlan with at least 1 Task
- **Assert:** plan.tasks >= 1, plan.goal_id matches, plan.status = "created"

### PLNR-02: Multi-Task Decomposition with Dependencies
- **Given:** Goal "Build a React landing page with tests"
- **When:** Planner decomposes
- **Then:** Returns 3+ Tasks with dependency edges
- **Assert:** plan.dependencies list is not empty, DAG is valid (no cycles)

### PLNR-03: All Tasks Have Required Capability
- **Given:** Any Goal
- **When:** Planner produces a plan
- **Then:** Every Task has a non-empty required_capability
- **Assert:** All task.required_capability strings are non-empty

### PLNR-04: DAG Validation — No Orphan Tasks
- **Given:** Plan with 5 Tasks
- **When:** Post-LLM validation runs
- **Then:** Tasks referenced in dependencies must exist in the plan
- **Assert:** No dangling dependency references

### PLNR-05: DAG Validation — Acyclicity
- **Given:** LLM returns a plan with a cycle T1→T2→T1
- **When:** Planner validates
- **Then:** Plan is rejected with an error
- **Assert:** ValidationError raised

### PLNR-06: Invalid LLM JSON → Graceful Error
- **Given:** LLM returns malformed JSON
- **When:** Planner parses the response
- **Then:** Plan rejected, error includes the raw response
- **Assert:** Exception contains "Failed to parse"

### PLNR-07: Empty Tasks Array → Rejected
- **Given:** LLM returns valid JSON but with empty tasks array
- **When:** Planner validates
- **Then:** Plan rejected
- **Assert:** ValidationError, "at least one task"

### PLNR-08: Missing task_id in LLM Output → Auto-Generated
- **Given:** LLM returns tasks without task_id fields
- **When:** Planner processes
- **Then:** task_ids are auto-generated as UUIDs
- **Assert:** Every task has a non-empty task_id

### PLNR-09: Duplicate task_id → Rejected
- **Given:** LLM returns two tasks with the same task_id
- **When:** Planner validates
- **Then:** Plan rejected
- **Assert:** ValidationError mentioning duplicate

### PLNR-10: Model Configuration — OpenAI Provider
- **Given:** Planner configured with provider="openai", model="gpt-4o", api_key="sk-xxx"
- **When:** Planner is initialized
- **Then:** Provider is correctly configured
- **Assert:** planner.provider_name == "openai", model == "gpt-4o"

### PLNR-11: Model Configuration — Anthropic Provider
- **Given:** provider="anthropic", model="claude-opus-4-8"
- **When:** Planner is initialized
- **Then:** Provider correctly configured
- **Assert:** planner.provider_name == "anthropic"

### PLNR-12: Model Configuration — Google Provider
- **Given:** provider="google", model="gemini-2.5-pro"
- **When:** Planner is initialized
- **Then:** Provider correctly configured
- **Assert:** planner.provider_name == "google"

### PLNR-13: Model Configuration — Custom Endpoint
- **Given:** provider="openai", base_url="https://my-proxy.com/v1"
- **When:** Planner is initialized
- **Then:** Provider uses custom base URL
- **Assert:** provider base_url matches

### PLNR-14: Unknown Provider → Error
- **Given:** provider="unknown-llm"
- **When:** Planner is initialized
- **Then:** ValueError raised
- **Assert:** "Unsupported provider"

### PLNR-15: Temperature Configurable
- **Given:** temperature=0.3 in config
- **When:** LLM is called
- **Then:** Request includes temperature=0.3
- **Assert:** temperature in request payload

### PLNR-16: Max Tokens Configurable
- **Given:** max_tokens=8000 in config
- **When:** LLM is called
- **Then:** Request includes max_tokens=8000
- **Assert:** max_tokens constraint respected

### PLNR-17: System Prompt Injection
- **Given:** system_prompt="You are a senior architect" in config
- **When:** LLM is called
- **Then:** System prompt is included in the request
- **Assert:** system prompt present

### PLNR-18: Replan — Add Tasks to Existing Plan
- **Given:** An existing ExecutionPlan, a failed task event
- **When:** Planner.replan(goal, current_plan, events)
- **Then:** New tasks are added to the plan without removing completed tasks
- **Assert:** new_tasks added, completed_tasks preserved

### PLNR-19: Mock Provider — Deterministic Output
- **Given:** MockLLMProvider with predefined response
- **When:** Planner.plan(goal)
- **Then:** Returns the exact predefined plan structure
- **Assert:** Output matches mock response exactly

### PLNR-20: Retry on LLM API Failure
- **Given:** LLM provider fails first call, succeeds on retry
- **When:** Planner.plan(goal) with max_retries=2
- **Then:** Planner retries and eventually succeeds
- **Assert:** Plan produced successfully after retry

### PLNR-21: Task description is meaningful
- **Given:** Goal "Write API tests"
- **When:** Planner decomposes
- **Then:** Each task.description is a non-empty, human-readable sentence
- **Assert:** All descriptions are non-empty strings with length > 10

### PLNR-22: Replan Preserves Plan Identity
- **Given:** Existing plan with plan_id, planner_id
- **When:** Replan is called
- **Then:** plan_id and planner_id remain unchanged
- **Assert:** plan.plan_id same, plan.version incremented

### PLNR-23: zelos.yaml Config Integration
- **Given:** Plugin config in zelos.yaml format with llm section
- **When:** Planner is loaded via PLM
- **Then:** Config is correctly parsed
- **Assert:** provider, model, api_key, temperature, max_tokens all match config

### PLNR-24: Capability Names Follow Naming Convention
- **Given:** LLM returns capability names
- **When:** Planner validates
- **Then:** At minimum checks that capability names are non-empty strings with domain.subdomain format
- **Assert:** All capabilities match expected pattern or at minimum are non-empty strings
