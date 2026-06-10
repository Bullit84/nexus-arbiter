---
name: nexus-signal
description: |
  NEXUS Trading Signal Generation — erzeugt deterministische Trading-Signale aus CMC-Marktdaten 
  und NEXUS-eigenen Strategie-Indikatoren. Kombiniert technische Analyse, On-Chain-Daten und 
  Regime-Kontext für Entry/Exit-Entscheidungen. Backgetestet mit 155 Live-Trades auf BSC.
  Trigger: "trading signal", "entry signal", "should I trade", "nexus signal", "trade setup"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__get_crypto_quotes_latest
  - mcp__cmc-mcp__get_crypto_ohlcv_historical
  - mcp__cmc-mcp__get_crypto_ohlcv_latest
  - mcp__cmc-mcp__get_crypto_marketcap_technical_analysis
  - mcp__cmc-mcp__get_global_crypto_derivatives_metrics
  - mcp__cmc-mcp__search_cryptos
---

# NEXUS Signal Generation

Generates deterministic trading signals using CMC data fused with NEXUS strategy indicators.
Signals include: asset, direction (LONG/SHORT), entry price, stop loss, take profit, confidence, and strategy.

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

NEXUS doesn't predict — it REACTS to verifiable market structure. Every signal must cite:
1. **Which pattern** triggered it (SFP, Reclaim, Trendline, etc.)
2. **Which data point** confirms it (CMC tool + value)
3. **What invalidates it** (exit condition)

No signal without all three. This is NEXUS's edge over LLM-only agents that hallucinate setups.

## Workflow

### Step 1: Watchlist Scan
Call `get_crypto_quotes_latest` for NEXUS watchlist (BTC=1, ETH=1027, BNB=1839, DOT=6636, WBNB on BSC).
Extract for each:
- Price, 1h change %, 24h change %, volume 24h
- **Filter**: Only assets with 24h volume > $100M and 1h change > 1.5% (volatility filter)

### Step 2: Technical Pattern Detection
For each filtered asset, call `get_crypto_marketcap_technical_analysis`:
- Check oscillator summary: buy/sell/neutral count
- Check moving average summary: buy/sell/neutral count
- **Pattern detection (NEXUS strategies):**

**SFP (Swing Failure Pattern):**
- Condition: Oscillator says "sell" (bearish) BUT price bounced off key MA (e.g., 50-period)
- Signal: LONG — entry at current price, SL below recent swing low
- Confidence: 60% base, +10% if MA alignment, -20% if F&G < 30

**Reclaim Entry:**
- Condition: Price crossed ABOVE a recently lost MA level (e.g., reclaimed 20-period)
- Signal: LONG — entry at MA retest, SL below pre-reclaim low
- Regime gate: ONLY in TRENDING_UP or RANGING. HARD BLOCK in TRENDING_DOWN (0% WR in 9 trades)
- Confidence: 55% base, +15% in trending_up, -15% in ranging

**Trendline 3rd Touch:**
- Condition: 3rd touch of a trendline formed by 2 prior swing points
- Signal: LONG at touch, SHORT at resistance touch
- Requires: `get_crypto_ohlcv_historical` (30 days, daily) to identify swing points
- Confidence: 50% base, +20% if volume confirming

**Crisis Rebound (Blood on the Streets):**
- Condition: F&G < 20 AND price > 5% above 24h low AND oscillator says "buy"
- Signal: LONG — contrarian entry, wider SL (2× normal)
- Gate: Only when no active BTC invalidation
- Confidence: 45% base (high risk/high reward, 83.3% WR in live trading)

### Step 3: Derivate Confirmation
Call `get_global_crypto_derivatives_metrics`:
- If OI rising in signal direction → +10% confidence
- If OI rising against signal direction → -15% confidence (positioning disagrees)
- If liquidations recent (24h) in signal direction → +5% (momentum)

### Step 4: Signal Generation
For each valid setup, output a structured signal:

```json
{
  "signal_id": "NEXUS-{timestamp}-{asset}",
  "asset": "BTC",
  "cmc_id": 1,
  "direction": "LONG",
  "strategy": "SFP (Swing Failure Pattern)",
  "entry_price": 71250.00,
  "stop_loss": 69500.00,
  "take_profit": 74500.00,
  "confidence": 0.70,
  "size_multiplier": 0.75,
  "regime": "RANGING",
  "evidence": {
    "pattern": "SFP at 50-MA bounce",
    "oscillator": "sell (7/10 indicators bearish → reversal setup)",
    "ma_alignment": "price below 20-MA but above 50-MA",
    "volume": "24h vol $28.4B, 1h vol increasing",
    "derivatives": "OI +2.3%, shorts liquidated $12M"
  },
  "invalidation": "BTC closes below 69,500 (swing low) on 4h",
  "timestamp": "2026-06-10T12:00:00Z"
}
```

### Step 5: Risk Overlay
Apply NEXUS risk rules:
1. **BTC Invalidation Gate**: If BTC < invalidation_level → ALL signals BLOCKED
2. **Kill-Switch**: If active → ALL signals BLOCKED
3. **Concentration Cap**: Max 50% allocation per strategy
4. **Max Positions**: Hard cap at 5 open positions
5. **Drawdown Guard**: If portfolio drawdown > 15% → size_multiplier × 0.5

## Signal Priority

Sort signals by `confidence × size_multiplier`. Execute top N where N = (5 - current_positions).

## Report Structure

```markdown
# NEXUS Signal Report — {date} {time}

**Regime:** {REGIME} | **F&G:** {FNG} | **BTC:** ${BTC_PRICE}
**Active Positions:** {count}/5 | **Portfolio Drawdown:** {DD}%

## Signals Generated

| # | Asset | Direction | Strategy | Entry | SL | TP | Conf | Size |
|---|-------|-----------|----------|-------|----|----|------|------|
| 1 | {ASSET} | {DIR} | {STRAT} | ${ENTRY} | ${SL} | ${TP} | {CONF}% | {SIZE}x |

## Evidence

### {ASSET} — {STRATEGY}
- **Pattern:** {description}
- **Technical:** {oscillator_summary} / {ma_summary}
- **Volume:** {volume_data}
- **Derivatives:** {oi_change}, {liquidations}
- **Invalidation:** {exit_condition}

## Risk Checks
- [ ] BTC Invalidation: {PASS/FAIL}
- [ ] Kill-Switch: {PASS/FAIL}
- [ ] Concentration: {current_pct}% ≤ 50%
- [ ] Drawdown: {current_dd}% < 15%
```

## Backtest Validation

NEXUS signals validated on 155 live BSC trades (all numbers from trades.db SSOT):
- Reclaim Entry: 40 Trades, 25.0% WR, -$55.08 (0% in trending_down → hard block added June 2026)
- Trendline 3rd Touch: 16 Trades, 56.3% WR, +$2.94 (most consistent performer)
- SFP (Swing Failure Pattern): 14 Trades, 42.9% WR, -$7.19 (expectancy improving with regime gates)
- 10 SMA + MACD: 13 Trades, 46.2% WR, -$1.27
- S/R Flip: 9 Trades, 66.7% WR, -$53.32 (high WR, negative PnL — expectancy-aware deactivation)
- Crisis Rebound: 6 Trades, 83.3% WR, +$5 (highest WR, lowest sample)

**Key Insight:** May 2026 was the learning phase (-$114, 19.6% WR). The regime gates deployed in June directly address the failure patterns discovered: Reclaim Entry hard-blocked in trending_down (saves $22.74/month), S/R Flip deactivated despite 67% WR (negative expectancy -$5.92/trade).
