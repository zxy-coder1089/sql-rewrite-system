"""
Run boundary ablation tests for a single mode at a time.
Usage: python run_boundary_ablation.py [mode_index]
  mode_index: 0=Rules Only, 1=LLM Only, 2=Rules+Cases, 3=Rules+LLM, 4=Full System
"""
import sys, time
from datetime import datetime
from app.db_pg import get_conn
from app.rewrite_engine import SQLRewriteEngine
from app.semantic_validator import SemanticValidator
from test_boundary_cases import BOUNDARY_TEST_CASES

ABLATION_MODES = [
    {'name': 'Rules Only',       'config': {'use_llm': False, 'use_rules': True,  'use_cases': False}},
    {'name': 'LLM Only',         'config': {'use_llm': True,  'use_rules': False, 'use_cases': False}},
    {'name': 'Rules+Cases',      'config': {'use_llm': False, 'use_rules': True,  'use_cases': True}},
    {'name': 'Rules+LLM',        'config': {'use_llm': True,  'use_rules': True,  'use_cases': False}},
    {'name': 'Full System',      'config': {'use_llm': True,  'use_rules': True,  'use_cases': True}},
]

def execute_sql(sql, times=1):
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
            avg = times_list[0]
        conn.close()
        return round(avg, 2)
    except Exception as e:
        print(f"    Execution error: {e}")
        return None

def run_single_mode(mode_idx, cases):
    mode = ABLATION_MODES[mode_idx]
    name = mode['name']
    cfg = mode['config']
    print(f"\n{'='*60}")
    print(f"  Mode {mode_idx}: {name}")
    print(f"  Config: {cfg}")
    print(f"{'='*60}")
    engine = SQLRewriteEngine(**cfg, model_name="qwen2.5-coder:7b-sql")
    validator = SemanticValidator()

    total_triggered = 0
    total_semantic = 0
    total_orig = 0
    total_rew = 0
    count = 0

    for case in cases:
        original_sql = case['sql']
        cid = case.get('id', '?')
        try:
            rewritten_sql, _, steps = engine.rewrite(original_sql)
            changed = rewritten_sql.strip().lower() != original_sql.strip().lower()
        except Exception as e:
            print(f"    [{cid}] Rewrite failed: {e}")
            continue

        original_ms = execute_sql(original_sql)
        rewritten_ms = execute_sql(rewritten_sql)

        if original_ms and rewritten_ms:
            validation = validator.validate(original_sql, rewritten_sql)
            semantic_ok = validation.is_equivalent
            improvement = original_ms / rewritten_ms if rewritten_ms > 0 else 0
            if validation.is_equivalent:
                total_semantic += 1
            total_orig += original_ms
            total_rew += rewritten_ms
            count += 1
            triggered = any(case.get('expected_rule', '') in (note or '') for step in steps for note in step.notes)
            if triggered:
                total_triggered += 1
            print(f"    [{cid}] changed={changed} semantic={semantic_ok} {original_ms:.1f}ms->{rewritten_ms:.1f}ms {improvement:.2f}x")
        else:
            count += 1
            print(f"    [{cid}] SQL execution failed")

    avg_imp = total_orig / total_rew if total_rew > 0 else 0
    print(f"\n  Results: triggered={total_triggered}/{len(cases)} semantic={total_semantic}/{count} improvement={avg_imp:.2f}x")

if __name__ == "__main__":
    mode_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    run_single_mode(mode_idx, BOUNDARY_TEST_CASES)
