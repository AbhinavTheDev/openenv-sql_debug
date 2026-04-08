# inference.py
import asyncio
import os
import textwrap
from typing import List, Optional, Dict

from openai import OpenAI
from client import SQLDebugEnv, SQLDebugAction

# ── Env vars ──────────────────────────────────────────────────────────────────
IMAGE_NAME   = os.getenv("LOCAL_IMAGE_NAME")
API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
SERVER_URL   = os.getenv("SERVER_URL", "http://localhost:8000")

TASK_NAME         = os.getenv("SQL_ENV_TASK", "syntax_fix_001")
BENCHMARK         = "sql-debug-optimizer"
MAX_STEPS         = 8
TEMPERATURE       = 0.3
MAX_TOKENS        = 400
SUCCESS_THRESHOLD = 0.5


# ── Stdout loggers ────────────────────────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_clean = action.replace("\n", " ").replace("\r", "").strip()
    print(
        f"[STEP] step={step} action={action_clean} reward={reward:.2f} "
        f"done={str(done).lower()} error={error or 'null'}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert SQL engineer fixing and optimizing SQL queries.

STRICT OUTPUT RULES:
- Output ONLY raw SQL. No markdown. No backticks. No explanation. No comments.
- Your output is executed directly against a SQLite database.
- If your previous attempt got negative reward, you made things worse — try differently.
- If reward is stalled (same score 2+ steps), change strategy significantly."""

TASK_CONTEXT = {
    "syntax_fix_001": "The query has typographical errors in SQL keywords.",
    "logic_fix_001":  "The query runs but returns incorrect rows due to a logic error.",
    "optimize_001":   "The query is correct but slow. Rewrite it to be faster.",
}

GRADUATED_HINTS = {
    "syntax_fix_001": [
        "",
        "Check the spelling of SQL keywords like SELECT, FROM, WHERE.",
        "Compare each word: SELECT FROM WHERE ORDER BY GROUP BY — fix any typos.",
        "The typos are: SELEC → SELECT, FORM → FROM, WERE → WHERE.",
    ],
    "logic_fix_001": [
        "",
        "The query returns more rows than expected. Check your JOIN type.",
        "LEFT JOIN includes rows even when no match exists. Consider INNER JOIN.",
        "Change LEFT JOIN to INNER JOIN to exclude employees with no matching department.",
    ],
    "optimize_001": [
        "",
        "The query uses a subquery that runs once per row — this is slow.",
        "Compute the per-user average once using GROUP BY, then JOIN the result.",
        "Use: WITH user_avg AS (SELECT user_id, AVG(amount) AS avg FROM transactions GROUP BY user_id) SELECT t.* FROM transactions t JOIN user_avg u ON t.user_id = u.user_id WHERE t.amount > u.avg AND t.status = 'completed'",
    ],
}


def get_hint_level(step: int, stall_count: int) -> int:
    if step <= 2 and stall_count < 2:
        return 0
    if step <= 4 and stall_count < 4:
        return 1
    if step <= 6:
        return 2
    return 3


def build_prompt(obs, step: int, stall_count: int, prev_delta: float) -> str:
    context  = TASK_CONTEXT.get(obs.task_id, "Fix the SQL query.")
    hint_level = get_hint_level(step, stall_count)
    hint     = GRADUATED_HINTS.get(obs.task_id, [""] * 4)[hint_level]
    result_preview = str(obs.query_result[:3]) if obs.query_result else "none"

    # ← read feedback from metadata dict, not obs.feedback
    meta     = obs.metadata or {}
    feedback = meta.get("feedback", "analyse the result yourself")

    reward_context = ""
    if step > 1:
        if prev_delta > 0.01:
            reward_context = f"Last change IMPROVED score (+{prev_delta:.2f}). Keep going."
        elif prev_delta < -0.01:
            reward_context = f"Last change WORSENED score ({prev_delta:.2f}). Revert and try differently."
        else:
            reward_context = f"Last change had NO EFFECT (delta={prev_delta:.2f}). Try a completely different approach."

    hint_block = f"\nHINT: {hint}" if hint else ""

    return textwrap.dedent(f"""
        TASK: {context}
        {reward_context}{hint_block}

        SCHEMA:
        {obs.schema_sql.strip()[:600]}

        CURRENT QUERY:
        {obs.current_query.strip()}

        ERROR: {obs.error_message or "none"}
        RESULT (first 3 rows): {result_preview}
        FEEDBACK: {feedback}
        BEST SCORE SO FAR: {obs.reward_so_far:.3f}
        STEP: {step} of {MAX_STEPS}

        Write the corrected SQL:
    """).strip()


def call_llm(
    client: OpenAI,
    obs,
    history: List[Dict],
    step: int,
    stall_count: int,
    prev_delta: float,
) -> str:
    user_content = build_prompt(obs, step, stall_count, prev_delta)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_content})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        raw = (completion.choices[0].message.content or "").strip()
        if "```" in raw:
            raw = "\n".join(
                l for l in raw.split("\n")
                if not l.strip().startswith("```")
            ).strip()

        result = raw if raw else "SELECT 1"
        history.append({"role": "user",      "content": user_content})
        history.append({"role": "assistant", "content": result})
        return result

    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return "SELECT 1"


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env    = SQLDebugEnv(base_url=SERVER_URL)

    delta_rewards: List[float] = []   # per-step delta — logged in [STEP]
    abs_scores:    List[float] = []   # per-step absolute — used for final score
    history:       List[Dict]  = []
    stall_count  = 0
    prev_delta   = 0.0
    steps_taken  = 0
    score        = 0.0
    success      = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        # ── Reset ─────────────────────────────────────────────────────────────
        try:
            result = await env.reset(task_id=TASK_NAME)
        except Exception as e:
            print(f"[DEBUG] reset() failed: {e}", flush=True)
            raise

        obs = result.observation

        # ── Episode loop ──────────────────────────────────────────────────────
        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            sql_query = call_llm(
                client, obs, history,
                step=step,
                stall_count=stall_count,
                prev_delta=prev_delta,
            )

            result = await env.step(SQLDebugAction(query=sql_query))
            obs    = result.observation

            # delta reward from grader (can be negative)
            delta   = result.reward or 0.0
            # absolute score tracked via reward_so_far on observation
            abs_s   = obs.reward_so_far
            done    = result.done
            error   = obs.error_message if obs.error_message else None

            # Stall detection — reset on any meaningful change
            if abs(delta) < 0.01:
                stall_count += 1
            else:
                stall_count = 0

            prev_delta = delta
            delta_rewards.append(delta)
            abs_scores.append(abs_s)
            steps_taken = step

            log_step(step=step, action=sql_query, reward=delta, done=done, error=error)

            if done:
                break

        # Final score = best absolute score reached this episode
        score   = max(abs_scores) if abs_scores else 0.0
        score   = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Episode error: {exc}", flush=True)

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)

        log_end(success=success, steps=steps_taken, score=score, rewards=delta_rewards)


if __name__ == "__main__":
    asyncio.run(main())