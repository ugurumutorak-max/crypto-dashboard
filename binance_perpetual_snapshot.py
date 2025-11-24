#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Binance USDT-M Perpetual Snapshot

Bu script, Binance USDT margined (USDT-M) perpetual vadeli sözleşmelerinin
listesini, 24 saatlik istatistiklerini ve güncel funding rate bilgilerini
tek bir JSON çıktısında birleştirir.

Kullanım:
    python3 binance_perpetual_snapshot.py --output snap.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Dict, List

import requests

FAPI_BASE = "https://fapi.binance.com"
EXCHANGE_INFO_URL = f"{FAPI_BASE}/fapi/v1/exchangeInfo"
TICKER_24H_URL = f"{FAPI_BASE}/fapi/v1/ticker/24hr"
FUNDING_URL = f"{FAPI_BASE}/fapi/v1/premiumIndex"


def fetch_json(url: str) -> Dict:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()


def get_perpetual_usdt_symbols() -> Dict[str, Dict]:
    data = fetch_json(EXCHANGE_INFO_URL)
    out: Dict[str, Dict] = {}
    for item in data.get("symbols", []):
        if (
            item.get("contractType") == "PERPETUAL"
            and item.get("quoteAsset") == "USDT"
        ):
            out[item["symbol"]] = {
                "symbol": item.get("symbol"),
                "pair": item.get("pair"),
                "baseAsset": item.get("baseAsset"),
                "quoteAsset": item.get("quoteAsset"),
                "marginAsset": item.get("marginAsset"),
                "pricePrecision": item.get("pricePrecision"),
                "quantityPrecision": item.get("quantityPrecision"),
                "deliveryDate": item.get("deliveryDate"),
            }
    return out


def map_by_symbol(items: List[Dict]) -> Dict[str, Dict]:
    return {item.get("symbol"): item for item in items if item.get("symbol")}


def build_snapshot() -> Dict[str, List[Dict]]:
    symbols = get_perpetual_usdt_symbols()
    if not symbols:
        raise RuntimeError("USDT-M perpetual sözleşme bulunamadı")

    tickers = map_by_symbol(fetch_json(TICKER_24H_URL))
    funding = map_by_symbol(fetch_json(FUNDING_URL))

    records: List[Dict] = []
    for symbol, meta in symbols.items():
        ticker = tickers.get(symbol, {})
        funding_item = funding.get(symbol, {})
        records.append(
            {
                **meta,
                "priceChangePercent": float(ticker.get("priceChangePercent", 0.0)),
                "volume": float(ticker.get("volume", 0.0)),
                "quoteVolume": float(ticker.get("quoteVolume", 0.0)),
                "openPrice": float(ticker.get("openPrice", 0.0)),
                "highPrice": float(ticker.get("highPrice", 0.0)),
                "lowPrice": float(ticker.get("lowPrice", 0.0)),
                "lastPrice": float(ticker.get("lastPrice", 0.0)),
                "fundingRate": float(funding_item.get("lastFundingRate", 0.0)),
                "nextFundingTime": funding_item.get("nextFundingTime"),
                "interestRate": float(funding_item.get("interestRate", 0.0)),
            }
        )

    records.sort(key=lambda x: x["symbol"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "symbols": records,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Binance USDT perpetual snapshot")
    parser.add_argument(
        "--output",
        "-o",
        help="JSON çıktısını kaydetmek için dosya yolu (boş bırakılırsa stdout)",
    )
    args = parser.parse_args(argv)

    snapshot = build_snapshot()
    text = json.dumps(snapshot, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            fp.write(text)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
