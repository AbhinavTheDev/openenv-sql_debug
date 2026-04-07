TASK = {
    "task_id": "logic_fix_001",
    "difficulty": "medium",
    "max_steps": 8,

    "schema_sql": """
        CREATE TABLE employees (id INTEGER, name TEXT, dept_id INTEGER, salary REAL);
        CREATE TABLE departments (id INTEGER, dept_name TEXT, budget REAL);

        INSERT INTO departments VALUES (1, 'Engineering', 500000);
        INSERT INTO departments VALUES (2, 'Sales', 300000);

        INSERT INTO employees VALUES (1, 'Alice', 1, 95000);
        INSERT INTO employees VALUES (2, 'Bob',   2, 60000);
        INSERT INTO employees VALUES (3, 'Carol', 1, 85000);
        INSERT INTO employees VALUES (4, 'Dan',   99, 55000); -- dept 99 doesn't exist!
    """,

    # Bug: LEFT JOIN means Dan (no dept) appears in results. Should be INNER JOIN.
    "broken_query": """
        SELECT e.name, d.dept_name
        FROM employees e
        LEFT JOIN departments d ON e.dept_id = d.id
        WHERE d.budget > 400000
    """,

    "target_description": (
        "Return names of employees in departments with budget > 400000. "
        "Do NOT include employees whose department doesn't exist."
    ),

    "expected_rows": [
        {"name": "Alice", "dept_name": "Engineering"},
        {"name": "Carol", "dept_name": "Engineering"},
    ],

    "check_plan": False,
}