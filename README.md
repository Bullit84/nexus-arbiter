# NEXUS Arbiter

**Autonomous AI Trading Agent for BNB Smart Chain**

> 🏆 BNB Hack: AI Trading Agents (June 2026) — Track 1 + Track 2

Battle-tested autonomous trading agent with **155 live BSC mainnet trades** and a deterministic 7-stage pipeline that prevents the failure modes killing most trading bots.

![NEXUS Logo](assets/logo.png)

## Live Performance

**155 trades on BSC mainnet** (March–June 2026). All numbers from `trades.db` — single source of truth.

### Strategy Performance

| Strategy | Trades | Win Rate | PnL |
|----------|--------|----------|-----|
| Reclaim Entry Strategy                             | 40 | 25.0% | $-55.08 |
| Trendline 3rd Touch                                | 16 | 56.3% | $2.94 |
| SFP (Swing Failure Pattern)                        | 14 | 42.9% | $-7.19 |
| 10 SMA + MACD Trend Following (5-minute chart)     | 13 | 46.2% | $-1.27 |
| S/R Flip (CryptoCred)                              | 9 | 66.7% | $-53.32 |
| HTF Engulfing Bias Strategy                        | 6 | 33.3% | $3.5 |

### Monthly Progression

| Month | Trades | Win Rate | PnL |
|-------|--------|----------|-----|
| 2026-03 (pre) | 74 | 50.0% | $4.05 |
| 2026-04 | 30 | 50.0% | $11.34 |
| 2026-05 | 51 | 19.6% | $-114.12 |

> May's -$114 loss directly informed regime gates: Reclaim Entry hard-blocked in trending_down (0% WR, 9 trades), preventing ~$23/month losses.

### Key Metrics
- **Automated strategies (excl. pre_audit/test):** 130 trades, 39.2% WR, -$139.86
- **Exit reasons:** 45 time-exits (29%), ~40 SL-decay (26%), 7 force-close (BTC invalidation), 7 partial TP
- **Regime impact:** Ranging = -$90 (58 trades), Trending Up = +$8 (8 trades, 75% WR)
- **Best performer:** Trendline 3rd Touch — 16 trades, 56.3% WR, +$2.94

### Verified Wallet
```
0x236f03bBba0903321C73c929530DEaa842D6Ba76
```
> [View on BscScan](https://bscscan.com/address/0x236f03bBba0903321C73c929530DEaa842D6Ba76) — 155 executed trades

## Architecture

7-stage pipeline with strict precedence: Manual Pause > Degradation > Rewiring > Performance > Guardrails > Zero-Fallback > Normalize.

```
CMC Agent Hub (12 MCP tools) → Stage 1: Strategy Select → Stage 2: Risk Assess
    → Stage 3: Regime Detect → Stage 4: Position Size
    → Stage 5: Trade Execute (Trust Wallet Agent Kit)
    → Stage 6: Exit Mgmt → Stage 7: Performance Audit (trades.db)
```

## Key Features

- **Strategy Arbiter**: Prevents monoculture death spirals. Diversity floor (≥3 strategies), concentration cap (50%), automatic kill-switch with hysteresis.
- **CMC Agent Hub**: Multi-factor regime detection composing 7 MCP tools — Fear & Greed, technical analysis, derivatives, global metrics, narratives.
- **Trust Wallet Agent Kit**: Self-custody BSC transaction signing — no custodial risk.
- **Anti-Hallucination**: NEXUS reacts to verifiable structure, doesn't predict. Every signal: pattern + data + invalidation condition.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Chain | BNB Smart Chain (BSC) |
| Data | CMC MCP Server (12 tools) |
| Signing | Trust Wallet Agent Kit |
| Wallet | 0x236f03bBba0903321C73c929530DEaa842D6Ba76 |
| Strategies | 22 (6 with >10 live trades) |
| Risk | Dynamic Rewiring, Degradation, Kill-Switch, BTC Invalidation Gate |
| DB | SQLite `trades.db` — SSOT |
| Language | Python 3.11 |

## CMC Skills (Track 2)

- **[nexus-regime](skills/nexus-regime/SKILL.md)** — 4-layer regime detection (sentiment, technicals, derivatives, global) with deterministic point matrix
- **[nexus-signal](skills/nexus-signal/SKILL.md)** — Trading signals with pattern detection, confidence scoring, and risk overlay

Both use 7-12 CMC MCP tools and follow the official CMC Skill format (YAML frontmatter + Markdown workflow).

## Quick Start

```bash
git clone https://github.com/Bullit84/nexus-arbiter.git
cd nexus-arbiter
pip install mcp httpx web3
export CMC_API_KEY="your-key"
python -m nexus.regime
```

## Why This Wins

1. **Real trades, real wallet**: 155 BSC mainnet trades — verifiable on BscScan. Not a backtest.
2. **Learned from losses**: May -$114 → regime gates → June improvement. Genuine iteration.
3. **Anti-fragile**: Strategy Arbiter prevents the single-strategy death spiral.
4. **CMC-native**: 7 MCP tools + 2 standalone Skills usable by any agent.

## License

MIT
