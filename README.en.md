# SQL Query Rewrite System

Rule-guided, case-enhanced, and LLM-assisted SQL query rewrite system for PostgreSQL benchmarks.

## Architecture

```text
Input SQL
  |-- Case retrieval (example_store.py)
  |   `-- Retrieve similar rewrite examples
  |-- Rule pipeline (rewrite_engine.py)
  |   |-- P1-P5: Predicate optimization
  |   |-- J1-J3: Join optimization
  |   |-- A1-A2: Aggregation optimization
  |   |-- PG1-PG2: Pagination optimization
  |   |-- S1-S3: Safe rewrites
  |   `-- U1: UNION to UNION ALL rewrite
  |-- LLM rewrite (llm_client.py)
  |   `-- Qwen2.5-Coder:7b-SQL through Ollama
  |-- Semantic guard (rewrite_engine._guard_semantics)
  |   `-- Table/column checks and fallback handling
  `-- Output SQL
```

## Requirements

- Python 3.12 or later
- PostgreSQL 15 with a `benchmark` database
- Ollama with the `qwen2.5-coder:7b-sql` model
- Core dependencies: `pip install -r requirements.txt`
- Optional fine-tuning dependencies: `pip install -r requirements-finetune.txt`

The default PostgreSQL connection is defined in `app/db_pg.py`:

```text
host: 127.0.0.1
port: 5432
database: benchmark
user: postgres
```

## Setup

Run all commands from the `sql_rewrite_system` directory:

```bash
cd sql_rewrite_system
pip install -r requirements.txt
```

The FastAPI application initializes the PostgreSQL benchmark schema and base dataset on startup if needed. The base dataset contains about 1.3 million rows.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

To scale the benchmark data to 5x, about 7.5 million rows:

```bash
python scaleup_data.py
```

## Run The Web App

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in a browser.

## API

### Health Check

```bash
GET /health
```

### Rewrite SQL

```bash
POST /rewrite
```

Example request body:

```json
{
  "sql": "SELECT * FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2024",
  "use_llm": false,
  "use_rules": true,
  "use_cases": true,
  "model_name": "qwen2.5-coder:7b-sql"
}
```

## Tests And Experiments

Run the standard PostgreSQL benchmark suite. It contains 30 cases covering 15 rewrite rules.

```bash
python test_benchmark_pg.py
```

Run the boundary-case suite. It contains 20 cases designed to test semantic reasoning and LLM-assisted rewrites.

```bash
python test_boundary_cases.py
```

Run the full ablation experiment over standard and boundary test suites.

```bash
python test_ablation.py
```

Run one ablation mode at a time:

```bash
python run_boundary_ablation.py 0   # Rules only
python run_boundary_ablation.py 1   # LLM only
python run_boundary_ablation.py 2   # Rules + cases
python run_boundary_ablation.py 3   # Rules + LLM
python run_boundary_ablation.py 4   # Full system
```

Generate experiment charts:

```bash
python generate_charts.py
```

The chart script writes `chart_ablation.png`, `chart_finetune_comparison.png`, and `chart_complexity.png` to the parent project directory.

## Fine-Tuning

Fine-tuning scripts are kept under `finetune/`. Install the optional dependencies before using them:

```bash
pip install -r requirements-finetune.txt
```

Main scripts:

- `finetune/train_pg.py`: QLoRA fine-tuning script
- `finetune/merge_model.py`: Merge LoRA adapter weights into the base model
- `finetune/download_model.py`: Download the base model through ModelScope
- `finetune/train_pg.sh`: AutoDL-oriented training workflow

Training data is stored in `data/clean_train.jsonl` and `data/clean_valid.jsonl`.

## Project Structure

```text
sql_rewrite_system/
|-- app/
|   |-- rewrite_engine.py      # Rewrite engine with rules, cases, LLM support, and semantic guard
|   |-- llm_client.py          # Ollama client for Qwen2.5-Coder:7b-SQL
|   |-- example_store.py       # Rewrite example store and keyword retrieval
|   |-- semantic_validator.py  # Semantic equivalence validator
|   |-- main.py                # FastAPI entry point and embedded web UI
|   |-- models.py              # Pydantic request and response models
|   `-- db_pg.py               # PostgreSQL connection, schema, data generation, and benchmark helpers
|-- data/                      # Fine-tuning data
|-- finetune/                  # Fine-tuning scripts and optional data copies
|-- requirements.txt           # Core runtime dependencies
|-- requirements-finetune.txt  # Optional fine-tuning dependencies
|-- test_benchmark_pg.py       # Standard benchmark cases
|-- test_boundary_cases.py     # Boundary-case benchmark cases
|-- test_ablation.py           # Ablation experiment runner
|-- run_boundary_ablation.py   # Single-mode boundary ablation runner
|-- run_ablation_full.py       # Full ablation runner with progress logging
|-- generate_charts.py         # Experiment chart generation
|-- scaleup_data.py            # Benchmark data scale-up tool
`-- test_all_examples.py       # Smoke test for rewrite examples
```
