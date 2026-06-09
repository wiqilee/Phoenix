"""Fix strategies for Phoenix.

Each strategy is a self-contained module that knows how to attempt
a specific kind of repair. Strategies are registered here and selected
by the agent loop based on the diagnosis.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)


# ----- Strategy protocol -----

class Strategy(Protocol):
    """Protocol that every fix strategy must implement."""

    name: str
    description: str
    handles_categories: list[str]

    async def attempt(
        self,
        project_id: str,
        commit_sha: str,
        diagnosis: dict[str, Any],
        log_excerpt: str,
    ) -> dict[str, Any]:
        """Attempt to fix the failure.

        Returns a dict with:
            - branch_name: the new branch where the fix was applied
            - changes: a list of file changes made
            - explanation: a human readable summary
        """
        ...


# ----- Registry -----

from phoenix_agent.strategies.config import ConfigFixStrategy
from phoenix_agent.strategies.dependency import DependencyFixStrategy
from phoenix_agent.strategies.flaky_test import FlakyTestStrategy
from phoenix_agent.strategies.lint import LintFixStrategy

STRATEGIES: dict[str, Strategy] = {
    "regenerate_lockfile": DependencyFixStrategy(),
    "pin_dependency_version": DependencyFixStrategy(),
    "auto_format": LintFixStrategy(),
    "quarantine_flaky_test": FlakyTestStrategy(),
    "fix_env_var": ConfigFixStrategy(),
    "fix_ci_yaml": ConfigFixStrategy(),
}


def get_strategy(name: str) -> Strategy | None:
    """Look up a strategy by name."""
    return STRATEGIES.get(name)


def list_strategies() -> list[str]:
    """Return all registered strategy names."""
    return list(STRATEGIES.keys())
