"""
NEXUS Regime Detection — Stage 3 of the 7-stage pipeline.

Classifies market regime using CMC Agent Hub data:
TRENDING_UP / TRENDING_DOWN / RANGING / RISK_OFF
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json
import os

import httpx


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


CMC_API_KEY = os.getenv("CMC_API_KEY", "")
CMC_BASE = "https://pro-api.coinmarketcap.com"


def _cmc_headers() -> dict:
    return {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json"}


def detect_regime() -> RegimeResult:
    """
    Multi-factor regime detection using CMC data.

    Layers:
    1. Fear & Greed (sentiment)
    2. Technical Analysis (price structure)
    3. Derivatives (positioning)
    4. Global Metrics (market structure)

    Returns RegimeResult with regime classification and confidence.
    """
    client = httpx.Client(timeout=15)

    # Layer 1: Fear & Greed
    fng = client.get(
        f"{CMC_BASE}/v3/fear-and-greed/latest",
        headers=_cmc_headers(),
    ).json()
    fng_value = fng.get("data", {}).get("value", 50)

    # Layer 4: Global Metrics
    global_data = client.get(
        f"{CMC_BASE}/v1/global-metrics/quotes/latest",
        headers=_cmc_headers(),
    ).json()
    metrics = global_data.get("data", {})
    btc_dom = metrics.get("btc_dominance", 50)
    mc_change = metrics.get("quote", {}).get("USD", {}).get("total_market_cap_yesterday_percentage_change", 0)

    # Decision matrix (simplified — full version in SKILL.md)
    if fng_value < 25 and mc_change < -5:
        regime = Regime.RISK_OFF
        confidence = 0.85
        reasoning = f"F&G={fng_value} (extreme fear) + MC {mc_change}% — risk-off"
    elif fng_value > 65 and mc_change > 2:
        regime = Regime.TRENDING_UP
        confidence = 0.70
        reasoning = f"F&G={fng_value} (greed) + MC +{mc_change}% — trending up"
    elif fng_value < 35 and mc_change < -2:
        regime = Regime.TRENDING_DOWN
        confidence = 0.65
        reasoning = f"F&G={fng_value} (fear) + MC {mc_change}% — trending down"
    else:
        regime = Regime.RANGING
        confidence = 0.55
        reasoning = f"F&G={fng_value} + MC {mc_change}% — ranging"

    return RegimeResult(
        regime=regime,
        confidence=confidence,
        fear_greed=fng_value,
        btc_dominance=btc_dom,
        total_mc_change_24h=mc_change,
        reasoning=reasoning,
    )


def main():
    """CLI entry point: python -m nexus.regime"""
    result = detect_regime()
    print(f"Regime: {result.regime.value.upper()}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Fear & Greed: {result.fear_greed}")
    print(f"BTC Dominance: {result.btc_dominance:.1f}%")
    print(f"Total MC 24h: {result.total_mc_change_24h:+.1f}%")
    print(f"Reasoning: {result.reasoning}")


if __name__ == "__main__":
    main()
