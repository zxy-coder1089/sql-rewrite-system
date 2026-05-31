from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from app.models import RewriteRequest, RewriteResponse
from app.rewrite_engine import SQLRewriteEngine
from app.semantic_validator import SemanticValidator
from app.db_pg import init_benchmark_db, get_conn

app = FastAPI(title="SQL Rewrite System", version="1.2.0")
validator = SemanticValidator()

@app.on_event("startup")
def on_startup():
    """Initialize PostgreSQL database on startup (create tables and insert 1x data if empty)"""
    init_benchmark_db()

@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def home():
    """Return the SQL Rewrite System web UI (inline HTML/CSS/JS)"""
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>SQL Rewrite System</title>
      <style>
        :root {
          --bg: #f5f7fb;
          --card: #ffffff;
          --line: #e5e7eb;
          --text: #111827;
          --muted: #6b7280;
          --primary: #2563eb;
          --primary-dark: #1d4ed8;
          --good: #15803d;
          --good-bg: #dcfce7;
          --bad: #b91c1c;
          --bad-bg: #fee2e2;
          --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
        }

        * { box-sizing: border-box; }

        body {
          margin: 0;
          font-family: Arial, sans-serif;
          background: linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
          color: var(--text);
        }

        .page {
          max-width: 1180px;
          margin: 0 auto;
          padding: 32px 20px 48px;
        }

        .hero {
          background: var(--card);
          border: 1px solid var(--line);
          border-radius: 20px;
          padding: 28px;
          box-shadow: var(--shadow);
          margin-bottom: 24px;
        }

        .hero h1 {
          margin: 0 0 10px;
          font-size: 38px;
          line-height: 1.2;
        }

        .hero p {
          margin: 0;
          color: var(--muted);
          font-size: 16px;
          line-height: 1.7;
        }

        .hero a {
          color: var(--primary);
          text-decoration: none;
          font-weight: 600;
        }

        .layout {
          display: grid;
          grid-template-columns: 420px 1fr;
          gap: 24px;
          align-items: start;
        }

        .panel {
          background: var(--card);
          border: 1px solid var(--line);
          border-radius: 20px;
          box-shadow: var(--shadow);
        }

        .panel-header {
          padding: 20px 22px 12px;
          border-bottom: 1px solid #f1f5f9;
        }

        .panel-header h2 {
          margin: 0;
          font-size: 20px;
        }

        .panel-header p {
          margin: 8px 0 0;
          color: var(--muted);
          font-size: 14px;
        }

        .panel-body {
          padding: 20px 22px 22px;
        }

        label {
          display: block;
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 8px;
        }

        textarea, select, input[type="number"] {
          width: 100%;
          border: 1px solid #d1d5db;
          border-radius: 12px;
          padding: 12px 14px;
          font-size: 14px;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
          background: #fff;
        }

        textarea {
          min-height: 180px;
          resize: vertical;
          line-height: 1.6;
          font-family: Consolas, "Courier New", monospace;
        }

        textarea:focus, select:focus, input[type="number"]:focus {
          border-color: var(--primary);
          box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
        }

        .row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 14px;
          margin-top: 14px;
        }

        .check {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-top: 16px;
          font-weight: 500;
          color: var(--text);
        }

        .check input {
          width: 16px;
          height: 16px;
        }

        .actions {
          display: flex;
          gap: 12px;
          margin-top: 18px;
        }

        button {
          border: none;
          border-radius: 12px;
          padding: 12px 18px;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          transition: transform 0.15s ease, opacity 0.15s ease, background 0.2s ease;
        }

        button:hover {
          transform: translateY(-1px);
        }

        .btn-primary {
          background: var(--primary);
          color: #fff;
          flex: 1;
        }

        .btn-primary:hover {
          background: var(--primary-dark);
        }

        .btn-secondary {
          background: #eef2ff;
          color: #3730a3;
        }

        .example-list {
          margin-top: 18px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .example-item {
          border: 1px solid #dbeafe;
          background: #f8fbff;
          border-radius: 12px;
          padding: 10px 12px;
          font-size: 13px;
          cursor: pointer;
          color: #1e3a8a;
        }

        .example-item:hover {
          background: #eff6ff;
        }

        .results {
          display: grid;
          gap: 18px;
        }

        .section {
          border: 1px solid var(--line);
          border-radius: 18px;
          background: #fff;
          box-shadow: var(--shadow);
          overflow: hidden;
        }

        .section h3 {
          margin: 0;
          padding: 16px 18px;
          border-bottom: 1px solid #f3f4f6;
          font-size: 18px;
        }

        .section-body {
          padding: 16px 18px 18px;
        }

        .sql-box, .json-box {
          background: #0f172a;
          color: #e5eefc;
          padding: 14px 16px;
          border-radius: 14px;
          overflow-x: auto;
          white-space: pre-wrap;
          word-break: break-word;
          line-height: 1.6;
          font-family: Consolas, "Courier New", monospace;
          font-size: 13px;
        }

        .step-card, .example-card, .metric-card {
          border: 1px solid #e5e7eb;
          border-radius: 14px;
          padding: 14px;
          background: #fafafa;
          margin-bottom: 12px;
        }

        .step-card:last-child, .example-card:last-child {
          margin-bottom: 0;
        }

        .step-title, .example-title {
          font-weight: 700;
          margin-bottom: 10px;
        }

        .muted {
          color: var(--muted);
          font-size: 13px;
        }

        .tag {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 5px 10px;
          font-size: 12px;
          font-weight: 700;
        }

        .tag.good {
          color: var(--good);
          background: var(--good-bg);
        }

        .tag.bad {
          color: var(--bad);
          background: var(--bad-bg);
        }

        .metrics {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
        }

        .metric-card strong {
          display: block;
          font-size: 22px;
          margin-top: 6px;
        }

        .empty {
          color: var(--muted);
          text-align: center;
          padding: 32px 16px;
        }

        .loading {
          color: var(--primary);
          font-weight: 700;
        }

        @media (max-width: 980px) {
          .layout {
            grid-template-columns: 1fr;
          }

          .metrics, .row {
            grid-template-columns: 1fr;
          }

          .hero h1 {
            font-size: 30px;
          }
        }
      </style>
    </head>
    <body>
      <div class="page">
        <div class="hero">
          <h1>SQL Rewrite System</h1>
          <p>
             Rule-guided and case-enhanced SQL rewrite optimization with semantic consistency validation.
            <a href="/docs" target="_blank">Open Swagger API Docs</a>
          </p>
        </div>

        <div class="layout">
          <div class="panel">
            <div class="panel-header">
              <h2>Input &amp; Parameters</h2>
              <p>Enter SQL statement, select model, and execute rewrite optimization.</p>
            </div>
            <div class="panel-body">
              <label for="sql">Input SQL</label>
              <textarea id="sql">SELECT *
FROM orders
WHERE customer_id IN (
    SELECT id
    FROM customers
    WHERE region = 'East'
);</textarea>

              <div style="margin-top:14px;">
                <label for="model_name">Model Name</label>
                <select id="model_name">
                  <option value="qwen2.5-coder:7b" selected>qwen2.5-coder:7b</option>
                  <option value="qwen2.5-coder:7b-sql">qwen2.5-coder:7b-sql</option>
                </select>
              </div>

              <label class="check">
                <input type="checkbox" id="use_llm" checked />
                Enable LLM hybrid rewrite
              </label>

              <div class="actions">
                <button class="btn-primary" onclick="rewriteSQL()">Execute Rewrite</button>
                <button class="btn-secondary" onclick="fillExample()">Load Example</button>
              </div>

              <div class="example-list">
                <div class="example-item" onclick="setExample(`SELECT * FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2024`)">Example 1: Eliminate YEAR function</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM products WHERE price * 0.85 > 500`)">Example 2: Eliminate arithmetic</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM customers WHERE SUBSTRING(phone, 1, 3) = '138'`)">Example 3: SUBSTRING to LIKE</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM orders WHERE CAST(id AS CHAR) = '12345'`)">Example 4: Eliminate CAST</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM orders WHERE COALESCE(status, 'pending') = 'paid'`)">Example 5: Simplify COALESCE</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM products WHERE id NOT IN (SELECT product_id FROM order_items WHERE quantity > 10)`)">Example 6: Optimize NOT IN</div>
                <div class="example-item" onclick="setExample(`SELECT o.id, o.customer_id, (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.id) AS item_count FROM orders o`)">Example 7: Optimize scalar subquery</div>
                <div class="example-item" onclick="setExample(`SELECT dept_id, COUNT(*) AS cnt FROM employees GROUP BY dept_id HAVING COUNT(*) > 5`)">Example 8: HAVING pushdown</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM orders ORDER BY id LIMIT 10 OFFSET 50000`)">Example 9: Deferred join pagination</div>
                <div class="example-item" onclick="setExample(`SELECT * FROM orders WHERE status IN ('completed', 'pending') UNION SELECT * FROM orders WHERE status = 'shipped'`)">Example 10: Optimize UNION</div>
              </div>
            </div>
          </div>

          <div class="results">
            <div class="section">
              <h3>Original SQL</h3>
              <div class="section-body">
                <div id="original_sql" class="sql-box empty">Awaiting execution...</div>
              </div>
            </div>

            <div class="section">
              <h3>Final Rewritten SQL</h3>
              <div class="section-body">
                <div id="final_sql" class="sql-box empty">Awaiting execution...</div>
              </div>
            </div>

            <div class="section">
              <h3>Rewrite Steps</h3>
              <div class="section-body" id="steps">
                <div class="empty">After execution, each round's rewrite strategy, output SQL, and notes will be shown here.</div>
              </div>
            </div>

            <div class="section">
              <h3>Semantic Validation</h3>
              <div class="section-body" id="validation">
                <div class="empty">After execution, semantic consistency, row count, and execution time comparison will be shown here.</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <script>
        function setExample(text) {
          document.getElementById("sql").value = text;
        }

        function fillExample() {
          setExample(`SELECT *
