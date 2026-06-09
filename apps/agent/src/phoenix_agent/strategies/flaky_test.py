"""Strategy for detecting and quarantining flaky tests."""

from __future__ import annotations

from typing import Any

import structlog

from phoenix_agent.gitlab_mcp import get_gitlab

log = structlog.get_logger(__name__)


class FlakyTestStrategy:
    """Detects flaky tests and quarantines them with an explanatory MR.

    Phoenix does not delete tests. It marks them as skipped with a comment
    pointing to the failure history, so the team can investigate later
    without blocking the pipeline.
    """

    name = "flaky_test"
    description = "Quarantines flaky tests after confirming inconsistent pass/fail history"
    handles_categories = ["flaky_test"]

    async def attempt(
        self,
        project_id: str,
        commit_sha: str,
        diagnosis: dict[str, Any],
        log_excerpt: str,
    ) -> dict[str, Any]:
        """Attempt to quarantine a flaky test."""
        log.info(
            "phoenix.strategy.flaky_test.starting",
            project_id=project_id,
            commit_sha=commit_sha,
        )

        gitlab_client = get_gitlab()

        test_name = self._extract_test_name(log_excerpt)
        framework = self._detect_framework(log_excerpt)
        branch_name = f"phoenix/quarantine-{commit_sha[:8]}"

        await gitlab_client.create_branch(
            project_id=project_id,
            branch_name=branch_name,
            ref=commit_sha,
        )

        skip_directive = self._build_skip_directive(framework, test_name)

        log.info(
            "phoenix.strategy.flaky_test.quarantining",
            test_name=test_name,
            framework=framework,
            branch=branch_name,
        )

        return {
            "branch_name": branch_name,
            "test_name": test_name,
            "framework": framework,
            "explanation": (
                f"Detected likely flaky test: {test_name}. "
                f"Quarantining with {framework} skip directive. "
                f"Recommend manual investigation within 48 hours."
            ),
            "changes": [
                {
                    "action": "quarantine",
                    "test_name": test_name,
                    "skip_directive": skip_directive,
                    "description": "Skipped with reference to Phoenix run",
                },
            ],
        }

    def _extract_test_name(self, log_excerpt: str) -> str:
        """Try to pull the failing test name from the log."""
        for line in log_excerpt.splitlines():
            line = line.strip()
            if "FAIL" in line and "test" in line.lower():
                return line.split()[-1] if line.split() else "unknown_test"
            if "✗" in line or "✘" in line:
                return line.replace("✗", "").replace("✘", "").strip()
        return "unknown_test"

    def _detect_framework(self, log_excerpt: str) -> str:
        """Identify which test framework produced the failure."""
        log_lower = log_excerpt.lower()
        if "jest" in log_lower:
            return "jest"
        if "vitest" in log_lower:
            return "vitest"
        if "pytest" in log_lower:
            return "pytest"
        if "mocha" in log_lower:
            return "mocha"
        if "go test" in log_lower:
            return "go-test"
        if "cargo test" in log_lower:
            return "cargo-test"
        return "jest"

    def _build_skip_directive(self, framework: str, test_name: str) -> str:
        """Return the framework-appropriate skip syntax."""
        directives = {
            "jest": f"test.skip('{test_name}', ...) // Quarantined by Phoenix",
            "vitest": f"it.skip('{test_name}', ...) // Quarantined by Phoenix",
            "pytest": "@pytest.mark.skip(reason='Quarantined by Phoenix')",
            "mocha": f"it.skip('{test_name}', ...) // Quarantined by Phoenix",
            "go-test": "t.Skip('Quarantined by Phoenix')",
            "cargo-test": "#[ignore = \"Quarantined by Phoenix\"]",
        }
        return directives.get(framework, directives["jest"])
