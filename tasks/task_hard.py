# tasks/task_hard.py
import random

def generate_schema(n_rows=5000, seed=42):
    """Generates schema + INSERT statements for n_rows transactions."""
    rng = random.Random(seed)
    # statuses = ['completed', 'pending', 'failed']
    inserts = []
    for i in range(1, n_rows + 1):
        user_id = rng.randint(1, 100)
        amount = round(rng.uniform(10, 1000), 2)
        # status = rng.choice(statuses)
        inserts.append(f"INSERT INTO transactions VALUES ({i}, {user_id}, {amount}, 'completed');")
    return (
        "CREATE TABLE transactions (id INTEGER, user_id INTEGER, amount REAL, ts TEXT, status TEXT);\n"
        + "\n".join(inserts[:200])  # Keep it fast for demo (200 rows)
    )

TASK = {
    "task_id": "optimize_001",
    "difficulty": "hard",
    "max_steps": 10,

    "schema_sql": generate_schema(200),  # Use 200 rows for speed in hackathon

    # Slow: correlated subquery — runs inner SELECT once per outer row
    "broken_query": """
        SELECT *
        FROM transactions t1
        WHERE amount > (
            SELECT AVG(amount)
            FROM transactions t2
            WHERE t2.user_id = t1.user_id
        )
        AND t1.status = 'completed'
    """,

    "target_description": (
        "Return all completed transactions where the amount exceeds that user's average. "
        "Optimize it — avoid correlated subqueries. Use a CTE or subquery with GROUP BY."
    ),

    # For hard task we grade differently — no fixed expected_rows
    "expected_rows": None,

    # We check that the query plan is efficient (no per-row correlated scans)
    "check_plan": True,

    # Keywords we look for in the agent's solution
    "good_patterns": ["WITH", "GROUP BY", "AVG("],
}