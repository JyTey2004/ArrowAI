# Natural-Language Consultant Prompts for `pharma_data.csv` + `pharma_targets`
> Each prompt now includes **Expected outcome** (what the agent should deliver) and **Rationale** (why it matters).

---

1) **Re-profile the dataset end-to-end.**  
Confirm 2,106 rows, `datum` span 2014-01-02 → 2019-10-08, continuous Year/Month 2014-01 → 2019-10, true 0% missingness across listed columns, and surface hidden issues (duplicates, impossible values, dtype mismatches). Summarize the top 10 findings in plain English.  
**Expected outcome:** A refreshed profiling report with verified counts/ranges, a concise “Top 10” insight list, and a short anomalies table (dupes, type fixes, odd values).  
**Rationale:** Establishes a trusted baseline and prevents downstream error propagation from unnoticed data quality issues.

2) **Validate join keys with `pharma_targets`.**  
Evaluate `Year` + ATC columns (`M01AB`, `M01AE`, `N02BA`, `N02BE`, `N05B`, `N05C`, `R03`, `R06`) for uniqueness, coverage, and collisions by year; recommend a primary or composite key and hygiene rules.  
**Expected outcome:** A key-health table (uniqueness %, nulls, collisions), and a written recommendation for the definitive join strategy.  
**Rationale:** Robust joins avoid silent data loss/duplication, ensuring accurate target alignment and analytics.

3) **Merge with `pharma_targets` and quantify gaps.**  
Produce actual-vs-target tables by ATC × `YearMonth`; list top 10 shortfalls and top 10 over-achievers with absolute and % differences; add one paragraph on plausible internal/seasonal drivers.  
**Expected outcome:** `merged_actual_vs_target.csv`, `gap_top10.csv`, and a narrative on drivers for the largest gaps.  
**Rationale:** Directs attention to where performance deviates most and frames root-cause investigation.

4) **Decompose trend/seasonality/residuals by ATC.**  
Use the full 2014-01 → 2019-10 horizon; include weekday/holiday effects. Deliver a 10-bullet exec summary.  
**Expected outcome:** Decomposition charts per ATC and a crisp summary explaining recurring patterns and anomalies.  
**Rationale:** Separates systematic patterns from noise to improve forecastability and planning.

5) **Detect and explain anomalies/outliers.**  
Apply robust methods (IQR + isolation forest). For the 3 most material anomalies: write “what happened, why it matters, what to do.”  
**Expected outcome:** Anomalies table with severity, suspected causes, and three short action notes.  
**Rationale:** Early anomaly triage reduces misinterpretation and accelerates corrective action.

6) **Quantify concentration dynamics.**  
Compute Herfindahl or Top-N shares per ATC/year; identify rising/falling concentration and explain risks/opportunities briefly per ATC.  
**Expected outcome:** Concentration metrics and mini-comments per ATC highlighting exposure or whitespace.  
**Rationale:** Guides resource allocation toward diversification or focused bets.

7) **Build a defensible 12-month baseline forecast per ATC.**  
Compare ARIMA/Prophet vs. a tree-based model with calendar regressors; report rolling-CV metrics and pick one recommendation with intervals.  
**Expected outcome:** Forecast plots, metric table (e.g., MAPE/SMAPE/RMSE), and a one-page rationale for the chosen model.  
**Rationale:** Provides a believable forward view with quantified uncertainty for planning.

8) **Construct base/bear/bull scenarios.**  
Sensitize the top 3 drivers; present ranges per ATC for the next 4 quarters and list two concrete triggers and actions.  
**Expected outcome:** Scenario table per ATC with assumptions, ranges, and trigger→action mapping.  
**Rationale:** Readies leadership for uncertainty with pre-agreed playbooks.

9) **Estimate promotion/activation uplift (if markers exist).**  
Use DID or matched controls; otherwise define proxy windows and caveats; return an “evidence pack” and a control framework.  
**Expected outcome:** Uplift estimates with confidence intervals, diagnostics, and a 1-page guardrail framework.  
**Rationale:** Distinguishes real causal lift from noise, reducing wasted spend.

