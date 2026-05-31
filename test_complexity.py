"""
Query Complexity Layered Analysis - Performance statistics by query complexity
Run: python test_complexity.py
"""
import time
from datetime import datetime
from app.db_pg import get_conn
from app.rewrite_engine import SQLRewriteEngine
from app.semantic_validator import SemanticValidator

from test_benchmark_pg import TEST_CASES
from test_boundary_cases import BOUNDARY_TEST_CASES

LEVELS = {
    'L0-Simple': {
        'desc': 'Single table, WHERE ≤2, no subquery/JOIN',
        'ids': [],
    },
    'L1-Moderate': {
        'desc': '2-3 table JOIN or simple subquery',
        'ids': [],
    },
    'L2-Complex': {
        'desc': '≥3 table JOIN + nested subquery/aggregate/window',
        'ids': [],
    },
}

SIMPLE_IDS = {'P1','P2','P4','P5','E1','E3','E4','S1'}
MODERATE_IDS = {'P3','P6','J1','J2','J3','A1','A2','A3','PG1','PG2','PG3'}
COMPLEX_IDS = {f'B{i}' for i in range(1, 21)}

LEVEL_MAP = {
    'L0-Simple': SIMPLE_IDS,
    'L1-Moderate': MODERATE_IDS,
    'L2-Complex': COMPLEX_IDS,
}

ALL_CASES = TEST_CASES + BOUNDARY_TEST_CASES
CASE_ID_MAP = {c['id']: c for c in ALL_CASES}

MODES = [
    {'name': 'Rules Only', 'config': {'use_llm': False, 'use_rules': True, 'use_cases': False}},
    {'name': 'Rules+Base Model', 'config': {'use_llm': True, 'use_rules': True, 'use_cases': True, 'model_name': 'qwen2.5-coder:7b'}},
    {'name': 'Rules+Finetuned Model', 'config': {'use_llm': True, 'use_rules': True, 'use_cases': True, 'model_name': 'qwen2.5-coder:7b-sql'}},
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
        return None


def run_complexity_analysis():
    print("=" * 80)
    print("           Query Complexity Layered Analysis")
    print("=" * 80)
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\nQuery Complexity Classification:")
    for level, info in LEVELS.items():
        case_ids = LEVEL_MAP[level]
        cases = [c for cid, c in CASE_ID_MAP.items() if cid in case_ids]
        print(f"  {level}: {len(cases)} cases - {info['desc']}")
        print(f"      Case IDs: {', '.join(sorted(case_ids))}")

    results = {}
    for level_name, case_ids in LEVEL_MAP.items():
        cases = [CASE_ID_MAP[cid] for cid in case_ids if cid in CASE_ID_MAP]
        results[level_name] = {}
        for mode in MODES:
            name = mode['name']
            cfg = mode['config'].copy()
            model = cfg.pop('model_name', 'qwen2.5-coder:7b-sql')
            engine = SQLRewriteEngine(**cfg, model_name=model)

            total_orig = 0
            total_rew = 0
            count = 0

            for case in cases:
                original_sql = case['sql']
                try:
                    rewritten_sql, _, _ = engine.rewrite(original_sql)
                except Exception:
                    continue
                original_ms = execute_sql(original_sql)
                rewritten_ms = execute_sql(rewritten_sql)
                if original_ms and rewritten_ms:
                    total_orig += original_ms
                    total_rew += rewritten_ms
                    count += 1

            avg_imp = total_orig / total_rew if total_rew > 0 else 0
            results[level_name][name] = round(avg_imp, 2)

    print(f"\n{'=' * 60}")
    print(f"  Layered Analysis Results")
    print(f"{'=' * 60}")
    header = f"  {'Level':<12} {'Rules Only':<14} {'Rules+Base':<14} {'Rules+FT':<14}"
    print(header)
    print(f"  {'-' * 54}")
    for level_name in ['L0-Simple', 'L1-Moderate', 'L2-Complex']:
        r = results[level_name]
        print(f"  {level_name:<12} {r['Rules Only']:<14.2f}x {r['Rules+Base Model']:<14.2f}x {r['Rules+Finetuned Model']:<14.2f}x")
    print()

    return results


if __name__ == "__main__":
    run_complexity_analysis()
