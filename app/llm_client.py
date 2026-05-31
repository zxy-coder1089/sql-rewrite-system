from __future__ import annotations
from typing import List, Dict, Any, Optional
import json
import re
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:7b-sql"

SYSTEM_PROMPT = '''You are an SQL query optimization expert. Task: rewrite and optimize the original SQL based on reference examples while maintaining semantic equivalence.

Allowed operations (based only on reference examples):
- Eliminate function wrapping: DATE(col)=val → col>=val AND col<val+1d (leverage column index acceleration)
- Eliminate function wrapping: LEFT(col,n)=val → col LIKE 'val%'
- Eliminate type casting: CAST(col AS VARCHAR)=val → col=val::int
- Simplify arithmetic: col+const>val → col>val-const
- Eliminate nested functions: UPPER(TRIM(col))=val → col=val (val converted to lowercase/trim whitespace)

Hard constraints:
1. The output column semantics must remain consistent; do not add/remove/extend columns.
2. Do not modify high-risk scenarios such as DISTINCT, GROUP BY, LEFT JOIN, LIMIT, HAVING.
3. Output must be JSON in the following format:
{"rewritten_sql": "...", "notes": ["..."], "risk_flags": ["..."]}
4. Do not output markdown code blocks.
5. If the original SQL is already optimal, or you cannot confirm the correctness of the rewrite, directly return the rule candidate SQL.
'''

def build_prompt(original_sql: str, candidate_sql: str, examples: List[Dict[str, str]], iterative_round: int) -> str:
    """Build the Ollama LLM SQL rewrite prompt

    Includes system constraints, original SQL, rule candidate SQL, and reference examples,
    requiring the LLM to return a conservative and verifiable JSON rewrite result.
    """
    example_text = []
    for idx, ex in enumerate(examples, start=1):
        example_text.append(
            f"Example {idx}\n"
            f"Before: {ex['before_sql']}\n"
            f"After: {ex['after_sql']}\n"
            f"Explanation: {ex['explanation']}"
        )

    return f'''{SYSTEM_PROMPT}

This is rewrite round {iterative_round}.
Based on the reference examples, perform an equivalent rewrite of the function calls in the original SQL.

Original SQL:
{original_sql}

Rule candidate SQL:
{candidate_sql}

Reference examples:
{chr(10).join(example_text)}

Strictly follow the optimization patterns in the reference examples and apply the same rewrites to the original SQL.
If no matching pattern is found in the reference examples, directly return the rule candidate SQL.
'''

class OllamaClient:
    """Ollama LLM client: calls local LLM for SQL rewriting

    Requests Ollama via the POST /api/generate endpoint,
    uses format=json to ensure structured JSON output,
    sets temperature=0 for deterministic output
    """
    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL, timeout: int = 60) -> None:
        """Initialize the LLM client

        Args:
            model: Ollama model name
            url: Ollama API endpoint
            timeout: Request timeout in seconds
        """
        self.model = model
        self.url = url
        self.timeout = timeout

    def rewrite_sql(self, original_sql: str, candidate_sql: str, examples: List[Dict[str, str]], iterative_round: int = 1) -> Optional[Dict[str, Any]]:
        """Request LLM to rewrite the SQL

        Args:
            original_sql: The original SQL
            candidate_sql: The rule candidate SQL
            examples: List of reference examples
            iterative_round: Current iteration round
        Returns:
            {"rewritten_sql": "...", "notes": [...], "risk_flags": [...]}
            or None (request failed or parse error)
        """
        prompt = build_prompt(original_sql, candidate_sql, examples, iterative_round)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0}
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "").strip()
            if not raw:
                return None
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                raw = match.group(0)
            parsed = json.loads(raw)
            if "rewritten_sql" not in parsed:
                return None
            parsed.setdefault("notes", [])
            parsed.setdefault("risk_flags", [])
            return parsed
        except Exception:
            return None