10) **Cohort retention and change-point analysis.**  
Define monthly cohorts (e.g., first meaningful uptake), plot retention/decay per ATC, detect structural breaks; propose one retention tactic per ATC.  
**Expected outcome:** Cohort tables/plots and an actionable tactic list with expected effect sizes.  
**Rationale:** Highlights durability of performance and concrete levers to improve it.

11) **Explainability pack (transparent + tree model).**  
Train regularized GLM and a tree model; produce permutation/SHAP importance and translate top 5 drivers into non-technical recommendations; list key assumptions.  
**Expected outcome:** Explainability visuals and a driver-to-action mapping with assumptions called out.  
**Rationale:** Builds stakeholder trust and connects analytics to operations.

12) **Lightweight fairness/bias screen by segment.**  
Report outcome disparities across available segments (e.g., region/payer proxies) and recommend guardrails and monitoring.  
**Expected outcome:** Fairness diagnostics (metrics/plots) and a mitigation/monitoring checklist.  
**Rationale:** Reduces compliance risk and avoids biased decisions from skewed data.

13) **Propose a pragmatic data contract.**  
Specify schema, allowed ranges, null rules (even if currently 0%), timeliness SLAs, and drift checks (PSI/KS) per ATC × `YearMonth`; define fail vs. warn.  
**Expected outcome:** `data_contract.md` with enforceable rules and a CI-friendly checklist.  
**Rationale:** Institutionalizes data quality and prevents regressions as the pipeline evolves.

14) **Design anomaly/alert thresholds.**  
Use EWMA/control charts; backtest across 2014-01 → 2019-10; return threshold settings and two external indicators to track.  
**Expected outcome:** `alerts_spec.md` with thresholds, backtest precision/recall, and an external watchlist.  
**Rationale:** Moves from reactive to proactive monitoring with calibrated signal/noise trade-offs.

15) **Build an executive KPI deck.**  
Actual vs. target by ATC, YoY & rolling growth, seasonality overlays, annotated anomalies, and the recommended forecast; end with three prioritized next-quarter actions and expected impact ranges.  
**Expected outcome:** Slide deck (PDF/HTML) + a one-page takeaway summary.  
**Rationale:** Aligns leadership quickly on reality, forecast, and actions.

16) **Draft “evidence + context” briefs for the five worst shortfalls.**  
Use your analysis to propose the most likely internal drivers; list specific external items to research (guidelines, tenders, competitor moves) and what evidence would change our plan.  
**Expected outcome:** Five short briefs with hypothesis, evidence sought, decision trigger, and plan adjustments.  
**Rationale:** Structures follow-up research around decisions, not curiosity.

17) **Test three crisp hypotheses from EDA.**  
E.g., “N05B growth is primarily seasonality-driven,” “R03 breaks ~2017-Q4,” “N02BE has weekday variance.” Report effect sizes/p-values and one-paragraph conclusions with next steps.  
**Expected outcome:** Hypothesis table, supporting plots, stats, and decision-oriented conclusions.  
**Rationale:** Converts patterns into tested claims to avoid overfitting narratives.

18) **Assumption audit and robustness check.**  
List key assumptions (stationarity, outliers, calendar spec); re-run one robustness variant that could overturn results; state whether the headline conclusion changes and provide a “decision-proof” phrasing if needed.  
**Expected outcome:** Audit note with side-by-side metrics/plots and a clarified conclusion.  
**Rationale:** Prevents brittle recommendations and surprises in production.

19) **Produce tidy, shareable artifacts.**  
`profiling_report.md`, `merged_actual_vs_target.csv`, `gap_top10.csv`, `forecast_plots/`, `scenario_table.csv`, `explainability_summary.md`, `alerts_spec.md`, `exec_brief.pdf`. Ensure each file is self-contained and cross-referenced.  
**Expected outcome:** A clean artifact bundle ready for handoff, with a manifest describing each file and its location.  
**Rationale:** Speeds review, collaboration, and downstream reuse.

20) **Write a one-page leadership memo.**  
State the three most important truths in this data, the single forecast to believe (with caveats), the two actions to take first, and the riskiest assumption — plus how we’ll know within one month if we’re wrong.  
**Expected outcome:** A crisp, one-page memo suitable for executives, with a clear “how to falsify” check.  
**Rationale:** Drives decisive action while embedding fast feedback to course-correct.
