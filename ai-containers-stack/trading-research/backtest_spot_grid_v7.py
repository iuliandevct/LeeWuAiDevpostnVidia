"""Analysis-only ten-slot SOL spot grid with microstructure/trend filters."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    capital: float = 500.0
    slots: int = 50
    slot_notional: float = 10.0
    maker_fee: float = 0.00075  # account rate after enabled BNB discount
    taker_fee: float = 0.0007125
    target: float = 0.005
    stop: float | None = 0.003
    trailing_distance: float = 0.002
    grid_step: float = 0.0035
    min_imbalance: float = 0.08
    max_spread: float = 0.00025
    min_atr_pct: float = 0.00035
    min_flow_acceleration: float = 1.05
    min_rsi: float = 0.0
    max_rsi: float = 100.0
    require_above_vwap: bool = True
    min_vwap_slope_5m: float = 0.0
    max_bollinger_z: float = 0.5
    min_volume_ratio: float = 0.8
    entry_spacing_seconds: int = 30


def rows(path: Path) -> list[dict]:
    with path.open() as handle:
        result = [json.loads(line) for line in handle if line.strip()]
    if result and "price" in result[0]:
        result = [x for x in result if float(x.get("price", 0)) > 0 and float(x.get("amount", 0)) > 0]
    return result


def minute_features(trades: list[dict]) -> dict[int, dict]:
    bars: dict[int, dict] = {}
    for trade in trades:
        minute = int(trade["timestamp"]) // 60_000
        price, amount = float(trade["price"]), float(trade["amount"])
        bar = bars.setdefault(minute, {"o": price, "h": price, "l": price, "c": price,
                                       "buy": 0.0, "sell": 0.0, "volume": 0.0, "pv": 0.0})
        bar["h"], bar["l"], bar["c"] = max(bar["h"], price), min(bar["l"], price), price
        bar[trade["side"]] += amount
        bar["volume"] += amount
        bar["pv"] += price * amount
    ema20 = ema50 = None
    atr_window: deque[float] = deque(maxlen=14)
    close_window: deque[float] = deque(maxlen=6)
    changes: deque[float] = deque(maxlen=14)
    vwap_window: deque[tuple[float, float]] = deque(maxlen=20)
    indicator_closes: deque[float] = deque(maxlen=20)
    indicator_volumes: deque[float] = deque(maxlen=20)
    vwap_history: deque[float] = deque(maxlen=6)
    previous_close = None
    output = {}
    for minute in sorted(bars):
        bar = bars[minute]
        close = bar["c"]
        if previous_close is not None:
            changes.append(close - previous_close)
        vwap_window.append((bar["pv"], bar["volume"]))
        indicator_closes.append(close)
        indicator_volumes.append(bar["volume"])
        ema20 = close if ema20 is None else (2 / 21) * close + (19 / 21) * ema20
        ema50 = close if ema50 is None else (2 / 51) * close + (49 / 51) * ema50
        tr = bar["h"] - bar["l"] if previous_close is None else max(
            bar["h"] - bar["l"], abs(bar["h"] - previous_close), abs(bar["l"] - previous_close))
        atr_window.append(tr)
        close_window.append(close)
        momentum = close / close_window[0] - 1 if len(close_window) == 6 else 0.0
        total_flow = bar["buy"] + bar["sell"]
        gains = sum(max(change, 0) for change in changes)
        losses = sum(max(-change, 0) for change in changes)
        rsi = 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)
        vwap_volume = sum(item[1] for item in vwap_window)
        vwap = sum(item[0] for item in vwap_window) / vwap_volume if vwap_volume else close
        vwap_history.append(vwap)
        vwap_slope = vwap / vwap_history[0] - 1 if len(vwap_history) == 6 else 0.0
        close_mean = sum(indicator_closes) / len(indicator_closes)
        close_variance = sum((value - close_mean) ** 2 for value in indicator_closes) / len(indicator_closes)
        close_std = close_variance ** 0.5
        bollinger_z = (close - close_mean) / close_std if close_std else 0.0
        mean_volume = sum(indicator_volumes) / len(indicator_volumes)
        volume_ratio = bar["volume"] / mean_volume if mean_volume else 1.0
        output[minute] = {"ema20": ema20, "ema50": ema50, "momentum5": momentum,
                          "atr_pct": (sum(atr_window) / len(atr_window)) / close,
                          "buy_ratio": bar["buy"] / total_flow if total_flow else 0.5,
                          "close": close, "vwap20": vwap, "rsi14": rsi,
                          "vwap_slope_5m": vwap_slope, "bollinger_z": bollinger_z,
                          "volume_ratio": volume_ratio}
        previous_close = close
    return output


def simulate(depth: list[dict], trades: list[dict], cfg: Settings) -> dict:
    features = minute_features(trades)
    books = iter(depth)
    current_book = next(books)
    next_book = next(books, None)
    positions: list[dict] = []
    completed: list[dict] = []
    last_entry = 0
    recent_buys: deque[tuple[int, float]] = deque()
    prior_buys: deque[tuple[int, float]] = deque()
    recent_buy = prior_buy = 0.0
    last_price = float(current_book["ask"])

    for trade in trades:
        now, price = int(trade["timestamp"]), float(trade["price"])
        last_price = price
        while next_book and int(next_book["timestamp"]) <= now:
            current_book, next_book = next_book, next(books, None)

        while recent_buys and recent_buys[0][0] < now - 30_000:
            moved = recent_buys.popleft()
            recent_buy -= moved[1]
            prior_buys.append(moved)
            prior_buy += moved[1]
        while prior_buys and prior_buys[0][0] < now - 60_000:
            prior_buy -= prior_buys.popleft()[1]
        if trade["side"] == "buy":
            amount = float(trade["amount"])
            recent_buys.append((now, amount))
            recent_buy += amount
        acceleration = recent_buy / prior_buy if prior_buy > 0 else 0.0

        survivors = []
        for position in positions:
            position["high"] = max(position["high"], price)
            if position["high"] >= position["target"]:
                position["trailing_stop"] = max(position.get("trailing_stop", 0.0),
                                                position["high"] * (1 - cfg.trailing_distance))
            reason = None
            if cfg.stop is not None and price <= position["stop_price"]:
                reason = "stop"
            elif position.get("trailing_stop") and price <= position["trailing_stop"]:
                reason = "trailing"
            if reason:
                gross = cfg.slot_notional * (price / position["entry"] - 1)
                fees = cfg.slot_notional * (cfg.maker_fee + cfg.taker_fee)
                completed.append({"reason": reason, "net": gross - fees})
            else:
                survivors.append(position)
        positions = survivors

        if len(positions) >= cfg.slots or now - last_entry < cfg.entry_spacing_seconds * 1000:
            continue
        # Only the previous fully closed minute is observable at decision time.
        f = features.get(now // 60_000 - 1)
        if not f or f["ema20"] <= f["ema50"] or f["momentum5"] <= 0:
            continue
        if f["atr_pct"] < cfg.min_atr_pct or f["buy_ratio"] <= 0.5 or acceleration < cfg.min_flow_acceleration:
            continue
        if not cfg.min_rsi <= f["rsi14"] <= cfg.max_rsi:
            continue
        if cfg.require_above_vwap and f["close"] < f["vwap20"]:
            continue
        if f["vwap_slope_5m"] < cfg.min_vwap_slope_5m:
            continue
        if f["bollinger_z"] > cfg.max_bollinger_z or f["volume_ratio"] < cfg.min_volume_ratio:
            continue
        bid, ask = float(current_book["bid"]), float(current_book["ask"])
        if (ask - bid) / bid > cfg.max_spread or float(current_book["imbalance_5"]) < cfg.min_imbalance:
            continue
        # A classic descending grid: never consume another slot in the same
        # price area. ATR widens the spacing automatically in volatile periods.
        effective_step = max(cfg.grid_step, f["atr_pct"] * 0.75)
        if positions and bid > min(p["entry"] for p in positions) * (1 - effective_step):
            continue
        # Passive buy requires a recorded aggressive sell at or through our bid.
        if trade["side"] != "sell" or price > bid:
            continue
        positions.append({"entry": bid, "target": bid * (1 + cfg.target), "high": bid,
                          "stop_price": bid * (1 - cfg.stop) if cfg.stop is not None else 0.0})
        last_entry = now

    realized = sum(x["net"] for x in completed)
    unrealized = sum(cfg.slot_notional * (last_price / p["entry"] - 1) - cfg.slot_notional * cfg.maker_fee
                     for p in positions)
    fees = len(completed) * cfg.slot_notional * (cfg.maker_fee + cfg.taker_fee) + len(positions) * cfg.slot_notional * cfg.maker_fee
    return {"settings": asdict(cfg), "completed_cycles": len(completed), "open_slots": len(positions),
            "targets": sum(x["reason"] == "trailing" for x in completed),
            "stops": sum(x["reason"] == "stop" for x in completed), "realized_net": realized,
            "unrealized_net": unrealized, "mark_to_market_net": realized + unrealized,
            "ending_equity": cfg.capital + realized + unrealized, "fees_included": fees,
            "final_price": last_price,
            "average_open_entry": (sum(p["entry"] for p in positions) / len(positions)) if positions else None,
            "average_open_target": (sum(p["target"] for p in positions) / len(positions)) if positions else None}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--depth", type=Path, default=Path("artifacts/depth/solusdt.jsonl"))
    p.add_argument("--trades", type=Path, default=Path("artifacts/depth/solusdt-aggtrades.jsonl"))
    p.add_argument("--output", type=Path, default=Path("artifacts/spot_grid_v7/summary.json"))
    args = p.parse_args()
    depth, trades = rows(args.depth), rows(args.trades)
    base = dict(target=0.005, grid_step=0.002, min_imbalance=0.12,
                min_rsi=0.0, max_rsi=100.0, require_above_vwap=True,
                min_vwap_slope_5m=0.0001, max_bollinger_z=0.3,
                min_volume_ratio=1.0, min_flow_acceleration=1.20,
                min_atr_pct=0.00035)
    variants = {
        "very_high_confidence": {},
    }
    candidates = []
    for label, changes in variants.items():
        config = {**base, **changes}
        result = simulate(depth, trades, Settings(**config))
        result["ablation"] = label
        candidates.append(result)
    active = [candidate for candidate in candidates
              if candidate["completed_cycles"] + candidate["open_slots"] > 0]
    payload = {"suite": "spot_grid_v7", "mode": "analysis-only",
               "warning": "SOLUSDT stream is a proxy; collect SOLUSDC spot before deployment",
               "data": {"depth_rows": len(depth), "trade_rows": len(trades),
                        "start": depth[0]["timestamp"], "end": depth[-1]["timestamp"]},
               "inactive_candidate_count": len(candidates) - len(active),
               "candidates": sorted(active, key=lambda x: x["mark_to_market_net"], reverse=True),
               "guardrails": {"may_place_orders": False}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["candidates"][:5], indent=2))


if __name__ == "__main__":
    main()
