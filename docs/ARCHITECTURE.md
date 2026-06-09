# 🏗 Phoenix Architecture

> Deep technical documentation of how Phoenix works, with diagrams.

This document explains the full Phoenix architecture, from the moment a GitLab pipeline fails to the moment a merge request appears with a fix. Every diagram below is a Mermaid diagram and renders directly on GitHub.

---

## Table of Contents

- [System Overview](#system-overview)
- [The Multi-Agent Hierarchy](#the-multi-agent-hierarchy)
- [The Reasoning Loop](#the-reasoning-loop)
- [Request Flow: From Webhook to Merge Request](#request-flow-from-webhook-to-merge-request)
- [Service Communication](#service-communication)
- [Memory and Learning Flow](#memory-and-learning-flow)
- [Deployment Topology](#deployment-topology)
- [Compliance with Hackathon Rules](#compliance-with-hackathon-rules)

---

## System Overview

Phoenix is composed of five services. The agent service is the only one that does AI reasoning. The other four exist to support it: routing traffic, parsing logs, streaming updates to humans, and storing memory.

```mermaid
graph TB
    subgraph External["External Systems"]
        GitLab["GitLab.com<br/>Pipeline Failures"]
        Developer["Developer<br/>Watching Dashboard"]
    end

    subgraph GoogleCloud["Google Cloud Run"]
        Web["phoenix-web<br/>(React + Vite)"]
        Gateway["phoenix-gateway<br/>(Go + Fiber)"]
        Agent["phoenix-agent<br/>(Python + ADK)"]
        Parser["phoenix-parser<br/>(Rust + Axum)"]
    end

    subgraph GoogleAI["Google Cloud AI"]
        Gemini["Gemini 2.0<br/>via Vertex AI"]
        ADK["Agent Development Kit<br/>(Orchestration)"]
    end

    subgraph Storage["Google Cloud Storage"]
        Firestore["Firestore<br/>Run History + Memory"]
        Secrets["Secret Manager<br/>Tokens"]
    end

    GitLab -- "1. Webhook: pipeline failed" --> Gateway
    Gateway -- "2. Trigger agent" --> Agent
    Agent <-- "ADK Runtime" --> ADK
    ADK <-- "LLM calls" --> Gemini
    Agent -- "Parse log" --> Parser
    Agent -- "Store memory" --> Firestore
    Agent -- "Get secrets" --> Secrets
    Agent -- "5. Create MR" --> GitLab
    Gateway -- "3. Stream events" --> Web
    Web -- "4. Live trace" --> Developer

    style Gemini fill:#4285F4,stroke:#1a73e8,color:#fff
    style ADK fill:#34a853,stroke:#137333,color:#fff
    style Agent fill:#fbbc04,stroke:#ea8600,color:#000
    style GitLab fill:#fc6d26,stroke:#e24329,color:#fff
```

**Key design decisions:**

- **Multi-language by purpose.** Python for AI work (ADK is Python-first), Go for high-throughput HTTP and WebSocket fanout, Rust for the log parser where regex speed matters, TypeScript for the dashboard. Each language is used where it excels.
- **One cloud, one ecosystem.** Every service runs on Google Cloud Run. No third party orchestrators. This is both a hackathon rule and a clean architecture choice.
- **ADK is the orchestrator.** No LangChain, no LlamaIndex, no AutoGen, no CrewAI. The Google Agent Development Kit handles all multi-agent coordination.

---

## The Multi-Agent Hierarchy

Phoenix is a multi-agent system built using the ADK's `SequentialAgent` pattern. The coordinator runs three specialist agents in order, passing state between them.

```mermaid
graph TB
    Coordinator["🔥 phoenix_coordinator<br/>(SequentialAgent)"]

    subgraph Agents["Specialist Agents (LlmAgent)"]
        Diagnostician["🔍 diagnostician<br/><br/>Classifies the failure<br/>Outputs: category, signature, confidence"]
        Strategist["🧠 strategist<br/><br/>Selects repair strategy<br/>Checks memory for proven fixes"]
        Executor["🔧 executor<br/><br/>Applies fix, verifies, opens MR"]
    end

    subgraph Tools["ADK Tools (FunctionTool)"]
        T1["fetch_pipeline_details()"]
        T2["fetch_job_log()"]
        T3["fetch_commit_diff()"]
        T4["extract_error_signature()"]
        T5["recall_proven_strategy()"]
        T6["apply_fix_in_sandbox()"]
        T7["trigger_verification_pipeline()"]
        T8["create_merge_request()"]
    end

    Coordinator --> Diagnostician
    Coordinator --> Strategist
    Coordinator --> Executor

    Diagnostician -.uses.-> T1
    Diagnostician -.uses.-> T2
    Diagnostician -.uses.-> T3
    Diagnostician -.uses.-> T4
    Strategist -.uses.-> T5
    Executor -.uses.-> T6
    Executor -.uses.-> T7
    Executor -.uses.-> T8

    style Coordinator fill:#f97316,stroke:#c2410c,color:#fff
    style Diagnostician fill:#a855f7,stroke:#7e22ce,color:#fff
    style Strategist fill:#eab308,stroke:#a16207,color:#fff
    style Executor fill:#10b981,stroke:#047857,color:#fff
```

Each agent has:

1. **A focused instruction prompt** that defines its role
2. **A set of tools** it can call to gather information or take action
3. **A typed output** that flows to the next agent via ADK session state

This is the modern way to build agentic systems. The ADK handles state passing, tool invocation, retry logic, and observability natively.

---

## The Reasoning Loop

The classic six-step Phoenix loop. Each box is a phase that streams to the dashboard live so engineers can watch the agent work.

```mermaid
stateDiagram-v2
    [*] --> PERCEIVE
    PERCEIVE --> DIAGNOSE: Gather logs, diff, metadata
    DIAGNOSE --> CheckConfidence: Classify failure with Gemini
    CheckConfidence --> ESCALATE: confidence < 0.7
    CheckConfidence --> CheckMemory: confidence >= 0.7
    CheckMemory --> STRATEGIZE: No prior fix found
    CheckMemory --> STRATEGIZE_FAST: Memory hit (proven fix)
    STRATEGIZE --> EXECUTE: Pick strategy
    STRATEGIZE_FAST --> EXECUTE: Use proven strategy
    EXECUTE --> VERIFY: Apply fix in sandbox
    VERIFY --> DECIDE: Pipeline passes
    VERIFY --> Retry: Pipeline fails
    Retry --> STRATEGIZE: Try next strategy
    Retry --> ESCALATE: All strategies exhausted
    DECIDE --> Success: Open merge request
    Success --> RecordMemory: Save proven fix
    RecordMemory --> [*]
    ESCALATE --> [*]

    note right of CheckMemory
        Memory is the secret weapon.
        Second time a failure type
        appears, Phoenix skips the
        guesswork.
    end note

    note right of VERIFY
        Sandbox is isolated.
        Production is never
        touched directly.
    end note
```

**Why this shape works:**

- **Confidence gates prevent embarrassment.** Phoenix would rather escalate than apply a wrong fix.
- **Memory shortens the loop over time.** Every successful fix teaches the next run.
- **Retry with different strategies is bounded.** Three attempts max, then escalate. No infinite loops.
- **Every transition is observable.** Each arrow in the diagram corresponds to an event streamed to the dashboard.

---

## Request Flow: From Webhook to Merge Request

This is the full happy path, end to end. Read it top to bottom.

```mermaid
sequenceDiagram
    autonumber
    participant GL as GitLab
    participant GW as Gateway (Go)
    participant AG as Agent (Python + ADK)
    participant GM as Gemini
    participant FS as Firestore
    participant PR as Parser (Rust)
    participant WS as Dashboard

    GL->>+GW: POST /webhooks/gitlab<br/>{pipeline_id, status: failed}
    GW->>GW: Verify webhook secret
    GW-->>WS: Broadcast: pipeline_failed
    GW->>+AG: POST /trigger
    GW-->>-GL: 202 Accepted

    AG->>+FS: create_run()
    FS-->>-AG: run_id
    AG->>AG: Initialize ADK Session

    Note over AG,GM: Diagnostician Agent
    AG->>GL: fetch_pipeline_details()
    GL-->>AG: pipeline + jobs
    AG->>GL: fetch_job_log()
    GL-->>AG: raw log
    AG->>+PR: POST /parse
    PR-->>-AG: signature + excerpt
    AG->>+GM: Classify failure
    GM-->>-AG: {category, confidence, signature}
    AG-->>WS: Stream: DIAGNOSE event

    Note over AG,FS: Strategist Agent
    AG->>+FS: recall_proven_strategy()
    FS-->>-AG: best known strategy
    AG->>+GM: Select strategy
    GM-->>-AG: {strategy, rationale}
    AG-->>WS: Stream: STRATEGIZE event

    Note over AG,GL: Executor Agent
    AG->>GL: create_branch(phoenix/fix-*)
    AG->>GL: commit_files(fix)
    AG-->>WS: Stream: EXECUTE event
    AG->>GL: trigger_pipeline(fix_branch)
    GL-->>AG: pipeline running
    Note right of AG: ...wait for verification...
    GL-->>AG: pipeline passed
    AG-->>WS: Stream: VERIFY event
    AG->>GL: create_merge_request()
    GL-->>AG: MR !192 created
    AG-->>WS: Stream: DECIDE event

    AG->>FS: remember_fix(signature, strategy, success=true)
    AG->>FS: complete_run(success)
    AG-->>-GW: (background task done)
```

Every numbered arrow is a real network call. The total time, in practice, is two to five minutes for most pipeline failures.

---

## Service Communication

Inside the Phoenix cluster, services talk over HTTP. The dashboard talks to the gateway via WebSocket. Gemini calls go over gRPC. Firestore over its own SDK.

```mermaid
flowchart LR
    subgraph Browser["Developer Browser"]
        Dashboard["Phoenix Dashboard<br/>React"]
    end

    subgraph CloudRun["Google Cloud Run"]
        Gateway["Gateway<br/>:8080"]
        Agent["Agent<br/>:8000"]
        Parser["Parser<br/>:8001"]
        Web["Web<br/>:5173"]
    end

    subgraph Managed["Managed Services"]
        Gemini["Vertex AI<br/>Gemini"]
        Firestore[("Firestore")]
        Secrets["Secret Manager"]
    end

    External["GitLab"]

    Browser <-- "WebSocket (live events)" --> Gateway
    Browser -- "Initial page load" --> Web
    External -- "Webhook POST" --> Gateway
    Gateway -- "HTTP /trigger" --> Agent
    Agent -- "HTTP /parse" --> Parser
    Agent -- "gRPC" --> Gemini
    Agent -- "SDK" --> Firestore
    Agent -- "SDK" --> Secrets
    Agent -- "REST API v4" --> External

    style Browser fill:#1f2937,stroke:#374151,color:#f3f4f6
    style Gemini fill:#4285F4,stroke:#1a73e8,color:#fff
    style External fill:#fc6d26,stroke:#e24329,color:#fff
```

**Protocols summary:**

| From | To | Protocol | Why |
|------|-----|----------|-----|
| GitLab | Gateway | HTTPS POST | Webhook standard |
| Gateway | Agent | HTTP POST | Simple internal RPC |
| Agent | Parser | HTTP POST | Fast, easy debugging |
| Agent | Gemini | gRPC | Vertex AI SDK default |
| Agent | Firestore | gRPC | Firestore SDK default |
| Dashboard | Gateway | WebSocket | Real time streaming |

---

## Memory and Learning Flow

Phoenix gets smarter with every run. The memory subsystem is what makes that possible.

```mermaid
flowchart TB
    Start([New Failure Detected])
    Diagnose["Diagnose with Gemini<br/>Get signature: e.g. 'npm_eresolve_peer_dep'"]
    Lookup{"Query Firestore<br/>fixes collection<br/>for this signature"}

    FoundProven["Memory Hit<br/>Found proven strategy<br/>with 90% success rate"]
    NoMemory["No prior fix recorded"]

    UseProven["Use proven strategy<br/>Confidence: HIGH"]
    UseSuggested["Try Gemini's<br/>top suggested strategy<br/>Confidence: MEDIUM"]

    Execute["Apply fix in sandbox"]
    Verify{"Pipeline<br/>passes?"}

    Success["Record success<br/>signature -> strategy<br/>success_rate++"]
    Failure["Record failure<br/>signature -> strategy<br/>attempts++"]

    NextRun([Next time same failure<br/>appears, lookup succeeds<br/>and Phoenix is faster])

    Start --> Diagnose
    Diagnose --> Lookup
    Lookup -->|Hit| FoundProven
    Lookup -->|Miss| NoMemory
    FoundProven --> UseProven
    NoMemory --> UseSuggested
    UseProven --> Execute
    UseSuggested --> Execute
    Execute --> Verify
    Verify -->|Yes| Success
    Verify -->|No| Failure
    Success --> NextRun
    Failure --> NextRun

    style FoundProven fill:#10b981,stroke:#047857,color:#fff
    style NoMemory fill:#6b7280,stroke:#374151,color:#fff
    style Success fill:#10b981,stroke:#047857,color:#fff
    style Failure fill:#ef4444,stroke:#991b1b,color:#fff
```

**Firestore schema for `phoenix_fixes` collection:**

```typescript
{
  project_id: string,           // GitLab project path
  signature: string,            // From the parser, e.g. "npm_eresolve_peer_dep"
  strategy: string,             // Name of strategy that was tried
  attempts: number,             // How many times this combo has been tried
  successes: number,            // How many times it worked
  success_rate: number,         // successes / attempts
  first_seen: timestamp,
  last_seen: timestamp,
  last_ttr: number              // Last time-to-resolution in seconds
}
```

The combination `(project_id, signature)` is what makes memory team-specific. A fix that works at company A might not work at company B if their codebases differ. Phoenix respects that.

---

## Deployment Topology

All five services run on Cloud Run. Each is independently scalable. The agent and parser scale based on incoming work. The gateway scales based on dashboard connections.

```mermaid
graph TB
    subgraph Internet["Public Internet"]
        Users["Developers"]
        GLPub["GitLab.com"]
    end

    subgraph CR["Google Cloud Run (us-central1)"]
        subgraph PublicServices["Public Services"]
            WebSvc["phoenix-web<br/>Cloud Run<br/>min:0 max:10"]
            GwSvc["phoenix-gateway<br/>Cloud Run<br/>min:1 max:20"]
        end
        subgraph InternalServices["Internal Services"]
            AgentSvc["phoenix-agent<br/>Cloud Run<br/>min:1 max:5<br/>2 CPU / 2 GB"]
            ParserSvc["phoenix-parser<br/>Cloud Run<br/>min:0 max:10<br/>internal only"]
        end
    end

    subgraph DataPlane["Google Managed"]
        Gemini2["Vertex AI Gemini 2.0"]
        FS2[("Firestore Native")]
        SM["Secret Manager"]
        AR["Artifact Registry"]
    end

    Users -- HTTPS --> WebSvc
    Users -- WSS --> GwSvc
    GLPub -- HTTPS --> GwSvc
    GwSvc -- HTTP --> AgentSvc
    AgentSvc -- HTTP --> ParserSvc
    AgentSvc -- gRPC --> Gemini2
    AgentSvc -- gRPC --> FS2
    AgentSvc -- HTTPS --> GLPub
    AgentSvc -- gRPC --> SM
    CR -. pulls images .-> AR

    style PublicServices fill:#dbeafe,stroke:#1d4ed8,color:#000
    style InternalServices fill:#fef3c7,stroke:#a16207,color:#000
    style DataPlane fill:#dcfce7,stroke:#15803d,color:#000
```

**Scaling characteristics:**

- **Agent service** is the bottleneck because each run takes 2 to 5 minutes. Set `min_instances: 1` so the first webhook does not pay cold start cost.
- **Parser** is stateless and fast, can scale to zero between bursts.
- **Gateway** keeps WebSocket connections open, so it needs `min_instances: 1` whenever there are active dashboard users.
- **Web** is just static assets and an initial bundle, scales to zero happily.

---

## Compliance with Hackathon Rules

Phoenix is built to satisfy every mandatory hackathon requirement. This section maps the rules to the architecture.

```mermaid
graph LR
    subgraph Requirements["Hackathon Requirements"]
        R1["Built with Gemini"]
        R2["Built with Google Cloud<br/>Agent Builder ecosystem"]
        R3["Integrates GitLab<br/>MCP Server"]
        R4["No competing<br/>orchestrators"]
        R5["Web platform"]
        R6["New project during<br/>contest period"]
        R7["Open source<br/>(MIT license)"]
    end

    subgraph Architecture["How Phoenix Satisfies"]
        A1["Vertex AI Gemini 2.0 Flash<br/>in adk_agents.py"]
        A2["Google ADK (LlmAgent<br/>SequentialAgent, FunctionTool)"]
        A3["GitLab MCP via<br/>gitlab_mcp.py + tools/"]
        A4["No LangChain, LlamaIndex,<br/>CrewAI, or AutoGen anywhere"]
        A5["React dashboard<br/>on Cloud Run"]
        A6["First commit dated<br/>during contest window"]
        A7["LICENSE file at root"]
    end

    R1 --> A1
    R2 --> A2
    R3 --> A3
    R4 --> A4
    R5 --> A5
    R6 --> A6
    R7 --> A7

    style Requirements fill:#fef3c7,stroke:#a16207
    style Architecture fill:#dcfce7,stroke:#15803d
```

**What is intentionally absent from Phoenix:**

- ❌ LangChain (third party orchestrator)
- ❌ LlamaIndex (third party orchestrator)
- ❌ AutoGen (third party orchestrator)
- ❌ CrewAI (third party orchestrator)
- ❌ Vercel, Netlify, AWS Lambda, Azure Functions (competing cloud platforms)
- ❌ OpenAI API, Anthropic API, Cohere API (competing AI providers)

**What Phoenix uses:**

- ✅ Google ADK (Agent Development Kit) for all orchestration
- ✅ Vertex AI Gemini 2.0 Flash for all reasoning
- ✅ Google Cloud Run for all compute
- ✅ Google Firestore for all state
- ✅ GitLab MCP server + REST API for partner integration

---

## File-Level Reference

For developers reading the source, here is where to find each architectural concept in code:

| Concept | File |
|---------|------|
| Multi-agent definition | `apps/agent/src/phoenix_agent/adk_agents.py` |
| GitLab tools (MCP integration) | `apps/agent/src/phoenix_agent/tools/gitlab_tools.py` |
| Parser tools | `apps/agent/src/phoenix_agent/tools/parser_tools.py` |
| Fix strategies | `apps/agent/src/phoenix_agent/strategies/` |
| Firestore memory | `apps/agent/src/phoenix_agent/memory.py` |
| HTTP entry point | `apps/agent/src/phoenix_agent/main.py` |
| Webhook handler | `apps/gateway/internal/webhook/handler.go` |
| WebSocket hub | `apps/gateway/internal/websocket/hub.go` |
| Log signature extraction | `apps/parser/src/main.rs` |
| Dashboard trace view | `apps/web/src/components/ReasoningTrace.tsx` |

---

Made by [Wiqi Lee](https://x.com/wiqi_lee) for the Google Cloud Rapid Agent Hackathon 2026.
