"""Replay the very-high-confidence strategy across the monitored top-50 USDC universe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backtest_spot_grid_v7 import Settings, rows, simulate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("artifacts/top50-spot-depth"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/top50-v8/summary.json"))
    args = parser.parse_args()
    universe_path = args.input / "universe.json"
    universe = json.loads(universe_path.read_text()) if universe_path.exists() else {"symbols": []}
    config = Settings(capital=10.0, slots=1, slot_notional=10.0, target=0.005,
                      stop=0.003, trailing_distance=0.002, min_imbalance=0.12,
                      min_flow_acceleration=1.20, min_volume_ratio=1.0,
                      max_bollinger_z=0.30, min_vwap_slope_5m=0.0001)
    results = []
    for symbol in universe["symbols"]:
        name = symbol.replace("/", "").lower()
        depth_path = args.input / f"{name}.jsonl"
        trade_path = args.input / f"{name}-aggtrades.jsonl"
        if not depth_path.exists() or not trade_path.exists():
            continue
        depth, trades = rows(depth_path), rows(trade_path)
        if len(depth) < 20 or len(trades) < 20:
            results.append({"symbol": symbol, "status": "insufficient_data",
                            "depth_rows": len(depth), "trade_rows": len(trades)})
            continue
        result = simulate(depth, trades, config)
        result.update({"symbol": symbol, "status": "tested", "depth_rows": len(depth),
                       "trade_rows": len(trades)})
        results.append(result)
    tested = [result for result in results if result["status"] == "tested"]
    payload = {
        "suite": "top50_spot_v8", "mode": "analysis-only", "quote": "USDC",
        "allocation": {"pairs": 50, "per_pair_usdc": 10, "total_usdc": 500},
        "execution": {"take_profit_activation": 0.005, "trailing_distance": 0.002,
                      "stop_loss": 0.003, "maker_fee": config.maker_fee,
                      "taker_fee": config.taker_fee},
        "tested_pairs": len(tested), "results": results,
        "aggregate": {
            "realized_net": sum(x["realized_net"] for x in tested),
            "unrealized_net": sum(x["unrealized_net"] for x in tested),
            "mark_to_market_net": sum(x["mark_to_market_net"] for x in tested),
            "completed_cycles": sum(x["completed_cycles"] for x in tested),
            "open_positions": sum(x["open_slots"] for x in tested),
        },
        "guardrails": {"may_place_orders": False, "confidence": "very_high"},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload["aggregate"], indent=2))


if __name__ == "__main__":
    main()
