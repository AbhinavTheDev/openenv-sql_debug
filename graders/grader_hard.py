# tasks/grader_hard.py
"""
Grader for optimize_001 — replace correlated subquery with CTE.

Unlike easy/medium, there are no fixed expected_rows.
Score is entirely driven by query plan quality:
  - uses WITH (CTE)
  - uses GROUP BY
  - uses AVG(
  - does NOT use correlated subquery pattern
  - executes without error
"""


def grade(
    task: dict,
    agent_query: str,
    run_result: dict,
    prev_absolute_score: float = 0.0,
    step_count: int = 1,
    max_steps: int = 10,
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

    query_upper = agent_query.upper()
    # good_patterns = task.get("good_patterns", ["WITH", "GROUP BY", "AVG("])

    # ── Plan component scores ─────────────────────────────────────────────────

    # 1. Uses CTE (WITH keyword) — most important signal
    has_cte = "WITH" in query_upper
    cte_score = 1.0 if has_cte else 0.0

    # 2. Uses GROUP BY — required for computing per-user average
    has_group_by = "GROUP BY" in query_upper
    group_score = 1.0 if has_group_by else 0.0

    # 3. Uses AVG — must be aggregating correctly
    has_avg = "AVG(" in query_upper
    avg_score = 1.0 if has_avg else 0.0

    # 4. Correlated subquery penalty — still using the slow pattern
    still_correlated = (
        "SELECT AVG" in query_upper
        and "WHERE" in query_upper
        and not has_cte          # WITH overrides this penalty
    )
    correlation_penalty = 0.4 if still_correlated else 0.0

    # 5. Execution quality — did the query actually return rows?
    rows_returned = len(run_result["rows"])
    execution_score = 1.0 if rows_returned > 0 else 0.3
    # 0.3 credit for running without error even if empty result

    # ── Plan score weighted combination ───────────────────────────────────────
    # CTE 40% + GROUP BY 25% + AVG 20% + execution 15%
    plan_score = round(
        max(
            0.0,
            0.40 * cte_score
            + 0.25 * group_score
            + 0.20 * avg_score
            + 0.15 * execution_score
            - correlation_penalty,
        ),
        4,
    )

    # ── Efficiency bonus ──────────────────────────────────────────────────────
    steps_remaining = max_steps - step_count
    efficiency_bonus = 0.0
    if plan_score >= 0.85:
        efficiency_bonus = round(0.05 * (steps_remaining / max_steps), 4)

    # ── Absolute score — hard: syntax 10% + plan 85% + bonus 5% ─────────────
    absolute_score = round(
        min(0.99, 0.10 * 1.0 + 0.85 * plan_score + efficiency_bonus), 4
    )
    absolute_score = max(0.05, absolute_score)

    # ── Delta ─────────────────────────────────────────────────────────────────
    delta = absolute_score - prev_absolute_score
    if abs(delta) < 0.001 and step_count > 1:
        delta -= 0.02
    delta = round(max(-0.3, min(0.5, delta)), 4)

    # ── Feedback ─────────────────────────────────────────────────────────────
    issues = []
    if not has_cte:
        issues.append("missing_cte: query needs WITH clause to precompute averages")
    if not has_group_by:
        issues.append("missing_group_by: need GROUP BY user_id to compute per-user avg")
    if not has_avg:
        issues.append("missing_avg: need AVG(amount) in the CTE")
    if still_correlated:
        issues.append("still_correlated: subquery in WHERE runs per-row — move to CTE")
    if rows_returned == 0 and syntax_ok:
        issues.append("empty_result: query runs but returns no rows — check JOIN and WHERE")
    feedback = "; ".join(issues) if issues else "plan looks optimized"

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
        "result_score": execution_score,
        "plan_score": plan_score,
        "delta": delta,
        "status": status,
        "feedback": feedback,
        "message": (
            f"{status} | abs={absolute_score:.3f} | delta={delta:+.3f} | "
            f"plan={plan_score:.0%} | cte={has_cte} | group={has_group_by}"
        ),
    }