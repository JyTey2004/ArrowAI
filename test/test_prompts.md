# Pharma Sales & Targets — Prompt Pack (with expected actions)

## Quick sanity + data quality
1) Profile the dataset in `pharma_data`. List row count, date range (min/max of `datum`), unique Year/Month combos, and % missing by column. Flag join keys for `pharma_targets`. Return a 1-page summary and a data-quality table.
   - **Expected Outcome/Actions:**  
     - Produce `data_profile.md` (coverage 2014–2019), `data_quality.csv` with types and missing%.  
     - Recommend **annual join on `Year`**; note need for monthly aggregation when comparing to annual targets.  
     - Flag oddities (duplicate timestamps, impossible hours, non-monotonic dates) and create a fix list.

2) Validate that monthly sales (from `pharma_data`) roll up consistently to quarterly totals you compute (tolerance 0.1%). Show mismatches with product and month. Output `agg_validation.csv`.
   - **Expected Outcome/Actions:**  
     - Report pass/fail per product-quarter; highlight months that break tolerance.  
     - Create a remediation checklist (recompute, cap spikes, fill gaps) and re-aggregate.

3) Detect outliers in monthly TRx by product using both IQR and z-score. Output columns: product, Year, Month, value, method, reason. Save as `outliers.csv`.
   - **Expected Outcome/Actions:**  
     - 0–2% points flagged with rationale.  
     - Suggest treatment: winsorize, investigate events, or exclude from model backtests.

## Sales vs. target basics
4) Aggregate `pharma_data` to annual by product and join to `pharma_targets` on `Year`. Produce `scorecard.csv` with columns: product, Year, Sales, Target, Variance, Pct_to_Target. Sort by worst Pct_to_Target.
   - **Expected Outcome/Actions:**  
     - Annual scorecard 2014–2019 per product (+Total).  
     - Identify underperformers (<90% to target) and log for actions (#15).

5) Create a heatmap-ready table of Pct_to_Target by product for the latest year with both sales and targets (expected 2019). Save `pct_to_target_2019.csv`.
   - **Expected Outcome/Actions:**  
     - Visual ranking of products by target attainment for 2019.  
     - Mark bottom quartile for “next-best-actions” (#15).

6) For 2019, compute total shortfall vs target and return the top 10 product contributors with columns: SKU, Shortfall, CumShare. Save `shortfall_waterfall_2019.csv`.
   - **Expected Outcome/Actions:**  
     - Pareto list (often top 3–5 drive ~80% of shortfall).  
     - Direct these SKUs to scenario planning (#13) and resource rebalancing (#14).

## Segmentation & drivers
7) Segment products into A/B/C based on trailing-3-month average TRx and growth (from `pharma_data` monthly rollup). Return `product, segment, TRx, growth` plus 3 recommended actions per segment. Save `segment_table.csv`.
   - **Expected Outcome/Actions:**  
     - A: protect & optimize; B: invest selectively; C: fix or de-prioritize.  
     - Attach 3 concrete moves per segment (e.g., sampling cadence change, messaging test).

8) Decompose annual variance vs target into volume and mix effects (price not available). Provide a bridge table for 2019 with clear math. Save `variance_bridge_2019.csv`.
   - **Expected Outcome/Actions:**  
     - Quantify whether shortfall is broad (volume) or concentrated (mix).  
     - Prioritize SKU-level levers accordingly.

9) Compute monthly seasonality indices per product (normalize annual sum = 12). Return `seasonality.csv` and brief commentary on peaks/troughs.
   - **Expected Outcome/Actions:**  
     - Seasonality factors for monthly planning and pro-rating annual targets.  
     - Feed into forecasts (#12) and monthly target pacing.

## Launch & cohort views
10) For product `<SKU_X>`, build a launch curve vs analogs `<SKU_A>, <SKU_B>`. Index each to 100 at its first non-zero month and compare the first 6 months. Output `launch_curves.csv`.
   - **Expected Outcome/Actions:**  
     - Label `<SKU_X>` as tracking/leading/lagging vs analogs.  
     - If lagging, trigger corrective actions (detail frequency, messaging) and recheck in 2 months.

11) Cohort analysis: define cohorts by the first month a product exceeds 100 TRx. Track average TRx over the next 4 quarters. Output `cohorts.csv`.
   - **Expected Outcome/Actions:**  
     - Retention-style curves to spot early momentum decay.  
     - Recommend playbooks for weak cohorts (sampling, HCP education).

## Forecasting (baseline + uncertainty)
12) Build a 6-month forecast by product using monthly history (2014–2019). Include 80%/95% CIs and a rolling backtest MAPE per product. Output `forecast.csv` and `backtest_metrics.csv`.
   - **Expected Outcome/Actions:**  
     - 2020-H1 projections with uncertainty bands; MAPE/SMAPE table.  
     - Use Base forecast as input to scenarios (#13) and capacity planning.

13) Create 3 demand scenarios for 2020H1: Base, Upside (+10% elastic lift), Downside (−8% headwinds). Return scenario totals by product and a probability-weighted mean with ≤8 bullet assumptions. Output `scenario_totals.csv`.
   - **Expected Outcome/Actions:**  
     - Scenario deltas vs Base and weighted expectation.  
     - Define triggers to switch plans (e.g., if month-1 < P10, enact cost guardrails).

## Allocation optimization (no territory fields present)
14) Recommend rebalancing attention (proxy FTE) across products to maximize Pct_to_Target next year. Identify +1/−1 attention slots per product with expected lift and rationale. Output `rebalancing_plan.csv`.
   - **Expected Outcome/Actions:**  
     - Top 10 adds / 10 reduces with estimated lift per move.  
     - Implementation plan: reassignments, KPIs, review cadence.

15) Next-best-action for bottom-quartile products by Pct_to_Target (2019): return `product, inferred_barrier, action_1..3, expected_lift, effort_1_5`. Output `nba.csv`.
   - **Expected Outcome/Actions:**  
     - Action stack ranked by impact/effort with owners/dates.  
     - Feed prioritized actions to `actions.csv` (#30).

## Channel/payer (not in metadata — proxy cuts)
16) Using `Weekday Name`, quantify contribution to 2019 variance vs target by weekday as a timing proxy. Return a stacked table of variance by weekday and product. Output `weekday_variance.csv`.
   - **Expected Outcome/Actions:**  
     - Identify timing-related patterns (e.g., Mon/Fri dips).  
     - Adjust operational cadence (call scheduling, sampli
