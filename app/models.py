from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class RewriteRequest(BaseModel):
    """Rewrite request parameters"""
    sql: str = Field(..., description="Original SQL")
    use_llm: bool = False
    use_rules: bool = True
    use_cases: bool = True
    model_name: str = "qwen2.5-coder:7b"

class RewriteStep(BaseModel):
    """Single round rewrite step record"""
    round_id: int
    strategy: str
    input_sql: str
    output_sql: str
    notes: List[str] = []

class ValidationResult(BaseModel):
    """Semantic validation result"""
    is_equivalent: bool
    original_row_count: int
    rewritten_row_count: int
    normalized_match: bool
    schema_match: bool
    original_exec_ms: float
    rewritten_exec_ms: float
    details: Dict[str, Any] = {}

class RewriteResponse(BaseModel):
    """Rewrite response result"""
    original_sql: str
    final_sql: str
    retrieved_examples: List[Dict[str, str]]
    steps: List[RewriteStep]
    validation: Optional[ValidationResult] = None
