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

# Import each task's dedicated grader
from graders.grader_easy import grade as grade_easy
from graders.grader_medium import grade as grade_medium
from graders.grader_hard import grade as grade_hard


def _load_all_tasks() -> dict:
    from tasks.task_easy import TASK as EASY
    from tasks.task_medium import TASK as MEDIUM
    from tasks.task_hard import TASK as HARD

    return {
        EASY["task_id"]: EASY,
        MEDIUM["task_id"]: MEDIUM,
        HARD["task_id"]: HARD,
    }


# Maps each task_id to its dedicated grader function
TASK_GRADERS = {
    "syntax_fix_001": grade_easy,
    "logic_fix_001": grade_medium,
    "optimize_001": grade_hard,
}


class SQLDebugEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._all_tasks = _load_all_tasks()
        self._current_task = None
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._best_reward = 0.0
        self._prev_absolute_score = 0.0  # used for delta computation
        self._current_query = ""

    # sql_debug_environment.py — replace reset() return and step() return only

    def reset(self, task_id: str = None, **kwargs) -> SQLDebugObservation:
        if task_id is None:
            task_id = list(self._all_tasks.keys())[0]

        if task_id not in self._all_tasks:
            return SQLDebugObservation(
                task_id=task_id,
                error_message=f"Unknown task '{task_id}'. Available: {list(self._all_tasks.keys())}",
                available_tasks=list(self._all_tasks.keys()),
                metadata={},
            )

        self._current_task = self._all_tasks[task_id]
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._best_reward = 0.0
        self._prev_absolute_score = 0.0
        self._current_query = self._current_task["broken_query"]

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
            metadata={"feedback": "", "status": "ready"},  # ← feedback in metadata
        )

    def step(self, action: SQLDebugAction) -> SQLDebugObservation:
        # Auto-reset if not already initialized (handles session management issues)
        if self._current_task is None:
            self.reset()

        self._state.step_count += 1
        self._current_query = action.query

        run_result = run_query(
            self._current_task["schema_sql"],
            action.query,
        )

        task_id = self._current_task["task_id"]
        grader_fn = TASK_GRADERS.get(task_id, grade_easy)

        reward_dict = grader_fn(
            task=self._current_task,
            agent_query=action.query,
            run_result=run_result,
            prev_absolute_score=self._prev_absolute_score,
            step_count=self._state.step_count,
            max_steps=self._current_task.get("max_steps", 8),
        )

        self._prev_absolute_score = reward_dict["absolute_score"]
        self._best_reward = max(self._best_reward, reward_dict["absolute_score"])

        max_steps = self._current_task.get("max_steps", 8)
        done = (
            reward_dict["absolute_score"] >= 0.99 or self._state.step_count >= max_steps
        )

        return SQLDebugObservation(
            task_id=task_id,
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
            reward=reward_dict["value"],
            metadata={  # ← all extra data here
                "feedback": reward_dict["feedback"],
                "status": reward_dict["status"],
                "absolute_score": reward_dict["absolute_score"],
                "delta": reward_dict["delta"],
                "result_score": reward_dict["result_score"],
                "plan_score": reward_dict["plan_score"],
            },
        )

    @property
    def state(self) -> State:
        return self._state
