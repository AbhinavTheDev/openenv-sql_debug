# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the SQL Debug & Optimizer Environment.
"""

from typing import Any, Dict, List
from pydantic import Field
from openenv.core.env_server.types import Action, Observation


class SQLDebugAction(Action):
    """
    What the agent submits each step — just a SQL query string.
    The environment will run it, grade it, and return a new observation.
    """
    query: str = Field(..., description="The SQL query the agent wants to try")


class SQLDebugObservation(Observation):
    """
    What the agent sees after each step.
    Contains everything it needs to improve its next query.
    """
    task_id: str = Field(default="", description="Which task is active")
    schema_sql: str = Field(default="", description="CREATE TABLE statements for this task")
    current_query: str = Field(default="", description="Last query that was run")
    error_message: str = Field(default="", description="SQLite error if query failed, else empty string")
    query_result: List[Dict[str, Any]] = Field(default_factory=list, description="First 10 rows returned")
    execution_plan: str = Field(default="", description="EXPLAIN QUERY PLAN output")
    step_count: int = Field(default=0, description="How many steps taken so far")
    target_description: str = Field(default="", description="Plain English goal for this task")
    reward_so_far: float = Field(default=0.0, description="Best reward achieved this episode")
    available_tasks: List[str] = Field(default_factory=list, description="All task IDs you can reset to")