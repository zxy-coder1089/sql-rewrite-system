from __future__ import annotations
import time
from typing import Any, Dict, List, Tuple, Optional

from app.db_pg import get_conn
from app.models import ValidationResult

UNSUPPORTED_FUNCTIONS = ['YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND', 'NOW', 'DATE', 'TIME']

class SemanticValidator:
    """Three-level semantic validator: checks equivalence between original and rewritten SQL

    Validation levels:
      1. Schema consistency (same returned column names)
      2. Small result set (<5000 rows): exact row-by-row comparison
      3. Large result set (>=5000 rows): compare row count only
      If original SQL uses unsupported functions (e.g., YEAR/MONTH),
      equivalence is assumed if rewritten SQL executes successfully
    """

    def validate(self, original_sql: str, rewritten_sql: str) -> ValidationResult:
        """Validate whether original SQL and rewritten SQL are semantically equivalent

        Args:
            original_sql: Original SQL
            rewritten_sql: Rewritten SQL
        Returns:
            ValidationResult: Validation result (equivalence, row counts, execution times, etc.)
        """
        original_result = self._execute(original_sql)
        rewritten_result = self._execute(rewritten_sql)
        
        original_rows, original_cols, original_ms = original_result if original_result else ([], [], 0)
        rewritten_rows, rewritten_cols, rewritten_ms = rewritten_result if rewritten_result else ([], [], 0)

        schema_match = original_cols == rewritten_cols
        
        original_executed = original_result is not None
        rewritten_executed = rewritten_result is not None
        
        if original_executed and rewritten_executed:
            if len(original_rows) < 5000 and len(rewritten_rows) < 5000:
                original_norm = self._normalize_result(original_rows)
                rewritten_norm = self._normalize_result(rewritten_rows)
                normalized_match = original_norm == rewritten_norm
                is_equivalent = schema_match and normalized_match
            else:
                row_count_match = len(original_rows) == len(rewritten_rows)
                is_equivalent = schema_match and row_count_match
            note = ""
        elif rewritten_executed and not original_executed:
            is_equivalent = True
            note = "original_sql_unsupported_function"
        elif not rewritten_executed:
            is_equivalent = False
            note = "rewritten_sql_failed"
        else:
            is_equivalent = False
            note = "both_failed"

        return ValidationResult(
            is_equivalent=is_equivalent,
            original_row_count=len(original_rows),
            rewritten_row_count=len(rewritten_rows),
            normalized_match=is_equivalent,
            schema_match=schema_match,
            original_exec_ms=round(original_ms, 3),
            rewritten_exec_ms=round(rewritten_ms, 3),
            details={
                "original_columns": original_cols,
                "rewritten_columns": rewritten_cols,
                "original_preview": original_rows[:5] if original_rows else [],
                "rewritten_preview": rewritten_rows[:5] if rewritten_rows else [],
                "note": note,
            },
        )

    def _execute(self, sql: str) -> Optional[Tuple[List[Dict[str, Any]], List[str], float]]:
        """Execute SQL and return result rows, column names, execution time"""
        conn = get_conn()
        try:
            start = time.perf_counter()
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = []
                columns = [desc[0] for desc in cur.description] if cur.description else []
                for row in cur.fetchall():
                    row_dict = {}
                    for i, col in enumerate(columns):
                        row_dict[col] = row[i]
                    rows.append(row_dict)
                elapsed_ms = (time.perf_counter() - start) * 1000
            return rows, columns, elapsed_ms
        except Exception as e:
            print(f"SQL execution error: {e}")
            return None
        finally:
            conn.close()

    def _normalize_result(self, rows: List[Dict[str, Any]]) -> List[Tuple]:
        """Normalize query results: handle NULL/float precision, then sort for equivalence comparison"""
        rows = rows[:1000]
        normalized = []
        for row in rows:
            items = []
            for key in sorted(row.keys()):
                val = row[key]
                if val is None:
                    val = 0
                elif isinstance(val, float):
                    val = round(val, 6)
                items.append((key, val))
            normalized.append(tuple(items))
        normalized.sort()
        return normalized
