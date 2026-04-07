# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI server for the SQL Debug & Optimizer Environment.

Exposes the environment over HTTP + WebSocket so inference.py
(and the OpenEnv evaluator) can interact with it remotely.

Endpoints created automatically by openenv:
    POST /reset    — start new episode (optionally pass task_id in body)
    POST /step     — submit an action, get observation + reward
    GET  /state    — current episode state
    GET  /schema   — action/observation JSON schemas
    WS   /ws       — WebSocket for persistent low-latency sessions

Run locally:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload

Or via Docker (defined in Dockerfile):
    docker build -t sql-debug-env .
    docker run -p 8000:8000 sql-debug-env
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError(
        "openenv-core is required. Install with: pip install openenv-core"
    ) from e

try:
    from models import SQLDebugAction, SQLDebugObservation
    from .sql_debug_environment import SQLDebugEnvironment
except ModuleNotFoundError:
    from models import SQLDebugAction, SQLDebugObservation
    from sql_exp.server.sql_debug_environment import SQLDebugEnvironment


app = create_app(
    SQLDebugEnvironment,
    SQLDebugAction,
    SQLDebugObservation,
    env_name="sql_debug_optimizer",
    max_concurrent_envs=4,   # one per task running in parallel
)


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()