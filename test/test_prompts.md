# Pharma Sales & Targets — Prompt Pack (copy-ready)

## Quick sanity + data quality
1) Profile the dataset in `pharma_data`. List row count, date range (min/max of `datum`), unique Year/Month combos, and % missing by column. Flag join keys for `pharma_targets`. Return a 1-page summary and a data-quality table.

2) Validate that monthly sales (from `pharma_data`) roll up consistently to quarterly totals you compute (tolerance 0.1%). Show mismatches with product and month. Output `agg_validation.csv`.

3) Detect outliers in monthly TRx by product using both IQR and z-score. Output columns: product, Year, Month, value, method, reason. Save as `outliers.csv`.

## Sales vs. target basics
4) Aggregate `pharma_data` to annual by product and join to `pharma_targets` on `Year`. Produce `scorecard.csv` with columns: product, Year, Sales, Target, Variance, Pct_to_Target. Sort by worst Pct_to_Target.

5) Create a heatmap-ready table of Pct_to_Target by product for the latest year with both sales and targets (expected 2019). Save `pct_to_target_2019.csv`.

6) For 2019, compute total shortfall vs target and return the top 10 product contributors with columns: SKU, Shortfall, CumShare. Save `shortfall_waterfall_2019.csv`.

## Segmentation & drivers
7) Segment products into A/B/C based on trailing-3-month average TRx and growth (from `pharma_data` monthly rollup). Return `product, segment, TRx, growth` plus 3 recommended actions per segment. Save `segment_table.csv`.

8) Decompose annual variance vs target into volume and mix effects (price not available). Provide a bridge table for 2019 with clear math. Save `variance_bridge_2019.csv`.

9) Compute monthly seasonality indices per product (normalize annual sum = 12). Return `seasonality.csv` and brief commentary on peaks/troughs.

## Launch & cohort views
10) For product `<SKU_X>`, build a launch curve vs analogs `<SKU_A>, <SKU_B>`. Index each to 100 at its first non-zero month and compare the first 6 months. Output `launch_curves.csv`.

11) Cohort analysis: define cohorts by the first month a product exceeds 100 TRx. Track average TRx over the next 4 quarters. Output `cohorts.csv`.

## Forecasting (baseline + uncertainty)
12) Build a 6-month forecast by product using monthly history (2014–2019). Include 80%/95% CIs and a rolling backtest MAPE per product. Output `forecast.csv` and `backtest_metrics.csv`.

13) Create 3 demand scenarios for 2020H1: Base, Upside (+10% elastic lift), Downside (−8% headwinds). Return scenario totals by product and a probability-weighted mean with ≤8 bullet assumptions. Output `scenario_totals.csv`.

## Allocation optimization (no territory fields present)
14) Recommend rebalancing attention (proxy FTE) across products to maximize Pct_to_Target next year. Identify +1/−1 attention slots per product with expected lift and rationale. Output `rebalancing_plan.csv`.

15) Next-best-action for bottom-quartile products by Pct_to_Target (2019): return `product, inferred_barrier, action_1..3, expected_lift, effort_1_5`. Output `nba.csv`.

## Channel/payer (not in metadata — proxy cuts)
16) Using `Weekday Name`, quantify contribution to 2019 variance vs target by weekday as a timing proxy. Return a stacked table of variance by weekday and product. Output `weekday_variance.csv`.

17) Document data gaps needed for payer/access and GTN analysis; produce a checklist of missing fields and suggested capture logic. Output `data_gaps.md`.

## Marketing & ROI (not in metadata — proxy timing)
18) Correlate monthly TRx with `Hour`/`Weekday Name` as timing proxies; report strongest lags (0–2 months) and plain-English interpretations. Output `lag_correlation.csv`.

19) Simple CBA thought-experiment: if we shift 10% “attention” from the least elastic to most elastic products (based on prompt 18/seasonality), estimate incremental TRx next month. Output `cba_elasticity.md`.

## Inventory / supply (signature detection)
20) Detect possible stockout signatures: dips >30% vs 3-month moving average followed by a rebound within 2 months. Return product, start_month, depth, rebound_month, confidence. Output `stockout_candidates.csv`.

## Executive-ready briefs
21) Create a 1-page “Market Performance Brief — 2019”: headline, 3 key insights, variance vs target sparkline, top 5 risks, next 5 actions with owners/dates, and appendix of sources. Output `brief_2019.md` (or PDF).

22) Produce a board slide outline (6–8 slides): performance (2014–2019), forecast (2020H1), scenario deltas, and actions. List exact charts/tables and why. Output `board_outline.md`.

## Data robustness / adversarial tests
23) If `pharma_targets` has duplicates (same `Year`, product), deduplicate by latest `updated_at` if present; else first occurrence. Re-run the scorecard and quantify changes. Output `targets_deduped.csv`, `scorecard_after_dedup.csv`, `dedup_impact.md`.

24) Randomly mask 5% of months per product; impute via (a) carry-forward and (b) seasonal mean. Compare Pct_to_Target shifts and which products flip status. Output `imputation_compare.csv`.

25) Compliance guardrails: scan generated content for off-label implications or PII leakage. Replace with compliant alternatives and log triggered rules. Output `compliance_log.md`.

## Debugging / transparency
26) Explain forecast feature set, training window (2014–2019), chosen model(s), and 3 rejected alternatives with reasons in ≤12 bullets. Output `forecast_notes.md`.

27) Generate a data dictionary for `pharma_data` and `pharma_targets` using the provided metadata and inferred types/ranges from the files. Output `data_dictionary.md`.

## Handy templates (fill-in)
28) Compare [PRODUCT_LIST] for [DATE_RANGE] (e.g., 2018–2019). Return Sales, Target (annual), Variance, Pct_to_Target, plus a 5-bullet summary. Output `comparison.csv` and `comparison_summary.md`.

29) Identify the top 5 root causes of missing the target in [YEAR] (e.g., 2019). Attribute % of total shortfall to each and suggest one action per cause. Output `root_causes_[YEAR].md`.

30) Create `actions.csv` with columns: owner, action, product, due_date, expected_lift, confidence (low/med/high), dependency. Populate with at least 10 prioritized items.
