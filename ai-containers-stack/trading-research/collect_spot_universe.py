"""Collect public spot order-book/trade streams for the grid universe."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from contextlib import ExitStack
from pathlib import Path

import aiohttp


DEFAULT_SYMBOLS = ("SOL/USDC", "ETH/USDC", "BTC/USDC", "LTC/USDC")


def slug(symbol: str) -> str:
    return symbol.replace("/", "").replace(":", "").lower()


async def collect_symbol(session: aiohttp.ClientSession, symbol: str, root: Path, deadline: float) -> None:
    name = slug(symbol)
    depth_path = root / f"{name}.jsonl"
    trades_path = root / f"{name}-aggtrades.jsonl"
    stream = name
    url = ("wss://stream.binance.com:9443/stream?streams="
           f"{stream}@depth20@100ms/{stream}@aggTrade")
    with depth_path.open("a", encoding="utf-8") as depth_handle, trades_path.open("a", encoding="utf-8") as trade_handle:
        async with session.ws_connect(url, heartbeat=20) as websocket:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                try:
                    message = await websocket.receive(timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = json.loads(message.data).get("data", {})
                if data.get("e") == "depthUpdate" or ("bids" in data and "asks" in data):
                    bids, asks = data.get("b", data.get("bids", [])), data.get("a", data.get("asks", []))
                    if not bids or not asks:
                        continue
                    bid_qty = sum(float(level[1]) for level in bids[:5])
                    ask_qty = sum(float(level[1]) for level in asks[:5])
                    depth_handle.write(json.dumps({
                        "timestamp": data.get("E", int(time.time() * 1000)),
                        "bid": float(bids[0][0]), "ask": float(asks[0][0]),
                        "bid_qty_5": bid_qty, "ask_qty_5": ask_qty,
                        "imbalance_5": (bid_qty - ask_qty) / (bid_qty + ask_qty) if bid_qty + ask_qty else 0.0,
                    }) + "\n")
                    depth_handle.flush()
                elif data.get("e") == "aggTrade":
                    trade_handle.write(json.dumps({"id": str(data.get("a", "")),
                                                   "timestamp": data.get("T"),
                                                   "side": "sell" if data.get("m") else "buy",
                                                   "price": float(data["p"]),
                                                   "amount": float(data["q"])}) + "\n")
                    trade_handle.flush()


async def discover_top_usdc(session: aiohttp.ClientSession, count: int) -> list[str]:
    async with session.get("https://api.binance.com/api/v3/exchangeInfo") as response:
        response.raise_for_status()
        exchange_info = await response.json()
    async with session.get("https://api.binance.com/api/v3/ticker/24hr") as response:
        response.raise_for_status()
        tickers = await response.json()
    allowed = {
        item["symbol"]: f'{item["baseAsset"]}/{item["quoteAsset"]}'
        for item in exchange_info["symbols"]
        if item.get("status") == "TRADING" and item.get("quoteAsset") == "USDC"
        and item.get("isSpotTradingAllowed", False)
        and not item.get("baseAsset", "").endswith(("UP", "DOWN", "BULL", "BEAR"))
        and item.get("baseAsset") not in {"USDT", "FDUSD", "USDC", "DAI", "TUSD", "EURI",
                                              "USD1", "EUR", "AEUR", "USDP"}
    }
    ranked = sorted(
        (ticker for ticker in tickers if ticker.get("symbol") in allowed),
        key=lambda ticker: float(ticker.get("quoteVolume") or 0), reverse=True,
    )
    return [allowed[ticker["symbol"]] for ticker in ranked[:count]]


async def collect_batch(session: aiohttp.ClientSession, symbols: list[str], root: Path, deadline: float) -> None:
    streams = "/".join(f"{slug(symbol)}@{kind}" for symbol in symbols
                       for kind in ("depth20@100ms", "aggTrade"))
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    with ExitStack() as stack:
        depth_handles = {slug(symbol): stack.enter_context((root / f"{slug(symbol)}.jsonl").open("a"))
                         for symbol in symbols}
        trade_handles = {slug(symbol): stack.enter_context((root / f"{slug(symbol)}-aggtrades.jsonl").open("a"))
                         for symbol in symbols}
        async with session.ws_connect(url, heartbeat=20) as websocket:
            while time.monotonic() < deadline:
                try:
                    message = await websocket.receive(timeout=deadline - time.monotonic())
                except asyncio.TimeoutError:
                    break
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                wrapper = json.loads(message.data)
                stream, data = wrapper.get("stream", ""), wrapper.get("data", {})
                name = stream.split("@", 1)[0]
                if not name:
                    continue
                if "depth" in stream:
                    bids, asks = data.get("bids", []), data.get("asks", [])
                    if not bids or not asks:
                        continue
                    bid_qty = sum(float(level[1]) for level in bids[:5])
                    ask_qty = sum(float(level[1]) for level in asks[:5])
                    depth_handles[name].write(json.dumps({
                        "timestamp": int(time.time() * 1000), "bid": float(bids[0][0]),
                        "ask": float(asks[0][0]), "bid_qty_5": bid_qty, "ask_qty_5": ask_qty,
                        "imbalance_5": (bid_qty - ask_qty) / (bid_qty + ask_qty) if bid_qty + ask_qty else 0.0,
                    }) + "\n")
                    depth_handles[name].flush()
                elif data.get("e") == "aggTrade":
                    trade_handles[name].write(json.dumps({"id": str(data.get("a", "")),
                                                          "timestamp": data.get("T"),
                                                          "side": "sell" if data.get("m") else "buy",
                                                          "price": float(data["p"]),
                                                          "amount": float(data["q"])}) + "\n")
                    trade_handles[name].flush()


async def collect(symbols: list[str], root: Path, seconds: int, top: int = 0) -> None:
    root.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + seconds
    async with aiohttp.ClientSession() as session:
        if top:
            symbols = await discover_top_usdc(session, top)
            (root / "universe.json").write_text(json.dumps({"generated_at": int(time.time() * 1000),
                                                            "quote": "USDC", "symbols": symbols}, indent=2))
            batches = [symbols[index:index + 5] for index in range(0, len(symbols), 5)]
            await asyncio.gather(*(collect_batch(session, batch, root, deadline) for batch in batches))
        else:
            await asyncio.gather(*(collect_symbol(session, symbol, root, deadline) for symbol in symbols))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=86_400)
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--top", type=int, default=0,
                        help="Auto-select top N USDC spot pairs by 24h quote volume")
    parser.add_argument("--output", type=Path, default=Path("artifacts/spot-depth"))
    args = parser.parse_args()
    asyncio.run(collect(args.symbols, args.output, args.seconds, args.top))


if __name__ == "__main__":
    main()
