"""Phoenix Agent FastAPI application.

The HTTP layer is a thin wrapper around the ADK runtime. When a webhook
arrives, FastAPI delegates to the ADK Runner which orchestrates the
Phoenix multi-agent system. All actual reasoning, tool calling, and
state management happens inside ADK.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from phoenix_agent.adk_agents import get_root_agent
from phoenix_agent.config import settings
from phoenix_agent.memory import get_memory

log = structlog.get_logger(__name__)


# ----- Lifespan -----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the ADK Runner on startup."""
    log.info("phoenix.agent.starting", project=settings.gcp_project_id)

    session_service = InMemorySessionService()
    root_agent = get_root_agent()

    app.state.session_service = session_service
    app.state.runner = Runner(
        app_name="phoenix",
        agent=root_agent,
        session_service=session_service,
    )
    app.state.memory = get_memory()
    app.state.trace_subscribers = {}  # run_id -> asyncio.Queue

    log.info("phoenix.agent.ready", agent_name=root_agent.name)
    yield

    log.info("phoenix.agent.shutting_down")
    await app.state.memory.close()


# ----- App -----

app = FastAPI(
    title="Phoenix Agent",
    description="Autonomous GitLab pipeline repair agent built on Google ADK",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- Models -----

class TriggerRequest(BaseModel):
    """A request from the gateway when a GitLab webhook arrives."""

    project_id: str
    pipeline_id: int
    commit_sha: str
    ref: str
    triggered_by: str = "webhook"


class TriggerResponse(BaseModel):
    """Response to the trigger request."""

    run_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    gemini_model: str
    framework: str


# ----- Endpoints -----

@app.get("/")
async def root() -> dict[str, str]:
    """Service identification."""
    return {
        "service": "phoenix-agent",
        "version": "0.1.0",
        "author": "Wiqi Lee",
        "framework": "Google ADK (Agent Development Kit)",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        gemini_model=settings.gemini_model,
        framework="google-adk",
    )


@app.post("/trigger", response_model=TriggerResponse)
async def trigger_agent(request: TriggerRequest) -> TriggerResponse:
    """Trigger Phoenix on a failed pipeline.

    The ADK Runner orchestrates the full Phoenix multi-agent flow:
    Diagnostician -> Strategist -> Executor. This endpoint kicks off
    the run asynchronously and returns immediately.
    """
    log.info(
        "phoenix.agent.trigger_received",
        project_id=request.project_id,
        pipeline_id=request.pipeline_id,
    )

    run_id = str(uuid.uuid4())

    # Persist the run in Firestore before starting
    await app.state.memory.create_run(
        project_id=request.project_id,
        pipeline_id=request.pipeline_id,
        commit_sha=request.commit_sha,
        ref=request.ref,
        triggered_by=request.triggered_by,
    )

    # Build the initial prompt for the coordinator
    initial_prompt = f"""A GitLab pipeline has failed and needs repair.

Project ID: {request.project_id}
Pipeline ID: {request.pipeline_id}
Commit SHA: {request.commit_sha}
Branch (ref): {request.ref}

Please diagnose the failure, select a repair strategy, apply the fix,
and open a merge request if verification succeeds.
"""

    # Run the ADK pipeline in the background
    asyncio.create_task(_run_phoenix_pipeline(
        runner=app.state.runner,
        session_service=app.state.session_service,
        memory=app.state.memory,
        run_id=run_id,
        user_id=request.triggered_by,
        prompt=initial_prompt,
        request=request,
    ))

    return TriggerResponse(
        run_id=run_id,
        status="accepted",
        message=f"Phoenix multi-agent system started on pipeline {request.pipeline_id}",
    )


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Get the current state of a Phoenix run."""
    run = await app.state.memory.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/runs")
async def list_runs(limit: int = 20) -> dict[str, Any]:
    """List recent Phoenix runs."""
    runs = await app.state.memory.list_runs(limit=limit)
    return {"runs": runs, "count": len(runs)}


# ----- Background pipeline runner -----

async def _run_phoenix_pipeline(
    runner: Runner,
    session_service: InMemorySessionService,
    memory: Any,
    run_id: str,
    user_id: str,
    prompt: str,
    request: TriggerRequest,
) -> None:
    """Execute the ADK pipeline and stream events to memory."""
    session_id = f"phoenix-{run_id}"

    try:
        # Create a session for this run
        await session_service.create_session(
            app_name="phoenix",
            user_id=user_id,
            session_id=session_id,
        )

        content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        # Stream events from the ADK runner
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            await _record_event(memory, run_id, event)

        await memory.complete_run(run_id, "completed", {
            "session_id": session_id,
        })
        log.info("phoenix.pipeline.complete", run_id=run_id)

    except Exception as e:
        log.error("phoenix.pipeline.failed", run_id=run_id, error=str(e))
        await memory.complete_run(run_id, "failed", {"error": str(e)})


async def _record_event(memory: Any, run_id: str, event: Any) -> None:
    """Record an ADK event in the run trace."""
    entry: dict[str, Any] = {
        "agent": getattr(event, "author", "unknown"),
    }

    if hasattr(event, "content") and event.content:
        parts_text = []
        for part in event.content.parts or []:
            if hasattr(part, "text") and part.text:
                parts_text.append(part.text)
            elif hasattr(part, "function_call") and part.function_call:
                entry["tool_call"] = {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args or {}),
                }
            elif hasattr(part, "function_response") and part.function_response:
                entry["tool_result"] = {
                    "name": part.function_response.name,
                }
        if parts_text:
            entry["message"] = "\n".join(parts_text)

    if "message" in entry or "tool_call" in entry or "tool_result" in entry:
        entry["step"] = _infer_step(entry)
        await memory.append_trace(run_id, entry)


def _infer_step(entry: dict[str, Any]) -> str:
    """Guess the loop phase from an ADK event for dashboard display."""
    agent = entry.get("agent", "")
    if "diagnost" in agent.lower():
        return "DIAGNOSE"
    if "strategist" in agent.lower():
        return "STRATEGIZE"
    if "executor" in agent.lower():
        if "tool_call" in entry:
            tool = entry["tool_call"].get("name", "")
            if "verify" in tool or "trigger_verification" in tool:
                return "VERIFY"
            if "merge_request" in tool:
                return "DECIDE"
            return "EXECUTE"
        return "EXECUTE"
    return "INFO"
