# Mapping The Paper To Implementation

## What To Preserve

- Objective: protect a benchmark portfolio in bad states.
- Factor preprocessing: the paper scales individual factors to an ex-ante 10% annualized volatility target with a 10-year rolling window before comparing and combining them.
- Ranking variable: historical rolling correlation with the benchmark.
- DAR4020 construction: long 40% most negative-correlation factors, short 20% most positive-correlation factors.
- Original DAR comparison: when using tercile/tercile legs with 25 factors, use 8 long and 8 short factors (`--leg-count-mode floor`), not ceiling counts.
- Trend-following construction: use past trend signals without lookahead, with the paper emphasizing 12M-1M style signals as the main baseline and equal-volatility aggregation across trend sleeves.
- Drawdown definition: use high-watermark peak-to-trough losses and evaluate defensive strategy performance from drawdown start to trough for Table 5-style comparisons.
- 50/50 defensive blend scaling: scale the combined DAR4020 plus trend-following overlay when reproducing the paper's risk-matched comparison tables.
- Evaluation focus: downside states, drawdowns, and worst benchmark months, not only unconditional return.
- Complementarity: compare DAR4020 with trend-following and test their combination.

## What To Adapt

- Benchmark: the paper uses global 60/40 as the main benchmark; your implementation can use your own strategy returns.
- Factor universe: the paper uses long historical factor returns; your implementation should use tradable sleeves available to you.
- Frequency: the paper uses monthly data; intraday/daily strategies need explicit resampling and noise controls.
- Costs: the paper does not fully optimize implementation frictions; your version must include them.
- Scaling: the paper often scales strategies to 5% realized volatility for comparison; live implementation needs ex-ante scaling.
- Volatility warm-up: the paper states a 10-year rolling factor volatility target, but does not fully specify early-sample warm-up handling. Treat shorter `min_periods` settings as documented implementation choices.
- Missing data: practical implementations must explicitly decide whether to drop, freeze, or reweight unavailable factors at each rebalance.
- Significance testing: add t-tests or Newey-West-style tests when reproducing paper table annotations; the bundled scripts focus on point estimates and portfolio construction.
- Defensive stock screening: useful for building tradable sleeves, but not a direct substitute for the paper's factor-correlation ranking.
- Recession regime probabilities: useful for conditioning or sizing defensive overlays, but outside the paper's core DAR4020 construction.
- Position sell signals: useful for single-name risk control, but separate from portfolio-level drawdown protection.

## Minimal Research Specification

State these before coding:

- Benchmark return series.
- Factor universe and start dates.
- Rebalance frequency.
- Rolling correlation lookback.
- Long and short fractions.
- Weighting method.
- Factor volatility targeting rule.
- Factor volatility warm-up rule.
- Leg-count rounding rule.
- Overlay size.
- Whether volatility scaling is applied per component or after blending.
- Defensive-stock universe construction rule, if using individual equities.
- Regime-scaling rule, if using recession probabilities.
- Position exit rule, if applying sell discipline to individual names.
- Cost model.
- Out-of-sample split.
- Metrics for success.
