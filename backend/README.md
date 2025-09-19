# Minimal 3‑Tool Architecture — AI Decision Partner (MCP)

> **Design goal:** Replace many agents with **three generic tools** that can express any workflow via code‑first, notebook‑style steps.

## The Three Tools

1. **Code Sandbox**
   A persistent, notebook‑like execution environment. Runs small, incremental code cells (Python by default) with access to a working directory. Maintains kernel/session state across steps.
   **Why:** Every “agent” (research, KPI calc, forecasting, strategy, exporter) becomes a **recipe of cells**.

2. **Access Browser (Tavily)**
   A single web research/search capability that returns structured results (URL, title, snippet, published\_at) and optional page text for citation.
   **Why:** External evidence gathering, competitor snapshots, market scans.

3. **Tmp Files**
   Ephemeral file API (read/write/list/delete) scoped to the run/session.
   **Why:** Share artifacts between Code Sandbox cells and the outside world (CSV/Parquet, PNGs, PPTX/PDF, MD).

---

## MCP Tool Contracts (High‑Level)

### 1) `sandbox.exec`

* **Input:** `{ code: string, language?: "python", files_in?: [{name, path}], timeout_s?: number }`
* **Behavior:** Executes in a persistent session (per run\_id). Captures stdout/stderr/returned value; may write to working dir.
* **Output:** `{ ok: boolean, stdout: string, stderr: string, display?: any, files_out?: [{path, size, sha256}] }`

### 2) `browser.search`

* **Input:** `{ query: string, top_k?: number, include_page?: boolean, allow_domains?: string[], date_range?: string }`
* **Output:** `{ results: [{url, title, snippet, published_at?, content?}], citations_id: string }`

### 3) `tmp.{write,read,list,delete}`

* `tmp.write` **Input:** `{ path: string, bytes_b64?: string, text?: string }` → **Output:** `{ path, size, sha256 }`
* `tmp.read` **Input:** `{ path: string }` → **Output:** `{ bytes_b64 | text, size, sha256 }`
* `tmp.list` **Input:** `{ prefix?: string }` → **Output:** `{ files: [{path, size, sha256, modified_at}] }`
* `tmp.delete` **Input:** `{ path: string }` → **Output:** `{ ok: boolean }`

**Sessioning & Isolation:** All tools accept an implicit `run_id`/`session_id` header so the sandbox state and tmp dir are isolated per run.

---

## How the “Sub‑Agents” Collapse Into 3 Tools

* **Market Research & Competitor Analysis**

  1. `browser.search` to fetch sources → save to `tmp.write` as `evidence.json`.
  2. `sandbox.exec` to consolidate, dedupe, and score confidence; emit `facts.md` and `citations.json`.

* **Company Data (Ingest + KPI calc)**

  1. `tmp.write` to upload CSV/Parquet.
  2. `sandbox.exec` to load (pandas/polars), profile, compute KPIs; emit `kpis.parquet`, `profile.md`.

* **Forecasting**

  1. `sandbox.exec` to fit ARIMA/ETS, compute MAPE, produce CI; write `forecast.parquet`, `charts/*.png`.

* **Implementation Scenarios & Strategy**

  1. `sandbox.exec` to run a simple CBA and sensitivity; emit `options.json`, `cba.md`.

* **Deliverables (Brief/Deck/Dossier)**

  1. `sandbox.exec` to render Jinja2 → HTML → PDF; python‑pptx for PPTX; write to `artifacts/` in tmp.
  2. Client downloads via `tmp.read`.

**Everything above is just ordered calls to** `browser.search` + `sandbox.exec` + `tmp.*`.

---

## Orchestration Pattern (Pseudo)

```
START(run_id)
→ browser.search(q) → tmp.write(evidence.json)
→ sandbox.exec(load_evidence + dedupe + score)
→ tmp.write(company.csv)  # user upload
→ sandbox.exec(profile + kpis)
→ sandbox.exec(forecast + charts)
→ sandbox.exec(scenarios + cba)
→ sandbox.exec(render_brief + deck)
→ tmp.list(prefix="artifacts/") → RETURN links
```

