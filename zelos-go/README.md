# Zelos Go SDK

Build Agents and submit Goals on the Zelos Multi-Agent Orchestration Runtime.

## Install

```bash
go get github.com/zelos/zelos-go
```

## Quick Start

```go
package main

import (
    "fmt"
    "github.com/zelos/zelos-go/client"
    "github.com/zelos/zelos-go/agent"
    "github.com/zelos/zelos-go/schema"
)

func main() {
    // Remote client
    c := client.New("http://localhost:9876", "zk-client-dev")
    health, _ := c.Health()
    fmt.Println(health["status"])

    // Build an Agent
    a := &agent.DemoAgent{BaseAgent: *agent.NewBaseAgent(nil)}
    caps := a.DeclareCapabilities()
    fmt.Printf("Agent provides: %s\n", caps[0].Name)
}
```

## Package Layout

| Package | Description |
|---------|-------------|
| `schema` | Data types: CapabilityDeclaration, Task, Artifact, etc. |
| `agent`  | Agent interface + BaseAgent + DemoAgent |
| `client` | HTTP client for remote Runtime (Goal/Agent/Admin APIs) |
