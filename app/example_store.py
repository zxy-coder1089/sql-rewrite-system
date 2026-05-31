from __future__ import annotations
from dataclasses import dataclass
from typing import List
import re

@dataclass
class ExampleCase:
    """Case definition: an example of an SQL rewrite pattern

    Attributes:
        pattern: matching keyword (e.g. "year(", " in (select ")
        before_sql: SQL before rewrite
        after_sql: SQL after rewrite
        explanation: explanation of the rewrite
        category: category (predicate/join/aggregation/set/pagination/projection)
    """
    pattern: str
    before_sql: str
    after_sql: str
    explanation: str
    category: str = "general"

EXAMPLES: List[ExampleCase] = [
    # ========== Existing cases (preserved) ==========
    ExampleCase(
        pattern=" in (select ",
        before_sql="SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE region = 'East')",
        after_sql="SELECT customers.id, orders.* FROM customers JOIN orders ON customers.id = orders.customer_id WHERE customers.region = 'East'",
        explanation="Rewrite IN subquery to JOIN, suitable for one-to-one or deduplicated equivalent scenarios.",
        category="join"
    ),
    ExampleCase(
        pattern="select *",
        before_sql="SELECT * FROM orders WHERE amount > 100",
        after_sql="SELECT id, customer_id, amount, status, created_at FROM orders WHERE amount > 100",
        explanation="Avoid SELECT * when target columns are known, reducing unnecessary column reads.",
        category="projection"
    ),
    ExampleCase(
        pattern=" exists (select ",
        before_sql="SELECT * FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)",
        after_sql="SELECT c.id, c.name, c.region, c.vip FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)",
        explanation="Conservative handling of EXISTS, preserving semantics, avoiding incorrect direct JOIN conversion that introduces duplicate rows.",
        category="join"
    ),

    # ========== Predicate optimization (PRED-001 ~ PRED-005) ==========
    ExampleCase(
        pattern="year(",
        before_sql="SELECT * FROM logs WHERE YEAR(timestamp) = 2024",
        after_sql="SELECT * FROM logs WHERE timestamp >= '2024-01-01' AND timestamp < '2025-01-01'",
        explanation="Eliminate date function YEAR(), keeping the index column in its raw form, enabling B+ tree index range scan.",
        category="predicate"
    ),
    ExampleCase(
        pattern="*",
        before_sql="SELECT * FROM items WHERE quantity * 1.1 >= 50",
        after_sql="SELECT * FROM items WHERE quantity >= 46",
        explanation="Constant pre-computation, eliminating arithmetic on index columns, avoiding per-row computation while keeping the index usable.",
        category="predicate"
    ),
    ExampleCase(
        pattern="substring(",
        before_sql="SELECT * FROM users WHERE SUBSTRING(phone, 1, 3) = '138'",
        after_sql="SELECT * FROM users WHERE phone LIKE '138%'",
        explanation="SUBSTRING function prevents index usage, changing to LIKE prefix match allows index utilization.",
        category="predicate"
    ),
    ExampleCase(
        pattern="cast(",
        before_sql="SELECT * FROM products WHERE CAST(id AS CHAR) = '100'",
        after_sql="SELECT * FROM products WHERE id = 100",
        explanation="Eliminate implicit/explicit type conversion to prevent index invalidation.",
        category="predicate"
    ),
    ExampleCase(
        pattern="ifnull(",
        before_sql="SELECT * FROM orders WHERE IFNULL(status, 'pending') = 'completed'",
        after_sql="SELECT * FROM orders WHERE status = 'completed'",
        explanation="Simplify null check conditions, avoid function calls, leverage index for direct lookup.",
        category="predicate"
    ),

    # ========== Join optimization (JOIN-001, JOIN-004, JOIN-005) ==========
    ExampleCase(
        pattern="select count(*) from",
        before_sql="SELECT d.name, (SELECT COUNT(*) FROM employees e WHERE e.dept_id = d.id) cnt FROM departments d",
        after_sql="SELECT d.name, COALESCE(sub.cnt, 0) FROM departments d LEFT JOIN (SELECT dept_id, COUNT(*) AS cnt FROM employees GROUP BY dept_id) sub ON d.id = sub.dept_id",
        explanation="Scalar subquery executes row-by-row with low efficiency, rewriting to JOIN with subquery aggregation completes computation in one pass.",
        category="join"
    ),
    ExampleCase(
        pattern="not in (",
        before_sql="SELECT * FROM users WHERE id NOT IN (SELECT uid FROM banned_users)",
        after_sql="SELECT users.* FROM users LEFT JOIN banned_users ON users.id = banned_users.uid WHERE banned_users.uid IS NULL",
        explanation="NOT IN returns empty result set when NULL values are present, rewriting to ANTI JOIN is safer and more efficient.",
        category="join"
    ),
    ExampleCase(
        pattern="not exists",
        before_sql="SELECT * FROM products p WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.product_id = p.id)",
        after_sql="SELECT * FROM products p WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.product_id = p.id AND o.product_id IS NOT NULL)",
        explanation="NOT EXISTS combined with NOT NULL condition can better utilize indexes and has clearer semantics.",
        category="join"
    ),

    # ========== Aggregation optimization (AGGR-001, AGGR-004, AGGR-005) ==========
    ExampleCase(
        pattern="having",
        before_sql="SELECT dept_id, AVG(salary) FROM employees GROUP BY dept_id HAVING dept_id = 10",
        after_sql="SELECT dept_id, AVG(salary) FROM employees WHERE dept_id = 10 GROUP BY dept_id",
        explanation="HAVING filters after aggregation, rewriting to WHERE filters before aggregation, significantly reducing aggregation data volume.",
        category="aggregation"
    ),
    ExampleCase(
        pattern="distinct",
        before_sql="SELECT DISTINCT dept_id FROM employees",
        after_sql="SELECT dept_id FROM employees GROUP BY dept_id",
        explanation="GROUP BY is more efficient in some optimizers and can replace DISTINCT for deduplication.",
        category="aggregation"
    ),
    ExampleCase(
        pattern="select sum(",
        before_sql="SELECT SUM(amount), AVG(amount), MAX(amount), MIN(amount) FROM sales",
        after_sql="SELECT SUM(amount), SUM(amount)/COUNT(*) AS avg_amount, MAX(amount), MIN(amount) FROM sales",
        explanation="Leverage existing SUM and COUNT to calculate AVG, avoiding repeated data scans.",
        category="aggregation"
    ),

    # ========== Set operation optimization (SET-001, SET-003, SET-004) ==========
    ExampleCase(
        pattern=" union ",
        before_sql="SELECT col FROM a UNION SELECT col FROM b",
        after_sql="SELECT col FROM a UNION ALL SELECT col FROM b",
        explanation="When two tables have no duplicates or dedup is unnecessary, use UNION ALL to eliminate sort-and-dedup overhead.",
        category="set"
    ),
    ExampleCase(
        pattern="intersect",
        before_sql="SELECT id FROM users INTERSECT SELECT id FROM customers",
        after_sql="SELECT DISTINCT u.id FROM users u JOIN customers c ON u.id = c.id",
        explanation="INTERSECT rewritten to JOIN for intersection, hash join is typically more efficient.",
        category="set"
    ),
    ExampleCase(
        pattern="except",
        before_sql="SELECT id FROM users EXCEPT SELECT uid FROM banned_users",
        after_sql="SELECT u.id FROM users u LEFT JOIN banned_users b ON u.id = b.uid WHERE b.uid IS NULL",
        explanation="EXCEPT rewritten to ANTI JOIN for set difference, outer join + null filter is more versatile.",
        category="set"
    ),

    # ========== Pagination optimization (PAGE-001, PAGE-002, PAGE-003) ==========
    ExampleCase(
        pattern="limit",
        before_sql="SELECT * FROM orders ORDER BY id LIMIT 100000, 10",
        after_sql="SELECT orders.* FROM orders JOIN (SELECT id FROM orders ORDER BY id LIMIT 100000, 10) t ON orders.id = t.id",
        explanation="Deferred join: query primary keys first then join to the table, avoiding large table lookups.",
        category="pagination"
    ),
    ExampleCase(
        pattern="offset",
        before_sql="SELECT * FROM orders ORDER BY id LIMIT 10 OFFSET 100000",
        after_sql="SELECT * FROM orders WHERE id > 100000 ORDER BY id LIMIT 10",
        explanation="Keyset pagination: use index for positioning, avoiding large OFFSET scans.",
        category="pagination"
    ),
    ExampleCase(
        pattern="offset",
        before_sql="SELECT * FROM orders ORDER BY created_at, id LIMIT 10",
        after_sql="SELECT * FROM orders WHERE (created_at, id) > ('2024-01-01', 1000) ORDER BY created_at, id LIMIT 10",
        explanation="Bookmark pagination: use composite bookmark for non-unique sort columns, avoiding duplicates.",
        category="pagination"
    ),

    # ========== Edge case supporting examples ==========
    ExampleCase(
        pattern="date(",
        before_sql="SELECT * FROM orders WHERE DATE(order_date) = '2024-06-15'",
        after_sql="SELECT * FROM orders WHERE order_date >= '2024-06-15' AND order_date < '2024-06-16'",
        explanation="Eliminate DATE() function, use range query instead, leveraging the order_date index.",
        category="predicate"
    ),
    ExampleCase(
        pattern="left(",
        before_sql="SELECT * FROM customers WHERE LEFT(email, 5) = 'admin'",
        after_sql="SELECT * FROM customers WHERE email LIKE 'admin%'",
        explanation="LEFT() function prevents index usage, rewriting to LIKE prefix match allows email index utilization.",
        category="predicate"
    ),
    ExampleCase(
        pattern="cast(",
        before_sql="SELECT * FROM employees WHERE CAST(id AS VARCHAR) = '500'",
        after_sql="SELECT * FROM employees WHERE id = 500",
        explanation="Eliminate CAST AS VARCHAR type conversion to prevent primary key index invalidation.",
        category="predicate"
    ),
    ExampleCase(
        pattern="+",
        before_sql="SELECT id, name, price FROM products WHERE price + 50 > 200",
        after_sql="SELECT id, name, price FROM products WHERE price > 150",
        explanation="Constant pre-computation for addition, eliminating arithmetic expressions on index columns.",
        category="predicate"
    ),
    ExampleCase(
        pattern="trim(",
        before_sql="SELECT * FROM employees WHERE UPPER(TRIM(email)) = 'ADMIN@COMPANY.COM'",
        after_sql="SELECT * FROM employees WHERE email = 'admin@company.com'",
        explanation="Eliminate nested UPPER/TRIM functions, use direct string comparison instead.",
        category="predicate"
    ),
]

def retrieve_examples(sql: str, top_k: int = 3) -> List[ExampleCase]:
    """Retrieve relevant rewrite examples by SQL keyword matching

    Scoring: exact pattern match gives 10 points,
    token overlap gives 0.5 each (max 5 points, to avoid common word dominance)
    Returns top_k matching cases with highest scores; returns the first case as default if no match
    """
    lowered = sql.lower()
    scored = []
    for ex in EXAMPLES:
        score = 0
        if ex.pattern in lowered:
            score += 10
        overlap = sum(1 for token in re.findall(r"[a-z_]+", ex.before_sql.lower()) if token in lowered)
        score += min(overlap * 0.5, 5)
        scored.append((score, ex))
    scored.sort(key=lambda x: x[0], reverse=True)
    matched = [ex for score, ex in scored if score > 0]
    return matched[:top_k] if matched else EXAMPLES[:1]
