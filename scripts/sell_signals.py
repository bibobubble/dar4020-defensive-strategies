#!/usr/bin/env python3
"""Compute position-level sell signals for defensive stock holdings."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def read_prices(path: Path, date_col: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    if date_col not in data.columns:
        raise ValueError(f"Missing date column {date_col!r} in {path}")
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(date_col).drop_duplicates(date_col).set_index(date_col)
    return data.apply(pd.to_numeric, errors="coerce")


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Compute Wilder-style RSI from a close price series."""

    if window <= 1:
        raise ValueError("window must be greater than 1")
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    return rsi.rename("rsi")


def compute_sell_signals(
    prices: pd.DataFrame,
    close_col: str = "close",
    volume_col: str = "volume",
    buy_price: float | None = None,
    profit_target_pct: float = 0.20,
    rsi_window: int = 14,
    rsi_threshold: float = 70.0,
    ma_window: int = 50,
    volume_multiplier: float = 1.5,
    trailing_stop_pct: float = 0.15,
) -> pd.DataFrame:
    """Return sell-signal columns for a single position."""

    if close_col not in prices.columns:
        raise ValueError(f"Missing close column {close_col!r}")
    if volume_col not in prices.columns:
        raise ValueError(f"Missing volume column {volume_col!r}")
    if buy_price is None:
        buy_price = float(prices[close_col].dropna().iloc[0])
    if buy_price <= 0:
        raise ValueError("buy_price must be positive")
    if not 0 < trailing_stop_pct < 1:
        raise ValueError("trailing_stop_pct must be in (0, 1)")

    close = prices[close_col].astype(float)
    volume = prices[volume_col].astype(float)
    ma = close.rolling(ma_window, min_periods=ma_window).mean().rename("moving_average")
    vol_avg = volume.rolling(ma_window, min_periods=ma_window).mean().rename("volume_average")
    running_max = close.cummax()
    trailing_stop_level = (running_max * (1.0 - trailing_stop_pct)).rename("trailing_stop_level")
    result = pd.DataFrame(
        {
            "close": close,
            "volume": volume,
            "rsi": compute_rsi(close, rsi_window),
            "moving_average": ma,
            "volume_average": vol_avg,
            "trailing_stop_level": trailing_stop_level,
        }
    )
    result["profit_target"] = close >= buy_price * (1.0 + profit_target_pct)
    result["rsi_overbought"] = result["rsi"] > rsi_threshold
    result["ma_volume_violation"] = (close < result["moving_average"]) & (volume > result["volume_average"] * volume_multiplier)
    result["trailing_stop"] = close <= result["trailing_stop_level"]
    result["any_sell_signal"] = result[["profit_target", "rsi_overbought", "ma_volume_violation", "trailing_stop"]].any(axis=1)
    return result


def first_trigger(signals: pd.DataFrame) -> pd.Series:
    """Return the first triggered sell signal and date."""

    signal_cols = ["profit_target", "rsi_overbought", "ma_volume_violation", "trailing_stop"]
    for date, row in signals.iterrows():
        for col in signal_cols:
            if bool(row.get(col, False)):
                return pd.Series({"date": date, "signal": col, "close": row["close"]})
    return pd.Series({"date": pd.NaT, "signal": None, "close": np.nan})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", required=True, type=Path, help="CSV with date, close, and volume columns")
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--close-col", default="close")
    parser.add_argument("--volume-col", default="volume")
    parser.add_argument("--buy-price", type=float, default=None)
    parser.add_argument("--profit-target-pct", type=float, default=0.20)
    parser.add_argument("--rsi-window", type=int, default=14)
    parser.add_argument("--rsi-threshold", type=float, default=70.0)
    parser.add_argument("--ma-window", type=int, default=50)
    parser.add_argument("--volume-multiplier", type=float, default=1.5)
    parser.add_argument("--trailing-stop-pct", type=float, default=0.15)
    parser.add_argument("--out-dir", type=Path, default=Path("sell_signals_output"))
    args = parser.parse_args()

    prices = read_prices(args.prices, args.date_col)
    signals = compute_sell_signals(
        prices,
        close_col=args.close_col,
        volume_col=args.volume_col,
        buy_price=args.buy_price,
        profit_target_pct=args.profit_target_pct,
        rsi_window=args.rsi_window,
        rsi_threshold=args.rsi_threshold,
        ma_window=args.ma_window,
        volume_multiplier=args.volume_multiplier,
        trailing_stop_pct=args.trailing_stop_pct,
    )
    first = first_trigger(signals)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    signals.to_csv(args.out_dir / "sell_signals.csv", index_label=args.date_col)
    first.to_csv(args.out_dir / "first_trigger.csv", header=["value"])
    print(first.to_string())


if __name__ == "__main__":
    main()
