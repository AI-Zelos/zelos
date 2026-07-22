/**
 * Zelos TypeScript SDK — HTTP Client for remote Runtime access.
 *
 * Usage:
 *   const client = new ZelosClient("http://localhost:9876", "zk-client-dev");
 *   const health = await client.health();
 *   const goal = await client.submitGoal("Build a landing page");
 */
export class ZelosError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ZelosError";
  }
}

export class AuthenticationError extends ZelosError {
  constructor(message: string) {
    super(message);
    this.name = "AuthenticationError";
  }
}

export class ConnectionError extends ZelosError {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionError";
  }
}

export class ZelosClient {
  private baseUrl: string;
  private apiKey?: string;
  private timeout: number;

  constructor(baseUrl: string = "http://127.0.0.1:9876", apiKey?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.timeout = 30000;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) {
      h["Authorization"] = `Bearer ${this.apiKey}`;
    }
    return h;
  }

  private async request(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<Record<string, unknown>> {
    const url = `${this.baseUrl}${path}`;
    const init: RequestInit = {
      method,
      headers: this.headers(),
    };
    if (body) {
      init.body = JSON.stringify(body);
    }

    const resp = await fetch(url, init);
    if (resp.status === 401) {
      throw new AuthenticationError("Invalid API key");
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new ZelosError(
        `HTTP ${resp.status}: ${(err as Record<string, unknown>).error || resp.statusText}`,
      );
    }
    return resp.json() as Promise<Record<string, unknown>>;
  }

  // ── Goal API ──
  async submitGoal(description: string, options?: {
    priority?: string;
    budget?: number;
  }): Promise<Record<string, unknown>> {
    return this.request("POST", "/api/v1/goals", {
      description,
      priority: options?.priority ?? "medium",
      ...(options?.budget ? { budget: options.budget } : {}),
    });
  }

  async getGoalStatus(goalId: string): Promise<Record<string, unknown>> {
    return this.request("GET", `/api/v1/goals/${goalId}`);
  }

  async cancelGoal(goalId: string): Promise<Record<string, unknown>> {
    return this.request("DELETE", `/api/v1/goals/${goalId}`);
  }

  // ── Agent API ──
  async registerAgent(
    name: string,
    entrypoint: string,
    capabilities: Record<string, unknown>[],
  ): Promise<Record<string, unknown>> {
    return this.request("POST", "/api/v1/agents", {
      name,
      entrypoint,
      capabilities,
    });
  }

  async listAgents(): Promise<Record<string, unknown>> {
    return this.request("GET", "/api/v1/agents");
  }

  // ── Admin API ──
  async health(): Promise<Record<string, unknown>> {
    return this.request("GET", "/api/v1/health");
  }

  async metrics(): Promise<Record<string, unknown>> {
    return this.request("GET", "/api/v1/admin/metrics");
  }
}
