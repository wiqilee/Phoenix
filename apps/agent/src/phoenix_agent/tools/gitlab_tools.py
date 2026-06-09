"""GitLab REST fallback tools for Phoenix ADK agents.

The mandatory partner integration is the GitLab **MCP server** (wired in
adk_agents.py via McpToolset). These FunctionTools cover only the operations the
MCP server does not expose: raw job trace, commit file list, applying a fix to a
branch (create branch + commit), and triggering a verification pipeline.

Opening the merge request is done through the MCP tool `create_merge_request`,
not here, so the partner write path goes through MCP.
"""

from __future__ import annotations

from typing import Any

import structlog

from phoenix_agent.gitlab_mcp import get_gitlab
from phoenix_agent.memory import get_memory
from phoenix_agent.strategies import get_strategy

log = structlog.get_logger(__name__)


# ----- Read fallbacks (MCP has no raw-trace / commit-diff tool) -----

async def fetch_job_log(project_id: str, job_id: int) -> dict[str, str]:
    """Fetch the RAW log/trace of a failed job (not exposed by the MCP server).

    Args:
        project_id: The GitLab project ID (numeric or namespaced path).
        job_id: The failed job's numeric ID (from get_pipeline_jobs).

    Returns:
        The trimmed log text and basic stats.
    """
    log.info("phoenix.tools.fetch_job_log", project_id=project_id, job_id=job_id)
    client = get_gitlab()
    raw_log = await client.get_job_log(project_id, job_id)
    return {
        "log": raw_log[-8000:],  # last 8K to fit context
        "total_lines": str(len(raw_log.splitlines())),
        "size_bytes": str(len(raw_log)),
    }


async def fetch_commit_diff(project_id: str, commit_sha: str) -> dict[str, Any]:
    """List files changed in the failing commit.

    Args:
        project_id: The GitLab project ID.
        commit_sha: The commit SHA that triggered the failing pipeline.

    Returns:
        A list of changed file paths and a brief summary.
    """
    log.info("phoenix.tools.fetch_diff", project_id=project_id, commit_sha=commit_sha)
    client = get_gitlab()
    diff = await client.get_commit_diff(project_id, commit_sha)
    return {
        "files_changed": len(diff),
        "files": [
            {
                "path": d.get("new_path", "unknown"),
                "is_new": d.get("new_file", False),
                "is_deleted": d.get("deleted_file", False),
            }
            for d in diff[:30]
        ],
    }


# ----- Memory -----

async def recall_proven_strategy(project_id: str, signature: str) -> dict[str, Any]:
    """Look up a previously successful repair strategy for a failure signature.

    Args:
        project_id: The GitLab project ID where the failure occurred.
        signature: The failure signature string from the diagnosis.

    Returns:
        The proven strategy if one exists, otherwise a not-found marker.
    """
    log.info("phoenix.tools.recall_strategy", project_id=project_id, signature=signature)
    memory = get_memory()
    proven = await memory.recall_best_strategy(project_id=project_id, signature=signature)
    if proven:
        return {
            "found": True,
            "strategy": proven,
            "message": f"Memory hit: '{proven}' has worked for this signature before",
        }
    return {
        "found": False,
        "strategy": None,
        "message": "No prior fix recorded for this signature",
    }


# ----- Write: apply the real fix (create branch + commit changed files) -----

async def apply_fix_in_sandbox(
    project_id: str,
    commit_sha: str,
    strategy_name: str,
    log_excerpt: str,
) -> dict[str, Any]:
    """Apply a repair strategy: create a fix branch and COMMIT the real change.

    This is the part that actually edits code. The selected strategy fetches the
    offending files, computes the corrected content, creates a phoenix/fix-*
    branch, and commits the fix. main is never touched.

    Args:
        project_id: The GitLab project ID.
        commit_sha: The commit SHA that triggered the failing pipeline.
        strategy_name: Registered strategy to apply (e.g. "auto_format").
        log_excerpt: Trimmed log the strategy can inspect.

    Returns:
        success flag, branch name, the list of files actually changed, and an
        explanation. If nothing changed or the strategy is unknown, success=false.
    """
    log.info(
        "phoenix.tools.apply_fix",
        project_id=project_id,
        commit_sha=commit_sha,
        strategy=strategy_name,
    )
    strategy = get_strategy(strategy_name)
    if not strategy:
        return {"success": False, "error": f"Unknown strategy: {strategy_name}"}

    try:
        result = await strategy.attempt(
            project_id=project_id,
            commit_sha=commit_sha,
            diagnosis={},
            log_excerpt=log_excerpt,
        )
        changes = result.get("changes", [])
        if not changes:
            return {
                "success": False,
                "error": "Strategy produced no file changes; nothing to commit.",
                "branch_name": result.get("branch_name"),
            }
        return {
            "success": True,
            "branch_name": result.get("branch_name"),
            "changes": changes,
            "explanation": result.get("explanation"),
        }
    except Exception as e:  # noqa: BLE001
        log.error("phoenix.tools.apply_fix_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def trigger_verification_pipeline(
    project_id: str,
    branch_name: str,
) -> dict[str, Any]:
    """Trigger a fresh pipeline on the fix branch (MCP has no trigger tool).

    Args:
        project_id: The GitLab project ID.
        branch_name: The phoenix/fix-* branch to verify.

    Returns:
        The new pipeline ID and initial state, or an error.
    """
    log.info("phoenix.tools.verify", project_id=project_id, branch=branch_name)
    client = get_gitlab()
    try:
        pipeline = await client.trigger_pipeline(project_id, branch_name)
        return {
            "success": True,
            "pipeline_id": pipeline.get("id"),
            "status": pipeline.get("status"),
            "web_url": pipeline.get("web_url"),
        }
    except Exception as e:  # noqa: BLE001
        log.error("phoenix.tools.verify_failed", error=str(e))
        return {"success": False, "error": str(e)}
