"""
Ablation Study - Testing performance contribution of different component combinations
Run: python test_ablation.py
"""
import time
from datetime import datetime
from app.db_pg import get_conn
from app.rewrite_engine import SQLRewriteEngine
from app.semantic_validator import SemanticValidator

from test_benchmark_pg import TEST_CASES
from test_boundary_cases import BOUNDARY_TEST_CASES

ABLATION_MODES = [
    {
        'name': 'Rules Only',
        'config': {'use_llm': False, 'use_rules': True, 'use_cases': False},
    },
    {
        'name': 'LLM Only',
        'config': {'use_llm': True, 'use_rules': False, 'use_cases': False},
    },
    {
        'name': 'Rules+Cases',
        'config': {'use_llm': False, 'use_rules': True, 'use_cases': True},
    },
    {
        'name': 'Rules+LLM',
        'config': {'use_llm': True, 'use_rules': True, 'use_cases': False},
    },
    {
        'name': 'Full System (Rules+Cases+LLM)',
        'config': {'use_llm': True, 'use_rules': True, 'use_cases': True},
    },
]


def execute_sql(sql, times=2):
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
            avg = sum(times_list) / len(times_list)
        conn.close()
        return round(avg, 2)
    except Exception as e:
        print(f"    Execution error: {e}")
        return None


def run_ablation(cases, case_type_name):
    print(f"\n{'=' * 80}")
    print(f"  Ablation Study - {case_type_name}")
    print(f"{'=' * 80}")

    summary = {}
    for mode in ABLATION_MODES:
        name = mode['name']
        cfg = mode['config']
        print(f"\n  --- Mode: {name} ---")
        engine = SQLRewriteEngine(**cfg, model_name="qwen2.5-coder:7b-sql")
        validator = SemanticValidator()

        total_triggered = 0
        total_semantic = 0
        total_orig = 0
        total_rew = 0
        count = 0

        for case in cases:
            original_sql = case['sql']
            try:
                rewritten_sql, _, steps = engine.rewrite(original_sql)
            except Exception as e:
                print(f"    [{case.get('id','?')}] Rewrite failed: {e}")
                continue

            original_ms = execute_sql(original_sql)
            rewritten_ms = execute_sql(rewritten_sql)

            if original_ms and rewritten_ms:
                semantic = validator.validate(original_sql, rewritten_sql)
                improvement = original_ms / rewritten_ms if rewritten_ms > 0 else 0
                if semantic:
                    total_semantic += 1
                total_orig += original_ms
                total_rew += rewritten_ms
                count += 1
                triggered = any(case.get('expected_rule', '') in (note or '') for step in steps for note in step.notes)
                if triggered:
                    total_triggered += 1
            else:
                count += 1

        avg_improvement = total_orig / total_rew if total_rew > 0 else 0
        trigger_rate = f"{total_triggered}/{len(cases)}"
        semantic_rate = f"{total_semantic}/{count}" if count > 0 else "0/0"

        summary[name] = {
            'trigger_rate': trigger_rate,
            'semantic_rate': semantic_rate,
            'avg_improvement': round(avg_improvement, 2),
            'orig_total': round(total_orig, 2),
            'rew_total': round(total_rew, 2),
        }
        print(f"    Trigger rate: {trigger_rate}")
        print(f"    Semantic OK rate: {semantic_rate}")
        print(f"    Avg improvement: {avg_improvement:.2f}x")

    print(f"\n  {'=' * 40}")
    print(f"  {case_type_name} Ablation Summary")
    print(f"  {'=' * 40}")
    print(f"  {case_type_name} Ablation Summary")
    print(f"  {'=' * 40}")
    print(f"  {'Mode':<30} {'Trigger Rate':<12} {'Semantic Rate':<12} {'Avg Improv':<10}")
    print(f"  {'-' * 64}")
    for name, data in summary.items():
        print(f"  {name:<30} {data['trigger_rate']:<12} {data['semantic_rate']:<12} {data['avg_improvement']:<10.2f}x")
    return summary


if __name__ == "__main__":
    print("SQL Rewrite System - Ablation Study")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Modes: {len(ABLATION_MODES)}")
    for m in ABLATION_MODES:
        print(f"  - {m['name']}: {m['config']}")

    std_summary = run_ablation(TEST_CASES, "Standard Tests (30 cases)")
    bnd_summary = run_ablation(BOUNDARY_TEST_CASES, "Boundary Tests (20 cases)")
