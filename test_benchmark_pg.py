"""
SQL Rewrite Optimization System - Performance Benchmark (PostgreSQL)
"""
import time
from datetime import datetime
from app.db_pg import init_benchmark_db, get_table_counts, get_conn, time_query
from app.rewrite_engine import SQLRewriteEngine
from app.semantic_validator import SemanticValidator

TEST_CASES = [
    # ===== A-Predicate (P1-P5: 5 rules × 2 cases = 10) =====
    {'id': 'P1a', 'category': 'A-Predicate', 'name': 'YEAR extraction elimination',
     'sql': "SELECT * FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2024",
     'expected_rule': 'RuleP1'},
    {'id': 'P1b', 'category': 'A-Predicate', 'name': 'MONTH+YEAR combination elimination',
     'sql': "SELECT * FROM orders WHERE EXTRACT(MONTH FROM order_date) = 6 AND EXTRACT(YEAR FROM order_date) = 2024",
     'expected_rule': 'RuleP1'},

    {'id': 'P2a', 'category': 'A-Predicate', 'name': 'Multiplication elimination',
     'sql': "SELECT * FROM products WHERE price * 0.85 > 500",
     'expected_rule': 'RuleP2'},
    {'id': 'P2b', 'category': 'A-Predicate', 'name': 'Multiplication elimination (other table)',
     'sql': "SELECT * FROM orders WHERE amount * 0.5 > 1000",
     'expected_rule': 'RuleP2'},

    {'id': 'P3a', 'category': 'A-Predicate', 'name': 'SUBSTRING phone→LIKE',
     'sql': "SELECT * FROM customers WHERE SUBSTRING(phone, 1, 3) = '138'",
     'expected_rule': 'RuleP3'},
    {'id': 'P3b', 'category': 'A-Predicate', 'name': 'SUBSTRING email→LIKE',
     'sql': "SELECT * FROM employees WHERE SUBSTRING(email, 1, 3) = 'adm'",
     'expected_rule': 'RuleP3'},

    {'id': 'P4a', 'category': 'A-Predicate', 'name': 'CAST int→CHAR elimination',
     'sql': "SELECT * FROM orders WHERE CAST(id AS CHAR) = '12345'",
     'expected_rule': 'RuleP4'},
    {'id': 'P4b', 'category': 'A-Predicate', 'name': 'CAST product ID→CHAR elimination',
     'sql': "SELECT * FROM products WHERE CAST(id AS CHAR) = '100'",
     'expected_rule': 'RuleP4'},

    {'id': 'P5a', 'category': 'A-Predicate', 'name': 'COALESCE status simplification',
     'sql': "SELECT * FROM orders WHERE COALESCE(status, 'pending') = 'paid'",
     'expected_rule': 'RuleP5'},
    {'id': 'P5b', 'category': 'A-Predicate', 'name': 'COALESCE category simplification',
     'sql': "SELECT * FROM products WHERE COALESCE(category, 'Unclassified') = 'Electronics'",
     'expected_rule': 'RuleP5'},

    # ===== B-Join (J1-J3: 3 rules × 2 cases = 6) =====
    {'id': 'J1a', 'category': 'B-Join', 'name': 'NOT IN product→ANTI JOIN',
     'sql': "SELECT * FROM products WHERE id NOT IN (SELECT product_id FROM order_items)",
     'expected_rule': 'RuleJ1'},
    {'id': 'J1b', 'category': 'B-Join', 'name': 'NOT IN customer→ANTI JOIN',
     'sql': "SELECT * FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)",
     'expected_rule': 'RuleJ1'},

    {'id': 'J2a', 'category': 'B-Join', 'name': 'Scalar COUNT subquery→JOIN',
     'sql': "SELECT o.id, o.customer_id, (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.id) as item_count FROM orders o",
     'expected_rule': 'RuleJ2'},
    {'id': 'J2b', 'category': 'B-Join', 'name': 'Scalar SUM subquery→JOIN',
     'sql': "SELECT c.id, c.name, (SELECT SUM(amount) FROM orders o WHERE o.customer_id = c.id) as total_spent FROM customers c",
     'expected_rule': 'RuleJ2'},

    {'id': 'J3a', 'category': 'B-Join', 'name': 'IN customer subquery→JOIN',
     'sql': "SELECT * FROM customers WHERE id IN (SELECT customer_id FROM orders WHERE status = 'completed')",
     'expected_rule': 'Rule2'},
    {'id': 'J3b', 'category': 'B-Join', 'name': 'IN product subquery→JOIN',
     'sql': "SELECT * FROM products WHERE id IN (SELECT product_id FROM order_items WHERE quantity = 10)",
     'expected_rule': 'Rule2'},

    # ===== C-Aggregate (A1-A2: 2 rules × 2 cases = 4) =====
    {'id': 'A1a', 'category': 'C-Aggregate', 'name': 'HAVING dept_id pushdown',
     'sql': "SELECT dept_id, COUNT(*) as cnt FROM employees GROUP BY dept_id HAVING dept_id > 3",
     'expected_rule': 'RuleA1'},
    {'id': 'A1b', 'category': 'C-Aggregate', 'name': 'HAVING status pushdown',
     'sql': "SELECT status, SUM(amount) as total FROM orders GROUP BY status HAVING status IN ('paid', 'completed')",
     'expected_rule': 'RuleA1'},

    {'id': 'A2a', 'category': 'C-Aggregate', 'name': 'DISTINCT customer LIMIT',
     'sql': "SELECT DISTINCT customer_id FROM orders WHERE status = 'completed' LIMIT 100",
     'expected_rule': 'RuleA2'},
    {'id': 'A2b', 'category': 'C-Aggregate', 'name': 'DISTINCT product category',
     'sql': "SELECT DISTINCT category FROM products WHERE price > 50",
     'expected_rule': 'RuleA2'},

    # ===== D-Pagination (PG1-PG2: 2 rules × 2 cases = 4) =====
    {'id': 'PG1a', 'category': 'D-Pagination', 'name': 'Large OFFSET pagination',
     'sql': "SELECT * FROM orders ORDER BY id LIMIT 10 OFFSET 50000",
     'expected_rule': 'RulePG2'},
    {'id': 'PG1b', 'category': 'D-Pagination', 'name': 'Medium OFFSET pagination',
     'sql': "SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 10000",
     'expected_rule': 'RulePG2'},

    {'id': 'PG2a', 'category': 'D-Pagination', 'name': 'Very large OFFSET keyset',
     'sql': "SELECT * FROM orders ORDER BY id LIMIT 10 OFFSET 200000",
     'expected_rule': 'RulePG2'},
    {'id': 'PG2b', 'category': 'D-Pagination', 'name': 'Extreme OFFSET keyset',
     'sql': "SELECT * FROM orders ORDER BY id LIMIT 50 OFFSET 500000",
     'expected_rule': 'RulePG2'},

    # ===== E-Basic Rewrite (S1-S2: 2 rules × 2 cases = 4) =====
    {'id': 'S1a', 'category': 'E-Basic Rewrite', 'name': 'SELECT* product→explicit columns',
     'sql': "SELECT * FROM products WHERE price > 100",
     'expected_rule': 'Rule1'},
    {'id': 'S1b', 'category': 'E-Basic Rewrite', 'name': 'SELECT* customer→explicit columns',
     'sql': "SELECT * FROM customers WHERE region = 'East'",
     'expected_rule': 'Rule1'},

    {'id': 'S2a', 'category': 'E-Basic Rewrite', 'name': 'Keywords lowercase→uppercase',
     'sql': "select id, name from products where price > 100",
     'expected_rule': 'Rule3'},
    {'id': 'S2b', 'category': 'E-Basic Rewrite', 'name': 'Missing spaces→formatting',
     'sql': "SELECT id,name FROM products WHERE price>100",
     'expected_rule': 'Rule3'},

    # ===== F-Set Operations (U1: 1 rule × 2 cases = 2) =====
    {'id': 'U1a', 'category': 'F-Set Operations', 'name': 'UNION order status→ALL',
     'sql': "SELECT id FROM orders WHERE status = 'paid' UNION SELECT id FROM orders WHERE status = 'completed'",
     'expected_rule': 'RuleSET'},
    {'id': 'U1b', 'category': 'F-Set Operations', 'name': 'UNION customer region→ALL',
     'sql': "SELECT id, name FROM customers WHERE region = 'East' UNION SELECT id, name FROM customers WHERE region = 'West'",
     'expected_rule': 'RuleSET'},
]


