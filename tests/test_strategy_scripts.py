import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trend_following_uses_lookback_skipping_most_recent_month():
    trend_following = load_module("trend_following")
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    returns = pd.DataFrame(
        {
            "rising": [0.02, 0.02, 0.02, -0.01, 0.03, 0.01, 0.01, 0.01],
            "falling": [-0.02, -0.02, -0.02, 0.01, -0.03, -0.01, -0.01, -0.01],
        },
        index=dates,
    )

    signals = trend_following.compute_trend_signals(returns, lookback=3, skip=1)
    strategy = trend_following.compute_trend_returns(returns, lookback=3, skip=1)

    assert signals.loc[dates[4], "rising"] == 1
    assert signals.loc[dates[4], "falling"] == -1
    assert np.isclose(strategy.loc[dates[4]], 0.03)


def test_trend_following_supports_equal_vol_weighting():
    trend_following = load_module("trend_following")
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    returns = pd.DataFrame(
        {
            "low_vol": [0.010, 0.011, 0.009, 0.010, 0.011, 0.009, 0.010, 0.011],
            "high_vol": [0.04, -0.02, 0.04, -0.02, 0.04, -0.02, 0.04, -0.02],
        },
        index=dates,
    )

    weights = trend_following.compute_equal_vol_weights(returns, lookback=4, periods_per_year=12)

    assert weights.loc[dates[4], "low_vol"] > weights.loc[dates[4], "high_vol"]
    assert np.isclose(weights.loc[dates[4]].abs().sum(), 1.0)


def test_dar4020_can_vol_target_factors_before_weighting_and_returns():
    dar4020 = load_module("dar4020_weights")
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    factors = pd.DataFrame(
        {
            "low_vol": [0.01, -0.01, 0.01, -0.01, 0.01, -0.01, 0.01, -0.01],
            "high_vol": [0.04, -0.04, 0.04, -0.04, 0.04, -0.04, 0.04, -0.04],
        },
        index=dates,
    )

    scaled = dar4020.ex_ante_vol_target(factors, lookback=4, target_vol=0.10, periods_per_year=12)
    expected_scale = 0.10 / (factors["high_vol"].iloc[:4].std(ddof=1) * np.sqrt(12))

    assert np.isclose(scaled.loc[dates[4], "high_vol"], factors.loc[dates[4], "high_vol"] * expected_scale)


def test_dar4020_vol_target_supports_shorter_warmup_min_periods():
    dar4020 = load_module("dar4020_weights")
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    factors = pd.DataFrame(
        {
            "factor": [0.01, -0.02, 0.015, -0.01, 0.02, -0.015],
        },
        index=dates,
    )

    scaled = dar4020.ex_ante_vol_target(
        factors,
        lookback=5,
        min_periods=3,
        target_vol=0.10,
        periods_per_year=12,
    )
    expected_scale = 0.10 / (factors["factor"].iloc[:3].std(ddof=1) * np.sqrt(12))

    assert np.isnan(scaled.loc[dates[2], "factor"])
    assert np.isclose(scaled.loc[dates[3], "factor"], factors.loc[dates[3], "factor"] * expected_scale)


def test_dar4020_leg_count_mode_can_match_original_dar_terciles():
    dar4020 = load_module("dar4020_weights")

    assert dar4020.leg_count(1 / 3, 25, mode="floor") == 8
    assert dar4020.leg_count(1 / 3, 25, mode="ceil") == 9


def test_dar4020_rebalances_when_current_factor_return_is_missing():
    dar4020 = load_module("dar4020_weights")
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    benchmark = pd.Series([0.01, -0.01, 0.01, -0.01, 0.02, -0.02], index=dates, name="benchmark")
    factors = pd.DataFrame(
        {
            "a": [-0.01, 0.01, -0.01, 0.01, np.nan, 0.01],
            "b": [-0.01, 0.01, -0.01, 0.01, -0.02, 0.01],
            "c": [0.01, -0.01, 0.01, -0.01, 0.03, -0.01],
            "d": [0.01, -0.01, 0.01, -0.01, 0.04, -0.01],
        },
        index=dates,
    )

    weights, strategy = dar4020.compute_dar4020(factors, benchmark, lookback=4, long_frac=0.5, short_frac=0.25)

    assert weights.loc[dates[4], "a"] == 0.0
    assert np.isclose(weights.loc[dates[4]][weights.loc[dates[4]] > 0].sum(), 1.0)
    assert np.isfinite(strategy.loc[dates[4]])


def test_drawdown_events_identify_start_trough_recovery_and_return():
    drawdown_analysis = load_module("drawdown_analysis")
    dates = pd.date_range("2021-01-31", periods=6, freq="ME")
    returns = pd.Series([0.10, -0.10, -0.10, 0.30, -0.05, 0.10], index=dates, name="benchmark")

    dd = drawdown_analysis.compute_drawdowns(returns)
    events = drawdown_analysis.find_drawdown_events(returns, min_depth=0.05)

    assert np.isclose(dd.loc[dates[2]], -0.19)
    assert len(events) == 2
    first = events.iloc[0]
    assert first["start"] == dates[1]
    assert first["trough"] == dates[2]
    assert first["recovery"] == dates[3]
    assert np.isclose(first["depth"], -0.19)
    assert np.isclose(first["start_to_trough_return"], (1 - 0.10) * (1 - 0.10) - 1)
    assert np.isclose(first["start_to_recovery_return"], (1 - 0.10) * (1 - 0.10) * (1 + 0.30) - 1)