**Retry/Idempotency:** The planner replays from the last successful artifact in `tmp/` (content‑addressed by sha256). Cells are small and composable.

---

## Example Notebook (Cell Recipes)

**Cell 1 — Load evidence & consolidate**

```python
import json, hashlib, datetime as dt
from collections import defaultdict
E = json.load(open("evidence.json"))
# Deduplicate by URL/title
seen, facts = set(), []
for r in E["results"]:
    k = (r["url"], r.get("title"))
    if k in seen:
        continue
    seen.add(k)
    facts.append({"fact": r["snippet"], "url": r["url"], "date": r.get("published_at")})
json.dump({"facts": facts}, open("facts.json","w"))
print(f"facts={len(facts)} saved")
```

**Cell 2 — KPIs**

```python
import pandas as pd
leads = pd.read_csv("leads.csv")
spend = pd.read_csv("spend.csv")
df = spend.merge(leads.groupby("source").size().rename("leads"), left_on="source", right_index=True, how="left").fillna(0)
df["cac"] = df["spend"]/df["leads"].replace(0, pd.NA)
df.to_parquet("kpis.parquet")
```

**Cell 3 — Forecast**

```python
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
s = pd.read_parquet("kpis.parquet")["leads"].asfreq("MS").fillna(0)
model = SARIMAX(s, order=(1,1,1), seasonal_order=(1,1,1,12)).fit(disp=False)
fc = model.get_forecast(12)
fc.summary_frame().to_csv("forecast.csv")
```

**Cell 4 — Brief rendering**

```python
from jinja2 import Template
brief = Template(open("brief.html.j2").read()).render(
    objective="Improve lead quality via spend reallocation",
    key_insights=open("facts.json").read(),
)
open("artifacts/decision_brief.html","w").write(brief)
```

---

## Error & Safety Model

* **Sandbox guardrails:** resource limits (CPU/RAM/time), no outbound network, whitelisted libs; filesystem jailed to `tmp/`.
* **Browser trust:** keep raw results; record timestamps; show top domains; always store citations.
* **Determinism:** small cells; content hashes; re‑runnable from `tmp/` products.

---

## Minimal Backend Endpoints

* `POST /run` — accepts objective + params; executes a predefined recipe of tool calls.
* `POST /sandbox/exec` — dev endpoint for manual cells (optional in prod).
* `GET  /tmp/list | /tmp/read` — fetch artifacts under `artifacts/`.

---

## Why This Works

* **General‑purpose:** Any “agent” = (search) → (compute) → (write files) loop.
* **Transparent:** Code cells are auditable and editable; easy to debug.
* **Composable:** New verticals = new recipes, not new agents.
* **Lean:** Only 3 tools to secure, test, and maintain.

---

## Next Steps

* Define the handful of **standard recipes** (Market Scan, Competitor Alert, Sales Reallocation, Forecast Pack, Implementation Brief).
* Ship a default **starter notebook** per recipe with \~5–8 cells each.
* Add a simple **artifact index** (JSON) so the UI can show links without a DB.

---

## Context Engineering Log (CEL.md)

**Goal:** Maintain a single, human‑readable markdown file that evolves after **every tool call**, capturing progress, artifacts, next steps, and a lightweight evaluation. This doubles as:

* a live operations journal,
* a scratchpad for planning,
* a reproducible trace for audits,
* and context for subsequent tool calls.

### File

* **Path:** `tmp/CEL.md` (scoped per `run_id`/session)
* **Lifecycle:** created at `START(run_id)`; appended after each step; finalized at `END` with a summary.

### Required Sections per Step

Each tool invocation must append a **Step Block**:

