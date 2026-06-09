"""Strategy for fixing dependency conflicts."""

from __future__ import annotations

from typing import Any

import structlog

from phoenix_agent.gitlab_mcp import get_gitlab

log = structlog.get_logger(__name__)


class DependencyFixStrategy:
    """Fixes npm, yarn, and pip dependency conflicts.

    Common failure signatures handled here:
    - ERESOLVE could not resolve dependency tree
    - peer dependency conflicts
    - lockfile out of sync with package.json
    - pip resolver backtracking failures
    """

    name = "dependency"
    description = "Regenerates lockfiles to resolve dependency conflicts"
    handles_categories = ["dependency_conflict"]

    async def attempt(
        self,
        project_id: str,
        commit_sha: str,
        diagnosis: dict[str, Any],
        log_excerpt: str,
    ) -> dict[str, Any]:
        """Attempt to fix a dependency conflict."""
        log.info(
            "phoenix.strategy.dependency.starting",
            project_id=project_id,
            commit_sha=commit_sha,
        )

        gitlab_client = get_gitlab()

        # Detect package manager from the log
        package_manager = self._detect_package_manager(log_excerpt)

        branch_name = f"phoenix/fix-deps-{commit_sha[:8]}"

        # Create a fix branch from the failed commit
        await gitlab_client.create_branch(
            project_id=project_id,
            branch_name=branch_name,
            ref=commit_sha,
        )

        # Build the fix command based on package manager
        fix_action = self._build_fix_action(package_manager)

        log.info(
            "phoenix.strategy.dependency.applying",
            package_manager=package_manager,
            branch=branch_name,
        )

        # In a real run, the sandbox executor would run the fix command and
        # return the resulting lockfile content. For the demo we record the
        # intended fix here so the agent loop knows what was attempted.
        return {
            "branch_name": branch_name,
            "package_manager": package_manager,
            "fix_action": fix_action,
            "explanation": (
                f"Detected {package_manager} dependency conflict. "
                f"Regenerating lockfile with conflict-resolution flags."
            ),
            "changes": [
                {
                    "action": "update",
                    "file_path": self._lockfile_for(package_manager),
                    "description": "Regenerated to resolve peer dependency conflicts",
                },
            ],
        }

    def _detect_package_manager(self, log_excerpt: str) -> str:
        """Identify which package manager produced this error."""
        log_lower = log_excerpt.lower()
        if "eresolve" in log_lower or "npm err" in log_lower:
            return "npm"
        if "yarn" in log_lower:
            return "yarn"
        if "pnpm" in log_lower:
            return "pnpm"
        if "pip" in log_lower or "resolutionimpossible" in log_lower:
            return "pip"
        if "go.sum" in log_lower or "go mod" in log_lower:
            return "go"
        if "cargo" in log_lower:
            return "cargo"
        return "npm"

    def _build_fix_action(self, package_manager: str) -> str:
        """Build the shell command that the sandbox will run."""
        commands = {
            "npm": "rm -f package-lock.json && npm install --legacy-peer-deps",
            "yarn": "rm -f yarn.lock && yarn install",
            "pnpm": "rm -f pnpm-lock.yaml && pnpm install",
            "pip": "pip-compile --upgrade requirements.in",
            "go": "go mod tidy",
            "cargo": "cargo update",
        }
        return commands.get(package_manager, commands["npm"])

    def _lockfile_for(self, package_manager: str) -> str:
        """Return the lockfile name for a given package manager."""
        lockfiles = {
            "npm": "package-lock.json",
            "yarn": "yarn.lock",
            "pnpm": "pnpm-lock.yaml",
            "pip": "requirements.txt",
            "go": "go.sum",
            "cargo": "Cargo.lock",
        }
        return lockfiles.get(package_manager, "package-lock.json")
