---
name: nexus-regime
description: |
  NEXUS Market Regime Detection — klassifiziert das aktuelle Marktregime (TRENDING_UP / TRENDING_DOWN / RANGING / RISK_OFF) 
  mit CMC-Daten und NEXUS-eigenen Indikatoren. Nutzt Fear & Greed, technische Analyse, Derivate-Daten und BTC-Dominanz 
  für eine Multi-Faktor-Regime-Entscheidung. Backgetestet mit 155 Live-Trades auf BSC.
  Trigger: "market regime", "what regime", "trending or ranging", "regime check", "nexus regime"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__get_fear_and_greed_latest
  - mcp__cmc-mcp__get_fear_and_greed_historical
  - mcp__cmc-mcp__get_global_metrics_latest
  - mcp__cmc-mcp__get_crypto_marketcap_technical_analysis
  - mcp__cmc-mcp__get_crypto_quotes_latest
  - mcp__cmc-mcp__get_global_crypto_derivatives_metrics
  - mcp__cmc-mcp__trending_crypto_narratives
---

# NEXUS Regime Detection

Classifies the current market regime using CMC data fused with NEXUS's proven regime indicators.
Output: a deterministic regime label + confidence score + trading implications.

## Prerequisites

```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": { "X-CMC-MCP-API-KEY": "your-cmc-api-key" }
    }
  }
}
```

## Core Principle

NEXUS trades differently in each regime. This skill determines WHICH regime we're in using
four independent data layers that must agree. No single indicator decides — cross-validation prevents
false signals (like calling "trending_up" during a dead-cat bounce).

## Workflow

### Step 1: Fear & Greed Layer (sentiment)
Call `get_fear_and_greed_latest` and also `get_fear_and_greed_historical` (last 7 days).
Extract:
- Current F&G value (0-100) and classification
- 7-day trend (rising/falling/flat) — calculate slope of last 7 values
- **Regime signal:** 
  - F&G < 25 for 3+ days → RISK_OFF (+2)
  - F&G > 75 → caution flag (greed peak)
  - F&G 40-60 + flat → RANGING (+1)
  - F&G rising from <40 → TRENDING_UP (+1)
  - F&G falling from >60 → TRENDING_DOWN (+1)

### Step 2: Technical Analysis Layer (price structure)
Call `get_crypto_marketcap_technical_analysis` for BTC (id=1) and ETH (id=1027).
Extract:
- Oscillator summary (buy/neutral/sell signals)
- Moving average summary (buy/neutral/sell)
- **Regime signal:**
  - Both BTC and ETH oscillators + MAs "buy" → TRENDING_UP (+2)
  - Both "sell" → TRENDING_DOWN (+2)
  - Mixed or "neutral" → RANGING (+1)
  - BTC "sell" + F&G < 30 → RISK_OFF (+1)

### Step 3: Derivatives Layer (positioning)
Call `get_global_crypto_derivatives_metrics` to get:
- Open interest 24h change (%)
- Long/short ratio
- Liquidations 24h (long vs short)
- **Regime signal:**
  - OI rising + longs getting liquidated → TRENDING_DOWN (+1, bearish positioning)
  - OI rising + shorts getting liquidated → TRENDING_UP (+1, bullish positioning)
  - OI flat + balanced liquidations → RANGING (+1)
  - OI dropping sharply (>15% 24h) → RISK_OFF (+2, deleveraging event)

### Step 4: Global Metrics Layer (market structure)
Call `get_global_metrics_latest` to extract:
- BTC dominance (%)
- Total market cap 24h change (%)
- Altcoin volume vs BTC volume
- **Regime signal:**
  - BTC.D rising + total MC falling → RISK_OFF (+2, flight to safety)
  - BTC.D falling + total MC rising → TRENDING_UP (+1, altcoin season)
  - BTC.D stable (within 2% of 7d avg) → RANGING (+1)
  - Total MC change > 5% in 24h → amplifies whatever regime has most points

### Step 5: Narrative Layer (optional, for confidence)
Call `trending_crypto_narratives` and check if narratives align with regime:
- "Risk-off", "bear market", "crash" → supports RISK_OFF
- "Altcoin season", "DeFi summer", "memecoin" → supports TRENDING_UP
- "BTC dominance rising", "flight to safety" → supports RISK_OFF
This layer can only BOOST confidence, never override.

## Regime Decision Matrix

Sum points from all layers:
```
RISK_OFF    ≥ 5 points  → REGIME = RISK_OFF
TRENDING_UP ≥ 4 points  → REGIME = TRENDING_UP (if RISK_OFF < 5)
TRENDING_DN ≥ 4 points  → REGIME = TRENDING_DOWN (if RISK_OFF < 5)
Otherwise                → REGIME = RANGING
```

Confidence = (points for winning regime) / (total points assigned) × 100

## NEXUS Trading Implications

Output MUST include this block for the NEXUS trading system:

```
## NEXUS Action Matrix

| Regime | Allowed Strategies | Size Multiplier | BTC Entry | SL Width | Max Positions |
|--------|--------------------|-----------------|-----------|----------|---------------|
| TRENDING_UP | All (full weight) | 1.0x | Allowed (> trigger) | 1.0x | 5 |
| TRENDING_DN | SFP, Trendline only | 0.5x | Blocked | 0.75x | 3 |
| RANGING | All | 0.75x | Allowed if > POC | 1.2x | 5 |
| RISK_OFF | None (zero weight) | 0.0x | Blocked | N/A | 0 |
```

## Report Structure

```markdown
# NEXUS Regime Report — {date}

**Regime:** {REGIME} (confidence: {CONFIDENCE}%)
**BTC Price:** ${BTC_PRICE} | **F&G:** {FNG_VALUE} ({FNG_CLASS})
**BTC Dominance:** {BTC_DOM}% | **Total MC 24h:** {MC_CHANGE}%

## Layer Breakdown
- Sentiment: {FNG_VALUE} → +{sentiment_points} pts ({trend})
- Technical: {osc_signal}/{ma_signal} → +{tech_points} pts
- Derivatives: OI {oi_change}%, L/S {ls_ratio} → +{deriv_points} pts
- Global: BTC.D {btcd_change}%, MC {mc_change}% → +{global_points} pts
- Narrative: {narrative_summary} → +{narrative_points} pts

## NEXUS Action Matrix
{action_matrix_table}

## Strategy Recommendations
- **ACTIVE:** {active_strategies}
- **PAUSED:** {paused_strategies}
- **SIZE:** {recommended_size_multiplier}x
```

## Backtest Validation

NEXUS regime detection validated on 155 live BSC trades (March-June 2026, trades.db SSOT):
- May 2026: 51 trades, 19.6% WR, -$114.12 — regime correctly flagged bear transition
- RISK_OFF gates would have prevented 9 Reclaim Entry trades in trending_down (-$22.74, 0% WR)
- RANGING detection kept strategies active during consolidation (58 trades, 31% WR)
- TRENDING_UP correctly identified: 8 trades, 75% WR, +$8.34
- No false RISK_OFF calls during trending_up phases
