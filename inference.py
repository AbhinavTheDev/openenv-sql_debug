# inference.py
"""
SQL Debug & Optimizer — OpenEnv Inference Script

Mandatory stdout format:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...>
"""

import asyncio
import os
import textwrap
from typing import List, Optional

from openai import OpenAI
from client import SQLDebugEnv, SQLDebugAction

# ── Mandatory env vars (injected by evaluator on submission) ──────────────────
IMAGE_NAME   = os.getenv("LOCAL_IMAGE_NAME")
API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "llama-3.3-70b-versatile")

# ── Task + run config ─────────────────────────────────────────────────────────
TASK_NAME  = os.getenv("SQL_ENV_TASK", "syntax_fix_001")
BENCHMARK  = "sql-debug-optimizer"
MAX_STEPS  = 8       # well under 20 min limit; each step is ~2s
TEMPERATURE = 0.0    # deterministic = reproducible scores
MAX_TOKENS  = 400
SUCCESS_THRESHOLD = 0.5   # reward >= 0.5 = success


# ── Mandatory stdout loggers — DO NOT change field names or order ─────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    # action must be single-line — newlines break log parsing
    action_clean = action.replace("\n", " ").replace("\r", "").strip()
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action_clean} reward={reward:.2f} "
        f"done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── Prompt design ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert SQL engineer helping debug and optimize SQL queries.

    Rules (follow exactly):
    - Respond with ONLY the corrected SQL query.
    - No markdown, no code fences (no ```sql), no explanation.
    - No comments inside the SQL.
    - If the query has a syntax error, fix it first.
    - If the query has a logic bug (wrong JOIN, wrong WHERE), fix the logic.
    - If asked to optimize, replace correlated subqueries with CTEs using WITH.
    - Output raw SQL only — it will be executed directly.
""").strip()


def build_prompt(obs) -> str:
    """Build the user prompt from the current observation."""
    result_preview = str(obs.query_result[:3]) if obs.query_result else "empty / error"
    return textwrap.dedent(f"""
        TASK: {obs.target_description}

        DATABASE SCHEMA:
        {obs.schema_sql.strip()[:800]}

        CURRENT QUERY (this is broken or slow — fix it):
        {obs.current_query.strip()}

        ERROR: {obs.error_message or "none"}
        CURRENT RESULT (first 3 rows): {result_preview}
        STEP: {obs.step_count + 1} of {MAX_STEPS}

        Write the corrected SQL query:
    """).strip()


def call_llm(client: OpenAI, obs) -> str:
    """Ask the LLM for a better SQL query. Returns clean SQL string."""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_prompt(obs)},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        raw = (completion.choices[0].message.content or "").strip()

        # Strip markdown code fences if model adds them despite instructions
        if "```" in raw:
            lines = raw.split("\n")
            raw = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            ).strip()

        return raw if raw else "SELECT 1"

    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return "SELECT 1"


# ── Main loop ─────────────────────────────────────────────────────────────────

async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # Connect to the environment (Docker or local server)
    SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")
    env = SQLDebugEnv(base_url=SERVER_URL)

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        # Reset — get the broken query and task info
        result = await env.reset(task_id=TASK_NAME)
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            # Ask LLM for a better query
            sql_query = call_llm(client, obs)

            # Submit to environment
            result = await env.step(SQLDebugAction(query=sql_query))
            obs = result.observation

            reward = result.reward or 0.0
            done   = result.done
            error  = obs.error_message if obs.error_message else None

            rewards.append(reward)
            steps_taken = step

            log_step(
                step=step,
                action=sql_query,
                reward=reward,
                done=done,
                error=error,
            )

            if done:
                break

        # Score = best reward achieved (already 0.0–1.0 from grader)
        score = max(rewards) if rewards else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Episode error: {exc}", flush=True)

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)

        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())