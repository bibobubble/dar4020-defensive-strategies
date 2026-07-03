#!/usr/bin/env python3
"""Compute high-watermark drawdowns and drawdown events."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def read_return_series(path: Path, date_col: str, return_col: str | None = None) -> pd.Series:
    data = pd.read_csv(path)
    if date_col not in data.columns:
        raise ValueError(f"Missing date column {date_col!r} in {path}")
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(date_col).drop_duplicates(date_col).set_index(date_col)
    if return_col is None:
        candidates = [c for c in data.columns if c != date_col]
        if not candidates:
            raise ValueError("No return column found")
        return_col = candidates[0]
    if return_col not in data.columns:
        raise ValueError(f"Missing return column {return_col!r}")
    return pd.to_numeric(data[return_col], errors="coerce").rename(return_col)


def compute_wealth(returns: pd.Series, initial_wealth: float = 1.0) -> pd.Series:
    return (initial_wealth * (1.0 + returns.fillna(0.0)).cumprod()).rename("wealth")


def compute_drawdowns(returns: pd.Series) -> pd.Series:
    wealth = compute_wealth(returns)
    high_watermark = wealth.cummax()
    return (wealth / high_watermark - 1.0).rename("drawdown")


def find_drawdown_events(returns: pd.Series, min_depth: float = 0.0) -> pd.DataFrame:
    """Identify high-watermark drawdown episodes.

    Returns rows with start, trough, recovery, depth, length_months, and
    drawdown_return. depth is negative.
    """

    wealth = compute_wealth(returns)
    drawdown = compute_drawdowns(returns)
    in_event = False
    start = None
    trough = None
    trough_depth = 0.0
    rows = []

    for date, dd in drawdown.items():
        if not in_event and dd < 0:
            in_event = True
            start = date
            trough = date
            trough_depth = dd
        elif in_event:
            if dd < trough_depth:
                trough_depth = dd
                trough = date
            if dd == 0:
                if abs(trough_depth) >= min_depth:
                    event_returns = returns.loc[start:date]
                    trough_returns = returns.loc[start:trough]
                    rows.append(
                        {
                            "start": start,
                            "trough": trough,
                            "recovery": date,
                            "depth": trough_depth,
                            "length_months": len(event_returns),
                            "start_to_trough_return": (1.0 + trough_returns).prod() - 1.0,
                            "start_to_recovery_return": (1.0 + event_returns).prod() - 1.0,
                            "drawdown_return": (1.0 + trough_returns).prod() - 1.0,
                            "start_wealth": wealth.loc[start],
                            "trough_wealth": wealth.loc[trough],
                            "recovery_wealth": wealth.loc[date],
                        }
                    )
                in_event = False
                start = None
                trough = None
                trough_depth = 0.0

    if in_event and start is not None and abs(trough_depth) >= min_depth:
        event_returns = returns.loc[start:]
        trough_returns = returns.loc[start:trough]
        rows.append(
            {
                "start": start,
                "trough": trough,
                "recovery": pd.NaT,
                "depth": trough_depth,
                "length_months": len(event_returns),
                "start_to_trough_return": (1.0 + trough_returns).prod() - 1.0,
                "start_to_recovery_return": np.nan,
                "drawdown_return": (1.0 + trough_returns).prod() - 1.0,
                "start_wealth": wealth.loc[start],
                "trough_wealth": wealth.loc[trough],
                "recovery_wealth": np.nan,
            }
        )

    return pd.DataFrame(rows)


def average_by_drawdown_month(returns: pd.Series, events: pd.DataFrame, max_month: int = 15) -> pd.Series:
    values = {i: [] for i in range(1, max_month + 1)}
    for _, event in events.iterrows():
        end = event["recovery"] if pd.notna(event["recovery"]) else returns.index[-1]
        path = returns.loc[event["start"] : end].iloc[:max_month]
        for i, value in enumerate(path, start=1):
            values[i].append(value)
    return pd.Series({i: np.mean(v) if v else np.nan for i, v in values.items()}, name="avg_return")


def cumulative_average_by_drawdown_month(returns: pd.Series, events: pd.DataFrame, max_month: int = 15) -> pd.Series:
    values = {i: [] for i in range(1, max_month + 1)}
    for _, event in events.iterrows():
        end = event["recovery"] if pd.notna(event["recovery"]) else returns.index[-1]
        path = returns.loc[event["start"] : end].iloc[:max_month]
        cumulative = (1.0 + path).cumprod() - 1.0
        for i, value in enumerate(cumulative, start=1):
            values[i].append(value)
    return pd.Series({i: np.mean(v) if v else np.nan for i, v in values.items()}, name="avg_cumulative_return")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--returns", required=True, type=Path, help="CSV with date plus benchmark return column")
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--return-col", default=None)
    parser.add_argument("--min-depth", type=float, default=0.02, help="Minimum absolute drawdown depth")
    parser.add_argument("--out-dir", type=Path, default=Path("drawdown_output"))
    args = parser.parse_args()

    returns = read_return_series(args.returns, args.date_col, args.return_col)
    drawdowns = compute_drawdowns(returns)
    events = find_drawdown_events(returns, min_depth=args.min_depth)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    drawdowns.to_csv(args.out_dir / "drawdowns.csv", index_label=args.date_col)
    events.to_csv(args.out_dir / "drawdown_events.csv", index=False)
    average_by_drawdown_month(returns, events).to_csv(args.out_dir / "avg_by_drawdown_month.csv", header=True)
    cumulative_average_by_drawdown_month(returns, events).to_csv(
        args.out_dir / "avg_cumulative_by_drawdown_month.csv",
        header=True,
    )
    print(events.to_string(index=False))


if __name__ == "__main__":
    main()
