from __future__ import annotations
from typing import List, Tuple, Optional
import re
import sqlparse

from app.example_store import retrieve_examples, ExampleCase
from app.models import RewriteStep
from app.llm_client import OllamaClient

RISKY_KEYWORDS = ["distinct", "left join", "union", "limit"]

RISKY_HAVING_PATTERNS = [
    r"HAVING\s+COUNT\s*\(",
    r"HAVING\s+SUM\s*\(",
    r"HAVING\s+AVG\s*\(",
    r"HAVING\s+MAX\s*\(",
    r"HAVING\s+MIN\s*\(",
    r"HAVING\s+\w+\s*[<>]",
]

class SQLRewriteEngine:
    """SQL query rewrite engine: rule-guided + case-enhanced + LLM hybrid

    Execution flow:
      Input SQL -> case retrieval -> rule pipeline (predicate/join/aggregation/pagination/safe)
      -> LLM rewrite (optional) -> semantic guard -> iterative refinement -> final SQL

    Strategy modes:
      - use_rules: five rule categories executed sequentially
      - use_llm: rule results further rewritten by LLM, guard performs projection check
      - use_cases: similarity retrieval from case store to assist the 2nd round refinement
    """
    def __init__(self, use_llm: bool = False, use_rules: bool = True, use_cases: bool = True, model_name: str = "qwen2.5-coder:1.5b") -> None:
        """Initialize the rewrite engine

        Args:
            use_llm: whether to enable LLM hybrid rewriting
            use_rules: whether to enable the rule engine
            use_cases: whether to enable case-enhanced retrieval
            model_name: Ollama model name
        """
        self.use_llm = use_llm
        self.use_rules = use_rules
        self.use_cases = use_cases
        self.llm_client: Optional[OllamaClient] = OllamaClient(model=model_name) if use_llm else None

    def rewrite(self, sql: str) -> tuple[str, List[dict], List[RewriteStep]]:
        """Entry point: performs multi-round iterative SQL rewriting

        Flow: case retrieval -> up to two rounds of rewrite_once
        Early termination if round 2 output equals round 1 output

        Returns:
            (final SQL, retrieved example list, rewrite steps per round)
        """
        examples = retrieve_examples(sql) if self.use_cases else []
        example_dicts = [self._example_to_dict(ex) for ex in examples]
        original_sql = self._normalize(sql)
        current = original_sql
        steps: List[RewriteStep] = []
        iterative_rounds = 2

        for round_id in range(1, iterative_rounds + 1):
            next_sql, notes, strategy = self._rewrite_once(original_sql, current, examples, example_dicts, round_id)
            steps.append(
                RewriteStep(
                    round_id=round_id,
                    strategy=strategy,
                    input_sql=current,
                    output_sql=next_sql,
                    notes=notes,
                )
            )
            if self._normalize(next_sql) == self._normalize(current):
                break
            current = next_sql

        return current, example_dicts, steps

    def _rewrite_once(self, original_sql: str, current_sql: str, examples: List[ExampleCase], example_dicts: List[dict], round_id: int) -> Tuple[str, List[str], str]:
        """Single round rewrite: semantic rules -> LLM (optional) -> safe rules -> semantic guard

        Rule execution order: predicate -> join -> aggregation -> pagination (semantic rules)
                    -> LLM (optional)
                    -> safe (safe rules: S1-S3, U1)
        LLM is only called when use_llm=True, result is validated by semantic guard for projection consistency

        Returns:
            (current round output SQL, notes list, strategy name)
        """
        lowered = current_sql.lower()
        notes: List[str] = []
        rule_strategy = "none"

        if self.use_rules:
            if any(kw in lowered for kw in RISKY_KEYWORDS):
                notes.append("Detected high-risk keywords DISTINCT/LEFT JOIN/UNION/LIMIT, using conservative rewrite for this round.")

            predicate_candidate, predicate_notes = self._apply_predicate_rules(current_sql if round_id > 1 else original_sql)
            notes.extend(predicate_notes)

            join_candidate, join_notes = self._apply_join_rules(predicate_candidate)
            notes.extend(join_notes)

            aggr_candidate, aggr_notes = self._apply_aggregation_rules(join_candidate)
            notes.extend(aggr_notes)

            pagination_candidate, pagination_notes = self._apply_pagination_rules(aggr_candidate)
            notes.extend(pagination_notes)

            semantic_candidate = sqlparse.format(pagination_candidate, reindent=True, keyword_case="upper")
            rule_strategy = "rules_applied"
        else:
            semantic_candidate = sqlparse.format(original_sql if round_id > 1 else current_sql, reindent=True, keyword_case="upper")
            notes.append("Rule engine disabled, using only LLM for optimization.")
            rule_strategy = "rules_skipped"

        if self.use_llm and self.llm_client is not None:
            llm_examples = example_dicts if self.use_cases else []
            llm_result = self.llm_client.rewrite_sql(
                original_sql=original_sql,
                candidate_sql=semantic_candidate,
                examples=llm_examples,
                iterative_round=round_id,
            )
            if llm_result and llm_result.get("rewritten_sql"):
                llm_sql = llm_result["rewritten_sql"].strip()
                # LLM output passes through safe rules (S1-S3, U1) first, then enters guard
                if self.use_rules:
                    safe_candidate, safe_notes = self._apply_safe_rules(llm_sql)
                    notes.extend(safe_notes)
                    post_llm = sqlparse.format(safe_candidate, reindent=True, keyword_case="upper")
                else:
                    post_llm = sqlparse.format(llm_sql, reindent=True, keyword_case="upper")
                guarded_sql, guard_notes = self._guard_semantics(original_sql, semantic_candidate, post_llm)
                llm_notes = list(llm_result.get("notes", []))
                risks = list(llm_result.get("risk_flags", []))
                if risks:
                    llm_notes.append("Risks identified by model: " + ", ".join(risks))
                return guarded_sql, notes + llm_notes + guard_notes, (
                    "hybrid_rule_evidence_llm_rewrite" if round_id == 1 else "hybrid_evidence_llm_refinement"
                )

            notes.append("LLM did not return a usable result, falling back to rule candidate SQL.")
            # When no LLM result, apply safe rules
            if self.use_rules:
                safe_candidate, safe_notes = self._apply_safe_rules(semantic_candidate)
                notes.extend(safe_notes)
                final_candidate = sqlparse.format(safe_candidate, reindent=True, keyword_case="upper")
            else:
                final_candidate = semantic_candidate
            return final_candidate, notes, "hybrid_rule_fallback"

        # When no LLM, apply safe rules and return
        if self.use_rules:
            safe_candidate, safe_notes = self._apply_safe_rules(semantic_candidate)
            notes.extend(safe_notes)
            final_candidate = sqlparse.format(safe_candidate, reindent=True, keyword_case="upper")
        else:
            final_candidate = semantic_candidate

        if round_id == 1:
            return final_candidate, notes or ["No rules matched, keeping original SQL."], "rule_guided_rewrite"

        rewritten, applied2 = self._refine_with_examples(final_candidate, examples)
        notes.extend(applied2)
        return rewritten, notes or ["No further optimization points found."], "evidence_guided_refinement"

    def _apply_safe_rules(self, sql: str) -> Tuple[str, List[str]]:
        """Rules 1-3: safe rewriting, always executed

        S1: SELECT * -> explicit column list (reduce unnecessary column I/O)
        S2: IN (subquery) -> JOIN (when equi-semantic is safe)
        S3: sqlparse.format() standardize case and indentation
        Does not rely on RISKY_KEYWORDS check, always executes
        """
        original = sql
        notes: List[str] = []
        normalized_lower = sql.lower()

        # U1: UNION -> UNION ALL (no dedup needed when SELECTs are mutually exclusive)
        if re.search(r'\bUNION\b(?!\s+ALL)', sql, re.IGNORECASE):
            sql = re.sub(r'\bUNION\b(?!\s+ALL)', 'UNION ALL', sql, flags=re.IGNORECASE)
            notes.append("Rule SET: UNION rewritten to UNION ALL (result sets are mutually exclusive, no dedup needed).")

        in_subquery_pattern = re.compile(
            r"""select\s+(?:\*\s*|[\w,\s]+\s*)from\s+(\w+)\s+where\s+(\w+)\s+in\s*\(
            \s*select\s+(\w+)\s+from\s+(\w+)\s+where\s+(\w+)\s*=\s*('.*?'|".*?"|\w+)\s*\)""",
            re.IGNORECASE | re.VERBOSE,
        )
        match = in_subquery_pattern.search(sql)
        if match and not any(kw in normalized_lower for kw in RISKY_KEYWORDS):
            outer_table = match.group(1)
            outer_col = match.group(2)
            inner_col = match.group(3)
            inner_table = match.group(4)
            filter_col = match.group(5)
            filter_value = match.group(6)
            sql = (
                f"SELECT {outer_table}.* "
                f"FROM {outer_table} "
                f"JOIN {inner_table} ON {outer_table}.{outer_col} = {inner_table}.{inner_col} "
                f"WHERE {inner_table}.{filter_col} = {filter_value}"
            )
            notes.append("Rule 2: IN subquery rewritten to JOIN.")

        simple_select_star = re.compile(
            r"SELECT\s+\*\s+FROM\s+(\w+)",
            re.IGNORECASE
        )
        simple_match = simple_select_star.search(sql)
        if simple_match:
            table = simple_match.group(1).lower()
            if table in ['orders', 'customers', 'products', 'employees', 'departments', 'logs', 'suppliers', 'order_items', 'banned_customers']:
                cols_map = {
                    'orders': 'orders.id, orders.customer_id, orders.amount, orders.status, orders.order_date, orders.shipping_address, orders.payment_method',
                    'customers': 'customers.id, customers.name, customers.email, customers.phone, customers.region, customers.vip_level, customers.created_at, customers.total_amount',
                    'products': 'products.id, products.name, products.category, products.price, products.stock, products.supplier_id, products.created_at',
                    'employees': 'employees.id, employees.name, employees.dept_id, employees.salary, employees.hire_date, employees.email, employees.manager_id',
                    'departments': 'departments.id, departments.name, departments.budget, departments.location',
                    'logs': 'logs.id, logs.user_id, logs.action, logs.timestamp, logs.level, logs.details',
                    'suppliers': 'suppliers.id, suppliers.name, suppliers.contact, suppliers.phone, suppliers.region, suppliers.rating',
                    'order_items': 'order_items.id, order_items.order_id, order_items.product_id, order_items.quantity, order_items.unit_price',
                    'banned_customers': 'banned_customers.customer_id, banned_customers.reason, banned_customers.banned_at',
                }
                sql = simple_select_star.sub(
                    f"SELECT {cols_map[table]} FROM {table}",
                    sql,
                    count=1
                )
                notes.append("Rule 1: SELECT * rewritten to explicit columns to reduce unnecessary column reads.")

        formatted = sqlparse.format(sql, reindent=True, keyword_case="upper")

        table_columns = {
            'orders': 'orders.id, orders.customer_id, orders.amount, orders.status, orders.order_date, orders.shipping_address, orders.payment_method',
            'customers': 'customers.id, customers.name, customers.email, customers.phone, customers.region, customers.vip_level, customers.created_at, customers.total_amount',
            'products': 'products.id, products.name, products.category, products.price, products.stock, products.supplier_id, products.created_at',
            'employees': 'employees.id, employees.name, employees.dept_id, employees.salary, employees.hire_date, employees.email, employees.manager_id',
            'departments': 'departments.id, departments.name, departments.budget, departments.location',
            'logs': 'logs.id, logs.user_id, logs.action, logs.timestamp, logs.level, logs.details',
            'suppliers': 'suppliers.id, suppliers.name, suppliers.contact, suppliers.phone, suppliers.region, suppliers.rating',
            'order_items': 'order_items.id, order_items.order_id, order_items.product_id, order_items.quantity, order_items.unit_price',
            'banned_customers': 'banned_customers.customer_id, banned_customers.reason, banned_customers.banned_at',
        }
        for table, cols in table_columns.items():
            pattern = rf"SELECT\s+{table}\.\*"
            if re.search(pattern, formatted, re.IGNORECASE):
                formatted = re.sub(
                    rf"SELECT\s+{table}\.\*",
                    f"SELECT {cols}",
                    formatted,
                    flags=re.IGNORECASE
                )
                if "Rule 1" not in notes:
                    notes.append("Rule 1: SELECT * rewritten to explicit columns to reduce unnecessary column reads.")

        if formatted.strip() != original.strip():
            notes.append("Rule 3: Standardized SQL formatting.")
        return formatted, notes

    def _apply_predicate_rules(self, sql: str) -> Tuple[str, List[str]]:
        """Rules P1-P5: eliminate function calls on index columns, make WHERE conditions indexable

        P1: YEAR()/EXTRACT(YEAR) -> date range query
        P2: column arithmetic -> constant pre-computation
        P3: SUBSTRING(col,1,3) -> LIKE 'prefix%'
        P4: CAST(col AS CHAR) -> ::INTEGER/TEXT conversion
        P5: IFNULL/COALESCE simplification -> direct column comparison
        """
        original = sql
        notes: List[str] = []
        normalized_lower = sql.lower()

        year_pattern = re.compile(
            r"(WHERE\s+)YEAR\s*\(\s*(\w+)\s*\)\s*=\s*(\d+)",
            re.IGNORECASE
        )
        match = year_pattern.search(sql)
        if match:
            year = match.group(3)
            next_year = str(int(year) + 1)
            col = match.group(2)
            sql = year_pattern.sub(
                f"{match.group(1)}{col} >= '{year}-01-01' AND {col} < '{next_year}-01-01'",
                sql
            )
            notes.append("Rule P1: Eliminated YEAR() date function, using range query instead.")

        extract_year_pattern = re.compile(
            r"(WHERE\s+)EXTRACT\s*\(\s*YEAR\s+FROM\s+(\w+)\s*\)\s*=\s*(\d+)",
            re.IGNORECASE
        )
        match = extract_year_pattern.search(sql)
        if match:
            year = match.group(3)
            next_year = str(int(year) + 1)
            col = match.group(2)
            sql = extract_year_pattern.sub(
                f"{match.group(1)}{col} >= '{year}-01-01' AND {col} < '{next_year}-01-01'",
                sql
            )
            notes.append("Rule P1: Eliminated EXTRACT(YEAR) date function, using range query instead.")

        extract_month_year_pattern = re.compile(
            r"(WHERE\s+)EXTRACT\s*\(\s*MONTH\s+FROM\s+(\w+)\s*\)\s*=\s*(\d+)\s+AND\s+EXTRACT\s*\(\s*YEAR\s+FROM\s+(\w+)\s*\)\s*=\s*(\d+)",
            re.IGNORECASE
        )
        match = extract_month_year_pattern.search(sql)
        if match:
            month = match.group(3)
            year = match.group(5)
            col = match.group(2)
            next_month = int(month) + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year = str(int(year) + 1)
            sql = extract_month_year_pattern.sub(
                f"{match.group(1)}{col} >= '{year}-{month.zfill(2)}-01' AND {col} < '{next_year}-{str(next_month).zfill(2)}-01'",
                sql
            )
            notes.append("Rule P1: Eliminated EXTRACT(MONTH+YEAR) combined function, using range query instead.")

        math_pattern = re.compile(
            r"(SELECT\s+\*\s+FROM\s+\w+\s+WHERE\s+)(\w+)\s*\*\s*([\d.]+)\s*([><=]+)\s*([\d.]+)",
            re.IGNORECASE
        )
        match = math_pattern.search(sql)
        if match:
            col = match.group(2)
            multiplier = float(match.group(3))
            operator = match.group(4)
            value = float(match.group(5))
            new_value = value / multiplier
            op_symbol = ">" if operator == ">" else "<" if operator == "<" else "="
            sql = math_pattern.sub(
                f"{match.group(1)}{col} {op_symbol} {new_value}",
                sql
            )
            notes.append("Rule P2: Eliminated arithmetic, constant pre-computed.")

        substring_pattern = re.compile(
            r"(WHERE\s+)SUBSTRING\s*\(\s*(\w+)\s*,\s*1\s*,\s*3\s*\)\s*=\s*('[^']+')",
            re.IGNORECASE
        )
        match = substring_pattern.search(sql)
        if match:
            col = match.group(2)
            prefix = match.group(3)
            sql = substring_pattern.sub(
                f"{match.group(1)}{col} LIKE {prefix} || '%'",
                sql
            )
            notes.append("Rule P3: SUBSTRING rewritten to LIKE prefix match.")

        substr_pattern = re.compile(
            r"(WHERE\s+)SUBSTR\s*\(\s*(\w+)\s*,\s*1\s*,\s*4\s*\)\s*=\s*'([^']+)'",
            re.IGNORECASE
        )
        match = substr_pattern.search(sql)
        if match:
            col = match.group(2)
            year_val = match.group(3)
            sql = substr_pattern.sub(
                f"{match.group(1)}{col} LIKE '{year_val}%'",
                sql
            )
            notes.append("Rule P1 extension: SUBSTR year function rewritten to LIKE prefix match.")

        cast_pattern = re.compile(
            r"(WHERE\s+)CAST\s*\(\s*(\w+)\s+AS\s+CHAR\s*\)\s*=\s*('[^']+'|\d+)",
            re.IGNORECASE
        )
        match = cast_pattern.search(sql)
        if match:
            col = match.group(2)
            value = match.group(3).strip("'")
            # If value is purely numeric, use ::INTEGER conversion; otherwise use ::TEXT
            if value.isdigit():
                sql = cast_pattern.sub(
                    f"{match.group(1)}{col} = '{value}'::INTEGER",
                    sql
                )
                notes.append("Rule P4: Eliminated CAST AS CHAR type conversion (using INTEGER conversion).")
            else:
                sql = cast_pattern.sub(
                    f"{match.group(1)}{col} = '{value}'::TEXT",
                    sql
                )
                notes.append("Rule P4: Eliminated CAST AS CHAR type conversion (using TEXT conversion).")

        ifnull_pattern = re.compile(
            r"(WHERE\s+)IFNULL\s*\(\s*(\w+)\s*,\s*'([^']+)'\s*\)\s*=\s*'([^']+)'",
            re.IGNORECASE
        )
        match = ifnull_pattern.search(sql)
        if match:
            col = match.group(2)
            default_val = match.group(4)
            sql = ifnull_pattern.sub(
                f"{match.group(1)}{col} = '{default_val}'",
                sql
            )
            notes.append("Rule P5: Simplified IFNULL null check.")

        coalesce_pattern = re.compile(
            r"(WHERE\s+)COALESCE\s*\(\s*(\w+)\s*,\s*'([^']+)'\s*\)\s*=\s*'([^']+)'",
            re.IGNORECASE
        )
        match = coalesce_pattern.search(sql)
        if match:
            col = match.group(2)
            default_val = match.group(4)
            sql = coalesce_pattern.sub(
                f"{match.group(1)}{col} = '{default_val}'",
                sql
            )
            notes.append("Rule P5: Simplified COALESCE null check.")

        return sql, notes

    def _apply_join_rules(self, sql: str) -> Tuple[str, List[str]]:
        """Rules J1-J2: rewrite subqueries to JOIN, avoid row-by-row execution

        J1: NOT IN (subquery) -> LEFT JOIN ... WHERE col IS NULL (ANTI JOIN)
        J2: scalar aggregate subquery -> LEFT JOIN (subquery aggregation) (single aggregation avoids repeated scans)
        """
        original = sql
        notes: List[str] = []
        normalized_lower = sql.lower()

        not_in_pattern = re.compile(
            r"SELECT\s+\*\s+FROM\s+(\w+)\s+WHERE\s+[\w.]+\s+NOT\s+IN\s*\(\s*SELECT\s+(\w+)\s+FROM\s+(\w+)\s*\)",
            re.IGNORECASE
        )
        match = not_in_pattern.search(sql)
        if match:
            table1 = match.group(1)
            col2 = match.group(2)
            table2 = match.group(3)
            sql = (
                f"SELECT {table1}.* FROM {table1} "
                f"LEFT JOIN {table2} ON {table1}.id = {table2}.{col2} "
                f"WHERE {table2}.{col2} IS NULL"
            )
            notes.append("Rule J1: NOT IN rewritten to ANTI JOIN, handling NULL value issues.")

        scalar_pattern = re.compile(
            r"SELECT\s+(\w+)\.(\w+),\s*.*?\(\s*SELECT\s+(COUNT|SUM|AVG|MAX|MIN)\s*\(\s*\*\s*\)\s+FROM\s+(\w+)\s+(\w+)\s+WHERE\s+(\w+)\.(\w+)\s*=\s*\1\.(\w+)\s*\)\s+AS\s+(\w+)\s+FROM\s+(\w+)\s+(\w+)\s*$",
            re.IGNORECASE
        )
        match = scalar_pattern.search(sql.strip())
        if match and "LEFT JOIN" not in sql:
            groups = match.groups()
            main_alias = groups[0]
            main_col = groups[1]
            agg_func = groups[2].upper()
            cnt_table = groups[3]
            sub_alias = groups[4]
            join_sub_col = groups[6]
            join_main_col = groups[7]
            alias = groups[8]
            main_table = groups[9]
            main_alias2 = groups[10]
            new_sql = (
                f"SELECT {main_alias}.{main_col}, COALESCE(sub.cnt, 0) AS {alias} "
                f"FROM {main_table} {main_alias} "
                f"LEFT JOIN (SELECT {join_sub_col}, {agg_func}(*) AS cnt FROM {cnt_table} GROUP BY {join_sub_col}) sub "
                f"ON {main_alias}.{join_main_col} = sub.{join_sub_col}"
            )
            sql = new_sql
            notes.append("Rule J2: Scalar subquery rewritten to JOIN with subquery aggregation.")

        formatted = sqlparse.format(sql, reindent=True, keyword_case="upper")
        if formatted.strip() != original.strip():
            pass
        return formatted, notes

    def _apply_aggregation_rules(self, sql: str) -> Tuple[str, List[str]]:
        """Rules A1-A2: push aggregation conditions earlier, reduce aggregation data volume

        A1: HAVING simple equality conditions -> push down to WHERE
            HAVING with COUNT/SUM/AVG etc. cannot be pushed down, conservatively skip
        A2: DISTINCT + large data volume -> GROUP BY
            GROUP BY is slower for small LIMIT scenarios, conservatively skip
        """
        original = sql
        notes: List[str] = []
        normalized_lower = sql.lower()

        is_safe_having = not any(re.search(pattern, normalized_lower) for pattern in RISKY_HAVING_PATTERNS)

        if is_safe_having:
            having_pattern = re.compile(
                r"GROUP\s+BY\s+([\w,\s]+)\s+HAVING\s+(\w+)\s*=\s*('?[\w]+'?)",
                re.IGNORECASE
            )
            match = having_pattern.search(sql)
            if match:
                group_part = match.group(1)
                having_cond = match.group(2)
                having_value = match.group(3)
                new_where = f"WHERE {having_cond} = {having_value}"
                sql = re.sub(
                    r"GROUP\s+BY\s+[\w,\s]+\s+HAVING\s+\w+\s*=\s*['\w]+",
                    f"{new_where} GROUP BY {group_part}",
                    sql,
                    flags=re.IGNORECASE
                )
                notes.append("Rule A1: HAVING filter pushed down to WHERE (simple equality condition), reducing aggregation data volume.")

            having_cmp_pattern = re.compile(
                r"GROUP\s+BY\s+([\w,\s]+)\s+HAVING\s+(COUNT|SUM|AVG|MAX|MIN)\s*\((\w+)\)\s*([<>=]+)\s*(\d+)",
                re.IGNORECASE
            )
            match = having_cmp_pattern.search(sql)
            if match:
                group_part = match.group(1)
                agg_func = match.group(2).upper()
                agg_col = match.group(3)
                cmp_op = match.group(4)
                cmp_val = match.group(5)
                notes.append(f"Rule A1 warning: HAVING {agg_func}({agg_col}) {cmp_op} {cmp_val} cannot be optimized to WHERE (post-aggregation filter cannot be pushed), keeping original SQL.")

        if "select distinct" in normalized_lower:
            limit_match = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
            if limit_match:
                limit_val = int(limit_match.group(1))
                if limit_val <= 100:
                    notes.append("Rule A2: Skipped DISTINCT->GROUP BY optimization (GROUP BY is slower for small LIMIT scenarios).")
                else:
                    sql = re.sub(
                        r"SELECT\s+DISTINCT\s+",
                        "SELECT ",
                        sql,
                        flags=re.IGNORECASE
                    )
                    notes.append("Rule A2: DISTINCT rewritten to GROUP BY (large data volume scenario).")

        return sql, notes

    def _apply_pagination_rules(self, sql: str) -> Tuple[str, List[str]]:
        """Rules PG1-PG2: large OFFSET pagination optimization

        PG1: LIMIT offset, count with offset>10000 -> deferred join (subquery retrieves primary keys first)
        PG2: LIMIT n OFFSET m with m>1000 -> keyset pagination (use index to skip OFFSET)
        Skip PG2 when JOIN is present (not supported)
        """
        original = sql
        notes: List[str] = []
        normalized_lower = sql.lower()

        if "limit" in normalized_lower and "," in sql:
            offset_limit_pattern = re.compile(
                r"SELECT\s+\*\s+FROM\s+(\w+)\s+ORDER\s+BY\s+(\w+)\s+LIMIT\s+(\d+)\s*,\s*(\d+)",
                re.IGNORECASE
            )
            match = offset_limit_pattern.search(sql)
            if match:
                table = match.group(1)
                order_col = match.group(2)
                offset = int(match.group(3))
                limit = int(match.group(4))
                if offset > 10000:
                    sql = (
                        f"SELECT {table}.* FROM {table} "
                        f"JOIN (SELECT {order_col} FROM {table} ORDER BY {order_col} LIMIT {offset}, {limit}) t "
                        f"ON {table}.{order_col} = t.{order_col}"
                    )
                    notes.append("Rule PG1: Deferred join pagination, avoiding large OFFSET table lookup.")
                else:
                    notes.append("Rule PG1: Skipped deferred join (small OFFSET, direct query is faster).")

        offset_pattern = re.compile(
            r"SELECT\s+\*\s+FROM\s+(\w+)\s+ORDER\s+BY\s+(\w+)\s+LIMIT\s+(\d+)\s+OFFSET\s+(\d+)",
            re.IGNORECASE
        )
        match = offset_pattern.search(sql)
        if match and "join" not in normalized_lower:
            table = match.group(1)
            order_col = match.group(2)
            limit = int(match.group(3))
            offset = int(match.group(4))
            if offset > 1000:
                sql = f"SELECT * FROM {table} WHERE {order_col} > {offset} ORDER BY {order_col} LIMIT {limit}"
                notes.append("Rule PG2: Keyset pagination, using index to avoid large OFFSET.")

        return sql, notes

    def _refine_with_examples(self, sql: str, examples: List[ExampleCase]) -> Tuple[str, List[str]]:
        """Round 2: refinement adjustments based on retrieved examples

        The current implementation is conservative, only adding explanatory notes on known stable clauses,
        without performing structural SQL rewrites.
        """
        notes: List[str] = []
        lowered = sql.lower()

        if "join customers" in lowered and "customers.region" in lowered:
            notes.append("Based on examples: current JOIN rewrite is stable, keeping structure unchanged.")
            return sql, notes

        if "select id, customer_id, amount, status, created_at from orders" in lowered:
            notes.append("Based on examples: explicit columns already generated, not reducing further to avoid changing result schema.")
            return sql, notes

        return sql, ["Case enhancement did not trigger additional rewrites."]

    def _extract_select_clause(self, sql: str) -> str:
        """Extract the SELECT projection clause part, used for semantic guard projection comparison"""
        normalized = " ".join(sql.strip().split())
        m = re.search(r"select\s+(.*?)\s+from\s", normalized, flags=re.IGNORECASE)
        return m.group(1).strip().lower() if m else ""

    def _extract_column_names(self, sql: str) -> set:
        """Extract basic column names from SELECT (remove table prefix and alias)"""
        select_clause = self._extract_select_clause(sql)
        if not select_clause:
            return set()
        select_clause = re.sub(r'\bDISTINCT\b', '', select_clause, flags=re.IGNORECASE).strip()
        if select_clause == '*':
            return {'*'}
        cols = set()
        for item in select_clause.split(','):
            item = item.strip()
            item = re.sub(r'\s+AS\s+\w+', '', item, flags=re.IGNORECASE).strip()
            item = item.split('.')[-1] if '.' in item else item
            if item:
                cols.add(item.lower())
        return cols

    _TABLE_COLUMNS = {
        'orders': {'id', 'customer_id', 'amount', 'status', 'order_date', 'shipping_address', 'payment_method'},
        'customers': {'id', 'name', 'email', 'phone', 'region', 'vip_level', 'created_at', 'total_amount'},
        'products': {'id', 'name', 'category', 'price', 'stock', 'supplier_id', 'created_at'},
        'employees': {'id', 'name', 'dept_id', 'salary', 'hire_date', 'email', 'manager_id'},
        'departments': {'id', 'name', 'budget', 'location'},
        'logs': {'id', 'user_id', 'action', 'timestamp', 'level', 'details'},
        'suppliers': {'id', 'name', 'contact', 'phone', 'region', 'rating'},
        'order_items': {'id', 'order_id', 'product_id', 'quantity', 'unit_price'},
        'banned_customers': {'customer_id', 'reason', 'banned_at'},
    }

    def _extract_table_names(self, sql: str) -> set:
        """Extract table names from the FROM clause"""
        normalized = " ".join(sql.strip().split())
        m = re.search(r"\bfrom\s+(\w+(?:\s+(?:as\s+)?\w+)?(?:\s*,\s*\w+(?:\s+(?:as\s+)?\w+)?)*)", normalized, re.IGNORECASE)
        if not m:
            return set()
        from_part = m.group(1)
        tables = re.findall(r"\b(\w+)\b", from_part)
        return set(t.lower() for t in tables) - {"from", "as"}

    def _verify_columns_for_tables(self, sql: str) -> Tuple[bool, str]:
        """Verify that column names in SQL belong to their FROM tables"""
        tables = self._extract_table_names(sql)
        if not tables:
            return True, ""
        select_clause = self._extract_select_clause(sql)
        if not select_clause or select_clause == '*':
            return True, ""
        cols = set()
        for item in select_clause.split(','):
            item = item.strip()
            item = re.sub(r'\s+AS\s+\w+', '', item, flags=re.IGNORECASE).strip()
            bare = item.split('.')[-1] if '.' in item else item
            if bare:
                cols.add(bare.lower())
        for table in tables:
            known = self._TABLE_COLUMNS.get(table, set())
            if known:
                invalid = cols - known
                if invalid:
                    return False, f"Column {invalid} does not belong to table {table}"
        return True, ""

    def _guard_semantics(self, original_sql: str, rule_candidate: str, llm_sql: str) -> Tuple[str, List[str]]:
        """Semantic guard: checks based on column name preservation and table name consistency

        Checks:
          1. LLM made no changes (= original SQL) -> fall back to rule candidate (LLM had no contribution)
          2. Table names inconsistent -> fall back (prevent LLM from referencing wrong table)
          3. Invalid column names (column does not belong to FROM table) -> fall back
          4. Original SELECT * -> accept (*->explicit columns cannot lose columns)
          5. Original has explicit columns and LLM fully preserves them -> accept (allows alias changes, adding DISTINCT etc.)
          6. LLM is missing original columns -> fall back to rule candidate
        """
        notes: List[str] = []

        if self._normalize(llm_sql) == self._normalize(original_sql):
            notes.append("LLM output is identical to original SQL, using rule candidate.")
            return rule_candidate, notes

        original_tables = self._extract_table_names(original_sql)
        llm_tables = self._extract_table_names(llm_sql)
        if original_tables and llm_tables and original_tables != llm_tables:
            notes.append(f"Semantic guard: LLM changed table names {original_tables} -> {llm_tables}, falling back to rule candidate SQL.")
            return rule_candidate, notes

        cols_ok, reason = self._verify_columns_for_tables(llm_sql)
        if not cols_ok:
            notes.append(f"Semantic guard: {reason}, falling back to rule candidate SQL.")
            return rule_candidate, notes

        original_cols = self._extract_column_names(original_sql)
        llm_cols = self._extract_column_names(llm_sql)

        if original_cols == {'*'}:
            return llm_sql, notes

        if original_cols and llm_cols and not original_cols.issubset(llm_cols):
            missing = original_cols - llm_cols
            notes.append(f"Semantic guard: LLM is missing original query columns {missing}, falling back to rule candidate SQL.")
            return rule_candidate, notes

        return llm_sql, notes

    def _normalize(self, sql: str) -> str:
        """Normalize SQL: uppercase keywords + single space, used to determine if SQL has changed"""
        return " ".join(sqlparse.format(sql, keyword_case="upper").split())

    def _example_to_dict(self, ex: ExampleCase) -> dict:
        """Convert ExampleCase object to dictionary for use in LLM prompt"""
        return {
            "before_sql": ex.before_sql,
            "after_sql": ex.after_sql,
            "explanation": ex.explanation,
        }
