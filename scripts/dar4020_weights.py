#!/usr/bin/env python3
"""Compute DAR4020 weights and returns from factor and benchmark CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _read_returns(path: Path, date_col: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    if date_col not in data.columns:
        raise ValueError(f"Missing date column {date_col!r} in {path}")
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(date_col).drop_duplicates(date_col).set_index(date_col)
    return data.apply(pd.to_numeric, errors="coerce")


def ex_ante_vol_target(
    returns: pd.DataFrame,
    lookback: int = 120,
    min_periods: int | None = None,
    target_vol: float = 0.10,
    periods_per_year: int = 12,
) -> pd.DataFrame:
    """Scale each column using prior realized volatility only.

    At date t, the scale uses returns through t-1. This matches the paper's
    premise that factor inputs are ex-ante volatility-targeted before entering
    the DAR ranking and equal-weighting step.
    """

    if lookback <= 1:
        raise ValueError("lookback must be greater than 1")
    if min_periods is None:
        min_periods = lookback
    if min_periods < 2 or min_periods > lookback:
        raise ValueError("min_periods must be between 2 and lookback")
    if target_vol <= 0:
        raise ValueError("target_vol must be positive")
    rolling_vol = returns.rolling(lookback, min_periods=min_periods).std(ddof=1).shift(1) * np.sqrt(periods_per_year)
    scale = target_vol / rolling_vol.replace(0.0, np.nan)
    return returns * scale


def leg_count(frac: float, n: int, mode: str = "ceil") -> int:
    """Convert a leg fraction to a factor count."""

    if not 0 <= frac <= 1:
        raise ValueError("frac must be in [0, 1]")
    if n < 0:
        raise ValueError("n must be non-negative")
    if frac == 0 or n == 0:
        return 0
    raw = frac * n
    if mode == "ceil":
        count = int(np.ceil(raw))
    elif mode == "floor":
        count = int(np.floor(raw))
    elif mode == "round":
        count = int(np.round(raw))
    else:
        raise ValueError("mode must be one of: ceil, floor, round")
    return min(n, max(1, count))


def compute_dar4020(
    factors: pd.DataFrame,
    benchmark: pd.Series,
    lookback: int = 60,
    long_frac: float = 0.40,
    short_frac: float = 0.20,
    min_periods: int | None = None,
    target_factor_vol: float | None = None,
    vol_lookback: int = 120,
    vol_min_periods: int | None = None,
    periods_per_year: int = 12,
    leg_count_mode: str = "ceil",
) -> tuple[pd.DataFrame, pd.Series]:
    """Return no-lookahead DAR4020 weights and strategy returns.

    Weights at date t are estimated from returns through t-1, then applied to
    factor returns at t.
    """

    if min_periods is None:
        min_periods = lookback
    if not 0 < long_frac <= 1:
        raise ValueError("long_frac must be in (0, 1]")
    if not 0 <= short_frac <= 1:
        raise ValueError("short_frac must be in [0, 1]")

    aligned = factors.join(benchmark.rename("__benchmark__"), how="inner")
    factors = aligned.drop(columns=["__benchmark__"])
    benchmark = aligned["__benchmark__"]
    if target_factor_vol is not None:
        factors = ex_ante_vol_target(
            factors,
            lookback=vol_lookback,
            min_periods=vol_min_periods,
            target_vol=target_factor_vol,
            periods_per_year=periods_per_year,
        )

    weights = pd.DataFrame(0.0, index=factors.index, columns=factors.columns)

    for pos in range(len(factors)):
        if pos < min_periods:
            continue
        window_factors = factors.iloc[max(0, pos - lookback) : pos]
        window_benchmark = benchmark.iloc[max(0, pos - lookback) : pos]
        valid_pair_counts = window_factors.notna().mul(window_benchmark.notna(), axis=0).sum()
        eligible = valid_pair_counts[valid_pair_counts >= min_periods].index
        if len(eligible) == 0:
            continue
        corrs = window_factors[eligible].corrwith(window_benchmark).dropna()
        current_available = factors.iloc[pos][corrs.index].notna()
        historical_available = window_factors[corrs.index].iloc[-1].notna()
        available = corrs.index[current_available & historical_available]
        corrs = corrs.loc[available]
        n = len(corrs)
        if n == 0:
            continue
        n_long = leg_count(long_frac, n, mode=leg_count_mode)
        n_short = leg_count(short_frac, n, mode=leg_count_mode)

        ranked = corrs.sort_values()
        long_names = ranked.index[:n_long]
        short_names = ranked.index[-n_short:] if n_short > 0 else []

        weights.loc[factors.index[pos], long_names] = 1.0 / len(long_names)
        if n_short > 0:
            weights.loc[factors.index[pos], short_names] -= 1.0 / len(short_names)

    strategy_returns = (weights * factors).sum(axis=1, min_count=1)
    strategy_returns[weights.abs().sum(axis=1) == 0] = np.nan
    return weights, strategy_returns


def summarize(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    aligned = pd.concat({"strategy": strategy, "benchmark": benchmark}, axis=1).dropna()
    if aligned.empty:
        raise ValueError("No overlapping non-null strategy and benchmark returns")

    s = aligned["strategy"]
    b = aligned["benchmark"]
    ann = 12
    worst10 = b <= b.quantile(0.10)
    down = b < 0

    beta = np.nan
    if b.var() > 0:
        beta = s.cov(b) / b.var()

    return pd.Series(
        {
            "months": len(aligned),
            "return_pa": s.mean() * ann,
            "vol_pa": s.std(ddof=1) * np.sqrt(ann),
            "corr_to_benchmark": s.corr(b),
            "beta_to_benchmark": beta,
            "avg_when_benchmark_down": s[down].mean(),
            "avg_worst_10pct_benchmark_months": s[worst10].mean(),
            "hit_rate_worst_10pct": (s[worst10] > 0).mean(),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factors", required=True, type=Path, help="CSV with date plus factor return columns")
    parser.add_argument("--benchmark", required=True, type=Path, help="CSV with date plus benchmark return column")
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--benchmark-col", default=None)
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--long-frac", type=float, default=0.40)
    parser.add_argument("--short-frac", type=float, default=0.20)
    parser.add_argument("--target-factor-vol", type=float, default=None, help="Optional annualized ex-ante volatility target for factor inputs")
    parser.add_argument("--vol-lookback", type=int, default=120, help="Lookback periods for factor volatility targeting")
    parser.add_argument("--vol-min-periods", type=int, default=None, help="Minimum prior periods required for factor volatility targeting")
    parser.add_argument("--leg-count-mode", choices=["ceil", "floor", "round"], default="ceil", help="How to convert long/short fractions into factor counts")
    parser.add_argument("--periods-per-year", type=int, default=12)
    parser.add_argument("--out-dir", type=Path, default=Path("dar4020_output"))
    args = parser.parse_args()

    factors = _read_returns(args.factors, args.date_col)
    benchmark_df = _read_returns(args.benchmark, args.date_col)
    benchmark_col = args.benchmark_col or benchmark_df.columns[0]
    if benchmark_col not in benchmark_df.columns:
        raise ValueError(f"Missing benchmark column {benchmark_col!r}")

    weights, returns = compute_dar4020(
        factors=factors,
        benchmark=benchmark_df[benchmark_col],
        lookback=args.lookback,
        long_frac=args.long_frac,
        short_frac=args.short_frac,
        target_factor_vol=args.target_factor_vol,
        vol_lookback=args.vol_lookback,
        vol_min_periods=args.vol_min_periods,
        periods_per_year=args.periods_per_year,
        leg_count_mode=args.leg_count_mode,
    )
    summary = summarize(returns, benchmark_df[benchmark_col])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    weights.to_csv(args.out_dir / "dar4020_weights.csv", index_label=args.date_col)
    returns.rename("dar4020_return").to_csv(args.out_dir / "dar4020_returns.csv", index_label=args.date_col)
    summary.to_csv(args.out_dir / "dar4020_summary.csv", header=["value"])
    print(summary.to_string())


if __name__ == "__main__":
    main()
