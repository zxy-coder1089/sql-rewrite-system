# run_ablation_full.py - Run all ablation modes with file-based progress logging
import sys, os, time, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from run_boundary_ablation import ABLATION_MODES, BOUNDARY_TEST_CASES, run_single_mode
from test_benchmark_pg import TEST_CASES

LOG = os.path.join(os.path.dirname(__file__), 'ablation_results.json')
log_data = {}

# Load existing results if any
if os.path.exists(LOG):
    with open(LOG, 'r') as f:
        log_data = json.load(f)
    print(f"Resuming from log: {len(log_data)} modes logged")

def save_log():
    with open(LOG, 'w') as f:
        json.dump(log_data, f, indent=2)

# Redirect stdout to log file
log_file = os.path.join(os.path.dirname(__file__), 'ablation_run.log')
f = open(log_file, 'a', encoding='utf-8')
f.write(f"\n{'='*60}\nRun started: {datetime.now()}\n{'='*60}\n")

# Monkey-patch print to also log
orig_print = print
def log_print(*args, **kw):
    orig_print(*args, **kw)
    f.write(' '.join(str(a) for a in args) + '\n')
    f.flush()

import builtins
builtins.print = log_print

try:
    # Run boundary tests for all modes
    for mode_idx in range(5):
        mode_key = f"boundary_mode_{mode_idx}"
        if mode_key in log_data:
            print(f"\nSkipping {mode_key} - already done")
            continue
        print(f"\n{'#'*60}")
        print(f"Starting boundary mode {mode_idx}: {ABLATION_MODES[mode_idx]['name']}")
        print(f"{'#'*60}")
        try:
            run_single_mode(mode_idx, BOUNDARY_TEST_CASES)
            log_data[mode_key] = "done"
            save_log()
        except Exception as e:
            print(f"ERROR in mode {mode_idx}: {e}")
            log_data[mode_key] = f"error: {e}"
            save_log()
    
    # Run standard tests for all modes
    for mode_idx in range(5):
        mode_key = f"standard_mode_{mode_idx}"
        if mode_key in log_data:
            print(f"\nSkipping {mode_key} - already done")
            continue
        print(f"\n{'#'*60}")
        print(f"Starting standard mode {mode_idx}: {ABLATION_MODES[mode_idx]['name']}")
        print(f"{'#'*60}")
        try:
            run_single_mode(mode_idx, TEST_CASES)
            log_data[mode_key] = "done"
            save_log()
        except Exception as e:
            print(f"ERROR in mode {mode_idx}: {e}")
            log_data[mode_key] = f"error: {e}"
            save_log()

except Exception as e:
    print(f"FATAL: {e}")
finally:
    save_log()
    f.close()
    builtins.print = orig_print
    print(f"\nLog saved to: {log_file}")
    print(f"Results saved to: {LOG}")
