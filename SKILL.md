---
name: dar4020-defensive-strategies
description: "Use when implementing, backtesting, adapting, or validating DAR4020, Defensive Absolute Return, factor-correlation hedges, downside-protection overlays, trend-following complements, recession-regime defensive scaling, defensive stock screening, sell-signal rules, or 60/40 drawdown-control logic in a quantitative investment strategy."
---

# DAR4020 Defensive Strategies

## Purpose

Use this skill to turn the DAR4020 idea from *The Best Defensive Strategies: Two Centuries of Evidence* into a practical quant research workflow. The goal is not to explain the paper; the goal is to build, test, and integrate a defensive overlay based on factor correlations with a benchmark portfolio, optionally extended with defensive stock screening, recession-regime sizing, and position-level sell discipline.

## Core Workflow

1. Define the benchmark to protect:
   - Default: 60/40 portfolio returns.
   - Alternative: equity portfolio, multi-asset strategy, or the user's live strategy returns.
2. Define the factor return universe:
   - Each column should be a tradable factor, strategy sleeve, or alpha sleeve return series.
   - Use excess returns when possible.
   - For paper-faithful DAR replication, volatility-target factor inputs ex ante to 10% annualized volatility using a 10-year rolling window before ranking and equal-weighting.
   - Align all series to the same monthly calendar unless the user explicitly chooses another rebalance frequency.
3. Build DAR4020 without lookahead:
   - At each rebalance date, use only past data.
   - Compute each factor's rolling correlation with the benchmark, typically over 60 months.
   - Rank factors from most negative correlation to most positive correlation.
   - Go long the most negative-correlation 40% of factors.
   - Go short the most positive-correlation 20% of factors.
   - Equal-weight within each leg unless the user requests risk weighting.
4. Backtest the overlay:
   - Compute standalone DAR4020 returns.
   - Test overlay returns when added to the benchmark.
   - Optionally compute trend-following returns and a DAR4020/trend blend.
   - Include transaction costs, turnover, leverage, shorting constraints, and volatility targeting if relevant.
5. Add practical application layers only after the core overlay is correct:
   - Use defensive-stock screens to build a candidate universe; do not treat hand-picked defensive stocks as a direct substitute for factor-level DAR4020.
   - Use recession probabilities as a regime input for overlay sizing, not as a standalone all-in/all-out market timer.
   - Use sell-signal rules for single-stock risk management, not to replace the portfolio-level DAR4020 signal.
6. Validate defensiveness before optimizing return:
   - Worst 10% benchmark months.
   - Benchmark drawdowns over 2%, 10%, and 20%.
   - First 1-2 months of drawdowns.
   - Recessions / inflation regimes if data exists.
   - Correlation, beta, hit rate, turnover, and capacity.
7. Compare with alternatives:
   - Trend-following.
   - Gold or safe-haven assets.
   - Put option overlays.
   - Low-risk, quality, and value sleeves.
   - 50/50 DAR4020 plus trend-following.

## Load References

- Read `references/implementation-guide.md` when building or reviewing code.
- Read `references/validation-checklist.md` before trusting backtest results.
- Read `references/paper-mapping.md` when mapping the paper's definitions to practical implementation choices.
- Read `references/defensive-stock-screening.md` when adapting the strategy to individual defensive stock candidates.
- Read `references/recession-regime-overlay.md` when using recession probabilities to scale a defensive overlay.
- Read `references/position-exit-rules.md` when adding RSI, moving-average, profit-taking, or trailing-stop sell discipline.

## Script

Use `scripts/dar4020_weights.py` when the user has CSV files for factor returns and benchmark returns. The script computes rolling-correlation ranks, DAR4020 weights, DAR4020 returns, and summary metrics.

Use `scripts/trend_following.py` to compute 12M-1M style time-series trend signals and trend-following returns. Use `--weighting equal_vol` for the paper-like equal-volatility trend aggregation.

Use `scripts/drawdown_analysis.py` to compute high-watermark drawdowns, drawdown start/trough/recovery dates, drawdown depth, peak-to-trough returns, full start-to-recovery returns, and drawdown-window behavior.

Use `scripts/portfolio_overlay.py` to combine benchmark returns with DAR4020 and/or trend-following overlays, apply overlay weights, estimate turnover costs, and risk-match overlays with realized volatility scaling.

