"""Parser tools for Phoenix ADK agents.

These tools call the Rust log parser service to extract structured
signatures from raw CI logs.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from phoenix_agent.config import settings

log = structlog.get_logger(__name__)


async def extract_error_signature(log_text: str) -> dict[str, Any]:
    """Extract a normalized error signature from a raw CI log.

    Calls the Rust parser service which tokenizes the log and identifies
    known error patterns. The resulting signature can be used as a memory
    key for cross-run pattern matching.

    Args:
        log_text: The raw log output, or the last portion of it.

    Returns:
        A dictionary with the extracted signature, error category hint,
        and the relevant log excerpt.
    """
    log.info("phoenix.tools.extract_signature", log_size=len(log_text))

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.parser_url}/parse",
                json={"log": log_text},
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "signature": data.get("signature", "unknown"),
                    "category_hint": data.get("category_hint", "unknown"),
                    "excerpt": data.get("excerpt", log_text[-2000:]),
                    "matched_patterns": data.get("matched_patterns", []),
                }
    except Exception as e:
        log.warning("phoenix.parser.unavailable", error=str(e))

    # Fallback to client-side simple matching
    return _fallback_signature(log_text)


def _fallback_signature(log_text: str) -> dict[str, Any]:
    """Simple fallback if the Rust parser is unreachable."""
    log_lower = log_text.lower()
    if "eresolve" in log_lower:
        return {
            "signature": "npm_eresolve_peer_dep",
            "category_hint": "dependency_conflict",
            "excerpt": log_text[-2000:],
            "matched_patterns": ["ERESOLVE"],
        }
    if "eslint" in log_lower:
        return {
            "signature": "eslint_lint_error",
            "category_hint": "lint_error",
            "excerpt": log_text[-2000:],
            "matched_patterns": ["eslint"],
        }
    if "test failed" in log_lower or "✗" in log_text:
        return {
            "signature": "test_failure",
            "category_hint": "flaky_test",
            "excerpt": log_text[-2000:],
            "matched_patterns": ["test failed"],
        }
    return {
        "signature": "unknown",
        "category_hint": "unknown",
        "excerpt": log_text[-2000:],
        "matched_patterns": [],
    }
