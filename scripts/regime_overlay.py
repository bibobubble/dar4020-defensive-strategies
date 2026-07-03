#!/usr/bin/env python3
"""Scale a defensive overlay by a point-in-time recession probability signal."""

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


def regime_weight(
    probability: pd.Series,
    low_threshold: float = 0.20,
    high_threshold: float = 0.60,
    min_weight: float = 0.50,
    max_weight: float = 1.50,
) -> pd.Series:
    """Map recession probability to overlay weight with a clipped linear ramp."""

    if not 0 <= low_threshold < high_threshold <= 1:
        raise ValueError("thresholds must satisfy 0 <= low_threshold < high_threshold <= 1")
    if min_weight < 0 or max_weight < min_weight:
        raise ValueError("weights must satisfy 0 <= min_weight <= max_weight")

    p = probability.astype(float)
    ramp = (p - low_threshold) / (high_threshold - low_threshold)
    ramp = ramp.clip(lower=0.0, upper=1.0)
    return (min_weight + ramp * (max_weight - min_weight)).rename("overlay_weight")


def apply_regime_overlay(
    overlay_returns: pd.Series,
    recession_probability: pd.Series,
    low_threshold: float = 0.20,
    high_threshold: float = 0.60,
    min_weight: float = 0.50,
    max_weight: float = 1.50,
    signal_lag: int = 0,
) -> pd.DataFrame:
    """Apply regime-dependent weights to a defensive overlay return series."""

    if signal_lag < 0:
        raise ValueError("signal_lag must be non-negative")

    overlay = overlay_returns.rename("overlay_return")
    prob = recession_probability.rename("recession_probability").shift(signal_lag)
    aligned = pd.concat([overlay, prob], axis=1).dropna(subset=["overlay_return"])
    aligned["recession_probability"] = aligned["recession_probability"].ffill()
    aligned = aligned.dropna(subset=["recession_probability"])
    weights = regime_weight(
        aligned["recession_probability"],
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        min_weight=min_weight,
        max_weight=max_weight,
    )
    aligned["overlay_weight"] = weights
    aligned["regime_scaled_overlay"] = aligned["overlay_return"] * aligned["overlay_weight"]
    return aligned


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", required=True, type=Path, help="CSV with date plus overlay return column")
    parser.add_argument("--regime", required=True, type=Path, help="CSV with date plus recession probability column")
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--overlay-col", default=None)
    parser.add_argument("--prob-col", default=None)
    parser.add_argument("--low-threshold", type=float, default=0.20)
    parser.add_argument("--high-threshold", type=float, default=0.60)
    parser.add_argument("--min-weight", type=float, default=0.50)
    parser.add_argument("--max-weight", type=float, default=1.50)
    parser.add_argument("--signal-lag", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("regime_overlay_output"))
    args = parser.parse_args()

    overlay_df = read_returns(args.overlay, args.date_col)
    regime_df = read_returns(args.regime, args.date_col)
    overlay_col = args.overlay_col or overlay_df.columns[0]
    prob_col = args.prob_col or regime_df.columns[0]
    if overlay_col not in overlay_df.columns:
        raise ValueError(f"Missing overlay column {overlay_col!r}")
    if prob_col not in regime_df.columns:
        raise ValueError(f"Missing probability column {prob_col!r}")

    result = apply_regime_overlay(
        overlay_df[overlay_col],
        regime_df[prob_col],
        low_threshold=args.low_threshold,
        high_threshold=args.high_threshold,
        min_weight=args.min_weight,
        max_weight=args.max_weight,
        signal_lag=args.signal_lag,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out_dir / "regime_scaled_overlay.csv", index_label=args.date_col)
    print(result.tail().to_string())


if __name__ == "__main__":
    main()