FROM orders
WHERE customer_id IN (
    SELECT id
    FROM customers
    WHERE region = 'East'
);`);
        }

        function escapeHtml(str) {
          return String(str)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
        }

        function renderSQL(id, sql) {
          const el = document.getElementById(id);
          el.classList.remove("empty");
          el.innerHTML = escapeHtml(sql || "");
        }

        function renderSteps(steps) {
          const container = document.getElementById("steps");
          const strategyMap = {
            "rule_guided_rewrite": "Rule-guided rewrite",
            "evidence_guided_refinement": "Case-enhanced refinement",
            "hybrid_rule_evidence_llm_rewrite": "Hybrid rewrite (rule + case + LLM)",
            "hybrid_evidence_llm_refinement": "Hybrid refinement (case + LLM)",
            "hybrid_rule_fallback": "Hybrid fallback (rule candidate)",
            "ollama_llm_rewrite": "LLM rewrite"
          };

          if (!steps || !steps.length) {
            container.innerHTML = '<div class="empty">No steps to display.</div>';
            return;
          }

          container.innerHTML = steps.map(step => `
            <div class="step-card">
              <div class="step-title">Round ${step.round_id}: ${strategyMap[step.strategy] || step.strategy}</div>
              <div class="muted">Input SQL</div>
              <div class="sql-box" style="margin:8px 0 12px;">${escapeHtml(step.input_sql || "")}</div>
              <div class="muted">Output SQL</div>
              <div class="sql-box" style="margin:8px 0 12px;">${escapeHtml(step.output_sql || "")}</div>
              <div class="muted">Notes</div>
              <div style="margin-top:8px; line-height:1.8;">${(step.notes || []).map(n => `• ${escapeHtml(n)}`).join("<br>") || "None"}</div>
            </div>
          `).join("");
        }

        function renderValidation(v) {
          const container = document.getElementById("validation");
          if (!v) {
            container.innerHTML = '<div class="empty">Semantic validation was not performed this time.</div>';
            return;
          }

          container.innerHTML = `
            <div style="margin-bottom:14px;">
              <span class="tag ${v.is_equivalent ? "good" : "bad"}">
                ${v.is_equivalent ? "Semantically equivalent" : "Not semantically equivalent"}
              </span>
            </div>
            <div class="metrics">
              <div class="metric-card">
                <div class="muted">Original row count</div>
                <strong>${v.original_row_count}</strong>
              </div>
              <div class="metric-card">
                <div class="muted">Rewritten row count</div>
                <strong>${v.rewritten_row_count}</strong>
              </div>
              <div class="metric-card">
                <div class="muted">Schema match</div>
                <strong>${v.schema_match ? "Yes" : "No"}</strong>
              </div>
            </div>
            <div class="metrics" style="margin-top:12px;">
              <div class="metric-card">
                <div class="muted">Result content match</div>
                <strong>${v.normalized_match ? "Yes" : "No"}</strong>
              </div>
              <div class="metric-card">
                <div class="muted">Original exec time</div>
                <strong>${v.original_exec_ms} ms</strong>
              </div>
              <div class="metric-card">
                <div class="muted">Rewritten exec time</div>
                <strong>${v.rewritten_exec_ms} ms</strong>
              </div>
            </div>
          `;
        }

        async function rewriteSQL() {
          const sql = document.getElementById("sql").value;
          const useLLM = document.getElementById("use_llm").checked;
          const modelName = document.getElementById("model_name").value;

          document.getElementById("original_sql").innerHTML = '<span class="loading">Executing rewrite, please wait...</span>';
          document.getElementById("final_sql").innerHTML = '<span class="loading">Generating final SQL...</span>';
          document.getElementById("steps").innerHTML = '<div class="loading">Organizing rewrite steps...</div>';
          document.getElementById("validation").innerHTML = '<div class="loading">Running semantic validation...</div>';

          try {
            const res = await fetch("/rewrite", {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({
                sql: sql,
                use_llm: useLLM,
                model_name: modelName
              })
            });

            const data = await res.json();

            if (!res.ok) {
              throw new Error(data.detail || "Request failed");
            }

            renderSQL("original_sql", data.original_sql || "");
            renderSQL("final_sql", data.final_sql || "");
            renderSteps(data.steps || []);
            renderValidation(data.validation || null);
          } catch (err) {
            const message = err && err.message ? err.message : "Unknown error";
            document.getElementById("original_sql").innerHTML = '<span class="tag bad">Execution failed</span>';
            document.getElementById("final_sql").innerHTML = `<div class="sql-box">${escapeHtml(message)}</div>`;
            document.getElementById("steps").innerHTML = '<div class="empty">Failed to generate step information.</div>';
            document.getElementById("validation").innerHTML = '<div class="empty">Failed to complete semantic validation.</div>';
          }
        }
      </script>
    </body>
    </html>
    '''

@app.post("/rewrite", response_model=RewriteResponse)
def rewrite_sql(request: RewriteRequest):
    """Execute SQL rewrite and return results

    Call rewrite_engine for rule+LLM (optional) rewrite,
    then validate semantic consistency via semantic_validator
    """
    try:
        engine = SQLRewriteEngine(use_llm=request.use_llm, use_rules=request.use_rules, use_cases=request.use_cases, model_name=request.model_name)
        final_sql, examples, steps = engine.rewrite(request.sql)
        validation = validator.validate(request.sql, final_sql)

        return RewriteResponse(
            original_sql=request.sql,
            final_sql=final_sql,
            retrieved_examples=examples,
            steps=steps,
            validation=validation,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
