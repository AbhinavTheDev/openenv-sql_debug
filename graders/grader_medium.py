# tasks/grader_medium.py
"""
Grader for logic_fix_001 — fix wrong JOIN type / WHERE logic.

Harder than easy: agent must get BOTH precision and recall right.
Extra penalty for wrong row count (catches SELECT * with no WHERE).
"""


def grade(
    task: dict,
    agent_query: str,
    run_result: dict,
    prev_absolute_score: float = 0.0,
    step_count: int = 1,
    max_steps: int = 8,
) -> dict:

    syntax_ok = run_result["error"] is None

    # ── Syntax ────────────────────────────────────────────────────────────────
    if not syntax_ok:
        absolute_score = 0.05
        delta = round(
            max(-0.3, min(0.5, absolute_score - prev_absolute_score)), 4
        )
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

    expected = task["expected_rows"]
    got = run_result["rows"]

    # ── F1 row score ──────────────────────────────────────────────────────────
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

    # ── Extra penalty for wrong row count ─────────────────────────────────────
    # Logic bugs typically show up as too many rows (LEFT JOIN returns NULLs)
    # Penalize harder than easy task to encourage precise reasoning
    row_count_penalty = 0.0
    if len(got) > len(expected):
        extra = len(got) - len(expected)
        row_count_penalty = min(0.25, extra * 0.08)

    # ── JOIN type hint score ──────────────────────────────────────────────────
    # Gives partial credit for using the right JOIN type even if rows are off
    # Avoids zero-reward cliff for agents that fix JOIN but have minor issues
    query_upper = agent_query.upper()
    join_score = 0.0
    if "INNER JOIN" in query_upper:
        join_score = 0.15   # using INNER JOIN is the right direction
    elif "LEFT JOIN" in query_upper:
        join_score = 0.0    # LEFT JOIN is the bug — no credit
    elif "JOIN" in query_upper:
        join_score = 0.05   # some join exists — small credit

    # ── Efficiency bonus ──────────────────────────────────────────────────────
    steps_remaining = max_steps - step_count
    efficiency_bonus = 0.0
    if result_score >= 0.99:
        efficiency_bonus = round(0.05 * (steps_remaining / max_steps), 4)

    # ── Absolute score — medium: syntax 10% + correctness 70% + join 15% + bonus 5% ──
    absolute_score = round(
        min(
            0.99,
            0.10 * 1.0
            + 0.70 * result_score
            + 0.15 * join_score
            + efficiency_bonus
            - row_count_penalty,
        ),
        4,
    )
    absolute_score = max(0.05, absolute_score)  # floor at 0.05

    # ── Delta ─────────────────────────────────────────────────────────────────
    delta = absolute_score - prev_absolute_score
    if abs(delta) < 0.001 and step_count > 1:
        delta -= 0.02
    delta = round(max(-0.3, min(0.5, delta)), 4)

    # ── Feedback ─────────────────────────────────────────────────────────────
    issues = []
    if "LEFT JOIN" in query_upper:
        issues.append("join_type: using LEFT JOIN includes rows with no matching department")
    if len(got) > len(expected):
        issues.append(f"extra_rows: got {len(got)} rows, expected {len(expected)} — filter too loose")
    if len(got) < len(expected) and len(got) > 0:
        issues.append(f"missing_rows: got {len(got)} rows, expected {len(expected)} — filter too strict")
    if result_score < 0.5:
        issues.append("result_rows: output does not match expected — check JOIN and WHERE")
    feedback = "; ".join(issues) if issues else "rows and join look correct"

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
        "plan_score": join_score,
        "delta": delta,
        "status": status,
        "feedback": feedback,
        "message": (
            f"{status} | abs={absolute_score:.3f} | delta={delta:+.3f} | "
            f"result={result_score:.0%} | join={join_score:.2f}"
        ),
    }