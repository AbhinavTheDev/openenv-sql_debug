# tasks/grader_easy.py
"""
Grader for syntax_fix_001 — fix typos in SQL keywords.
Reward is shaped on: syntax correctness + F1 row match + step efficiency.
"""


def grade(
    task: dict,
    agent_query: str,
    run_result: dict,
    prev_absolute_score: float = 0.0,
    step_count: int = 1,
    max_steps: int = 5,
) -> dict:
    """
    Easy task grader. Pure row-match scoring — no plan check needed.

    Reward components:
        syntax_score   : 0.0 or 1.0 — did the query run at all?
        result_score   : 0.0–1.0    — F1 of returned vs expected rows
        efficiency_bonus: 0.0–0.05  — small bonus for solving early
        delta          : absolute_score - prev_absolute_score
    """

    syntax_ok = run_result["error"] is None

    # ── Syntax ────────────────────────────────────────────────────────────────
    if not syntax_ok:
        absolute_score = 0.05   # tiny gradient so agent knows to fix syntax first
        delta = absolute_score - prev_absolute_score
        delta = max(-0.3, min(0.5, delta))
        return {
            "value": delta,
            "absolute_score": absolute_score,
            "syntax_ok": False,
            "result_score": 0.0,
            "plan_score": 0.0,
            "delta": delta,
            "status": "syntax_error",
            "feedback": f"syntax_error: {run_result['error'][:100]}",
            "message": f"syntax_error | abs=0.050 | delta={delta:+.3f}",
        }

    # ── Row matching (F1) ─────────────────────────────────────────────────────
    expected = task["expected_rows"]
    got = run_result["rows"]

    if not got:
        result_score = 0.0
    else:
        correct_returned = sum(1 for row in got if row in expected)
        correct_expected = sum(1 for row in expected if row in got)

        precision = correct_returned / max(len(got), 1)
        recall    = correct_expected / max(len(expected), 1)

        if precision + recall > 0:
            result_score = 2 * precision * recall / (precision + recall)
        else:
            result_score = 0.0

    # ── Efficiency bonus ──────────────────────────────────────────────────────
    steps_remaining = max_steps - step_count
    efficiency_bonus = 0.0
    if result_score >= 0.99:
        efficiency_bonus = round(0.05 * (steps_remaining / max_steps), 4)

    # ── Absolute score — easy: syntax 15% + correctness 80% + bonus 5% ───────
    absolute_score = round(
        min(0.99, 0.15 * 1.0 + 0.80 * result_score + efficiency_bonus), 4
    )

    # ── Delta reward — the RL signal ──────────────────────────────────────────
    delta = absolute_score - prev_absolute_score
    if abs(delta) < 0.001 and step_count > 1:
        delta -= 0.02   # stall penalty — discourages repeating same query
    delta = round(max(-0.3, min(0.5, delta)), 4)

    # ── Feedback for agent ────────────────────────────────────────────────────
    issues = []
    if result_score < 0.5:
        issues.append("result_rows: returned rows do not match expected — check your WHERE clause")
    elif result_score < 0.99:
        issues.append(f"result_rows: partial match ({result_score:.0%}) — some rows still wrong")
    if len(got) > len(expected):
        issues.append(f"extra_rows: returned {len(got)} rows but expected {len(expected)}")
    feedback = "; ".join(issues) if issues else "rows match — looking good"

    status = (
        "solved"     if absolute_score >= 0.99
        else "improving" if delta > 0.01
        else "regression" if delta < -0.01
        else "stalled"
    )

    return {
        "value": delta,
        "absolute_score": absolute_score,
        "syntax_ok": True,
        "result_score": result_score,
        "plan_score": 0.0,
        "delta": delta,
        "status": status,
        "feedback": feedback,
        "message": (
            f"{status} | abs={absolute_score:.3f} | delta={delta:+.3f} | "
            f"result={result_score:.0%}"
        ),
    }