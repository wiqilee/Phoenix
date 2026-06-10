# Phoenix - Devpost Submission

This document contains the exact text to paste into the Devpost submission form.
Devpost's "About the project" field supports Markdown, so paste the About section as is.

---

## Project name

Phoenix

## Elevator pitch (tagline)

An autonomous multi-agent system that diagnoses broken GitLab CI/CD pipelines and ships the fix as a merge request before you even wake up.

---

## About the project (paste as Markdown)

## Inspiration

Every engineer I know has a story about a pipeline that broke at the worst possible time. Friday afternoon. The night before a release. 2 AM, with the on-call phone buzzing on the nightstand.

The frustrating part is that most of these failures are boring. A lockfile drifted out of sync. A linter complained about a new file. A flaky test failed on its third retry of the week. A senior engineer who has seen the pattern twenty times fixes it in under a minute. The expensive part is not the fix. It is the waiting: waiting for someone to wake up, open a laptop, read the log, and type the same three commands they typed last month.

When I read the Google ADK docs and saw that GitLab now ships an official MCP server, the idea clicked. Here was an agent framework built for multi-step reasoning, and a protocol that gives agents structured access to a real DevOps platform. The pieces for a self-healing pipeline already existed. Nobody had wired them together. So I did.

## What it does

Phoenix watches your GitLab projects. When a pipeline fails, all of this happens without anyone touching a keyboard:

1. GitLab fires a webhook to Phoenix.
2. The **Diagnostician** agent pulls the failed jobs, raw logs, and commit diff through the GitLab MCP server, classifies the failure (dependency conflict, lint error, flaky test, or configuration error), and assigns a confidence score.
3. The **Strategist** agent checks Firestore memory for fixes that worked on the same failure signature before, then selects a repair strategy.
4. The **Executor** agent applies the fix on a fresh `phoenix/fix-*` branch inside a sandbox, triggers a verification pipeline, and opens a merge request once CI goes green. The MR description carries the full reasoning trace.
5. If confidence is low or every strategy fails, Phoenix escalates with a diagnostic report instead of guessing.

By the time the on-call engineer checks their phone, the fix is already sitting in the review queue. A human still approves the merge. Phoenix never pushes to main.

Everything streams live to a web dashboard: every tool call, every classification, every decision. You can literally watch the agents think.

## The numbers behind the problem

A team of 50 developers loses roughly 6.5 hours per developer per week to broken pipelines, counting investigation, context switching, and delayed deploys. That is 16,250 hours a year. At a loaded cost of $150 per hour, the bill comes to about $2.4 million, spent on failures that mostly follow the same handful of patterns. Those patterns are exactly what Phoenix automates.

## How I built it

Phoenix is a five-service monorepo, written in four languages, deployed entirely on Google Cloud.

- **phoenix-agent** (Python, Google ADK). The brain. Three `LlmAgent` sub-agents run under a `SequentialAgent` coordinator. Each one has its own instruction prompt, its own toolset, and its own output key, so state flows between agents through ADK session state instead of prompt stuffing. Gemini 3 Flash does the reasoning through Vertex AI.
- **phoenix-gateway** (Go, Fiber). Receives GitLab webhooks, validates signatures, fans events out to the dashboard over WebSocket, and proxies trigger calls to the agent.
- **phoenix-parser** (Rust, Axum). CI logs can be enormous. The parser tokenizes them and extracts stable error signatures, so the Diagnostician reasons over clean structured input instead of megabytes of raw text.
- **phoenix-runner** (Python). Executes fix attempts in isolated Cloud Run Jobs with no host secrets.
- **phoenix-web** (TypeScript, React, Tailwind). The live reasoning trace. A custom WebSocket hook renders agent events the moment they happen.

Memory lives in Firestore. Secrets live in Secret Manager. Images go to Artifact Registry, builds run on Cloud Build, and all compute is Cloud Run.

The GitLab integration is hybrid by design. The official MCP server covers most of the read path and the merge request write path. For the operations it does not expose yet (raw job traces, branch creation, commits, pipeline triggers), Phoenix falls back to thin REST tools. The agents never know or care which transport served a call.

## What makes Phoenix different

**It acts.** Most AI in this space stops at "your pipeline failed because of X." Phoenix replies with a merge request that fixes X. The gap between telling and doing is the whole product.

**It is a real multi-agent system.** Diagnostician, Strategist, and Executor are separate ADK agents with separate prompts, tools, and output schemas, coordinated sequentially. There is no monolithic mega-prompt and no third-party orchestrator anywhere in the stack.

**Every decision is auditable.** The dashboard shows the chain of reasoning, tool calls, and results in real time. If you do not trust a step, you can see exactly where it went wrong and take over.

**It learns your team's failures.** Every successful fix is stored in Firestore, keyed by failure signature and project. The second time the same signature shows up, the Strategist skips the deliberation and applies the proven fix. Resolution time on recurring failures keeps dropping.

**Safety is structural, not a setting.** Fixes run in sandboxes. Branches are always `phoenix/fix-*`. Merges always wait for a human. A confidence gate (default 0.7) routes ambiguous cases to escalation instead of letting the model guess, and after three failed strategies Phoenix stops and writes a report instead of thrashing.

## Challenges I ran into

