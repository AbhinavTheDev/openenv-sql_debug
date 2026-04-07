# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# client.py
"""
SQL Debug Environment client.
This is what inference.py uses to talk to the running server.
"""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from models import SQLDebugAction, SQLDebugObservation


class SQLDebugEnv(EnvClient[SQLDebugAction, SQLDebugObservation, State]):
    """
    Client for the SQL Debug & Optimizer environment.

    Maintains a persistent WebSocket connection to the server.
    Each instance gets its own dedicated environment session.

    Usage (direct server):
        with SQLDebugEnv(base_url="http://localhost:8000") as env:
            result = env.reset()
            print(result.observation.target_description)
            result = env.step(SQLDebugAction(query="SELECT * FROM orders"))
            print(result.reward)

    Usage (Docker):
        env = SQLDebugEnv.from_docker_image("sql-debug-env:latest")
        try:
            result = env.reset()
            result = env.step(SQLDebugAction(query="SELECT * FROM orders WHERE amount > 500"))
        finally:
            env.close()
    """

    def _step_payload(self, action: SQLDebugAction) -> Dict:
        """Convert SQLDebugAction to JSON payload."""
        return {"query": action.query}

    def _parse_result(self, payload: Dict) -> StepResult[SQLDebugObservation]:
        """Parse server JSON response into a typed StepResult."""
        obs_data = payload.get("observation", {})

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
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """Parse server JSON response into a State object."""
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )