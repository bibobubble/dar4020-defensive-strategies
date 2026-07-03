# DAR4020 Implementation Guide

## Inputs

Minimum required data:

- Benchmark returns `b_t`: the portfolio or strategy that needs downside protection.
- Factor returns `F_{t,i}`: one return series per factor, sleeve, alpha, or defensive candidate.

Optional application-layer data:

- Defensive-stock candidate data: beta, dividend yield, payout cover, leverage, sector, liquidity, and benchmark correlation.
- Recession probability signal: point-in-time 6-month or 12-month recession probability.
- Position price data: close and volume for sell-signal rules.

Recommended format:

- Monthly returns in decimal form, e.g. `0.012` for 1.2%.
- One row per date.
- No future-filled missing values.
- Use excess returns if the benchmark and factors are evaluated over cash.
- For paper-faithful DAR replication, pre-scale factor returns to 10% annualized volatility using a 120-month rolling window. If using the script, pass `--target-factor-vol 0.10 --vol-lookback 120`.
- The script defaults to requiring a full volatility lookback. For long historical samples where the paper's early-sample warm-up is not explicit, use `--vol-min-periods` only as a documented research choice.

## Baseline DAR4020 Algorithm

For each rebalance date `t`:

1. Take a rolling window ending at `t-1`.
2. Compute correlation between each factor and benchmark inside that window.
3. Rank factors ascending by correlation:
   - lowest correlation = most defensive candidate.
   - highest correlation = least defensive / most pro-cyclical candidate.
4. Long leg:
   - select `ceil(0.40 * N)` factors with lowest correlations by default.
   - equal weight so long leg sums to `+1.0`.
5. Short leg:
   - select `ceil(0.20 * N)` factors with highest correlations by default.
   - equal weight so short leg sums to `-1.0`.
6. Total weight is long weights plus short weights.
7. Apply the weights to factor returns at date `t`.

The key anti-lookahead rule is that weights at `t` must be estimated using information available before returns at `t`.

The paper's equal weighting assumes comparable factor volatility. If raw factor inputs have materially different risk levels, use ex-ante factor volatility targeting before forming DAR weights.

For the paper's original DAR tercile/tercile comparison with 25 factors, use floor rounding so the legs contain 8 long and 8 short factors: `--long-frac 0.333333 --short-frac 0.333333 --leg-count-mode floor`. The DAR4020 specification is unaffected because 40% and 20% of 25 are exactly 10 and 5.

When a factor is selected by the historical window but has a missing return at date `t`, exclude it from that date's tradable universe and re-rank/reweight the available factors. Do not let `pandas` silently skip missing returns after weights are fixed.

## Trend-Following Algorithm

For each asset or strategy sleeve:

1. At date `t`, skip the most recent `skip` periods.
2. Compute cumulative return over the prior `lookback` periods.
3. Assign signal:
   - `+1` if cumulative return is positive.
   - `-1` if cumulative return is negative.
   - `0` if cumulative return is zero.
4. Multiply the signal by the asset return at `t`.
5. Equal-weight active trend sleeves unless the user supplies weights.

The paper's baseline trend-following interpretation is close to a 12M-1M rule: use 12 months of past returns while skipping the most recent month.

For the paper-like multi-asset trend aggregate, use equal-volatility weighting rather than simple equal weighting. In the script, pass `--weighting equal_vol --vol-lookback 120`.

## Drawdown Mathematics

Use cumulative wealth:

`W_t = W_{t-1} * (1 + r_t)`

Use high-watermark drawdown:

`DD_t = W_t / max(W_0, ..., W_t) - 1`

A drawdown event starts when `DD_t` first drops below zero, reaches its trough at the minimum `DD_t`, and recovers when `DD_t` returns to zero. For incomplete drawdowns, set recovery to missing and report the current trough.

Report both:

- `start_to_trough_return`: peak-to-trough window, used for Table 5-style crisis-window comparisons.
- `start_to_recovery_return`: full drawdown episode through recovery, useful for implementation diagnostics.

## Overlay Construction

For benchmark return `b_t`, overlay returns `o_{t,j}`, and overlay weights `w_{t,j}`:

`combined_t = b_t + sum_j(w_{t,j} * o_{t,j}) - cost_t`

Turnover cost approximation:

`cost_t = cost_bps / 10000 * sum_j(abs(w_{t,j} - w_{t-1,j}))`

For risk-matched comparisons, scale an overlay return series by:

