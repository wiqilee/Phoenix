"""Strategy for fixing CI configuration errors."""

from __future__ import annotations

from typing import Any

import structlog

from phoenix_agent.gitlab_mcp import get_gitlab

log = structlog.get_logger(__name__)


class ConfigFixStrategy:
    """Fixes GitLab CI YAML errors and environment variable issues.

    Handles:
    - Missing or misnamed environment variables
    - Malformed .gitlab-ci.yml
    - Incorrect job dependencies
    - Cache misconfiguration
    """

    name = "config"
    description = "Repairs GitLab CI configuration errors"
    handles_categories = ["config_error"]

    async def attempt(
        self,
        project_id: str,
        commit_sha: str,
        diagnosis: dict[str, Any],
        log_excerpt: str,
    ) -> dict[str, Any]:
        """Attempt to fix a CI configuration error."""
        log.info(
            "phoenix.strategy.config.starting",
            project_id=project_id,
            commit_sha=commit_sha,
        )

        gitlab_client = get_gitlab()

        issue_type = self._classify_config_issue(log_excerpt)
        branch_name = f"phoenix/fix-config-{commit_sha[:8]}"

        await gitlab_client.create_branch(
            project_id=project_id,
            branch_name=branch_name,
            ref=commit_sha,
        )

        log.info(
            "phoenix.strategy.config.applying",
            issue_type=issue_type,
            branch=branch_name,
        )

        return {
            "branch_name": branch_name,
            "issue_type": issue_type,
            "explanation": (
                f"Detected CI configuration issue: {issue_type}. "
                f"Applying targeted fix to .gitlab-ci.yml or related config."
            ),
            "changes": self._build_changes(issue_type),
        }

    def _classify_config_issue(self, log_excerpt: str) -> str:
        """Classify the specific kind of config error."""
        log_lower = log_excerpt.lower()
        if "is not defined" in log_lower or "variable" in log_lower:
            return "missing_env_var"
        if "yaml" in log_lower and ("error" in log_lower or "invalid" in log_lower):
            return "malformed_yaml"
        if "cache" in log_lower:
            return "cache_misconfiguration"
        if "stage" in log_lower or "needs" in log_lower:
            return "invalid_job_dependency"
        return "unknown_config_issue"

    def _build_changes(self, issue_type: str) -> list[dict[str, Any]]:
        """Build the list of changes appropriate to the issue type."""
        if issue_type == "missing_env_var":
            return [
                {
                    "action": "add_variable",
                    "file_path": ".gitlab-ci.yml",
                    "description": "Added missing environment variable declaration",
                }
            ]
        if issue_type == "malformed_yaml":
            return [
                {
                    "action": "reformat",
                    "file_path": ".gitlab-ci.yml",
                    "description": "Reformatted YAML to fix syntax errors",
                }
            ]
        if issue_type == "cache_misconfiguration":
            return [
                {
                    "action": "update_cache",
                    "file_path": ".gitlab-ci.yml",
                    "description": "Corrected cache key and paths",
                }
            ]
        return [
            {
                "action": "review",
                "file_path": ".gitlab-ci.yml",
                "description": "Manual review recommended",
            }
        ]
