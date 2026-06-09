# Phoenix - Devpost Submission

This document contains the text to paste into the Devpost submission form.

---

## Project tagline (140 chars max)

> Phoenix is an autonomous multi-agent system that diagnoses and repairs broken GitLab CI/CD pipelines without human intervention.

---

## Inspiration

Every engineer has been woken up at 2 AM because a pipeline broke. Most of those pipelines break for the same handful of reasons every time: dependency conflicts, lint errors, flaky tests, configuration drift. These are not creative problems. They are mechanical problems. They need pattern matching, not deep human reasoning.

The opportunity hit me when I read about the Google ADK and the MCP server ecosystem. Here was a framework purpose-built for coordinating multiple LLM agents, paired with a protocol that gives those agents safe, structured access to real tools. The pieces were all there. Someone just had to put them together for the CI/CD problem.

Phoenix is what that looks like when you take it seriously.

## What it does

Phoenix listens for GitLab pipeline failure webhooks. When one arrives, a coordinator agent built with Google ADK orchestrates three specialized sub-agents through a complete repair cycle:

1. **Diagnostician** reads the failure log and commit diff through the GitLab MCP server, classifies the failure into a category (dependency conflict, lint error, flaky test, configuration error), and assigns a confidence score.
2. **Strategist** consults Firestore memory for proven fixes from past runs of the same kind of failure, then selects the best repair strategy.
3. **Executor** applies the chosen fix in a Cloud Run sandbox, triggers a verification pipeline on a `phoenix/fix-*` branch, and opens a merge request with the full reasoning trace if verification passes.

Engineers watch the agents reason in real time through a web dashboard. Every tool call, every classification, every decision is visible and auditable. Phoenix never touches the main branch directly. The merge request still goes through a human review.

## How we built it

Phoenix is a five service monorepo deployed entirely on Google Cloud.

- **phoenix-agent** is a Python service built on the Google Agent Development Kit. It defines three `LlmAgent` sub-agents (Diagnostician, Strategist, Executor) under a `SequentialAgent` coordinator. Each agent gets its own instruction prompt and its own set of `FunctionTool` instances. ADK handles state passing between agents through output keys, automatic function calling with Gemini, and session management.

- **phoenix-gateway** is a Go service built on Fiber v2. It handles GitLab webhook intake, validates signatures, manages WebSocket fan-out to the dashboard, and proxies trigger requests to the agent service.

- **phoenix-parser** is a Rust service built on Axum and Tokio. It tokenizes large CI logs and extracts known error signatures so the Diagnostician gets clean, structured input instead of raw log text.

- **phoenix-runner** is a Python service that runs fix attempts in isolated sandboxes. In production, it spawns Cloud Run Jobs with no host secrets and no network access beyond the GitLab API.

- **phoenix-web** is a React + Vite + Tailwind dashboard. A custom WebSocket hook streams agent events as they happen and renders them as a live reasoning trace.

All five services deploy to Cloud Run. Memory persists in Firestore. Secrets live in Secret Manager. Container images go to Artifact Registry. Gemini 2.0 Flash runs in Vertex AI and is invoked through the ADK runtime.

## Challenges we ran into

**Getting ADK state transitions right.** The first version had every agent re-deriving state from the prompt. The right pattern turned out to be ADK output keys, where each sub-agent writes its result to a named slot in the session state and the next agent reads from there. This took a few iterations to get clean.

**MCP server vs REST API balance.** The GitLab MCP server is excellent for read operations but does not yet expose every write operation Phoenix needs. The compromise was to use MCP for everything it supports (which is most of the read path and some of the write path) and fall back to the python-gitlab REST client for the operations MCP does not cover yet. The agent code does not have to care which transport is used because both are wrapped behind the same `gitlab_mcp.py` module.

**Avoiding "third party orchestrators".** The hackathon rules are explicit that you cannot use frameworks that compete with the Google Cloud agent ecosystem. This meant no LangChain, no CrewAI, no AutoGen. ADK had to do all the orchestration. The challenge was resisting the temptation to reach for a familiar library when ADK was missing something. In the end, ADK did everything I needed once I understood its primitives properly.

**Firestore async semantics.** The `google-cloud-firestore` library's `AsyncClient` has some sharp edges around transactions and array unions. Building the memory layer required a few rewrites before the trace appending was reliable under concurrent writes.

## Accomplishments that we're proud of

- A real multi-agent system with three specialized agents collaborating, not a single LLM doing everything.
- A working memory layer that genuinely makes Phoenix faster on recurring failures, not just a nice idea.
- End to end observability. Every decision is streamed and inspectable.
- Full hackathon compliance by design, not by retrofit. ADK orchestration, Gemini reasoning, MCP integration, single-cloud deployment, all from day one.
- A four-language stack (Python, Go, Rust, TypeScript) that each picks the right tool for its job.

## What we learned

The most important lesson was that ADK is genuinely production-ready, not a toy. The `SequentialAgent` + `LlmAgent` + `FunctionTool` primitives compose cleanly. Function calling through ADK is more reliable than rolling your own with the raw Gemini API. Session state management saves you from a hundred bugs you would have written yourself.

The second lesson was that the MCP protocol is the right interface for agents to access external systems. Tools defined as typed Python functions, with docstrings that become the function descriptions Gemini sees, made the integration almost invisible from the agent code's perspective. The agent just calls a function. ADK handles the rest.

The third lesson was about scoping. Four well-built strategies that handle real failures beat ten half-built strategies that handle hypothetical ones. Better in than wide.

## What's next for Phoenix

Phoenix has a five phase roadmap that goes beyond the hackathon scope:

- **Phase 2:** GitHub Actions and Jenkins adapters, database migration rollback, container build failure strategies, Terraform plan error recovery.
- **Phase 3:** Cross repository memory. A fix that works in one repo becomes a recommendation everywhere it applies.
- **Phase 4:** Proactive mode. Phoenix predicts where the next failure will come from and opens preventative MRs before anything breaks.
- **Phase 5:** Self improvement. Phoenix grades its own past fixes by long term outcome and updates its strategy preferences based on what actually shipped.

The bigger thesis is that ADK plus MCP is a general-purpose pattern for building autonomous engineering agents that act inside real systems, not just chat. CI/CD repair is the first use case. There are dozens more.

## Built With

- google-adk
- gemini-2.0
- vertex-ai
- google-cloud-platform
- cloud-run
- firestore
- secret-manager
- gitlab-mcp
- python
- fastapi
- go
- fiber
- rust
- axum
- tokio
- typescript
- react
- vite
- tailwindcss
- docker

## Try it out

- 🎬 [Demo video on YouTube](https://youtu.be/dQw4w9WgXcQ)
- 💻 [Source on GitHub](https://github.com/wiqi-lee/phoenix)
- 🚀 [Live demo](https://phoenix.run.app)