def test_overlay_combines_benchmark_overlay_costs_and_realized_vol_target():
    portfolio_overlay = load_module("portfolio_overlay")
    dates = pd.date_range("2022-01-31", periods=6, freq="ME")
    benchmark = pd.Series([0.01, -0.02, 0.03, -0.04, 0.02, 0.01], index=dates, name="benchmark")
    overlay = pd.Series([0.02, 0.03, -0.01, 0.04, -0.01, 0.00], index=dates, name="dar4020")
    weights = pd.Series([0.0, 0.5, 0.5, 1.0, 0.0, 0.5], index=dates, name="dar4020_weight")

    combined = portfolio_overlay.combine_overlay(
        benchmark=benchmark,
        overlays=pd.DataFrame({"dar4020": overlay}),
        overlay_weights=pd.DataFrame({"dar4020": weights}),
        cost_bps_per_turnover=10,
    )

    expected_turnover_cost = abs(0.5 - 0.0) * 0.001
    assert np.isclose(combined.loc[dates[1], "total_return"], -0.02 + 0.5 * 0.03 - expected_turnover_cost)
    assert combined.loc[dates[3], "overlay_contribution"] > 0

    scaled = portfolio_overlay.scale_to_realized_vol(overlay, target_vol=0.05, periods_per_year=12)
    assert np.isclose(scaled.std(ddof=1) * np.sqrt(12), 0.05)


def test_overlay_can_scale_combined_contribution_after_blending():
    portfolio_overlay = load_module("portfolio_overlay")
    dates = pd.date_range("2022-01-31", periods=8, freq="ME")
    benchmark = pd.Series([0.01, -0.02, 0.03, -0.04, 0.02, 0.01, -0.01, 0.02], index=dates, name="benchmark")
    overlays = pd.DataFrame(
        {
            "dar4020": [0.02, 0.01, -0.01, 0.03, -0.02, 0.01, 0.00, 0.02],
            "trend": [-0.01, 0.02, 0.01, -0.02, 0.03, -0.01, 0.02, 0.00],
        },
        index=dates,
    )

    combined = portfolio_overlay.combine_overlay(
        benchmark=benchmark,
        overlays=overlays,
        overlay_weights=0.5,
        target_combined_overlay_vol=0.05,
        periods_per_year=12,
    )

    assert np.isclose(combined["overlay_contribution"].std(ddof=1) * np.sqrt(12), 0.05)


def test_regime_overlay_maps_recession_probability_to_overlay_weight():
    regime_overlay = load_module("regime_overlay")
    dates = pd.date_range("2026-01-31", periods=5, freq="ME")
    overlay = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00], index=dates, name="dar4020")
    recession_probability = pd.Series([0.10, 0.20, 0.40, 0.60, 0.80], index=dates, name="p_12m")

    combined = regime_overlay.apply_regime_overlay(
        overlay,
        recession_probability,
        low_threshold=0.20,
        high_threshold=0.60,
        min_weight=0.50,
        max_weight=1.50,
    )

    assert np.isclose(combined.loc[dates[0], "overlay_weight"], 0.50)
    assert np.isclose(combined.loc[dates[2], "overlay_weight"], 1.00)
    assert np.isclose(combined.loc[dates[4], "overlay_weight"], 1.50)
    assert np.isclose(combined.loc[dates[3], "regime_scaled_overlay"], 0.03 * 1.50)


def test_sell_signals_compute_position_exit_rules():
    sell_signals = load_module("sell_signals")
    dates = pd.date_range("2026-01-01", periods=8, freq="D")
    prices = pd.DataFrame(
        {
            "close": [100, 105, 121, 125, 120, 104, 102, 101],
            "volume": [100, 100, 100, 100, 100, 250, 100, 100],
        },
        index=dates,
    )

    signals = sell_signals.compute_sell_signals(
        prices,
        buy_price=100,
        rsi_window=3,
        ma_window=3,
        volume_multiplier=1.5,
        trailing_stop_pct=0.15,
    )
    first = sell_signals.first_trigger(signals)

    assert signals.loc[dates[2], "profit_target"]
    assert signals.loc[dates[5], "ma_volume_violation"]
    assert signals.loc[dates[5], "trailing_stop"]
    assert first["signal"] == "profit_target"
    assert first["date"] == dates[2]


if __name__ == "__main__":
    tests = [
        test_trend_following_uses_lookback_skipping_most_recent_month,
        test_trend_following_supports_equal_vol_weighting,
        test_dar4020_can_vol_target_factors_before_weighting_and_returns,
        test_dar4020_vol_target_supports_shorter_warmup_min_periods,
        test_dar4020_leg_count_mode_can_match_original_dar_terciles,
        test_dar4020_rebalances_when_current_factor_return_is_missing,
        test_drawdown_events_identify_start_trough_recovery_and_return,
        test_overlay_combines_benchmark_overlay_costs_and_realized_vol_target,
        test_overlay_can_scale_combined_contribution_after_blending,
        test_regime_overlay_maps_recession_probability_to_overlay_weight,
        test_sell_signals_compute_position_exit_rules,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