ADK state passing took a few iterations. My first version had each agent re-deriving context from conversation history, which was fragile. The right pattern turned out to be output keys: each sub-agent writes structured output to a named slot in session state, and the next agent reads from there.

Balancing MCP against REST was a judgment call. I wanted the partner integration to be deep and real, not decorative, so MCP handles everything it can. The fallback layer exists only where the protocol has gaps today, and it is documented as exactly that.

Firestore's async client has sharp edges around transactions and array unions. The memory layer went through several rewrites before concurrent trace appends were reliable.

And I had to resist the muscle memory of reaching for LangChain. The rules require the Google agent ecosystem, and honestly, ADK needed no help. Sequential agents, function tools, and session state covered everything.

## Accomplishments I'm proud of

- Three specialized agents that genuinely collaborate through structured state handoffs, not one prompt pretending to be a team.
- A memory layer that measurably shortens resolution time on repeat failures.
- A four-language stack where every service uses the right tool for its job: Python for agents, Go for the gateway, Rust for log crunching, TypeScript for the UI.
- Compliance with the hackathon rules from the first commit rather than a retrofit: ADK orchestration, Gemini reasoning, deep GitLab MCP integration, and every service on Google Cloud.

## What I learned

ADK is production-grade. `SequentialAgent` plus `LlmAgent` plus `FunctionTool` composes cleanly, and ADK's function calling is more dependable than hand-rolling tool schemas against the raw Gemini API.

MCP is the right shape for agent-to-system access. A typed function with a clear docstring becomes a tool Gemini can call correctly, and the integration code almost disappears.

Scope discipline beats feature count. Four strategies that fix real failures well are worth more than ten that fix imaginary ones.

## What's next for Phoenix

- GitHub Actions and Jenkins adapters, so the same agents can heal pipelines on other platforms.
- Cross-repository memory: a fix proven in one repo becomes a recommendation in every repo that hits the same signature.
- Proactive mode: predict failures from pipeline history and open preventative MRs before anything breaks.
- Outcome-based self-grading: track whether Phoenix MRs were merged, reverted, or replaced, and feed that back into strategy selection.

CI/CD repair is the first use case. The pattern underneath, ADK agents acting on real systems through MCP, generalizes to a long list of engineering toil.

## Built for this hackathon's rules

- Powered by Gemini 3 Flash via Vertex AI, invoked through the ADK runtime.
- Orchestrated with Google ADK only. No LangChain, CrewAI, AutoGen, or any competing framework.
- Deep partner integration with the official GitLab MCP server, on both the read and write paths.
- Runs on the web: a React dashboard served from Cloud Run, backed by four more Cloud Run services.
- New project, built solo within the contest window, MIT licensed, public repository.

## Try it out

- Live agent API on Cloud Run: https://phoenix-agent-1018198774070.us-central1.run.app (interactive docs at /docs)
- Source on GitHub: https://github.com/wiqilee/Phoenix
- Demo video on YouTube: see the submission video above

## Go deeper: the article series

I am writing a three-part series on Medium that walks through the build in much more detail. This page gives you the what. The articles give you the how, with code.

**Inside Phoenix: a self-healing CI/CD agent on Google ADK and Gemini 3.** The full architecture story: why three agents instead of one, how session state flows between them, and what the coordinator actually does on every run. Read it on Medium: https://medium.com/@wiqilee/inside-phoenix-self-healing-ci-cd-agent-google-adk-gemini-3-1a2b3c4d5e6f

**MCP first, REST when you must.** How Phoenix integrates the official GitLab MCP server, where the protocol's coverage ends today, and how to wrap REST fallbacks so your agents never notice the difference. Read it on Medium: https://medium.com/@wiqilee/mcp-first-rest-when-you-must-gitlab-adk-2b3c4d5e6f7a

**My agent is not allowed to touch main.** The guardrail design behind Phoenix: sandboxed execution, confidence gates, branch isolation, and why human review is a feature rather than a limitation. Read it on Medium: https://medium.com/@wiqilee/my-agent-is-not-allowed-to-touch-main-guardrails-3c4d5e6f7a8b


---

## Built With (Devpost tags)

google-adk, gemini-3, vertex-ai, google-cloud, cloud-run, firestore, secret-manager, artifact-registry, cloud-build, gitlab, mcp, python, fastapi, go, fiber, rust, axum, tokio, typescript, react, vite, tailwindcss, docker, websockets

## Try it out (Devpost links)

- https://phoenix-agent-1018198774070.us-central1.run.app
- https://github.com/wiqilee/Phoenix
- https://gitlab.com/wiqilee/phoenix

## Describe your contribution (solo)

I built Phoenix alone, end to end, during the contest window. That covers the system design and every line of code across four languages: the Python ADK agent hierarchy with its three sub-agents, prompts, and tools; the Go gateway with webhook validation and WebSocket fan-out; the Rust log parser; the Python sandbox runner; and the React dashboard with the live reasoning trace. I also did all of the platform work: the Cloud Run deployment scripts, the Firestore memory schema, Secret Manager wiring, the GitLab MCP integration with its REST fallbacks, and the demo data seeding. The architecture diagrams, README, documentation, demo video, and this submission text are mine as well. No team, no starter template. Just me, the ADK docs, and a lot of coffee.
