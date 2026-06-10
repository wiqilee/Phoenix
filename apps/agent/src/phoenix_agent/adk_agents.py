"""Phoenix multi-agent system built on Google ADK.

This module defines the Phoenix agent hierarchy using the Agent Development Kit.

Partner integration (REQUIRED by the hackathon): the agents talk to the
**official GitLab MCP Server** through ADK's `McpToolset`. The MCP server
exposes GitLab tools (get_pipeline_jobs, get_merge_request_diffs,
create_merge_request, gitlab_search, semantic_code_search, ...) directly to
Gemini.

Where the GitLab MCP server does not (yet) expose an operation we need
(raw job trace, create branch, commit files, trigger pipeline), we use thin
GitLab REST FunctionTools as a documented fallback. This is the same hybrid
pattern the README describes.

Architecture:
    phoenix_coordinator (SequentialAgent)
    ├── diagnostician (LlmAgent) - classifies failures   [MCP + REST read]
    ├── strategist   (LlmAgent) - selects repair strategy [memory]
    └── executor     (LlmAgent) - applies fix & opens MR  [REST write + MCP MR]
"""

from __future__ import annotations

import os

import structlog
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from phoenix_agent.config import settings
from phoenix_agent.tools.gitlab_tools import (
    apply_fix_in_sandbox,
    fetch_commit_diff,
    fetch_job_log,
    recall_proven_strategy,
    trigger_verification_pipeline,
)
from phoenix_agent.tools.parser_tools import extract_error_signature

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# GitLab MCP Server toolset (THE mandatory partner integration)
# ---------------------------------------------------------------------------
# Connects to GitLab's official MCP server at https://<instance>/api/v4/mcp.
# On first run, `mcp-remote` performs an OAuth handshake (a browser window
# opens). Run the agent locally once to authorize before deploying.
#
# Prerequisites (per GitLab docs):
#   - GitLab Premium or Ultimate (a free Ultimate trial works for the demo)
#   - GitLab Duo enabled
#   - Beta & experimental features turned on in GitLab settings
#
# One shared instance is attached to the agents that need it. If you hit MCP
# session issues across agents, create a separate McpToolset per agent.

_GITLAB_INSTANCE = settings.gitlab_base_url.replace("https://", "").replace(
    "http://", ""
).rstrip("/")


def make_gitlab_mcp_toolset() -> McpToolset:
    """Build an McpToolset wired to the official GitLab MCP server."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "mcp-remote",
                    f"https://{_GITLAB_INSTANCE}/api/v4/mcp",
                    "--static-oauth-client-metadata",
                    '{"scope": "mcp"}',
                ],
            ),
            timeout=60,
        ),
    )


gitlab_mcp: McpToolset | None
if os.getenv("PHOENIX_DISABLE_MCP", "").strip() in {"1", "true", "TRUE", "yes"}:
    # Local development escape hatch: skip the MCP OAuth handshake entirely
    # and run on the REST fallback tools only. Set PHOENIX_DISABLE_MCP=1 in
    # the root .env to chat with the agents in the ADK Dev UI without a
    # GitLab Duo (Premium/Ultimate) account. Leave UNSET in production.
    gitlab_mcp = None
    log.warning("PHOENIX_DISABLE_MCP is set - GitLab MCP toolset disabled, using REST fallback tools only")
else:
    gitlab_mcp = make_gitlab_mcp_toolset()


def _tools(*items):
    """Build a tool list, silently dropping disabled (None) toolsets."""
    return [t for t in items if t is not None]


# ---------------------------------------------------------------------------
# Sub-agent: Diagnostician
# ---------------------------------------------------------------------------

DIAGNOSTICIAN_INSTRUCTION = """You are the Diagnostician for Phoenix, an autonomous CI/CD repair system.

Your job: read a failed GitLab pipeline and classify the root cause.

You have access to GitLab MCP tools and REST fallback tools:
- get_pipeline_jobs (MCP): list the jobs of the failed pipeline and find which failed
- get_merge_request_diffs (MCP): inspect changes when the failure is tied to an MR
- semantic_code_search / gitlab_search (MCP): understand the code involved
- fetch_job_log (REST): pull the RAW job trace for the failed job (MCP has no raw-trace tool)
- fetch_commit_diff (REST): list files changed in the failing commit
- extract_error_signature: turn the log into a stable signature string

Steps:
1. Call get_pipeline_jobs with the given pipeline_id to find the failed job(s).
2. Call fetch_job_log for the failed job_id to read the actual error.
3. Optionally fetch_commit_diff to see what changed.
4. Classify into ONE category:
   dependency_conflict | lint_error | flaky_test | config_error | resource_timeout | unknown

