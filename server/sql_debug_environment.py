# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
SQL Debug & Optimizer Environment — server-side implementation.

The server runs this. The agent never touches this file directly.
It loads tasks, runs queries in SQLite, grades them, and returns observations.
"""

from uuid import uuid4
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SQLDebugAction, SQLDebugObservation
except ImportError:
    from models import SQLDebugAction, SQLDebugObservation

from runner import run_query
from grader import compute_reward


def _load_all_tasks() -> dict:
    """Load every task from the tasks/ folder into a dict keyed by task_id."""
    from tasks.task_easy import TASK as EASY
    from tasks.task_medium import TASK as MEDIUM
    from tasks.task_hard import TASK as HARD
    return {
        EASY["task_id"]:   EASY,
        MEDIUM["task_id"]: MEDIUM,
        HARD["task_id"]:   HARD,
    }


class SQLDebugEnvironment(Environment):
    """
    SQL Debug & Optimizer environment.

    The agent receives a broken or slow SQL query and must fix/optimize it.
    Each step the agent submits a new query — the environment runs it in
    SQLite, grades it (0.0–1.0), and returns the result as an observation.

    Three tasks:
        syntax_fix_001  (easy)   — fix typos in SQL keywords
        logic_fix_001   (medium) — fix wrong JOIN type causing bad results
        # optimize_001    (hard)   — rewrite correlated subquery as a CTE
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._all_tasks = _load_all_tasks()
        self._current_task = None
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._best_reward = 0.0
        self._current_query = ""

    # ── reset ────────────────────────────────────────────────────────────────

    def reset(self, task_id: str = None) -> SQLDebugObservation:
        """
        Start a new episode.
        Pass task_id to pick a specific task, or leave None for the default (easy).
        """
        if task_id is None:
            task_id = list(self._all_tasks.keys())[0]   # default: easy

        if task_id not in self._all_tasks:
            # Unknown task — return error observation instead of crashing
            return SQLDebugObservation(
                task_id=task_id,
                error_message=f"Unknown task_id '{task_id}'. Available: {list(self._all_tasks.keys())}",
                available_tasks=list(self._all_tasks.keys()),
            )

        self._current_task = self._all_tasks[task_id]
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._best_reward = 0.0
        self._current_query = self._current_task["broken_query"]

        # Run the broken query so the agent sees the starting error
        run_result = run_query(
            self._current_task["schema_sql"],
            self._current_query,
        )

        return SQLDebugObservation(
            task_id=task_id,
            schema_sql=self._current_task["schema_sql"],
            current_query=self._current_query,
            error_message=run_result["error"] or "",
            query_result=run_result["rows"][:10],
            execution_plan=run_result["plan"],
            step_count=0,
            target_description=self._current_task["target_description"],
            reward_so_far=0.0,
            available_tasks=list(self._all_tasks.keys()),
            done=False,
            reward=0.0,
        )

    # ── step ─────────────────────────────────────────────────────────────────

    def step(self, action: SQLDebugAction) -> SQLDebugObservation:
        """
        Agent submits a query.
        We run it, grade it, and return the new observation + reward.
        """
        if self._current_task is None:
            return SQLDebugObservation(
                error_message="Call reset() before step()",
                available_tasks=list(self._all_tasks.keys()),
                done=True,
                reward=0.0,
            )

        self._state.step_count += 1
        self._current_query = action.query

        # Run the query in SQLite
        run_result = run_query(
            self._current_task["schema_sql"],
            action.query,
        )

        # Grade it (returns dict with value, syntax_ok, result_match_pct, etc.)
        reward_dict = compute_reward(self._current_task, action.query, run_result)
        reward_value = reward_dict["value"]

        # Track the best reward this episode
        self._best_reward = max(self._best_reward, reward_value)

        # Episode ends on perfect score or max steps
        max_steps = self._current_task.get("max_steps", 8)
        done = (reward_value >= 0.99) or (self._state.step_count >= max_steps)

        return SQLDebugObservation(
            task_id=self._current_task["task_id"],
            schema_sql=self._current_task["schema_sql"],
            current_query=action.query,
            error_message=run_result["error"] or "",
            query_result=run_result["rows"][:10],
            execution_plan=run_result["plan"],
            step_count=self._state.step_count,
            target_description=self._current_task["target_description"],
            reward_so_far=self._best_reward,
            available_tasks=list(self._all_tasks.keys()),
            done=done,
            reward=reward_value,
        )

    # ── state ─────────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state