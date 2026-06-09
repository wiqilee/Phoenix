"""Phoenix Runner - HTTP service that executes fixes in a sandbox.

For local development, this is a simple FastAPI service. In production,
the agent triggers Cloud Run Jobs that run this same code with stricter
isolation.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import structlog
from fastapi import FastAPI
from pydantic import BaseModel

log = structlog.get_logger(__name__)

app = FastAPI(title="Phoenix Runner", version="0.1.0")


class FixRequest(BaseModel):
    """A request to run a fix in the sandbox."""

    branch_name: str
    fix_command: str
    timeout_seconds: int = 300


class FixResponse(BaseModel):
    """The result of a sandboxed fix attempt."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    branch_name: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "phoenix-runner"}


@app.post("/run", response_model=FixResponse)
async def run_fix(request: FixRequest) -> FixResponse:
    """Run a fix command in a sandbox.

    In production this would run inside a Cloud Run Job with no network
    access beyond the GitLab API and no access to host secrets.
    """
    log.info(
        "phoenix.runner.starting",
        branch=request.branch_name,
        command=request.fix_command,
    )

    try:
        proc = await asyncio.create_subprocess_shell(
            request.fix_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=request.timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return FixResponse(
                success=False,
                stdout="",
                stderr="Sandbox execution timed out",
                exit_code=-1,
                branch_name=request.branch_name,
            )

        return FixResponse(
            success=proc.returncode == 0,
            stdout=stdout.decode("utf-8", errors="replace")[-4000:],
            stderr=stderr.decode("utf-8", errors="replace")[-4000:],
            exit_code=proc.returncode or 0,
            branch_name=request.branch_name,
        )

    except Exception as e:
        log.error("phoenix.runner.failed", error=str(e))
        return FixResponse(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=-2,
            branch_name=request.branch_name,
        )
