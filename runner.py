import sqlite3

def run_query(schema_sql: str, query: str) -> dict:
    """
    Runs query against an in-memory SQLite DB seeded with schema_sql.
    Returns: { "rows": [...], "error": str|None, "plan": str }
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(schema_sql)
        plan_rows = conn.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
        plan = " | ".join(str(dict(r)) for r in plan_rows)
        result_rows = [dict(r) for r in conn.execute(query).fetchall()]
        return {"rows": result_rows, "error": None, "plan": plan}
    except Exception as e:
        return {"rows": [], "error": str(e), "plan": ""}
    finally:
        conn.close()