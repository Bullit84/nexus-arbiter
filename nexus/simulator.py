"""
NEXUS Simulation Runner — Paper trading mode for pre-flight testing.

Usage:
    python -m nexus.simulator                    # Run once with live data
    python -m nexus.simulator --scenario fear    # F&G=15, trending_down
    python -m nexus.simulator --scenario greed   # F&G=75, trending_up
    python -m nexus.simulator --scenario flat    # F&G=50, ranging
    python -m nexus.simulator --loop 10          # Run 10 cycles, 60s apart

Multi-instance:
    terminal 1: python -m nexus.simulator --scenario fear --tag instance_1
    terminal 2: python -m nexus.simulator --scenario greed --tag instance_2
    terminal 3: python -m nexus.simulator --loop 5 --tag instance_3
"""
import json
import os
import sys
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .regime import detect_regime, Regime, RegimeResult
from .regime import _strategy_gates as get_strategy_gates

# ── Config ──────────────────────────────────────────

SIM_DB = Path(__file__).parent.parent / "sim_trades.db"

SCENARIOS = {
    "fear": {
        "fear_greed": 15,
        "btc_dominance": 58.0,
        "mc_change_24h": -3.5,
        "description": "Extreme Fear, weak downtrend — Crisis Rebound should activate"
    },
    "greed": {
        "fear_greed": 75,
        "btc_dominance": 52.0,
        "mc_change_24h": +4.2,
        "description": "Greed, strong uptrend — Trendline 3rd Touch dominates"
    },
    "flat": {
        "fear_greed": 50,
        "btc_dominance": 55.0,
        "mc_change_24h": +0.3,
        "description": "Neutral, ranging — SFP + Range Reversal active"
    },
    "crash": {
        "fear_greed": 8,
        "btc_dominance": 65.0,
        "mc_change_24h": -12.0,
        "description": "RISK_OFF — Everything blocked, BTC invalidation"
    },
}

ACTIVE_STRATEGIES = [
    {"name": "Trendline 3rd Touch", "weight": 0.40, "size": 20.0,
     "description": "Looks for 3rd touch of trendline in direction of trend"},
    {"name": "SFP (Swing Failure Pattern)", "weight": 0.30, "size": 15.0,
     "description": "False breakout pattern — fade the fakeout"},
    {"name": "Crisis Rebound", "weight": 0.20, "size": 15.0,
     "description": "Buy when blood on the streets — F&G < 25 only"},
    {"name": "Range Reversal", "weight": 0.10, "size": 12.5,
     "description": "BOS + Retest at range boundaries"},
]

# ── Database ────────────────────────────────────────

def init_db():
    db = sqlite3.connect(str(SIM_DB))
    db.execute("""
        CREATE TABLE IF NOT EXISTS sim_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scenario TEXT,
            tag TEXT,
            regime TEXT,
            confidence REAL,
            fear_greed INTEGER,
            btc_dominance REAL,
            mc_change_24h REAL,
            active_strategies TEXT,
            blocked_strategies TEXT,
            reasoning TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS sim_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            timestamp TEXT NOT NULL,
            strategy TEXT,
            direction TEXT,
            asset TEXT,
            size_usdt REAL,
            regime TEXT,
            status TEXT,
            FOREIGN KEY (run_id) REFERENCES sim_runs(id)
        )
    """)
    db.commit()
    return db

# ── Simulation ──────────────────────────────────────

