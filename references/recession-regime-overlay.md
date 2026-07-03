# Recession Regime Overlay

Use this when a point-in-time recession probability is available and the user wants to scale defensive exposure by macro risk.

## Role In The Strategy

A recession probability is a regime input. Use it to size, gate, or label defensive overlays. Do not treat it as proof that the whole portfolio should be liquidated.

The supplemental recession model describes a leak-free ensemble signal estimating the probability of a US NBER recession 6 or 12 months ahead, using yield-curve slope, credit spreads, and business-confidence inputs. Its intended use is downstream strategy conditioning.

## Practical Uses

- Increase DAR4020 or trend-following overlay notional when recession probability rises.
- Tilt defensive vs cyclical sleeves when macro risk is elevated.
- Segment backtests into low, medium, and high recession-risk regimes.
- Require confirmation from price trend before making large exposure changes.

## Default Mapping

Use a clipped linear ramp unless the user has a researched sizing rule:

- Probability at or below `low_threshold`: minimum overlay weight.
- Probability at or above `high_threshold`: maximum overlay weight.
- Between the thresholds: interpolate linearly.

Use `scripts/regime_overlay.py` for this mapping.

## No-Lookahead Requirements

- Use only point-in-time probabilities available at the decision date.
- Apply a signal lag when publication timing is uncertain.
- Do not train or calibrate recession thresholds on the full evaluation sample.
- Report false positives separately; curve-driven false alarms can still occur.
