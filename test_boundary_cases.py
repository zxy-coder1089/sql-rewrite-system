"""
Complex Boundary Scenario Tests - Designed to verify hybrid (Rules+LLM) advantages
In these scenarios, pure rules struggle and need semantic understanding and intelligent decisions
"""
import time
from datetime import datetime
from app.db_pg import get_conn
from app.rewrite_engine import SQLRewriteEngine

BOUNDARY_TEST_CASES = [
    # ========== 1. Semantically Ambiguous JOIN Optimization ==========
    {
        'id': 'B1',
        'name': 'LEFT JOIN→INNER (semantically safe)',
        'category': 'JOIN optimization',
        'reason': 'Rules need to confirm NULL rows have no business value for safe conversion',
        'sql': """SELECT c.id, c.name, o.id as order_id, o.amount
                  FROM customers c
                  LEFT JOIN orders o ON c.id = o.customer_id
                  WHERE o.status = 'completed'
                  AND o.amount > 1000""",
        'expected': 'Safely convert LEFT JOIN to INNER JOIN because WHERE condition makes NULL rows meaningless'
    },
    {
        'id': 'B2',
        'name': 'Multi-table JOIN order optimization',
        'category': 'JOIN optimization',
        'reason': 'Rules need to understand data distribution for optimal JOIN order',
        'sql': """SELECT o.id, c.name, p.name, s.name
                  FROM orders o
                  JOIN customers c ON o.customer_id = c.id
                  JOIN order_items oi ON o.id = oi.order_id
                  JOIN products p ON oi.product_id = p.id
                  JOIN suppliers s ON p.supplier_id = s.id
                  JOIN departments d ON c.region = d.name""",
        'expected': 'LLM should suggest joining small tables first (products 20K rows), then large tables (orders 200K rows)'
    },
    {
        'id': 'B3',
        'name': 'LEFT JOIN preserve rows+aggregate',
        'category': 'JOIN optimization',
        'reason': 'Rules need to understand if NULL rows participate in aggregate calculations',
        'sql': """SELECT c.id, COUNT(o.id) as order_count, SUM(o.amount) as total
                  FROM customers c
                  LEFT JOIN orders o ON c.id = o.customer_id
                  GROUP BY c.id""",
        'expected': 'LEFT JOIN is semantically correct, but COUNT can optimize to COUNT(o.id)'
    },

    # ========== 2. Complex Condition Priority ==========
    {
        'id': 'B4',
        'name': 'Multi-condition AND-OR combination',
        'category': 'Condition optimization',
        'reason': 'AND/OR combination priority rules may misjudge',
        'sql': """SELECT * FROM orders
                  WHERE (status = 'completed' AND amount > 1000)
                  OR (status = 'pending' AND amount > 2000)
                  OR (status = 'cancelled')""",
        'expected': 'LLM should understand business logic and suggest reasonable condition reorganization'
    },
    {
        'id': 'B5',
        'name': 'Negative condition+IN combination',
        'category': 'Condition optimization',
        'reason': 'NOT IN + NULL rules are hard to handle',
        'sql': """SELECT * FROM customers
                  WHERE region NOT IN ('East', 'West', 'North')
                  AND id NOT IN (SELECT customer_id FROM banned_customers)
                  AND vip_level > 0""",
        'expected': 'Rules can optimize NOT IN, but need to watch for NULL semantics'
    },
    {
        'id': 'B6',
        'name': 'LIKE pattern matching optimization',
        'category': 'Condition optimization',
        'reason': 'Different LIKE patterns need different index strategies',
        'sql': """SELECT * FROM products
                  WHERE name LIKE '%phone%'
                  OR name LIKE 'Apple%'
                  OR name LIKE '%pro'""",
        'expected': 'Analyze LIKE patterns; Apple% can use index, %phone% needs full-text search'
    },

    # ========== 3. Business Semantics Understanding ==========
    {
        'id': 'B7',
        'name': 'VIP customer special handling',
        'category': 'Business semantics',
        'reason': 'Rules don\'t understand VIP customer business semantics',
        'sql': """SELECT c.id, c.name, c.vip_level,
                  (SELECT SUM(amount) FROM orders WHERE customer_id = c.id) as total_spent
                  FROM customers c
                  WHERE c.vip_level >= 3
                  AND (SELECT COUNT(*) FROM orders WHERE customer_id = c.id) > 10""",
        'expected': 'LLM should recognize VIP customer scenario and suggest materializing intermediate results'
    },
    {
        'id': 'B8',
        'name': 'Order state machine semantics',
        'category': 'Business semantics',
        'reason': 'Order status transitions have business rules; rules are unaware',
        'sql': """SELECT o.id, o.status, o.order_date,
                  CASE
                       WHEN status = 'completed' THEN 'Completed'
                       WHEN status = 'shipped' THEN 'Shipped'
                       WHEN status = 'pending' THEN 'Pending'
                       ELSE 'Unknown'
                  END as status_desc
                  FROM orders o
                  WHERE status IN ('pending', 'shipped', 'completed')
                  AND order_date >= '2024-01-01'""",
        'expected': 'LLM should understand order state machine and identify simplifiable states'
    },
    {
        'id': 'B9',
        'name': 'Timezone+date range',
        'category': 'Business semantics',
        'reason': 'Business dates may have timezone concepts',
        'sql': """SELECT * FROM orders
                  WHERE order_date >= '2024-01-01'
                  AND order_date <= '2024-12-31'
                  AND EXTRACT(MONTH FROM order_date) BETWEEN 1 AND 6""",
        'expected': 'LLM should identify simplifiable date range and month conditions'
    },

    # ========== 4. Query Result Reuse ==========
    {
        'id': 'B10',
        'name': 'Repeated subquery materialization',
        'category': 'Reuse optimization',
        'reason': 'Rules struggle to find repeated computation across subqueries',
        'sql': """SELECT *,
                  (SELECT MAX(amount) FROM orders WHERE customer_id = c.id) as max_order,
                  (SELECT MIN(amount) FROM orders WHERE customer_id = c.id) as min_order,
                  (SELECT AVG(amount) FROM orders WHERE customer_id = c.id) as avg_order
                  FROM customers c""",
        'expected': 'LLM should find that subqueries can be merged into a single one for statistics'
    },
    {
        'id': 'B11',
        'name': 'CTE reuse analysis',
        'category': 'Reuse optimization',
        'reason': 'Multiple CTEs can be merged to reduce scans',
        'sql': """WITH recent_orders AS (
                      SELECT * FROM orders WHERE order_date >= '2024-01-01'
                  ),
                  big_orders AS (
                      SELECT * FROM orders WHERE amount > 1000
                  )
                  SELECT c.* FROM customers c
                  JOIN recent_orders ro ON c.id = ro.customer_id
                  JOIN big_orders bo ON c.id = bo.customer_id""",
        'expected': 'LLM should analyze whether two CTEs can be merged'
    },
    {
        'id': 'B12',
        'name': 'Window function overlap computation',
        'category': 'Reuse optimization',
        'reason': 'Multiple window functions can share computation',
        'sql': """SELECT id, amount,
                  SUM(amount) OVER () as total_all,
                  AVG(amount) OVER () as avg_all,
                  SUM(amount) OVER (PARTITION BY status) as total_by_status,
                  AVG(amount) OVER (PARTITION BY status) as avg_by_status
                  FROM orders""",
        'expected': 'LLM should find shareable partition calculations'
    },

    # ========== 5. Complex Aggregation Strategy ==========
    {
        'id': 'B13',
        'name': 'Multi-dimensional aggregate pushdown',
        'category': 'Aggregate optimization',
        'reason': 'Rules need to understand aggregate dimension relationships',
        'sql': """SELECT c.region, c.vip_level, COUNT(*) as cnt, SUM(o.amount) as total
                  FROM customers c
                  JOIN orders o ON c.id = o.customer_id
                  WHERE c.region IN ('East', 'West')
                  GROUP BY c.region, c.vip_level
                  HAVING SUM(o.amount) > 10000""",
        'expected': 'Analyze aggregate pushdown possibility; identify pre-filtering before aggregation'
    },
    {
        'id': 'B14',
        'name': 'Post-group condition placement',
        'category': 'Aggregate optimization',
        'reason': 'HAVING vs WHERE choice affects performance',
        'sql': """SELECT customer_id, COUNT(*) as order_count, SUM(amount) as total
                  FROM orders
                  WHERE status = 'completed'
                  AND amount > 100
                  GROUP BY customer_id
                  HAVING COUNT(*) > 3""",
        'expected': 'Ensure all pre-aggregation conditions are in WHERE'
    },

    # ========== 6. Cross-table Constraint Optimization ==========
    {
        'id': 'B15',
        'name': 'FK index missing detection',
        'category': 'Index optimization',
        'reason': 'Rules can detect, but LLM can suggest intelligently',
        'sql': """SELECT o.id, o.customer_id, c.name
                  FROM orders o
                  JOIN customers c ON o.customer_id = c.id
                  WHERE c.region = 'East'
                  AND o.amount > (SELECT AVG(amount) FROM orders)""",
        'expected': 'LLM should suggest creating indexes on orders.customer_id and customers.region'
    },
    {
        'id': 'B16',
        'name': 'Multi-table link optimization',
        'category': 'Index optimization',
        'reason': 'EXISTS subquery performance needs optimization',
        'sql': """SELECT o.id, o.amount, o.status
                  FROM orders o
                  WHERE EXISTS (
                      SELECT 1 FROM order_items oi
                      WHERE oi.order_id = o.id AND oi.quantity > 10
                  )
                  AND o.amount > 100""",
        'expected': 'LLM should suggest rewriting as JOIN, using small table as driver'
    },

    # ========== 7. Special SQL Patterns ==========
    {
        'id': 'B17',
        'name': 'Recursive depth limit',
        'category': 'Recursive query',
        'reason': 'Recursive queries need depth limit to prevent explosion',
        'sql': """WITH RECURSIVE emp_hierarchy AS (
                      SELECT id, name, manager_id, 1 as level
                      FROM employees
                      UNION ALL
                    SELECT e.id, e.name, e.manager_id, h.level + 1
                  FROM employees e
                  JOIN emp_hierarchy h ON e.manager_id = h.id
              )
              SELECT * FROM emp_hierarchy LIMIT 10000""",
        'expected': 'LLM should suggest adding MAX RECURSION limit'
    },
    {
        'id': 'B18',
        'name': 'Pagination+sorting optimization',
        'category': 'Pagination optimization',
        'reason': 'Deep pagination needs intelligent handling',
        'sql': """SELECT o.*, c.name as customer_name
                  FROM orders o
                  JOIN customers c ON o.customer_id = c.id
                  ORDER BY o.order_date DESC, o.id DESC
                  LIMIT 20 OFFSET 10000""",
        'expected': 'LLM should suggest using WHERE condition + keyset pagination instead of OFFSET'
    },
    {
        'id': 'B19',
        'name': 'UNION semantic dedup',
        'category': 'UNION optimization',
        'reason': 'UNION vs UNION ALL needs semantic understanding',
        'sql': """SELECT customer_id, 'order' as source, id as source_id
                  FROM orders WHERE amount > 1000
                  UNION
                  SELECT id, 'customer' as source, id as source_id
                  FROM customers WHERE vip_level > 0""",
        'expected': 'Analyze if dedup is really needed; could change to UNION ALL'
    },
    {
        'id': 'B20',
        'name': 'NULL handling strategy',
        'category': 'NULL optimization',
        'reason': 'NULL semantics are complex, rules are error-prone',
        'sql': """SELECT COALESCE(name, 'Unknown') as name,
                  COALESCE(email, 'no-email@placeholder.com') as email,
                  COALESCE(phone, '-') as phone
                  FROM customers
                  WHERE COALESCE(region, 'Unknown') != 'Banned'
                  AND COALESCE(vip_level, 0) > 0""",
        'expected': 'LLM should analyze if COALESCE is necessary and identify simplifiable scenarios'
    },
]

