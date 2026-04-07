def compute_reward(task: dict, agent_query: str, run_result: dict) -> dict:
    """
    task        = one of TASK dicts from tasks/
    agent_query = the SQL string the agent submitted
    run_result  = output from runner.run_query()

    Returns a dict: { value, syntax_ok, result_match_pct, plan_score, message }
    """

    # ── Step 1: Did the query even run? ───────────────────────────────────────
    syntax_ok = (run_result["error"] is None)

    if not syntax_ok:
        # Give tiny credit for trying (not zero, so agent gets gradient signal)
        return {
            "value": 0.05,
            "syntax_ok": False,
            "result_match_pct": 0.0,
            "plan_score": 0.0,
            "message": f"Syntax error: {run_result['error'][:100]}",
        }

    # ── Step 2: Did we get the right rows? ────────────────────────────────────
    result_match_pct = 0.0

    if task["expected_rows"] is not None:
        expected = task["expected_rows"]
        got = run_result["rows"]

        # Count how many expected rows are present in the result
        matches = sum(1 for row in expected if row in got)
        result_match_pct = matches / max(len(expected), 1)

        # Penalize extra rows (returned too many rows = wrong query)
        if len(got) > len(expected) * 2:
            result_match_pct *= 0.7  # 30% penalty for bloated results

    else:
        # Hard task: no fixed rows — give full match credit if query runs
        result_match_pct = 1.0

    # ── Step 3: Is the query plan good? (hard task only) ─────────────────────
    plan_score = 0.0

    if task.get("check_plan"):
        query_upper = agent_query.upper()
        good_patterns = task.get("good_patterns", [])

        # Each good pattern found = partial credit
        found = sum(1 for p in good_patterns if p.upper() in query_upper)
        plan_score = found / max(len(good_patterns), 1)

        # Also penalize if they still use correlated subquery pattern
        if "WHERE" in query_upper and "SELECT AVG" in query_upper:
            plan_score *= 0.3  # Heavy penalty — they didn't really optimize

    # ── Step 4: Combine into final score ──────────────────────────────────────
    # Weights: syntax 20% + correctness 60% + plan 20%
    base_score = 0.2 + (0.6 * result_match_pct) + (0.2 * plan_score)

    # Penalize absurdly long queries (e.g. agent spams SELECT *)
    length_penalty = max(0.0, (len(agent_query) - 800) / 2000)
    final = max(0.0, min(1.0, base_score - length_penalty))

    status = "perfect" if final >= 0.99 else "partial" if final > 0.2 else "wrong"
    msg = f"{status} | rows matched: {result_match_pct:.0%} | plan: {plan_score:.0%}"

    return {
        "value": round(final, 3),
        "syntax_ok": True,
        "result_match_pct": result_match_pct,
        "plan_score": plan_score,
        "message": msg,
    }