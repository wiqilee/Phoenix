"""Firestore-backed memory store for agent runs and learned fixes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from google.cloud import firestore

from phoenix_agent.config import settings

log = structlog.get_logger(__name__)


class MemoryStore:
    """Persists agent runs, decisions, and learned fix patterns to Firestore."""

    def __init__(self) -> None:
        self._client = firestore.AsyncClient(project=settings.gcp_project_id)
        self._prefix = settings.firestore_collection_prefix
        log.info("phoenix.memory.initialized", project=settings.gcp_project_id)

    @property
    def _runs_collection(self) -> Any:
        return self._client.collection(f"{self._prefix}_runs")

    @property
    def _fixes_collection(self) -> Any:
        return self._client.collection(f"{self._prefix}_fixes")

    # ----- Run lifecycle -----

    async def create_run(
        self,
        project_id: str,
        pipeline_id: int,
        commit_sha: str,
        ref: str,
        triggered_by: str,
    ) -> str:
        """Create a new agent run and return its ID."""
        run_id = str(uuid.uuid4())
        await self._runs_collection.document(run_id).set({
            "run_id": run_id,
            "project_id": project_id,
            "pipeline_id": pipeline_id,
            "commit_sha": commit_sha,
            "ref": ref,
            "triggered_by": triggered_by,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "trace": [],
        })
        log.info("phoenix.memory.run_created", run_id=run_id)
        return run_id

    async def append_trace(self, run_id: str, entry: dict[str, Any]) -> None:
        """Append a step to the run's reasoning trace."""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        await self._runs_collection.document(run_id).update({
            "trace": firestore.ArrayUnion([entry]),
        })

    async def complete_run(
        self,
        run_id: str,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Mark a run as completed with a final status."""
        update = {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if result:
            update["result"] = result
        await self._runs_collection.document(run_id).update(update)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch a run by ID."""
        doc = await self._runs_collection.document(run_id).get()
        return doc.to_dict() if doc.exists else None

    async def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent runs, newest first."""
        query = (
            self._runs_collection
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [doc.to_dict() async for doc in query.stream()]

    # ----- Learned fixes (the magic) -----

    async def remember_fix(
        self,
        project_id: str,
        signature: str,
        strategy: str,
        success: bool,
        time_to_resolution_seconds: float,
    ) -> None:
        """Record a fix attempt for future pattern matching.

        The combination of project_id + signature is the key. Phoenix
        will query this collection before deciding which strategy to try
        on a new failure.
        """
        fix_id = f"{project_id}_{signature}_{strategy}"
        doc_ref = self._fixes_collection.document(fix_id)
        doc = await doc_ref.get()

        if doc.exists:
            data = doc.to_dict() or {}
            attempts = data.get("attempts", 0) + 1
            successes = data.get("successes", 0) + (1 if success else 0)
            await doc_ref.update({
                "attempts": attempts,
                "successes": successes,
                "success_rate": successes / attempts,
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "last_ttr": time_to_resolution_seconds,
            })
        else:
            await doc_ref.set({
                "project_id": project_id,
                "signature": signature,
                "strategy": strategy,
                "attempts": 1,
                "successes": 1 if success else 0,
                "success_rate": 1.0 if success else 0.0,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "last_ttr": time_to_resolution_seconds,
            })

    async def recall_best_strategy(
        self,
        project_id: str,
        signature: str,
    ) -> str | None:
        """Find the historically best strategy for this kind of failure.

        Returns the strategy name with the highest success rate, or None
        if no prior attempts exist.
        """
        query = (
            self._fixes_collection
            .where("project_id", "==", project_id)
            .where("signature", "==", signature)
            .order_by("success_rate", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        async for doc in query.stream():
            data = doc.to_dict() or {}
            if data.get("success_rate", 0) > 0.5:
                return data.get("strategy")
        return None

    async def close(self) -> None:
        """Close the Firestore client."""
        self._client.close()


# Singleton instance
_memory_store: MemoryStore | None = None


def get_memory() -> MemoryStore:
    """Get the singleton memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