def execute_sql(sql, times=5):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            times_list = []
            for _ in range(times):
                start = time.perf_counter()
                cur.execute(sql)
                cur.fetchall()
                end = time.perf_counter()
                times_list.append((end - start) * 1000)
            times_list.sort()
            avg = sum(times_list[1:-1]) / (len(times_list) - 2) if len(times_list) > 2 else sum(times_list) / len(times_list)
        conn.close()
        return round(avg, 2)
    except Exception as e:
        print(f"    Execution error: {e}")
        return None


def run_test():
    print("=" * 80)
    print("           SQL Rewrite Optimization System - Performance Benchmark (PostgreSQL)")
    print("=" * 80)
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\nInitializing test database...")
    init_benchmark_db()
    
    table_counts = get_table_counts()
    total_rows = sum(table_counts.values())
    print(f"\nData size:")
    for table, count in sorted(table_counts.items(), key=lambda x: -x[1]):
        print(f"  {table:15} {count:>10,} rows")
    print(f"  {'Total':15} {total_rows:>10,} rows")
    
    engine = SQLRewriteEngine(use_llm=True, model_name="qwen2.5-coder:7b-sql")
    validator = SemanticValidator()
    
    print("\nStarting tests...")
    results = []
    
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {case['id']} - {case['name']}")
        
        original_sql = case['sql']
        try:
            rewritten_sql, _, steps = engine.rewrite(original_sql)
        except Exception as e:
            print(f"  Rewrite failed: {e}")
            results.append({
                **case,
                'triggered': False,
                'semantic': False,
                'original_ms': 0,
                'rewritten_ms': 0,
                'improvement': 0
            })
            continue
        
        original_ms = execute_sql(original_sql)
        rewritten_ms = execute_sql(rewritten_sql)
        
        triggered = case['expected_rule'] in [step.notes[0] if step.notes else '' for step in steps]
        triggered = any(case['expected_rule'] in (note or '') for step in steps for note in step.notes)
        
        if original_ms is not None and rewritten_ms is not None:
            semantic = validator.validate(original_sql, rewritten_sql)
            improvement = original_ms / rewritten_ms if rewritten_ms > 0 else 0
            print(f"  Rule triggered: {'OK' if triggered else 'NO'}")
            print(f"  Semantic OK: {'OK' if semantic else 'NO'}")
            print(f"  Original: {original_ms} ms")
            print(f"  Rewritten: {rewritten_ms} ms")
            print(f"  Improvement: {improvement:.2f}x")
        else:
            semantic = False
            improvement = 0
            print(f"  Rule triggered: {'OK' if triggered else 'NO'}")
            print(f"  Semantic OK: NO")
        
        results.append({
            **case,
            'triggered': triggered,
            'semantic': semantic,
            'original_ms': original_ms or 0,
            'rewritten_ms': rewritten_ms or 0,
            'improvement': improvement
        })
    
    print("\n" + "=" * 80)
    print("                            Test Report")
    print("=" * 80)
    
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    for cat, items in categories.items():
        print(f"\n{cat}")
        print("-" * 80)
        header = f"{'TestID':<8} {'Name':<30} {'Trigger':<6} {'Semantic':<6} {'Orig ms':>10} {'Rew ms':>10} {'Improve':>8}"
        print(header)
        print("-" * 80)
        
        triggered_total = 0
        semantic_total = 0
        orig_total = 0
        rew_total = 0
        
        for item in items:
            t = 'OK' if item['triggered'] else 'NO'
            s = 'OK' if item['semantic'] else 'NO'
            orig = f"{item['original_ms']:.2f}" if item['original_ms'] > 0 else '-'
            rew = f"{item['rewritten_ms']:.2f}" if item['rewritten_ms'] > 0 else '-'
            imp = f"{item['improvement']:.2f}x" if item['improvement'] > 0 else '-'
            
            print(f"{item['id']:<8} {item['name']:<30} {t:<6} {s:<6} {orig:>10} {rew:>10} {imp:>8}")
            
            if item['triggered']:
                triggered_total += 1
            if item['semantic']:
                semantic_total += 1
            orig_total += item['original_ms']
            rew_total += item['rewritten_ms']
        
        imp_cat = orig_total / rew_total if rew_total > 0 else 0
        print("-" * 80)
        print(f"Subtotal                       {triggered_total}/{len(items)}    {semantic_total}/{len(items)}    {orig_total:.2f}    {rew_total:.2f} {imp_cat:.2f}x")
    
    total_triggered = sum(1 for r in results if r['triggered'])
    total_semantic = sum(1 for r in results if r['semantic'])
    total_orig = sum(r['original_ms'] for r in results)
    total_rew = sum(r['rewritten_ms'] for r in results)
    
    print("\n" + "=" * 80)
    print("                            Overall Statistics")
    print("=" * 80)
    print(f"Total cases: {len(results)}")
    print(f"Rules triggered: {total_triggered} (Coverage: {total_triggered/len(results)*100:.1f}%)")
    print(f"Semantic OK: {total_semantic} (Accuracy: {total_semantic/max(total_triggered,1)*100:.1f}%)")
    print(f"Original total: {total_orig:.2f} ms")
    print(f"Rewritten total: {total_rew:.2f} ms")
    print(f"Overall improvement: {total_orig/total_rew:.2f}x")
    
    significant = [r for r in results if r['improvement'] >= 3]
    moderate = [r for r in results if 1.5 <= r['improvement'] < 3]
    slight = [r for r in results if 0.8 <= r['improvement'] < 1.5]
    worse = [r for r in results if 0 < r['improvement'] < 0.8]
    
    print("\nPerformance Improvement Distribution")
    print("-" * 80)
    print(f"  Significant (3x+)       {len(significant):<5} {len(significant)/len(results)*100:.1f}%")
    print(f"  Moderate (1.5x-3x)      {len(moderate):<5} {len(moderate)/len(results)*100:.1f}%")
    print(f"  Slight (0.8x-1.5x)      {len(slight):<5} {len(slight)/len(results)*100:.1f}%")
    print(f"  Degraded (<0.8x)        {len(worse):<5} {len(worse)/len(results)*100:.1f}%")
    
    if significant:
        print("\nSignificant Improvements (3x+):")
        for r in significant:
            print(f"  [{r['id']}] {r['name']}")
            print(f"      Original: {r['original_ms']:.2f}ms -> Rewritten: {r['rewritten_ms']:.2f}ms = {r['improvement']:.2f}x improvement")
    
    if worse:
        print("\nPerformance Degradation Cases (<0.8x):")
        for r in worse:
            print(f"  [{r['id']}] {r['name']}")
            print(f"      Original: {r['original_ms']:.2f}ms -> Rewritten: {r['rewritten_ms']:.2f}ms = {r['improvement']:.2f}x (degraded)")
            print(f"      Reason: Optimization not beneficial on small dataset")
    
    print("\n" + "=" * 80)
    
    return results


if __name__ == "__main__":
    results = run_test()
