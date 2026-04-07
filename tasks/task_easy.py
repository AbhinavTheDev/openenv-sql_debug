TASK = {
    "task_id": "syntax_fix_001",
    "difficulty": "easy",
    "max_steps": 5,

    # This creates the database the agent works with
    "schema_sql": """
        CREATE TABLE orders (
            id INTEGER, customer TEXT, amount REAL, order_date TEXT
        );
        INSERT INTO orders VALUES (1, 'Alice', 520.0, '2024-01-15');
        INSERT INTO orders VALUES (2, 'Bob',   90.0,  '2024-01-16');
        INSERT INTO orders VALUES (3, 'Carol', 800.0, '2024-01-17');
        INSERT INTO orders VALUES (4, 'Dan',   150.0, '2024-01-18');
    """,

    # This is the broken query the agent must fix
    "broken_query": "SELEC * FORM orders WERE amount > 500",

    # Plain English: what should the fixed query do?
    "target_description": "Return all orders where amount is greater than 500",

    # What the correct answer looks like — used by grader to check
    "expected_rows": [
        {"id": 1, "customer": "Alice", "amount": 520.0, "order_date": "2024-01-15"},
        {"id": 3, "customer": "Carol", "amount": 800.0, "order_date": "2024-01-17"},
    ],

    # For easy task, plan quality doesn't matter
    "check_plan": False,
}