def run_simulation(scenario: Optional[str] = None, tag: str = "default") -> dict:
    """Run one full pipeline cycle. Returns summary dict."""

    # Get market data
    if scenario and scenario in SCENARIOS:
        s = SCENARIOS[scenario]
        result = RegimeResult(
            regime=Regime.RANGING,  # Will be overridden by decision matrix
            confidence=0.0,
            fear_greed=s["fear_greed"],
            btc_dominance=s["btc_dominance"],
            total_mc_change_24h=s["mc_change_24h"],
            reasoning="",
        )
        # Apply decision matrix manually (matching regime.py logic)
        fng = s["fear_greed"]
        mc = s["mc_change_24h"]
        if fng < 25 and mc < -5:
            result.regime = Regime.RISK_OFF
            result.confidence = 0.85
            result.reasoning = f"[SIM:{scenario}] F&G={fng} (extreme fear) + MC {mc}% — risk-off"
        elif fng > 65 and mc > 2:
            result.regime = Regime.TRENDING_UP
            result.confidence = 0.70
            result.reasoning = f"[SIM:{scenario}] F&G={fng} (greed) + MC +{mc}% — trending up"
        elif fng < 35 and mc < -2:
            result.regime = Regime.TRENDING_DOWN
            result.confidence = 0.65
            result.reasoning = f"[SIM:{scenario}] F&G={fng} (fear) + MC {mc}% — trending down"
        else:
            result.regime = Regime.RANGING
            result.confidence = 0.55
            result.reasoning = f"[SIM:{scenario}] F&G={fng} + MC {mc}% — ranging"
    else:
        # Live data
        try:
            result = detect_regime()
            tag = "live"
        except Exception as e:
            print(f"⚠  Live detection failed: {e}")
            print("   Using flat scenario as fallback")
            return run_simulation(scenario="flat", tag="fallback")

    regime = result.regime
    gates = get_strategy_gates(regime, result.fear_greed)

    # Determine which strategies are active
    active = []
    blocked = []
    for name, status in gates:
        if "BLOCKED" in status:
            blocked.append(f"{name} ({status})")
        else:
            active.append(f"{name} ({status})")

    # Simulate trade decisions
    sim_trades = []
    for strat in ACTIVE_STRATEGIES:
        gate_match = [g for g in gates if g[0] in strat["name"] or strat["name"] in g[0]]
        if gate_match:
            status = gate_match[0][1]
            if "BLOCKED" in status:
                continue

        # Simulate: 40% chance of a signal in this cycle
        import random
        if random.random() < 0.4:
            size_mult = 1.0
            if "half-size" in (gate_match[0][1] if gate_match else ""):
                size_mult = 0.5
            elif "full-size" in (gate_match[0][1] if gate_match else ""):
                size_mult = 1.0

            sim_trades.append({
                "strategy": strat["name"],
                "direction": "LONG",
                "asset": "BNB",
                "size_usdt": round(strat["size"] * size_mult, 2),
                "regime": regime.value,
                "status": "SIMULATED"
            })

    # Save to DB
    db = init_db()
    cursor = db.execute(
        "INSERT INTO sim_runs (timestamp, scenario, tag, regime, confidence, "
        "fear_greed, btc_dominance, mc_change_24h, active_strategies, "
        "blocked_strategies, reasoning) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), scenario or "live", tag,
         regime.value, result.confidence, result.fear_greed,
         result.btc_dominance, result.total_mc_change_24h,
         json.dumps(active), json.dumps(blocked), result.reasoning)
    )
    run_id = cursor.lastrowid

    for trade in sim_trades:
        db.execute(
            "INSERT INTO sim_trades (run_id, timestamp, strategy, direction, "
            "asset, size_usdt, regime, status) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, datetime.now(timezone.utc).isoformat(), trade["strategy"],
             trade["direction"], trade["asset"], trade["size_usdt"],
             trade["regime"], trade["status"])
        )
    db.commit()

    return {
        "regime": regime.value,
        "confidence": result.confidence,
        "fear_greed": result.fear_greed,
        "btc_dominance": result.btc_dominance,
        "active": active,
        "blocked": blocked,
        "trades": sim_trades,
        "reasoning": result.reasoning,
        "run_id": run_id,
    }

# ── Display ─────────────────────────────────────────

def print_result(r: dict, scenario: str, tag: str):
    W = 50
    print(f"\n{'='*W}")
    print(f"  NEXUS SIMULATOR  |  Scenario: {scenario or 'live'}  |  Tag: {tag}")
    print(f"{'='*W}")
    print(f"  Regime:      {r['regime'].upper():<20}  Confidence: {r['confidence']:.0%}")
    btc_dom = r.get('btc_dominance', 0)
    btc_str = f"{btc_dom:.1f}%" if isinstance(btc_dom, (int, float)) else "?"
    print(f"  Fear & Greed: {r['fear_greed']:<5}  BTC Dom: {btc_str}")
    print(f"  {'─'*W}")

    if r['active']:
        print(f"  ✅ ACTIVE ({len(r['active'])}):")
        for s in r['active']:
            print(f"     → {s}")
    else:
        print(f"  ✅ ACTIVE: NONE — all strategies blocked")

    if r['blocked']:
        print(f"  ✕ BLOCKED ({len(r['blocked'])}):")
        for s in r['blocked']:
            print(f"     ✕ {s}")

    if r['trades']:
        print(f"  {'─'*W}")
        print(f"  📊 SIMULATED TRADES ({len(r['trades'])}):")
        for t in r['trades']:
            print(f"     {t['strategy']:<25} {t['direction']:<6} {t['asset']:<6} ${t['size_usdt']:.2f}")
    else:
        print(f"  📊 SIMULATED TRADES: 0 (no signals)")

    print(f"  {'─'*W}")
    print(f"  💡 {r['reasoning'][:80]}")
    print(f"  DB run_id: {r['run_id']}")
    print(f"{'='*W}\n")

# ── Main ────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="NEXUS Simulator")
    p.add_argument("--scenario", choices=list(SCENARIOS.keys()),
                   help="Market scenario to simulate")
    p.add_argument("--tag", default="default", help="Instance tag")
    p.add_argument("--loop", type=int, default=1,
                   help="Number of cycles (interval: 5s sim, 60s live)")
    p.add_argument("--all-scenarios", action="store_true",
                   help="Run all scenarios once")
    args = p.parse_args()

    init_db()

    if args.all_scenarios:
        for name in SCENARIOS:
            r = run_simulation(scenario=name, tag=args.tag)
            print_result(r, name, args.tag)
        return

    for i in range(args.loop):
        r = run_simulation(scenario=args.scenario, tag=args.tag)
        print_result(r, args.scenario or "live", args.tag)
        if args.loop > 1 and i < args.loop - 1:
            delay = 5 if args.scenario else 60
            print(f"  ⏳ Next cycle in {delay}s... (Ctrl+C to stop)")
            time.sleep(delay)

if __name__ == "__main__":
    main()
