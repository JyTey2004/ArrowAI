# ArrowAI
Functional Specification — AI Consultant (High‑Level)

## 1) Vision & Outcome

Provide a productized AI “decision partner” that converts business questions into **cited, decision‑ready outputs** (briefs, decks, datasets) across Strategy, Sales, Market Research, Forecasting, and Implementation planning.

**North Star:** “Ask. Evidence. Options. Decision.” — delivered fast, repeatably, and safely.

---

## 2) Scope (What the product does)

* **Aggregates evidence** from the public web and client systems.
* **Analyzes & forecasts** key KPIs with transparent assumptions.
* **Generates options & scenarios** with cost/benefit and risks.
* **Produces deliverables** (briefs, decks, datasets, charts) with citations.
* **Tracks decisions & outcomes** to learn and improve over time.

Out of scope (v1): autonomous execution in production systems; PIIs without masking; custom ML training.

---

## 3) Primary Personas

* **Executive Sponsor (CEO/CRO/CPO):** consumes briefs/decks; approves actions.
* **Strategy/Ops Manager:** runs decision packs; iterates scenarios; exports deliverables.
* **Analyst:** curates data connections; validates sources; tunes prompts.
* **Viewer/Stakeholder:** reads outputs; adds comments.

---

## 4) Core Use Cases

1. **Market Scan:** “What’s the size/growth and who’s winning?” → snapshot + sources.
2. **Competitor Watch:** “A competitor changed pricing—impact?” → alert + action brief.
3. **Sales Optimization:** “Reallocate media/territory to hit target?” → scenarios + CBA.
4. **Forecasting:** “Expected demand next 6–12 months?” → baseline + CI + sensitivity.
5. **Implementation Plan:** “How to roll out a pilot?” → roadmap, RACI, risks.

---

## 5) System Capabilities (functional)

* **Research & Evidence:** multi‑source search/ingest; dedupe; citation registry with timestamps and confidence flags.
* **Company Data Integration:** ingest CSV/Parquet/API; KPI dictionary; data quality report.
* **Forecasting:** time‑series forecast with error metrics; scenario switches.
* **Strategy & Scenario Engine:** option generation; CBA; sensitivity analysis; risk register.
* **Narrative & Visualization:** figures (line/bar/stacked) → human‑readable explanations.
* **Deliverable Generation:** decision brief (PDF), board deck (PPTX), research dossier (MD/HTML), forecast pack (CSV/Parquet).
* **Auditability:** artifact IDs, source links, hash of outputs, decision log.

---

## 6) Product Modules

* **Research Module:** web scan → consolidated facts + sources.
* **Data Module:** connectors, profiling, KPI computation, dataset pointers.
* **Forecast Module:** baseline/seasonality, backtests, CI bands.
* **Strategy Module:** options, CBA, risks, recommendation.
* **Explainer Module:** chart summaries into prose sections.
* **Exporter Module:** PPTX/PDF/CSV/MD builders using templates.
* **Governance Module:** RBAC, masking, domain allowlist, guardrails.
* **Observability Module:** runs, artifacts, metrics, alerts.

---

## 7) Inputs & Outputs

**Inputs**

* Business objective/question (natural language).
* Parameters: geography, time window, budget, KPIs, options.
* Data pointers: company datasets, external sources.

**Outputs**

* **Decision Brief** (2 pages): Objective, Insights, Options, Financials, Risks, Rec.
* **Board Deck** (10–15 slides): snapshot → scenarios → plan → ask.
* **Research Dossier:** annotated sources with confidence and dates.
* **Forecast Pack:** CSV/Parquet + charts.
* **Audit Log:** run metadata, citations, hashes.

---

## 8) High‑Level Workflow

1. **Intake:** user states objective → system resolves prior context & templates.
2. **Research:** gather & consolidate external evidence with citations/confidence.
3. **Company Data:** fetch/aggregate KPIs, compute derived metrics.
4. **Forecast:** build baseline + scenarios; compute error metrics.
5. **Strategy:** enumerate options; run CBA & sensitivity; create risk register.
6. **Explain & Visualize:** generate figures + narrative sections.
7. **Assemble Deliverables:** brief + deck + dossier + data pack.
8. **Guardrail Check:** evidence present, PII masked, policy gates pass.
9. **Publish:** artifacts stored; links shared; decision recorded.

---

## 9) Data & Integrations (conceptual)

* **Connectors:** file upload (CSV/Parquet), SQL/BI API (future), CRM/Ads (future).
* **Evidence Store:** URL, title, date, snippet, quote hash, domain, access date.
* **Artifact Store:** S3‑style objects; registry index with IDs & hashes.
* **Identity & Roles:** JWT/OIDC; roles ADMIN/USER/VIEWER; tenant isolation.

---

## 10) Guardrails & Compliance (functional)

* **Source‑required outputs:** any claim in briefs/decks must link to ≥1 source (or be marked internal with dataset ref).
* **PII policy:** masking by default on ingest; column‑level controls.
* **Domain allowlist/denylist:** for external web research.
* **Approval gates:** human‑in‑the‑loop before sharing external deliverables.

---

## 11) Non‑Functional Requirements (v1 targets)

* **Speed:** typical decision run completes within minutes on mock data; queued jobs allowed.
* **Reliability:** artifacts are content‑addressable (hash); reproducible from logged inputs.
* **Security:** tenant isolation; least‑privilege keys; signed download links.
* **Usability:** single “Run decision pack” entrypoint; clear status; downloadable artifacts.

---

## 12) KPIs & Success Metrics

* **Decision velocity:** time from question → deliverable.
* **Evidence coverage:** % of key statements with ≥1 citation.
* **Forecast quality:** MAPE/backtest metrics per KPI.
* **Adoption:** monthly active decision runs; stakeholder views/downloads.
* **Impact proxy (demo):** scenario uplifts in CAC/velocity (on sample data).

---

## 13) Packaging & Deliverables (product SKUs)

* **Discovery Sprint:** data map, KPI baseline, opportunity tree.
* **Pilot Pack:** N market scans + decision briefs + 1 board deck.
* **Subscription:** platform access + monthly decision packs + competitor watch.
* **Enterprise Add‑ons:** private deployment, custom templates, SLAs.

---

## 14) Risks & Mitigations (product level)

* **Hallucination:** enforce citation gates; confidence flags; block uncited claims.
* **Data quality:** ingest profiling; KPI dictionary; unit tests on transforms.
* **Change mgmt:** templates + playbooks; viewer/share links; audit trail.
* **Scope creep:** module boundaries; SKU‑based packaging; clear DoD for outputs.

---

## 15) Release Framing (v0 → v1)

* **v0 (Demo):** scripted flow on mock data; cited brief + deck; evidence list.
* **v1 (Pilot‑ready):** connectorized ingest; scenario toggles; audit log; role‑based access; templated exports.

---

### Glossary

* **Decision Pack:** End‑to‑end run that yields a brief, deck, dossier, forecast pack.
* **Evidence:** A deduped, timestamped citation object used to support claims.
* **Scenario:** A set of lever values producing forecast deltas and CBA results.