def execute_sql(sql):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            start = time.perf_counter()
            cur.execute(sql)
            results = cur.fetchall()
            end = time.perf_counter()
        conn.close()
        return round((end - start) * 1000, 2), len(results)
    except Exception as e:
        return None, 0

def run_test(engine, case):
    try:
        rewritten_sql, notes, risk = engine.rewrite(case['sql'])

        orig_ms, orig_rows = execute_sql(case['sql'])
        if orig_ms is None:
            return {'ok': False, 'error': 'orig failed'}

        rew_ms, rew_rows = execute_sql(rewritten_sql)
        if rew_ms is None:
            return {'ok': False, 'error': 'rew failed'}

        improvement = orig_ms / rew_ms if rew_ms > 0 else 0
        semantic_ok = orig_rows == rew_rows
        actually_optimized = rewritten_sql.strip().lower() != case['sql'].strip().lower()

        return {
            'id': case['id'],
            'name': case['name'],
            'category': case['category'],
            'expected': case['expected'],
            'orig_ms': orig_ms,
            'rew_ms': rew_ms,
            'imp': improvement,
            'rows': orig_rows,
            'semantic_ok': semantic_ok,
            'triggered': len(notes) > 0 or len(risk) > 0,
            'actually_optimized': actually_optimized,
            'notes': notes,
            'risk': risk,
            'rewritten_sql': rewritten_sql[:200] + '...' if len(rewritten_sql) > 200 else rewritten_sql,
            'ok': True
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)[:100]}

