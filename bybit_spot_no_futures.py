#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bybit Spot (Vadeli Olmayan) Coin Lister

Bybit Spot'ta olan ancak Vadeli İşlemde OLMAYAN coinleri listeler:
1. Bybit Spot'taki tüm coinleri çeker
2. Bybit Futures'daki coinleri çeker
3. Sadece Spot'ta olup Futures'da OLMAYAN coinleri filtreler
4. CoinMarketCap'tan market cap verilerini alır
5. Market cap'e göre sıralar ve kaydeder
"""

import requests
import time
from typing import Dict, List, Set
import warnings

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------------------------

BYBIT_SPOT_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info"
BYBIT_FUTURES_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info"
COINMARKETCAP_QUOTES_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"

# CoinMarketCap API Key
CMC_API_KEY = "951a1c7c-4e63-466e-8db7-3f4238162fd1"

# ---------------------------------------------------------------------------
# FUNCTIONS
# ---------------------------------------------------------------------------

def grouped_currency(value: float, decimals: int = 0) -> str:
    """Currency with thousands separator."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except Exception:
        return "N/A"
    spec = f",.{decimals}f"
    return "$" + format(v, spec)


def fetch_bybit_spot_symbols() -> Set[str]:
    """Bybit Spot'taki USDT çiftlerini çeker."""
    try:
        params = {
            "category": "spot"
        }
        response = requests.get(BYBIT_SPOT_SYMBOLS_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        symbols = set()
        if data.get("retCode") == 0:
            for item in data.get("result", {}).get("list", []):
                symbol = item.get("symbol", "")
                status = item.get("status", "")
                quote = item.get("quoteCoin", "")
                base = item.get("baseCoin", "")
                
                # Sadece USDT çiftleri ve trading durumunda olanlar
                if status == "Trading" and quote == "USDT" and base:
                    symbols.add(base)
        
        return symbols
    except Exception as e:
        print(f"[ERROR] Bybit Spot API hatasi: {e}")
        return set()


def fetch_bybit_futures_symbols() -> Set[str]:
    """Bybit Futures'daki USDT çiftlerini çeker (linear perpetual)."""
    try:
        params = {
            "category": "linear"  # USDT perpetual contracts
        }
        response = requests.get(BYBIT_FUTURES_SYMBOLS_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        symbols = set()
        if data.get("retCode") == 0:
            for item in data.get("result", {}).get("list", []):
                symbol = item.get("symbol", "")
                status = item.get("status", "")
                quote = item.get("quoteCoin", "")
                base = item.get("baseCoin", "")
                
                # Sadece USDT çiftleri ve trading durumunda olanlar
                if status == "Trading" and quote == "USDT" and base:
                    symbols.add(base)
        
        return symbols
    except Exception as e:
        print(f"[ERROR] Bybit Futures API hatasi: {e}")
        return set()


def fetch_coinmarketcap_data(symbols: List[str]) -> Dict[str, float]:
    """CoinMarketCap'ten market cap verilerini çeker."""
    if not symbols or CMC_API_KEY == "DEMO":
        return {}
    
    marketcaps: Dict[str, float] = {}
    batch_size = 100
    
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        symbols_str = ",".join(batch)
        
        params = {
            'symbol': symbols_str,
            'convert': 'USD'
        }
        
        try:
            response = requests.get(COINMARKETCAP_QUOTES_URL, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status', {}).get('error_code') == 0:
                coin_data = data.get('data', {})
                for symbol, info_list in coin_data.items():
                    if isinstance(info_list, list) and len(info_list) > 0:
                        info = info_list[0]
                        quote = info.get('quote', {}).get('USD', {})
                        mc = quote.get('market_cap')
                        if mc:
                            marketcaps[symbol.upper()] = float(mc)
        except Exception as e:
            print(f"[WARNING] CoinMarketCap batch hatasi ({i}-{i+batch_size}): {e}")
        
        if i + batch_size < len(symbols):
            time.sleep(0.3)
    
    return marketcaps


def main():
    print("=" * 80)
    print("BYBIT SPOT - VADELI OLMAYAN COINLER (CoinMarketCap MC)")
    print("=" * 80)
    print()

    # 1) Bybit Spot coinlerini çek
    print("[1/4] Bybit Spot coinleri cekiliyor...")
    spot_symbols = fetch_bybit_spot_symbols()
    if not spot_symbols:
        print("[ERROR] Bybit Spot verileri alinamadi!")
        return
    print(f"[OK] {len(spot_symbols)} spot coin bulundu")

    # 2) Bybit Futures coinlerini çek
    print("\n[2/4] Bybit Futures coinleri cekiliyor...")
    futures_symbols = fetch_bybit_futures_symbols()
    if not futures_symbols:
        print("[ERROR] Bybit Futures verileri alinamadi!")
        return
    print(f"[OK] {len(futures_symbols)} futures coin bulundu")

    # 3) Sadece Spot'ta olup Futures'da OLMAYAN coinleri filtrele
    print("\n[3/4] Vadeli olmayan coinler filtreleniyor...")
    non_futures = sorted(list(spot_symbols - futures_symbols))
    print(f"[OK] {len(non_futures)} coin sadece spot'ta var (vadeli yok)")

    if not non_futures:
        print("[INFO] Tum spot coinlerin vadeli islemi var!")
        return

    # 4) CoinMarketCap market cap verilerini çek
    print("\n[4/4] CoinMarketCap market cap verileri cekiliyor...")
    marketcaps = fetch_coinmarketcap_data(non_futures)
    print(f"[OK] {len(marketcaps)} coin icin market cap alindi")

    # 5) Market cap ile birleştir ve sırala
    coins_with_mc = []
    coins_without_mc = []

    for symbol in non_futures:
        mc = marketcaps.get(symbol)
        if mc is not None:
            coins_with_mc.append((symbol, mc))
        else:
            coins_without_mc.append((symbol, None))

    # Market cap'e göre azalan sırada sırala
    coins_with_mc.sort(key=lambda x: x[1], reverse=True)
    all_coins = coins_with_mc + coins_without_mc

    # 6) Konsola yazdır
    print("\n" + "=" * 70)
    print("BYBIT SPOT - VADELI OLMAYAN COINLER")
    print("=" * 70)
    print(f"{'Sira':<6} {'Coin':<10} {'Market Cap (CMC)':>25}")
    print("-" * 70)

    for idx, (symbol, mc) in enumerate(all_coins, 1):
        mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
        print(f"{idx:<6} {symbol:<10} {mc_str:>25}")

    # 7) Özet
    print("\n" + "=" * 70)
    print("OZET")
    print("=" * 70)
    print(f"Toplam Bybit Spot Coin: {len(spot_symbols)}")
    print(f"Bybit Futures Coin: {len(futures_symbols)}")
    print(f"Sadece Spot (Vadeli Olmayan): {len(non_futures)}")
    print(f"Market Cap Verisi Olan: {len(coins_with_mc)}")
    print("=" * 70)

    # 8) CSV kaydet
    csv_filename = "bybit_spot_no_futures.csv"
    try:
        with open(csv_filename, "w", encoding="utf-8") as f:
            f.write("Rank,Symbol,MarketCap_USD,Pretty_MC\n")
            for idx, (symbol, mc) in enumerate(all_coins, 1):
                mc_str = f"{mc:.0f}" if mc else "N/A"
                pretty_mc = grouped_currency(mc, decimals=0) if mc else "N/A"
                f.write(f"{idx},{symbol},{mc_str},{pretty_mc}\n")
        print(f"\n[OK] CSV dosyasi kaydedildi: {csv_filename}")
    except Exception as e:
        print(f"[WARNING] CSV kayit hatasi: {e}")

    # 9) TXT liste
    txt_filename = "bybit_spot_no_futures.txt"
    try:
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write("="*70 + "\n")
            f.write("BYBIT SPOT - VADELI OLMAYAN COINLER\n")
            f.write("="*70 + "\n")
            f.write(f"{'Sira':<6} {'Coin':<10} {'Market Cap (CMC)':>25}\n")
            f.write("-"*70 + "\n")
            for idx, (symbol, mc) in enumerate(all_coins, 1):
                mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
                f.write(f"{idx:<6} {symbol:<10} {mc_str:>25}\n")
            f.write("\n" + "="*70 + "\n")
            f.write("OZET\n")
            f.write("="*70 + "\n")
            f.write(f"Toplam Bybit Spot Coin: {len(spot_symbols)}\n")
            f.write(f"Bybit Futures Coin: {len(futures_symbols)}\n")
            f.write(f"Sadece Spot (Vadeli Olmayan): {len(non_futures)}\n")
            f.write(f"Market Cap Verisi Olan: {len(coins_with_mc)}\n")
            f.write("="*70 + "\n")
        print(f"[OK] TXT dosyasi kaydedildi: {txt_filename}")
    except Exception as e:
        print(f"[WARNING] TXT kayit hatasi: {e}")

    # 10) Markdown
    md_filename = "bybit_spot_no_futures.md"
    try:
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write("# Bybit Spot — Vadeli Olmayan Coinler (CMC MC)\n\n")
            f.write("| # | Coin | Market Cap (CMC) |\n")
            f.write("|---:|:----|-------:|\n")
            for idx, (symbol, mc) in enumerate(all_coins, 1):
                mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
                f.write(f"| {idx} | {symbol} | {mc_str} |\n")
        print(f"[OK] Markdown dosyasi kaydedildi: {md_filename}")
    except Exception as e:
        print(f"[WARNING] Markdown kayit hatasi: {e}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
