"""
NEXUS Regime Detection — Stage 3 of the 7-stage pipeline.

Classifies market regime using free APIs (no key required):
TRENDING_UP / TRENDING_DOWN / RANGING / RISK_OFF

Data sources:
- Fear & Greed: alternative.me (free, no key)
- Global Metrics: CoinGecko (free, no key)
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Regime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    RISK_OFF = "risk_off"


@dataclass
class RegimeResult:
    regime: Regime
    confidence: float  # 0.0 - 1.0
    fear_greed: int
    btc_dominance: float
    total_mc_change_24h: float
    reasoning: str


def detect_regime() -> RegimeResult:
    """
    Multi-factor regime detection using free APIs (no key required).

    Layers:
    1. Fear & Greed (alternative.me)
    2. Global Metrics (CoinGecko)
    3. BTC Dominance
    4. Market Cap 24h change

    Returns RegimeResult with regime classification and confidence.
    """
    import requests as _req

    fng_value = 50
    btc_dom = 50.0
    mc_change = 0.0

    # Layer 1: Fear & Greed (alternative.me)
    try:
        fng = _req.get(
            "https://api.alternative.me/fng/?limit=1", timeout=10
        ).json()
        fng_value = int(fng["data"][0]["value"])
    except Exception:
        pass

    # Layer 2-4: CoinGecko Global
    try:
        cg = _req.get(
            "https://api.coingecko.com/api/v3/global", timeout=10
        ).json()
        btc_dom = float(cg["data"]["market_cap_percentage"]["btc"])
        mc_change = float(cg["data"]["market_cap_change_percentage_24h_usd"])
    except Exception:
        pass

    # Decision matrix
    if fng_value < 25 and mc_change < -5:
        regime = Regime.RISK_OFF
        confidence = 0.85
        reasoning = (
            f"F&G={fng_value} (extreme fear) + MC {mc_change:.1f}% - risk-off"
        )
    elif fng_value > 65 and mc_change > 2:
        regime = Regime.TRENDING_UP
        confidence = 0.70
        reasoning = (
            f"F&G={fng_value} (greed) + MC +{mc_change:.1f}% - trending up"
        )
    elif fng_value < 35 and mc_change < -2:
        regime = Regime.TRENDING_DOWN
        confidence = 0.65
        reasoning = (
            f"F&G={fng_value} (fear) + MC {mc_change:.1f}% - trending down"
        )
    else:
        regime = Regime.RANGING
        confidence = 0.55
        reasoning = (
            f"F&G={fng_value} + MC {mc_change:.1f}% - ranging"
        )

    return RegimeResult(
        regime=regime,
        confidence=confidence,
        fear_greed=fng_value,
        btc_dominance=btc_dom,
        total_mc_change_24h=mc_change,
        reasoning=reasoning,
    )


def _strategy_gates(regime: Regime, fng: int) -> list:
    """Return active strategy gates based on regime."""
    gates = []
    if regime == Regime.RANGING:
        gates.append(("SFP", "half-size (ranging gate)"))
        gates.append(("Trendline 3rd Touch", "normal"))
        crisis = "ACTIVE" if fng < 25 else "BLOCKED (F&G > 25)"
        gates.append(("Crisis Rebound", crisis))
        gates.append(("Range Reversal", "ACTIVE"))
    elif regime == Regime.TRENDING_UP:
        gates.append(("Trendline 3rd Touch", "full-size"))
        gates.append(("SFP", "normal"))
        gates.append(("Crisis Rebound", "BLOCKED (F&G > 25)"))
        gates.append(("Range Reversal", "BLOCKED (not ranging)"))
    elif regime == Regime.TRENDING_DOWN:
        gates.append(("Trendline 3rd Touch", "half-size"))
        gates.append(("SFP", "BLOCKED (trending down)"))
        gates.append(("Crisis Rebound", "monitoring (F&G check)"))
        gates.append(("Range Reversal", "BLOCKED (not ranging)"))
    elif regime == Regime.RISK_OFF:
        gates.append(("ALL", "BLOCKED - RISK_OFF"))
    return gates


def main():
    """CLI entry point: python -m nexus.regime [--demo]"""
    import sys

    if "--demo" in sys.argv:
        # Demo mode: static data for video recording
        result = RegimeResult(
            regime=Regime.RANGING,
            confidence=0.72,
            fear_greed=34,
            btc_dominance=62.3,
            total_mc_change_24h=-1.2,
            reasoning=(
                "F&G=34 (fear) + MC -1.2% - ranging. "
                "Low momentum, neutral sentiment, sideways price structure."
            ),
        )
    else:
        result = detect_regime()

    regime_label = {
        Regime.TRENDING_UP: "TRENDING UP",
        Regime.TRENDING_DOWN: "TRENDING DOWN",
        Regime.RANGING: "RANGING",
        Regime.RISK_OFF: "RISK OFF",
    }[result.regime]

    confidence_bar = "X" * int(result.confidence * 10) + "." * (
        10 - int(result.confidence * 10)
    )

    # Box drawing
    W = 42
    top = "=" * (W + 2)
    bot = "=" * (W + 2)
    sep = "-" * (W + 2)

    print(top)
    print(f"  {'NEXUS REGIME DETECTION':^{W}}")
    print(sep)
    print(f"  {'Regime:':<15} {regime_label:<{W-15}}")
    print(
        f"  {'Confidence:':<15} {result.confidence:.0%}  [{confidence_bar}]"
    )
    print(f"  {'Fear & Greed:':<15} {result.fear_greed:<{W-15}}")
    print(f"  {'BTC Dominance:':<15} {result.btc_dominance:.1f}%")
    print(f"  {'24h Change:':<15} {result.total_mc_change_24h:+.1f}%")
    print(sep)

    gates = _strategy_gates(result.regime, result.fear_greed)
    for name, status in gates:
        arrow = ">" if "BLOCKED" not in status else "X"
        print(f"  {arrow} {name:<20} {status}")

    print(bot)
    print(f"\n  Reasoning: {result.reasoning}")


if __name__ == "__main__":
    main()