`scaled_t = r_t * target_vol / realized_vol`

There are two distinct scaling choices:

- `--target-overlay-vol`: scale each overlay column separately before applying overlay weights.
- `--target-combined-overlay-vol`: first blend the overlay columns using the specified weights, then scale the combined overlay contribution.

Use `--target-combined-overlay-vol 0.05` for paper-style 50/50 DAR4020 plus trend-following comparisons, because the paper scales the mixed defensive strategy rather than each component separately.

## Recession-Regime Overlay Sizing

Use a recession probability signal only after the base overlay exists. For an overlay return `o_t` and recession probability `p_t`, map `p_t` into a weight `g_t`:

`scaled_overlay_t = g_t * o_t`

The bundled `scripts/regime_overlay.py` uses a clipped linear ramp from `min_weight` to `max_weight` between low and high probability thresholds. This implements the recession model's intended use as a downstream regime input, not as a standalone liquidation signal.

Apply a signal lag if publication timing is uncertain.

## Defensive Stock Universe

When applying the research to stocks, separate stock selection from DAR4020 construction:

1. Build a tradable candidate universe using liquidity and market-cap filters.
2. Score defensiveness using low beta, low benchmark correlation, sustainable yield, leverage, sector resilience, and cash-flow stability.
3. Backtest the selected basket as a sleeve.
4. Feed the sleeve return into DAR4020, trend-following, or portfolio overlay analysis.

Do not treat high dividend yield alone as a defensive signal.

## Position-Level Sell Discipline

Use `scripts/sell_signals.py` for single-name exit diagnostics:

- 20% profit target.
- RSI above 70.
- Close below moving average on heavy volume.
- 15% trailing stop.

These are risk-management rules for holdings. They should be tested against opportunity cost because simple profit-taking and RSI rules can sell long-term winners too early.

## Practical Variations

Use the baseline first. Then test variations one at a time:

- Lookback: 36, 60, 120 months.
- Long/short split: original DAR tercile/tercile, 40/20, 50/10, long-only.
- Leg-count rounding: `ceil` for default fraction selection, `floor` for paper-style original DAR terciles with 25 factors.
- Weighting: equal weight, inverse volatility, covariance-aware weighting.
- Overlay size: fixed notional, volatility target, drawdown-aware scaling.
- Regime sizing: fixed overlay, recession-probability ramp, or trend-confirmed regime gate.
- Position exits: none, trailing stop, moving-average violation, RSI, or profit target.
- Benchmark: 60/40, equity-only, user's strategy return, or a risk model factor portfolio.

## Trend-Following Complement

The paper's practical message is not "DAR4020 alone solves defense." Treat trend-following as a complement:

- DAR4020 tends to help earlier because it has negative beta to the benchmark.
- Trend-following tends to help more after a downtrend persists.
- Test standalone DAR4020, standalone trend-following, and a 50/50 combination at matched volatility. For the 50/50 combination, scale the blended return series, not the two components separately, when reproducing the paper's comparison tables.

Use `scripts/portfolio_overlay.py` after producing DAR4020 and trend-following return series to test the combined overlay.

## Metrics To Report

Always report both standalone overlay metrics and combined portfolio metrics:

- Annualized return.
- Annualized volatility.
- Sharpe or information ratio.
- Correlation and beta to benchmark.
- Average return in benchmark up and down months.
- Average return in worst 10% benchmark months.
- Average return during benchmark drawdowns.
- Maximum drawdown of benchmark plus overlay.
- Turnover and estimated transaction cost drag.
- Hit rate in bad months.

## Failure Modes

- Using full-sample correlations to form past weights.
- Letting missing data change the universe in a biased way.
- Ranking on noisy correlations when the factor universe is small.
- Ignoring that short legs may be expensive or impossible.
- Vol-targeting with realized full-sample volatility instead of ex-ante estimates.
- Treating an early warm-up choice such as `--vol-min-periods 36` as if it were explicitly specified by the paper.
- Scaling component overlays separately when the comparison requires scaling a blended 50/50 overlay.
- Confusing the paper's 60/40 stock/bond benchmark with 60-day/40-day moving averages.
- Treating a hand-built defensive stock list as equivalent to rolling-correlation DAR4020.
- Using recession probability as a binary market-timing switch without out-of-sample validation.
- Selling every RSI or profit-target trigger without measuring missed upside.
- Selecting factors after seeing crisis performance.
- Treating the paper's 1800-2021 evidence as proof for a modern implementation without checking tradability.