Produce:
1. category
2. confidence (0.0-1.0)
3. signature (e.g. "black_would_reformat", "npm_eresolve_peer_dep")
4. reasoning (2-3 sentences)
5. suggested_strategies (ordered list)

Be honest about uncertainty. If ambiguous, lower confidence and pick 'unknown'.
Better to escalate than guess wrong.
"""

diagnostician_agent = LlmAgent(
    name="diagnostician",
    model=settings.gemini_model,
    description="Classifies CI/CD pipeline failures by root cause",
    instruction=DIAGNOSTICIAN_INSTRUCTION,
    tools=_tools(
        gitlab_mcp,  # MCP: get_pipeline_jobs, get_merge_request_diffs, search...
        FunctionTool(func=fetch_job_log),  # REST gap: raw job trace
        FunctionTool(func=fetch_commit_diff),  # REST gap: commit file list
        FunctionTool(func=extract_error_signature),
    ),
    output_key="diagnosis",
)


# ---------------------------------------------------------------------------
# Sub-agent: Strategist
# ---------------------------------------------------------------------------

STRATEGIST_INSTRUCTION = """You are the Strategist for Phoenix.

You receive a diagnosis from the Diagnostician. Your job:
1. Call recall_proven_strategy(project_id, signature) to check memory.
2. Pick the best strategy.
3. Explain the choice.

Available strategies:
- auto_format          : lint/format errors with auto-fix support (e.g. black, ruff, prettier)
- regenerate_lockfile  : npm/yarn/pip dependency conflicts
- pin_dependency_version
- quarantine_flaky_test
- fix_env_var
- fix_ci_yaml
- escalate             : when no automated fix is safe

If memory returns a proven strategy with success_rate > 0.5, strongly prefer it.
Otherwise pick the most likely strategy from the diagnosis suggestions.

Output EXACTLY this JSON:
{
  "strategy": "<strategy_name>",
  "confidence": <0.0-1.0>,
  "rationale": "<one sentence>",
  "memory_hit": <true|false>
}
"""

strategist_agent = LlmAgent(
    name="strategist",
    model=settings.gemini_model,
    description="Selects the best repair strategy based on diagnosis and memory",
    instruction=STRATEGIST_INSTRUCTION,
    tools=[FunctionTool(func=recall_proven_strategy)],
    output_key="strategy_decision",
)


# ---------------------------------------------------------------------------
# Sub-agent: Executor
# ---------------------------------------------------------------------------

EXECUTOR_INSTRUCTION = """You are the Executor for Phoenix.

You receive a strategy selection from the Strategist. Your job:
1. apply_fix_in_sandbox(project_id, commit_sha, strategy_name, log_excerpt)
   -> this creates a phoenix/fix-* branch AND commits the real fix. It returns
      the branch name and the list of changed files.
2. trigger_verification_pipeline(project_id, branch_name)
   -> runs CI on the fix branch to confirm it is green.
3. If verification passes, call the MCP tool **create_merge_request** to open an
   MR from the fix branch into the target branch. Put the full reasoning trace
   (diagnosis + strategy + files changed) in the description.
4. Report the final outcome.

NEVER push to main directly. ALWAYS use the phoenix/fix-* branch.
If apply_fix_in_sandbox returns success=false, report an escalation, do not open an MR.

Output EXACTLY this JSON:
{
  "outcome": "success" | "failure" | "escalated",
  "merge_request_url": "<url or null>",
  "branch": "<branch name>",
  "summary": "<two sentences>"
}
"""

executor_agent = LlmAgent(
    name="executor",
    model=settings.gemini_model,
    description="Applies repair strategies and opens merge requests",
    instruction=EXECUTOR_INSTRUCTION,
    tools=_tools(
        FunctionTool(func=apply_fix_in_sandbox),  # REST: branch + commit real fix
        FunctionTool(func=trigger_verification_pipeline),  # REST: trigger CI
        gitlab_mcp,  # MCP: create_merge_request (partner write path)
    ),
    output_key="execution_result",
)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

phoenix_coordinator = SequentialAgent(
    name="phoenix_coordinator",
    description=(
        "Phoenix root coordinator. Orchestrates diagnosis, strategy selection, "
        "and execution for failed GitLab pipelines via the GitLab MCP server."
    ),
    sub_agents=[diagnostician_agent, strategist_agent, executor_agent],
)


def get_root_agent() -> SequentialAgent:
    """Return the root Phoenix coordinator agent."""
    return phoenix_coordinator
