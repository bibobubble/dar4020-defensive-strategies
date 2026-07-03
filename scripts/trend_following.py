#!/usr/bin/env python3
"""Compute simple time-series trend-following signals and returns."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def read_returns(path: Path, date_col: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    if date_col not in data.columns:
        raise ValueError(f"Missing date column {date_col!r} in {path}")
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(date_col).drop_duplicates(date_col).set_index(date_col)
    return data.apply(pd.to_numeric, errors="coerce")


def compute_trend_signals(returns: pd.DataFrame, lookback: int = 12, skip: int = 1) -> pd.DataFrame:
    """Return no-lookahead trend signs from cumulative past returns.

    Signal at date t uses returns from t - lookback - skip through t - skip.
    This matches the common 12M-1M convention when lookback=12 and skip=1.
    """

    if lookback <= 0:
        raise ValueError("lookback must be positive")
    if skip < 0:
        raise ValueError("skip must be non-negative")

    signals = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns, dtype=float)
    for pos in range(len(returns)):
        end = pos - skip
        start = end - lookback
        if start < 0 or end <= start:
            continue
        window = returns.iloc[start:end]
        cumulative = (1.0 + window).prod(skipna=False) - 1.0
        signals.iloc[pos] = np.sign(cumulative)
    return signals


def compute_equal_vol_weights(
    returns: pd.DataFrame,
    lookback: int = 120,
    periods_per_year: int = 12,
) -> pd.DataFrame:
    """Return ex-ante inverse-volatility weights that sum to one by row."""

    if lookback <= 1:
        raise ValueError("lookback must be greater than 1")
    rolling_vol = returns.rolling(lookback).std(ddof=1).shift(1) * np.sqrt(periods_per_year)
    inv_vol = 1.0 / rolling_vol.replace(0.0, np.nan)
    return inv_vol.div(inv_vol.sum(axis=1), axis=0)


def compute_trend_returns(
    returns: pd.DataFrame,
    lookback: int = 12,
    skip: int = 1,
    weights: pd.Series | None = None,
    weighting: str = "equal",
    vol_lookback: int = 120,
    periods_per_year: int = 12,
) -> pd.Series:
    """Return trend-following returns across assets."""

    signals = compute_trend_signals(returns, lookback=lookback, skip=skip)
    positioned = signals * returns
    if weighting not in {"equal", "equal_vol"}:
        raise ValueError("weighting must be 'equal' or 'equal_vol'")
    if weights is None and weighting == "equal":
        active = positioned.notna()
        out = positioned.sum(axis=1, min_count=1) / active.sum(axis=1).replace(0, np.nan)
    elif weights is None and weighting == "equal_vol":
        equal_vol_weights = compute_equal_vol_weights(returns, lookback=vol_lookback, periods_per_year=periods_per_year)
        out = positioned.mul(equal_vol_weights, axis=1).sum(axis=1, min_count=1)
    else:
        aligned_weights = weights.reindex(returns.columns).astype(float)
        gross = aligned_weights.abs().sum()
        if gross == 0:
            raise ValueError("weights must have nonzero gross exposure")
        aligned_weights = aligned_weights / gross
        out = positioned.mul(aligned_weights, axis=1).sum(axis=1, min_count=1)
    out.name = "trend_following_return"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--returns", required=True, type=Path, help="CSV with date plus asset return columns")
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--lookback", type=int, default=12)
    parser.add_argument("--skip", type=int, default=1)
    parser.add_argument("--weighting", choices=["equal", "equal_vol"], default="equal")
    parser.add_argument("--vol-lookback", type=int, default=120)
    parser.add_argument("--periods-per-year", type=int, default=12)
    parser.add_argument("--out-dir", type=Path, default=Path("trend_following_output"))
    args = parser.parse_args()

    returns = read_returns(args.returns, args.date_col)
    signals = compute_trend_signals(returns, lookback=args.lookback, skip=args.skip)
    strategy = compute_trend_returns(
        returns,
        lookback=args.lookback,
        skip=args.skip,
        weighting=args.weighting,
        vol_lookback=args.vol_lookback,
        periods_per_year=args.periods_per_year,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    signals.to_csv(args.out_dir / "trend_signals.csv", index_label=args.date_col)
    if args.weighting == "equal_vol":
        weights = compute_equal_vol_weights(returns, lookback=args.vol_lookback, periods_per_year=args.periods_per_year)
        weights.to_csv(args.out_dir / "trend_equal_vol_weights.csv", index_label=args.date_col)
    strategy.to_csv(args.out_dir / "trend_following_returns.csv", index_label=args.date_col)
    print(strategy.dropna().describe().to_string())


if __name__ == "__main__":
    main()
