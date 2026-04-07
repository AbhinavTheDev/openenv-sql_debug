---
title: Sql Debug Environment Server
emoji: 🏒
colorFrom: pink
colorTo: red
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - sql
  - debugging
  - optimization
---

# 🏒 OpenEnv: SQL Debug Environment

An [OpenEnv](https://openenv.dev)-compliant environment where AI agents fix broken SQL queries and optimize slow ones against in-memory SQLite databases.

> ✅ **Validator:** `openenv validate` passes when the environment is wired up correctly
> 🚀 **Local API:** `http://localhost:8000`
> 📖 **Swagger UI:** `http://localhost:8000/docs`

---

## 🎯 Environment Description

This environment simulates the work of a SQL engineer who must repair syntax errors, correct logic bugs, and improve query performance. Agents receive a schema, a broken or slow query, and a natural-language target description. They submit SQL queries, observe the execution result and query plan, and are scored on correctness and efficiency.

The environment is intentionally practical: each task mirrors a real debugging pattern used in analytics, reporting, and data engineering workflows.

---

## 📋 Tasks

### Task 1 - Syntax Fix *(Easy)*
**Task ID:** `syntax_fix_001`

**Objective:** Fix a malformed query so it returns all orders where `amount > 500`.

| Field | Description |
|---|---|
| `schema` | `orders` table with `id`, `customer`, `amount`, `order_date` |
| `broken_query` | `SELEC * FORM orders WERE amount > 500` |
| `target` | Return all orders where amount is greater than 500 |

**Max steps:** 5 | **Difficulty:** Easy

---

### Task 2 - Logic Fix *(Medium)*
**Task ID:** `logic_fix_001`

**Objective:** Correct a join bug so only employees in valid departments are returned.

| Field | Description |
|---|---|
| `schema` | `employees` and `departments` tables |
| `broken_query` | Query uses `LEFT JOIN` but should exclude missing departments |
| `target` | Return employees in departments with budget > 400000 |

**Max steps:** 8 | **Difficulty:** Medium

---

### Task 3 - Query Optimization *(Hard)*
**Task ID:** `optimize_001`

**Objective:** Rewrite a correlated subquery into an efficient CTE or grouped subquery.

| Field | Description |
|---|---|
| `schema` | `transactions` table with generated sample rows |
| `broken_query` | Correlated subquery that scans per row |
| `target` | Return completed transactions above the user's average amount |

**Max steps:** 10 | **Difficulty:** Hard

---

## 🔌 API Reference

### Base URL
```text
http://localhost:8000
```

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/reset` | Start a new episode; pass `task_id` to choose a task |
| `POST` | `/step` | Submit a SQL query and receive the next observation |
| `GET` | `/state/{session_id}` | Inspect the current episode state |
| `GET` | `/schema` | View action, observation, and state schemas |
| `GET` | `/ws` | WebSocket endpoint for low-latency sessions |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |

---

## 🎮 Action Space

The agent submits a single SQL query each step.

```json
{
  "query": "SELECT * FROM orders WHERE amount > 500"
}
```

### Example Actions

```json
{ "query": "SELECT * FROM orders WHERE amount > 500" }

{ "query": "SELECT e.name, d.dept_name FROM employees e INNER JOIN departments d ON e.dept_id = d.id WHERE d.budget > 400000" }

{ "query": "WITH avg_amount AS (SELECT user_id, AVG(amount) AS avg_amount FROM transactions GROUP BY user_id) SELECT t.* FROM transactions t JOIN avg_amount a ON t.user_id = a.user_id WHERE t.status = 'completed' AND t.amount > a.avg_amount" }
```

---

## 📊 Observation Space

```json
{
  "task_id": "syntax_fix_001",
  "schema_sql": "CREATE TABLE orders (...)",
  "current_query": "SELEC * FORM orders WERE amount > 500",
  "error_message": "near \"SELEC\": syntax error",
  "query_result": [],
  "execution_plan": "",
  "step_count": 0,
  "target_description": "Return all orders where amount is greater than 500",
  "reward_so_far": 0.0,
  "available_tasks": ["syntax_fix_001", "logic_fix_001", "optimize_001"],
  "done": false,
  "reward": 0.05
}
```

---

## 💰 Reward Function

The reward is computed from syntax validity, result correctness, and query plan quality.

| Event | Reward |
|---|---|
| Query fails with syntax error | `0.05` |
| Query runs successfully | contributes to the main score |
| Correct row match on easy and medium tasks | up to `0.6` of the score |
| Good query plan on hard task | up to `0.2` of the score |
| Uses correlated-subquery pattern on hard task | heavy plan penalty |
| Excessively long query | length penalty |

Final scores are clamped to the range `[0.0, 1.0]`.

---

## 🚀 Setup & Usage

### Option 1 - Run Locally

```bash
pip install -e .
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
# Open http://localhost:8000/docs
```

### Option 2 - Run with Docker

```bash
docker build -t sql-debug-env -f server/Dockerfile .
docker run -p 8000:8000 sql-debug-env
curl http://localhost:8000/health
```

### Option 3 - Run the Inference Loop

```bash
export SERVER_URL=http://localhost:8000
export API_KEY=sk-...
python inference.py
```

The inference script defaults to `syntax_fix_001`, logs each step, and stops when the episode ends or the step budget is reached.

---

## 🏗️ Project Structure

```text
sql_exp/
├── client.py              # OpenEnv client wrapper
├── grader.py              # Reward computation
├── inference.py           # LLM-driven inference loop
├── models.py              # Action and observation models
├── openenv.yaml           # OpenEnv manifest
├── pyproject.toml         # Project metadata and dependencies
├── runner.py              # SQLite query runner
├── server/
│   ├── app.py             # FastAPI app and OpenEnv wiring
│   ├── Dockerfile         # Container definition
│   └── sql_debug_environment.py  # Core environment logic
├── tasks/
│   ├── task_easy.py       # Syntax-fix task
│   ├── task_medium.py     # Join logic task
│   └── task_hard.py       # Query optimization task
├── test.py                # Manual websocket smoke test
└── README.md              # Project overview
```

---

## 🛠️ Tech Stack

- **Python 3.10+** - Runtime
- **FastAPI** - HTTP framework
- **OpenEnv Core** - Environment server and client primitives
- **SQLite** - Query execution engine
- **Uvicorn** - ASGI server
- **Docker** - Containerization

---

## 📝 License

BSD-style license, matching the source headers in this repository.
