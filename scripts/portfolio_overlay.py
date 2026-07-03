#!/usr/bin/env python3
"""Combine benchmark returns with one or more defensive overlays."""

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


def scale_to_realized_vol(series: pd.Series, target_vol: float, periods_per_year: int = 12) -> pd.Series:
    """Scale a return series to a target annualized realized volatility."""

    realized = series.dropna().std(ddof=1) * np.sqrt(periods_per_year)
    if realized <= 0 or np.isnan(realized):
        raise ValueError("Cannot scale a zero-volatility or all-null series")
    return (series * (target_vol / realized)).rename(series.name)


def realized_vol_scale(series: pd.Series, target_vol: float, periods_per_year: int = 12) -> float:
    """Return the scalar needed to target annualized realized volatility."""

    realized = series.dropna().std(ddof=1) * np.sqrt(periods_per_year)
    if realized <= 0 or np.isnan(realized):
        raise ValueError("Cannot scale a zero-volatility or all-null series")
    return target_vol / realized


def resolve_overlay_weights(
    overlays: pd.DataFrame,
    overlay_weights: pd.DataFrame | pd.Series | float = 1.0,
) -> pd.DataFrame:
    """Align scalar, Series, or DataFrame overlay weights to overlay returns."""

    if isinstance(overlay_weights, (float, int)):
        return pd.DataFrame(float(overlay_weights), index=overlays.index, columns=overlays.columns)
    if isinstance(overlay_weights, pd.Series):
        if overlays.shape[1] != 1:
            raise ValueError("Series weights require exactly one overlay column")
        return pd.DataFrame({overlays.columns[0]: overlay_weights}).reindex(overlays.index).ffill().fillna(0.0)
    return overlay_weights.reindex(index=overlays.index, columns=overlays.columns).ffill().fillna(0.0)


def combine_overlay(
    benchmark: pd.Series,
    overlays: pd.DataFrame,
    overlay_weights: pd.DataFrame | pd.Series | float = 1.0,
    cost_bps_per_turnover: float = 0.0,
    target_combined_overlay_vol: float | None = None,
    periods_per_year: int = 12,
) -> pd.DataFrame:
    """Combine benchmark and overlay returns with turnover costs.

    `overlay_weights` can be a scalar, a Series for one overlay, or a DataFrame
    aligned with the overlay columns. Costs are charged on absolute one-period
    changes in overlay weights: turnover * bps / 10000.
    """

    benchmark = benchmark.rename("benchmark_return")
    aligned = overlays.join(benchmark, how="inner")
    overlays = aligned.drop(columns=["benchmark_return"])
    benchmark = aligned["benchmark_return"]

    weights = resolve_overlay_weights(overlays, overlay_weights)
    overlay_scale = 1.0
    if target_combined_overlay_vol is not None:
        if target_combined_overlay_vol <= 0:
            raise ValueError("target_combined_overlay_vol must be positive")
        raw_contribution = (weights * overlays).sum(axis=1).rename("overlay_contribution")
        overlay_scale = realized_vol_scale(raw_contribution, target_combined_overlay_vol, periods_per_year)
        weights = weights * overlay_scale

    overlay_contribution = (weights * overlays).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if len(turnover) > 0:
        turnover.iloc[0] = weights.iloc[0].abs().sum()
    cost = turnover * (cost_bps_per_turnover / 10000.0)
    total = benchmark + overlay_contribution - cost

    return pd.DataFrame(
        {
            "benchmark_return": benchmark,
            "overlay_contribution": overlay_contribution,
            "overlay_scale": overlay_scale,
            "turnover": turnover,
            "cost": cost,
            "total_return": total,
        }
    )


def summarize_portfolio(returns: pd.Series, periods_per_year: int = 12) -> pd.Series:
    clean = returns.dropna()
    wealth = (1.0 + clean).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.Series(
        {
            "periods": len(clean),
            "return_pa": clean.mean() * periods_per_year,
            "vol_pa": clean.std(ddof=1) * np.sqrt(periods_per_year),
            "sharpe_like": clean.mean() / clean.std(ddof=1) * np.sqrt(periods_per_year) if clean.std(ddof=1) > 0 else np.nan,
            "max_drawdown": drawdown.min(),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--overlays", required=True, type=Path)
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--benchmark-col", default=None)
    parser.add_argument("--overlay-weight", type=float, default=1.0)
    parser.add_argument("--target-overlay-vol", type=float, default=None)
    parser.add_argument("--target-combined-overlay-vol", type=float, default=None)
    parser.add_argument("--periods-per-year", type=int, default=12)
    parser.add_argument("--cost-bps-per-turnover", type=float, default=0.0)
    parser.add_argument("--out-dir", type=Path, default=Path("portfolio_overlay_output"))
    args = parser.parse_args()

    benchmark_df = read_returns(args.benchmark, args.date_col)
    overlays = read_returns(args.overlays, args.date_col)
    benchmark_col = args.benchmark_col or benchmark_df.columns[0]
    if benchmark_col not in benchmark_df.columns:
        raise ValueError(f"Missing benchmark column {benchmark_col!r}")

    if args.target_overlay_vol is not None:
        overlays = overlays.apply(scale_to_realized_vol, target_vol=args.target_overlay_vol, periods_per_year=args.periods_per_year)

    combined = combine_overlay(
        benchmark=benchmark_df[benchmark_col],
        overlays=overlays,
        overlay_weights=args.overlay_weight,
        cost_bps_per_turnover=args.cost_bps_per_turnover,
        target_combined_overlay_vol=args.target_combined_overlay_vol,
        periods_per_year=args.periods_per_year,
    )
    summary = pd.concat(
        {
            "benchmark": summarize_portfolio(combined["benchmark_return"], periods_per_year=args.periods_per_year),
            "combined": summarize_portfolio(combined["total_return"], periods_per_year=args.periods_per_year),
        },
        axis=1,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out_dir / "combined_returns.csv", index_label=args.date_col)
    summary.to_csv(args.out_dir / "portfolio_summary.csv")
    print(summary.to_string())


if __name__ == "__main__":
    main()
