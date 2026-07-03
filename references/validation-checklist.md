# Validation Checklist

Use this checklist before accepting a DAR4020 backtest.

## Data Integrity

- Dates are sorted and unique.
- Benchmark and factor returns use the same frequency.
- Returns are decimal returns, not percentages, unless explicitly converted.
- Missing values are handled with a documented rule.
- Factor series are available before they enter the universe.
- No backfilled future constituents or survivorship-biased factor universe.
- Factor inputs are ex-ante volatility-targeted if claiming paper-faithful DAR replication.
- Any shortened volatility warm-up rule is documented and not presented as an explicit paper assumption.
- Defensive-stock inputs have clean typed columns and no unresolved spreadsheet errors such as `#VALUE!`.
- Recession probabilities are point-in-time and publication timing is documented.
- Price and volume data for sell signals are adjusted and aligned to the correct holding period.

## No-Lookahead Checks

- Rolling correlations for date `t` use data ending at `t-1`.
- Volatility targets use only prior data.
- At-date missing factor returns do not silently alter effective long or short leg exposure.
- Original DAR tercile tests with 25 factors use 8 long and 8 short factors.
- Factor selection and parameter choices are not tuned on the full evaluation period.
- Rebalance timing matches realistic data availability.
- Regime probabilities used at date `t` were available at or before date `t`.
- Sell signals use only price and volume observations available at the signal date.

## Defensive Performance Checks

- Worst 1%, 5%, and 10% benchmark months.
- Benchmark drawdowns greater than 2%, 10%, and 20%.
- Peak-to-trough returns are used for Table 5-style drawdown-window comparisons.
- Full start-to-recovery returns are reported separately when useful.
- First and second month of benchmark drawdowns.
- Recessions, inflation regimes, or other bad states if available.
- Beta and correlation to the benchmark through time.
- Performance by recession-probability regime buckets.
- Defensive-stock sleeve returns separately from DAR4020 overlay returns.
- Exit-rule opportunity cost: first-signal return versus held return.

## Portfolio Integration Checks

- Standalone overlay.
- Benchmark plus DAR4020.
- Benchmark plus trend-following.
- Benchmark plus 50/50 DAR4020 and trend-following.
- Risk-matched comparison across alternatives.
- 50/50 DAR4020 plus trend-following is scaled after blending when matching the paper's comparison-table volatility.
- Regime-scaled overlay versus fixed overlay.
- Position exits tested with and without re-entry logic.
- Transaction cost and turnover sensitivity.
- Leverage and shorting constraints.

## Script Coverage Checks

- `scripts/dar4020_weights.py` produces rolling-correlation weights without lookahead, can ex-ante volatility-target factor inputs, supports configurable volatility warm-up, and supports configurable leg-count rounding.
- `scripts/trend_following.py` produces trend signals from prior returns, with configurable lookback, skip, and equal-volatility weighting.
- `scripts/drawdown_analysis.py` identifies high-watermark drawdown events and separates start-to-trough from start-to-recovery returns.
- `scripts/portfolio_overlay.py` combines benchmark and overlay returns, applies turnover costs, supports per-overlay realized volatility scaling, and supports post-blend overlay volatility scaling.
- `scripts/regime_overlay.py` scales an overlay by a point-in-time recession probability series.
- `scripts/sell_signals.py` computes profit-target, RSI, moving-average-volume, and trailing-stop sell signals.

For any user strategy, run the scripts in this order unless the user has an existing pipeline:

1. Build DAR4020 returns from factor returns and benchmark returns.
2. Build trend-following returns from tradable asset or sleeve returns.
3. Analyze benchmark drawdowns.
4. Combine benchmark plus DAR4020, trend-following, and their blend.
5. Optionally scale overlays by recession probability.
6. Optionally test position-level exits for individual stock sleeves.
7. Compare bad-state metrics and cost-adjusted results.

## Decision Rule

Do not proceed from research to live strategy unless:

- The defensive behavior survives out-of-sample testing.
- The overlay improves bad-state outcomes after costs.
- The combined portfolio does not introduce larger hidden risks elsewhere.
- The implementation can be traded with realistic liquidity, borrow, margin, and capacity.