```markdown
## Step {n}: <tool_name>
**When:** <ISO8601>
**Inputs:** <salient params only>
**What I did:** <1–3 bullets>
**Artifacts:**
- <name>: `tmp/<rel_path>` (size=<bytes>, sha256=<hash>)
**Next steps:** <bulleted checklist>
**Evaluation (by Evaluator):** <pass/fail + 1–2 line critique>
```

### Evaluator

* A second pass executed via the **Code Sandbox** (small Python cell) acts as the “Evaluator.”
* The Evaluator reads the last Step Block and writes the **Evaluation** line with a simple rubric (Completeness, Correctness, Citation coverage, Runtime warnings).

**Evaluator rubric (0–1 per dimension, aggregate shown):**

* Completeness: all required artifacts produced?
* Correctness: basic sanity checks (row counts, schema, non‑empty outputs)?
* Evidence: claims have sources or internal dataset refs?
* Hygiene: no errors/warnings in stderr; runtime within budget?

### Orchestration Contract Update

After **every** call to `browser.search`, `sandbox.exec`, or `tmp.*`, the orchestrator MUST:

1. Compute artifact metadata (path, size, sha256) for any new/updated files under `tmp/`.
2. Append a Step Block to `tmp/CEL.md`.
3. Invoke a short **Evaluator cell** (Code Sandbox) to write the Evaluation line for that Step.

### Minimal APIs (additions)

* `GET /cel` → returns the current `tmp/CEL.md` as text for the active `run_id`.
* `POST /cel/note` → append an operator/manual note (for human‑in‑the‑loop).

### Example: Appending from Sandbox

**Cell (Python) to append a Step Block:**

```python
from pathlib import Path
import json, hashlib, time
run_dir = Path("tmp")
cel = run_dir/"CEL.md"
cel.parent.mkdir(parents=True, exist_ok=True)
artifacts = [
    {"name": "facts.json", "path": "tmp/facts.json"},
    {"name": "kpis.parquet", "path": "tmp/kpis.parquet"},
]
for a in artifacts:
    p = Path(a["path"]).resolve()
    if p.exists():
        a["size"] = p.stat().st_size
        a["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]

block = f"""
## Step 3: sandbox.exec
**When:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
**Inputs:** computed KPIs for spend × leads
**What I did:**
- Merged spend with lead counts per source
- Calculated CAC and saved KPIs table
**Artifacts:**
""" + "
".join([f"- {a['name']}: `"+a['path']+f"` (size={a.get('size',0)}, sha256={a.get('sha256','-')})" for a in artifacts]) + "
" + """
**Next steps:**
- Forecast 12m horizon with SARIMA
**Evaluation (by Evaluator):** PENDING
"""

cel.write_text((cel.read_text() if cel.exists() else "# Context Engineering Log (CEL)

") + block)
print("CEL updated.")
```

**Evaluator Cell (Python):**

```python
from pathlib import Path
cel = Path("tmp/CEL.md")
text = cel.read_text()
# naive example: mark last Evaluation line as PASS if artifacts exist
if "facts.json" in text and "kpis.parquet" in text:
    text = text.rsplit("**Evaluation (by Evaluator):** PENDING", 1)[0] + "**Evaluation (by Evaluator):** PASS — completeness=1.0, correctness=0.8, evidence=0.7, hygiene=1.0
"
cel.write_text(text)
print("Evaluation written.")
```

### Consumption in Later Steps

* The orchestrator/sandbox can parse `CEL.md` to **recover context** (e.g., where `kpis.parquet` lives), choose **next steps**, or fail fast if a previous step is incomplete.
* The **Brief/Deck renderers** can embed a “Method & Evidence” appendix sourced from `CEL.md`.

### Concurrency & Versioning

* Single writer policy per `run_id`; if parallel tools are used, buffer Step Blocks and append in order `Step n`.
* Optionally checkpoint: `tmp/CEL.step_{n}.md` before each append for rollback.

### Definition of Done (CEL)

* `tmp/CEL.md` exists with ≥1 Step Block per tool call, each with artifacts listed and an Evaluation line not left as PENDING.
