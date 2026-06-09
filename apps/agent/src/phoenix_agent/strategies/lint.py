"""Auto-format strategy: actually fixes lint/format errors and commits them.

This is the demo path. For the hackathon we make it concrete and reproducible
using Black on Python files: Black formats deterministically in-process (no
subprocess, no Node needed), so the fix is reliable on a clean container and a
red "black --check" pipeline turns green after the fix.

Flow:
  1. Read the failing commit's diff to find changed Python files.
  2. Fetch each file's content at the failing commit.
  3. Reformat with Black in-memory; keep only files that actually change.
  4. Create a phoenix/fix-* branch and COMMIT the reformatted files.
  5. Return the branch + the real list of changed files.

Other linters (ruff, prettier, eslint, gofmt) are detected and reported, but the
committed fix in this build is implemented for Black/Python. Extending to ruff is
a few lines (ruff exposes `ruff.format`); the others need a sandbox runner.
"""

from __future__ import annotations

from typing import Any

import structlog

from phoenix_agent.gitlab_mcp import get_gitlab

log = structlog.get_logger(__name__)

try:
    import black

    _BLACK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BLACK_AVAILABLE = False


class LintFixStrategy:
    """Auto-fixes lint/format errors and commits the result to a fix branch."""

    name = "auto_format"
    description = "Reformats offending files and commits the fix to a new branch"
    handles_categories = ["lint_error"]

    async def attempt(
        self,
        project_id: str,
        commit_sha: str,
        diagnosis: dict[str, Any],
        log_excerpt: str,
    ) -> dict[str, Any]:
        log.info(
            "phoenix.strategy.auto_format.start",
            project_id=project_id,
            commit_sha=commit_sha,
        )
        client = get_gitlab()
        linter = self._detect_linter(log_excerpt)
        branch_name = f"phoenix/fix-lint-{commit_sha[:8]}"

        # 1. Which files changed in the failing commit?
        diff = await client.get_commit_diff(project_id, commit_sha)
        candidate_paths = [
            d.get("new_path")
            for d in diff
            if d.get("new_path", "").endswith(".py") and not d.get("deleted_file")
        ]

        if not candidate_paths:
            return {
                "branch_name": branch_name,
                "linter": linter,
                "explanation": (
                    f"Detected {linter}, but no Python files changed in this commit, "
                    "so the auto-format strategy has nothing safe to fix here."
                ),
                "changes": [],  # -> Executor will escalate
            }

        if not _BLACK_AVAILABLE:
            raise RuntimeError(
                "black is not installed; add 'black>=24.0.0' to dependencies."
            )

        # 2 + 3. Fetch each file and reformat with Black; keep only real changes.
        actions: list[dict[str, str]] = []
        changes: list[dict[str, str]] = []
        for path in candidate_paths:
            original = await client.get_file_content(project_id, path, ref=commit_sha)
            try:
                formatted = black.format_str(original, mode=black.Mode())
            except Exception as e:  # noqa: BLE001 - syntax errors etc.
                log.warning("phoenix.strategy.auto_format.skip", path=path, error=str(e))
                continue
            if formatted != original:
                actions.append(
                    {"action": "update", "file_path": path, "content": formatted}
                )
                changes.append({"action": "auto_format", "tool": "black", "path": path})

        if not actions:
            return {
                "branch_name": branch_name,
                "linter": linter,
                "explanation": (
                    "Files were already Black-clean; no formatting changes to commit."
                ),
                "changes": [],  # -> Executor will escalate
            }

        # 4. Create the branch and commit the real fix.
        await client.create_branch(
            project_id=project_id, branch_name=branch_name, ref=commit_sha
        )
        await client.commit_files(
            project_id=project_id,
            branch=branch_name,
            commit_message=(
                "fix: auto-format with Black\n\n"
                f"Phoenix reformatted {len(actions)} file(s) to satisfy the lint job."
            ),
            actions=actions,
        )

        log.info(
            "phoenix.strategy.auto_format.committed",
            branch=branch_name,
            files=len(actions),
        )
        return {
            "branch_name": branch_name,
            "linter": linter,
            "explanation": (
                f"Ran Black on {len(actions)} changed Python file(s) and committed "
                f"the reformatted result to {branch_name}."
            ),
            "changes": changes,
        }

    def _detect_linter(self, log_excerpt: str) -> str:
        s = log_excerpt.lower()
        for needle in ("black", "ruff", "prettier", "eslint", "gofmt", "rustfmt", "clippy"):
            if needle in s:
                return needle
        return "black"
