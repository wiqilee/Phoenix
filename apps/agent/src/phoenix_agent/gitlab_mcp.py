"""GitLab REST fallback client.

This module provides direct REST API calls for GitLab operations that
the official GitLab MCP server does not yet expose (raw job traces,
branch creation, file commits, pipeline triggers). For MCP-based tool
access, see `adk_agents.py` where the McpToolset is configured.
"""

from __future__ import annotations

from typing import Any

import gitlab
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from phoenix_agent.config import settings

log = structlog.get_logger(__name__)


class GitLabRESTClient:
    """REST fallback client for GitLab operations not covered by the MCP server.

    Read operations exposed to Gemini go through the MCP server (see adk_agents.py).
    This client handles the gaps: raw job traces, branch creation, file commits,
    pipeline triggers, and merge request creation via REST API + python-gitlab.
    """

    def __init__(self) -> None:
        self._gl = gitlab.Gitlab(
            url=settings.gitlab_base_url,
            private_token=settings.gitlab_token,
        )
        self._http = httpx.AsyncClient(
            base_url=settings.gitlab_base_url,
            headers={"PRIVATE-TOKEN": settings.gitlab_token},
            timeout=30.0,
        )
        log.info("phoenix.gitlab.initialized", base_url=settings.gitlab_base_url)

    # ----- Pipeline operations -----

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_pipeline(self, project_id: str, pipeline_id: int) -> dict[str, Any]:
        """Get details of a pipeline."""
        response = await self._http.get(
            f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
        )
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_pipeline_jobs(
        self, project_id: str, pipeline_id: int
    ) -> list[dict[str, Any]]:
        """Get all jobs in a pipeline."""
        response = await self._http.get(
            f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
        )
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_job_log(self, project_id: str, job_id: int) -> str:
        """Get the raw log output of a single job."""
        response = await self._http.get(
            f"/api/v4/projects/{project_id}/jobs/{job_id}/trace"
        )
        response.raise_for_status()
        return response.text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_commit_diff(
        self, project_id: str, commit_sha: str
    ) -> list[dict[str, Any]]:
        """Get the diff for a specific commit."""
        response = await self._http.get(
            f"/api/v4/projects/{project_id}/repository/commits/{commit_sha}/diff"
        )
        response.raise_for_status()
        return response.json()

    async def get_file_content(
        self, project_id: str, file_path: str, ref: str
    ) -> str:
        """Get the content of a file at a specific ref."""
        encoded_path = file_path.replace("/", "%2F")
        response = await self._http.get(
            f"/api/v4/projects/{project_id}/repository/files/{encoded_path}/raw",
            params={"ref": ref},
        )
        response.raise_for_status()
        return response.text

    # ----- Branch and MR operations -----

    async def create_branch(
        self, project_id: str, branch_name: str, ref: str
    ) -> dict[str, Any]:
        """Create a new branch from a ref."""
        response = await self._http.post(
            f"/api/v4/projects/{project_id}/repository/branches",
            params={"branch": branch_name, "ref": ref},
        )
        response.raise_for_status()
        return response.json()

    async def commit_files(
        self,
        project_id: str,
        branch: str,
        commit_message: str,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Commit one or more file changes to a branch.

        Actions follow GitLab's commit API format:
            [{"action": "update", "file_path": "...", "content": "..."}]
        """
        response = await self._http.post(
            f"/api/v4/projects/{project_id}/repository/commits",
            json={
                "branch": branch,
                "commit_message": commit_message,
                "actions": actions,
            },
        )
        response.raise_for_status()
        return response.json()

    async def create_merge_request(
        self,
        project_id: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        labels: list[str] | None = None,
        assignee_id: int | None = None,
    ) -> dict[str, Any]:
        """Open a merge request."""
        payload: dict[str, Any] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
        }
        if labels:
            payload["labels"] = ",".join(labels)
        if assignee_id:
            payload["assignee_id"] = assignee_id

        response = await self._http.post(
            f"/api/v4/projects/{project_id}/merge_requests",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def trigger_pipeline(
        self, project_id: str, ref: str
    ) -> dict[str, Any]:
        """Trigger a new pipeline run on a specific ref."""
        response = await self._http.post(
            f"/api/v4/projects/{project_id}/pipeline",
            json={"ref": ref},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()


# Singleton
_gitlab_client: GitLabRESTClient | None = None


def get_gitlab() -> GitLabRESTClient:
    """Get the singleton GitLab REST client."""
    global _gitlab_client
    if _gitlab_client is None:
        _gitlab_client = GitLabRESTClient()
    return _gitlab_client
