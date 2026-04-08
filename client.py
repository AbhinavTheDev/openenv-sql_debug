# client.py
from typing import Dict, Optional
import httpx

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from models import SQLDebugAction, SQLDebugObservation


class SQLDebugEnv(EnvClient[SQLDebugAction, SQLDebugObservation, State]):
    def __init__(self, base_url: str = "http://localhost:8000", **kwargs):
        super().__init__(base_url=base_url, **kwargs)
        self._base_url = base_url.rstrip("/")

    # ── Override reset to send task_id in body ────────────────────────────────
    async def reset(self, task_id: Optional[str] = None, **kwargs) -> StepResult:
        payload = {}
        if task_id:
            payload["task_id"] = task_id

        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.post(
                f"{self._base_url}/reset",
                json=payload,
            )
            response.raise_for_status()
            return self._parse_result(response.json())

    # ── step payload ──────────────────────────────────────────────────────────
    def _step_payload(self, action: SQLDebugAction) -> Dict:
        return {"query": action.query}

    # — update _parse_result only

    def _parse_result(self, payload: Dict) -> StepResult[SQLDebugObservation]:
        obs_data = payload.get("observation", {})
        meta = obs_data.get("metadata", {})  # ← feedback lives here now

        observation = SQLDebugObservation(
            task_id=obs_data.get("task_id", ""),
            schema_sql=obs_data.get("schema_sql", ""),
            current_query=obs_data.get("current_query", ""),
            error_message=obs_data.get("error_message", ""),
            query_result=obs_data.get("query_result", []),
            execution_plan=obs_data.get("execution_plan", ""),
            step_count=obs_data.get("step_count", 0),
            target_description=obs_data.get("target_description", ""),
            reward_so_far=obs_data.get("reward_so_far", 0.0),
            available_tasks=obs_data.get("available_tasks", []),
            done=payload.get("done", False),
            reward=payload.get("reward", 0.0),
            metadata=meta,
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
