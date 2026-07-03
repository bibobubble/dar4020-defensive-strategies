# Defensive Stock Screening

Use this when adapting DAR4020 ideas to an individual-stock candidate universe.

## Role In The Strategy

Defensive stock screening is a universe-construction layer. It is not the paper's DAR4020 method by itself. DAR4020 ranks factor or sleeve returns by rolling correlation to the benchmark; a stock screen identifies candidates that may belong in a defensive sleeve.

## Candidate Features

Start with measurable fields:

- Dividend yield and payout sustainability.
- Five-year beta or rolling beta to the relevant benchmark.
- Debt-to-equity, net debt, interest coverage, and balance-sheet resilience.
- Sector and revenue defensiveness: staples, healthcare, regulated utilities, telecom, infrastructure, defense, and selected insurers.
- Liquidity, market cap, borrow availability, currency, and listing venue.
- Rolling correlation to the benchmark and to existing portfolio holdings.

## Screen Logic

Prefer a staged screen:

1. Remove illiquid or untradable names.
2. Remove names with unsustainable yield: high yield plus weak coverage, declining cash flow, or high leverage.
3. Rank remaining names by low beta, low benchmark correlation, balance-sheet quality, and stable demand.
4. Diversify across sectors and regions; avoid a "defensive" portfolio that is just one crowded sector.
5. Backtest as a sleeve and then feed the sleeve return into DAR4020 or portfolio overlay analysis.

## Long And Short Interpretation

For long candidates, require both defensiveness and investability. High yield is not enough.

For short or underweight candidates, look for high positive benchmark correlation, cyclical exposure, capital intensity, high leverage, weak dividend cover, or dependence on favorable credit conditions. Shorting needs borrow, cost, and risk controls.

## Data Caution

If the source workbook has formula errors such as `#VALUE!`, use it as research notes only. Clean the data into typed columns before scoring or backtesting.
