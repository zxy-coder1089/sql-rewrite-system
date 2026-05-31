from app.rewrite_engine import SQLRewriteEngine
from app.semantic_validator import SemanticValidator
from app.db_pg import get_conn

engine = SQLRewriteEngine(use_llm=False)
validator = SemanticValidator()

examples = [
    ("Example 1: YEAR function elimination", "SELECT * FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2024"),
    ("Example 2: Arithmetic elimination", "SELECT * FROM products WHERE price * 0.85 > 500"),
    ("Example 3: SUBSTRING to LIKE", "SELECT * FROM customers WHERE SUBSTRING(phone, 1, 3) = '138'"),
    ("Example 4: CAST conversion elimination", "SELECT * FROM orders WHERE CAST(id AS CHAR) = '12345'"),
    ("Example 5: COALESCE simplification", "SELECT * FROM orders WHERE COALESCE(status, 'pending') = 'paid'"),
    ("Example 6: NOT IN optimization", "SELECT * FROM products WHERE id NOT IN (SELECT product_id FROM order_items WHERE quantity > 10)"),
    ("Example 7: Scalar subquery optimization", "SELECT o.id, o.customer_id, (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.id) AS item_count FROM orders o"),
    ("Example 8: HAVING pushdown", "SELECT dept_id, COUNT(*) AS cnt FROM employees GROUP BY dept_id HAVING COUNT(*) > 5"),
    ("Example 9: Deferred join pagination", "SELECT * FROM orders ORDER BY id LIMIT 10 OFFSET 50000"),
    ("Example 10: UNION optimization", "SELECT * FROM orders WHERE status IN ('completed', 'pending') UNION SELECT * FROM orders WHERE status = 'shipped'"),
]

print("=" * 70)
print("Test semantic consistency for all examples")
print("=" * 70)

consistent_count = 0
inconsistent_count = 0
error_count = 0

for name, sql in examples:
    print(f"\n{name}")
    print(f"SQL: {sql[:60]}...")

    try:
        rewritten, _, steps = engine.rewrite(sql)
        result = validator.validate(sql, rewritten)

        if result.is_equivalent:
            print(f"Result: CONSISTENT [OK] (rows: {result.original_row_count})")
            consistent_count += 1
        else:
            print(f"Result: INCONSISTENT [FAIL]")
            print(f"  - Original rows: {result.original_row_count}")
            print(f"  - Rewritten rows: {result.rewritten_row_count}")
            print(f"  - Schema match: {result.schema_match}")
            print(f"  - Normalized match: {result.normalized_match}")
            inconsistent_count += 1
    except Exception as e:
        print(f"Result: ERROR [ERR] - {e}")
        error_count += 1

print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Consistent: {consistent_count}/10")
print(f"Inconsistent: {inconsistent_count}/10")
print(f"Error: {error_count}/10")