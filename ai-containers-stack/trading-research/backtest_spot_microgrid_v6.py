"""Analysis-only SOL spot micro-grid using recorded top-of-book and trades.

The recorded SOLUSDT stream is a microstructure proxy until an equivalent
SOLUSDC spot capture is available.  Fills require an actual aggressing trade
through the passive limit and a configurable queue haircut.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random


@dataclass(frozen=True)
class Settings:
    capital: float = 100.0
    order_notional: float = 20.0
    maker_fee: float = 0.00075
    target: float = 0.0030
    stop: float = 0.0045
    max_hold_seconds: int = 900
    cooldown_seconds: int = 20
    min_imbalance: float = 0.05
    max_spread: float = 0.00025
    queue_fill_probability: float = 0.35


def load(path: Path) -> list[dict]:
    with path.open() as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    # The recorder emits zero-valued heartbeat/error rows; they are not trades.
    if rows and "price" in rows[0]:
        rows = [row for row in rows if float(row.get("price", 0)) > 0 and float(row.get("amount", 0)) > 0]
    return rows


def simulate(depth: list[dict], trades: list[dict], cfg: Settings) -> dict:
    rng = Random(42)
    trade_i = 0
    next_entry = 0
    results = []
    for book in depth:
        now = int(book["timestamp"])
        if now < next_entry or float(book["imbalance_5"]) < cfg.min_imbalance:
            continue
        bid, ask = float(book["bid"]), float(book["ask"])
        if (ask - bid) / bid > cfg.max_spread:
            continue
        while trade_i < len(trades) and int(trades[trade_i]["timestamp"]) < now:
            trade_i += 1
        entry_i = trade_i
        deadline = now + cfg.max_hold_seconds * 1000
        while entry_i < len(trades) and int(trades[entry_i]["timestamp"]) <= deadline:
            tick = trades[entry_i]
            if tick["side"] == "sell" and float(tick["price"]) <= bid:
                break
            entry_i += 1
        else:
            continue
        if rng.random() > cfg.queue_fill_probability:
            continue
        target = bid * (1 + cfg.target)
        stop = bid * (1 - cfg.stop)
        exit_price, reason, exit_ts = None, "timeout", deadline
        j = entry_i + 1
        last_price = bid
        while j < len(trades) and int(trades[j]["timestamp"]) <= deadline:
            tick = trades[j]
            last_price = float(tick["price"])
            if last_price <= stop:
                exit_price, reason, exit_ts = last_price, "stop", int(tick["timestamp"])
                break
            if tick["side"] == "buy" and last_price >= target:
                if rng.random() <= cfg.queue_fill_probability:
                    exit_price, reason, exit_ts = target, "target", int(tick["timestamp"])
                    break
            j += 1
        if exit_price is None:
            exit_price = last_price
        gross = cfg.order_notional * (exit_price / bid - 1)
        fees = cfg.order_notional * cfg.maker_fee * (2 if reason == "target" else 1)
        # A stop/timeout is conservatively charged as a taker exit at the same rate.
        if reason != "target":
            fees += cfg.order_notional * cfg.maker_fee
        results.append({"entry_ts": int(trades[entry_i]["timestamp"]), "exit_ts": exit_ts,
                        "reason": reason, "gross": gross, "fees": fees, "net": gross - fees})
        next_entry = exit_ts + cfg.cooldown_seconds * 1000
    pnls = [x["net"] for x in results]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    return {
        "settings": asdict(cfg), "trades": len(results), "net_pnl": sum(pnls),
        "ending_cash": cfg.capital + sum(pnls),
        "win_rate": len(wins) / len(pnls) if pnls else 0,
        "average_trade": sum(pnls) / len(pnls) if pnls else 0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "fees": sum(x["fees"] for x in results),
        "targets": sum(x["reason"] == "target" for x in results),
        "stops": sum(x["reason"] == "stop" for x in results),
        "timeouts": sum(x["reason"] == "timeout" for x in results),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--depth", type=Path, default=Path("artifacts/depth/solusdt.jsonl"))
    p.add_argument("--trades", type=Path, default=Path("artifacts/depth/solusdt-aggtrades.jsonl"))
    p.add_argument("--output", type=Path, default=Path("artifacts/spot_microgrid_v6/summary.json"))
    args = p.parse_args()
    depth, trades = load(args.depth), load(args.trades)
    candidates = []
    for target in (0.0045, 0.0055, 0.0070, 0.0085, 0.0100):
        for imbalance in (0.03, 0.05, 0.08, 0.12):
            cfg = Settings(target=target, min_imbalance=imbalance)
            candidates.append(simulate(depth, trades, cfg))
    payload = {
        "suite": "spot_microgrid_v6", "mode": "analysis-only",
        "warning": "SOLUSDT recorded stream is only a proxy for SOLUSDC spot",
        "data": {"depth_rows": len(depth), "trade_rows": len(trades),
                 "start": depth[0]["timestamp"], "end": depth[-1]["timestamp"]},
        "candidates": sorted(candidates, key=lambda x: x["net_pnl"], reverse=True),
        "guardrails": {"may_place_orders": False},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["candidates"][:5], indent=2))


if __name__ == "__main__":
    main()