def main():
    print("=" * 100)
    print("       SQL Rewrite System - Boundary Case Test (Hybrid Approach Advantage Verification)")
    print("=" * 100)
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test cases: {len(BOUNDARY_TEST_CASES)}")
    print()

    modes = [
        ('Rules Only', False, None),
        ('Rules + Base Model', True, 'qwen2.5-coder:7b'),
        ('Rules + Finetuned', True, 'qwen2.5-coder:7b-sql'),
    ]

    all_results = []

    for mode_name, use_llm, model_name in modes:
        print(f"\n{'='*80}")
        print(f"  Mode: {mode_name}")
        print(f"{'='*80}")

        engine = SQLRewriteEngine(use_llm=use_llm, model_name=model_name)
        results = []

        for i, case in enumerate(BOUNDARY_TEST_CASES, 1):
            result = run_test(engine, case)
            if result.get('ok'):
                results.append(result)
                status = "OK" if result['semantic_ok'] else "SEM"
                opt = "*" if result['actually_optimized'] else "-"
                trigger = "[T]" if result['triggered'] else "[ ]"
                imp_str = f"{result['imp']:.2f}x"
                print(f"  [{i:2d}/{len(BOUNDARY_TEST_CASES)}] {case['id']}: {status} {trigger} {opt} {imp_str} ({result['orig_ms']:.1f}ms -> {result['rew_ms']:.1f}ms)")
            else:
                results.append({'ok': False, 'id': case['id']})
                print(f"  [{i:2d}/{len(BOUNDARY_TEST_CASES)}] {case['id']}: FAIL ({result.get('error', 'unknown')})")

        all_results.append((mode_name, results))

    print("\n" + "=" * 100)
    print("                        Summary Report - By Category")
    print("=" * 100)

    categories = list(set(c['category'] for c in BOUNDARY_TEST_CASES))

    for mode_name, results in all_results:
        print(f"\n{mode_name}:")
        for cat in categories:
            cat_results = [r for r in results if r.get('ok') and r.get('category') == cat]
            if cat_results:
                avg_imp = sum(r['imp'] for r in cat_results) / len(cat_results)
                optimized = sum(1 for r in cat_results if r.get('actually_optimized'))
                print(f"  {cat}: {len(cat_results)} cases, Avg={avg_imp:.2f}x, Optimized={optimized}")

    print("\n" + "=" * 100)
    print("                        Detailed Analysis")
    print("=" * 100)

    print(f"\n{'ID':<4} {'Case':<35} {'Rules':<10} {'Base':<10} {'Finetuned':<10} {'Winner'}")
    print("-" * 100)

    for i, case in enumerate(BOUNDARY_TEST_CASES):
        r1 = all_results[0][1][i]
        r2 = all_results[1][1][i]
        r3 = all_results[2][1][i]

        r1_imp = r1.get('imp', 0) if r1.get('ok') else 0
        r2_imp = r2.get('imp', 0) if r2.get('ok') else 0
        r3_imp = r3.get('imp', 0) if r3.get('ok') else 0

        r1_str = f"{r1_imp:.2f}x" if r1.get('ok') else "FAIL"
        r2_str = f"{r2_imp:.2f}x" if r2.get('ok') else "FAIL"
        r3_str = f"{r3_imp:.2f}x" if r3.get('ok') else "FAIL"

        winner = "Rules" if r1_imp >= max(r2_imp, r3_imp) else ("Base" if r2_imp >= r3_imp else "Finetuned")
        if max(r1_imp, r2_imp, r3_imp) < 1.0:
            winner = "None"

        print(f"{case['id']:<4} {case['name']:<35} {r1_str:<10} {r2_str:<10} {r3_str:<10} {winner}")

    print("\n" + "=" * 100)
    print("                        Final Statistics")
    print("=" * 100)

    for idx, (mode_name, results) in enumerate(all_results):
        valid = [r for r in results if r.get('ok')]
        if valid:
            avg_imp = sum(r['imp'] for r in valid) / len(valid)
            optimized = sum(1 for r in valid if r.get('actually_optimized'))
            semantic = sum(1 for r in valid if r.get('semantic_ok'))
            print(f"\n{mode_name}:")
            print(f"  - Total cases: {len(valid)}/{len(BOUNDARY_TEST_CASES)}")
            print(f"  - Average improvement: {avg_imp:.2f}x")
            print(f"  - Actually optimized: {optimized}/{len(valid)} ({optimized*100//len(valid)}%)")
            print(f"  - Semantic correct: {semantic}/{len(valid)} ({semantic*100//len(valid)}%)")

    print("\n" + "=" * 100)
    print("                        Winner Analysis")
    print("=" * 100)

    winner_counts = {'Rules': 0, 'Base': 0, 'Finetuned': 0, 'None': 0}
    for i in range(len(BOUNDARY_TEST_CASES)):
        r1 = all_results[0][1][i]
        r2 = all_results[1][1][i]
        r3 = all_results[2][1][i]

        r1_imp = r1.get('imp', 0) if r1.get('ok') else 0
        r2_imp = r2.get('imp', 0) if r2.get('ok') else 0
        r3_imp = r3.get('imp', 0) if r3.get('ok') else 0

        winner = "Rules" if r1_imp >= max(r2_imp, r3_imp) else ("Base" if r2_imp >= r3_imp else "Finetuned")
        if max(r1_imp, r2_imp, r3_imp) < 1.0:
            winner = "None"

        winner_counts[winner] += 1

    for winner, count in winner_counts.items():
        pct = count * 100 // len(BOUNDARY_TEST_CASES)
        print(f"  {winner}: {count}/{len(BOUNDARY_TEST_CASES)} ({pct}%)")

    print("\n" + "=" * 100)
    print("  CONCLUSION: ", end="")
    if winner_counts['Base'] + winner_counts['Finetuned'] > winner_counts['Rules']:
        print("Hybrid (Rules+LLM) outperforms pure Rules!")
    else:
        print("Pure Rules still competitive. Need more LLM-advanced cases.")
    print("=" * 100)

if __name__ == '__main__':
    main()
