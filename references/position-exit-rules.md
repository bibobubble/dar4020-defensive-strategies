# Position Exit Rules

Use this when applying sell discipline to individual stock positions inside a defensive sleeve.

## Role In The Strategy

Position exit rules manage single-name risk. They do not replace DAR4020 ranking, recession-regime sizing, or portfolio-level drawdown analysis.

## Supported Rules

The bundled `scripts/sell_signals.py` supports:

- Profit target: sell once close reaches `buy_price * (1 + target)`.
- RSI overbought: flag when Wilder RSI is above a threshold, commonly 70.
- Moving-average violation on heavy volume: close below moving average and volume above a multiple of average volume.
- Trailing stop: sell when close falls below the running high times `1 - stop_pct`.

## Interpretation

Use these rules differently by position type:

- Long-term compounders: avoid selling only because RSI is high or a 20% profit target hit; those rules can cut major winners early.
- Tactical or speculative positions: trailing stops and moving-average violations can protect against sharp reversals.
- Defensive income names: combine price signals with dividend safety, debt, and cash-flow deterioration.

## Validation

Backtest the exit rules against:

- Return captured at the first signal.
- Return if held to the evaluation date.
- Maximum drawdown avoided.
- Opportunity cost from selling winners too early.
- Transaction costs, taxes, liquidity, and re-entry logic.

Do not present a sell rule as superior unless it improves the full portfolio objective after costs and opportunity cost.