Use `scripts/regime_overlay.py` to scale an already-built defensive overlay by a point-in-time recession probability series.

Use `scripts/sell_signals.py` to compute position-level sell signals from close and volume data: profit target, RSI overbought, moving-average violation on heavy volume, and trailing stop.

Expected inputs:

- `factor_returns.csv`: date column plus one column per factor return.
- `benchmark_returns.csv`: date column plus one benchmark return column.
- For regime scaling: `regime_signal.csv`: date column plus a point-in-time recession probability column.
- For sell-signal analysis: `prices.csv`: date, close, and volume columns for one position.

Default assumptions:

- Monthly returns.
- 60-month lookback.
- Long top 40% most negative-correlation factors.
- Short top 20% most positive-correlation factors.
- Equal-weight long and short legs.

Paper-faithful options:

- Add `--target-factor-vol 0.10 --vol-lookback 120` to `dar4020_weights.py`.
- Use `--vol-min-periods` only when intentionally allowing an earlier warm-up for long historical samples; the paper's exact early-sample volatility warm-up rule is not fully specified.
- For original DAR tercile/tercile comparisons with 25 factors, add `--long-frac 0.333333 --short-frac 0.333333 --leg-count-mode floor` to reproduce the paper's 8-long/8-short count.
- Add `--weighting equal_vol --vol-lookback 120` to `trend_following.py`.
- Use `start_to_trough_return` from `drawdown_analysis.py` to match Table 5-style drawdown-window returns.
- For Table 6/7-style 50/50 DAR4020 plus trend-following comparisons, use `portfolio_overlay.py --target-combined-overlay-vol 0.05` so the blended overlay is scaled after mixing.

## Mathematical Coverage

This skill includes executable support for:

- Rolling correlation ranking for DAR and DAR4020.
- Ex-ante factor volatility targeting before DAR weighting.
- Configurable volatility warm-up length for ex-ante factor scaling.
- No-lookahead long/short factor weights.
- Configurable leg-count rounding for paper-faithful original DAR terciles.
- Standalone DAR4020 return construction.
- 12M-1M trend-following signals, equal-vol trend weights, and trend returns.
- High-watermark drawdown series, drawdown events, start-to-trough returns, and start-to-recovery returns.
- Worst-month and down-month defensive metrics.
- Benchmark plus overlay return construction.
- Turnover-cost drag from changing overlay weights.
- Realized volatility scaling for risk-matched comparisons.
- Post-blend realized volatility scaling for mixed defensive overlays.
- Recession-probability scaling for defensive overlays.
- Position-level sell signals: profit target, RSI, moving-average plus volume violation, and trailing stop.

It does not fully implement option pricing, put replication, historical inflation-regime classification, statistical significance tests, live data ingestion, or a complete production execution/capacity model. Treat those as additional modules if needed.

## Required Cautions

- Do not use full-sample correlations to form historical positions.
- Do not optimize factor universe, lookback length, or overlay weight on the full sample without out-of-sample validation.
- Do not present historical drawdown improvement as investable edge until costs, borrow, turnover, leverage, liquidity, and capacity are included.
- Do not mix return frequencies without explicit resampling and alignment.
- Do not compare overlays at different volatilities unless scaled or clearly labeled.
- Do not treat raw-factor equal weighting as paper-faithful unless the factor inputs have already been ex-ante volatility-targeted.
- Do not use start-to-recovery drawdown returns when trying to reproduce the paper's peak-to-trough drawdown tables.
- Do not reproduce the original DAR tercile strategy with default ceiling counts; use floor rounding for the paper's 25-factor 8-long/8-short setup.
- Do not scale DAR4020 and trend-following separately if the target comparison is the paper's 50/50 blended overlay volatility.
- Do not confuse the paper's 60/40 stock/bond benchmark with 60-day/40-day moving averages.
- Do not treat high dividend yield alone as defensive quality; check beta, leverage, payout sustainability, sector cyclicality, liquidity, and correlation.
- Do not use recession probability as an untested binary market-timing switch; treat it as a sizing or gating input and validate out of sample.
- Do not let RSI or simple profit-taking rules automatically cut long-term winners without testing opportunity cost.
