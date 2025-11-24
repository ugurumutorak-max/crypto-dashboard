#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crypto Listings All-in-One

Tek çalıştırmada 3 liste üretir:
1. MEXC Vadeli - TÜM coinler (max pozisyon + CMC MC sıralı)
2. MEXC Vadeli'de VAR ama Binance Vadeli'de YOK (CMC MC sıralı)
3. MEXC Vadeli'de VAR ama Bybit Vadeli'de YOK (CMC MC sıralı)
"""

import requests
import time
import os
from typing import Dict, List, Set, Tuple, Optional
import warnings

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------------------------

# MEXC
MEXC_CONTRACT_DETAIL_URL = "https://contract.mexc.com/api/v1/contract/detail"
MEXC_SPOT_TICKER_URL = "https://api.mexc.com/api/v3/ticker/price"

# Binance
BINANCE_SPOT_SYMBOLS_URL = "https://api.binance.com/api/v3/exchangeInfo"
BINANCE_FUTURES_SYMBOLS_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"

# Bybit
BYBIT_SPOT_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info"
BYBIT_FUTURES_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info"

# CoinMarketCap
COINMARKETCAP_QUOTES_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
CMC_API_KEY = "951a1c7c-4e63-466e-8db7-3f4238162fd1"

# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def grouped_currency(value: Optional[float], decimals: int = 0) -> str:
    """Currency with thousands separator."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except Exception:
        return "N/A"
    spec = f",.{decimals}f"
    return "$" + format(v, spec)


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


# ---------------------------------------------------------------------------
# MEXC FUNCTIONS
# ---------------------------------------------------------------------------

def fetch_mexc_contracts() -> List[Dict]:
    """MEXC vadeli işlem sözleşmelerini çeker."""
    try:
        response = requests.get(MEXC_CONTRACT_DETAIL_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("success") and data.get("data"):
            return data["data"]
        return []
    except Exception as e:
        print(f"[ERROR] MEXC contract detail hatasi: {e}")
        return []


def fetch_mexc_spot_prices() -> Dict[str, float]:
    """MEXC spot fiyatlarini ceker (symbol -> price)."""
    try:
        response = requests.get(MEXC_SPOT_TICKER_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        price_map = {}
        if isinstance(data, list):
            for item in data:
                symbol = item.get("symbol", "")
                price = item.get("price")
                if symbol and price is not None:
                    try:
                        price_map[symbol] = float(price)
                    except (ValueError, TypeError):
                        pass
        return price_map
    except Exception as e:
        print(f"[ERROR] MEXC spot ticker hatasi: {e}")
        return {}


def calculate_max_positions(contracts: List[Dict], spot_prices: Dict[str, float]) -> List[Tuple[str, str, float, float, float, float, float]]:
    """Max pozisyon degerlerini hesaplar."""
    results = []
    for contract in contracts:
        symbol = contract.get("symbol", "")
        if not symbol or not symbol.endswith("_USDT"):
            continue

        base_coin = symbol.replace("_USDT", "")
        max_vol = contract.get("maxVol")
        contract_size = contract.get("contractSize")

        if max_vol is None or contract_size is None:
            continue

        try:
            max_vol = float(max_vol)
            contract_size = float(contract_size)
        except (ValueError, TypeError):
            continue

        spot_symbol = base_coin + "USDT"
        price = spot_prices.get(spot_symbol)
        if price is None or price <= 0:
            continue

        max_qty = max_vol * contract_size
        max_position_usdt = max_qty * price

        results.append((symbol, base_coin, max_vol, contract_size, price, max_qty, max_position_usdt))

    return results


def process_mexc():
    """MEXC vadeli işlem listesini işler."""
    print("\n" + "=" * 80)
    print("LISTE 1: MEXC VADELI ISLEMLER - TUM COINLER")
    print("=" * 80)
    
    print("\n[1/4] MEXC sozlesmeleri cekiliyor...")
    contracts = fetch_mexc_contracts()
    if not contracts:
        print("[ERROR] MEXC sozlesmeleri alinamadi!")
        return None, None
    print(f"[OK] {len(contracts)} sozlesme bulundu")

    print("\n[2/4] MEXC spot fiyatlari cekiliyor...")
    tickers = fetch_mexc_spot_prices()
    if not tickers:
        print("[ERROR] MEXC ticker verileri alinamadi!")
        return None, None
    print(f"[OK] {len(tickers)} ticker bulundu")

    print("\n[3/4] Max pozisyonlar hesaplaniyor...")
    positions = calculate_max_positions(contracts, tickers)
    if not positions:
        print("[ERROR] Hesaplama yapilamadi!")
        return None, None
    positions.sort(key=lambda x: x[6], reverse=True)
    print(f"[OK] {len(positions)} coin icin max pozisyon hesaplandi")

    # MEXC vadeli'deki tüm coin isimlerini set olarak sakla
    mexc_futures_coins = set([base_coin.upper() for _, base_coin, *_ in positions])
    
    # Max pozisyon map'i oluştur (symbol -> max_position_usdt)
    mexc_positions_map = {base_coin.upper(): max_pos_usdt for _, base_coin, _, _, _, _, max_pos_usdt in positions}

    print("\n[4/4] CoinMarketCap market cap verileri cekiliyor...")
    symbols_list = list(mexc_futures_coins)
    marketcaps_cmc = fetch_coinmarketcap_data(symbols_list)
    print(f"[OK] {len(marketcaps_cmc)} coin icin market cap alindi")

    # Birleştir ve sırala
    positions_with_cmc = []
    positions_without_cmc = []

    for symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt in positions:
        mc_cmc = marketcaps_cmc.get(base_coin.upper())
        if mc_cmc is not None:
            positions_with_cmc.append((symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt, mc_cmc))
        else:
            positions_without_cmc.append((symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt, None))

    positions_with_cmc.sort(key=lambda x: x[7], reverse=True)
    sorted_positions = positions_with_cmc + positions_without_cmc

    # Yazdır
    print("\n" + "=" * 110)
    print("MEXC FUTURES - TUM COINLER (MAX POZISYON VE MARKET CAP)")
    print("=" * 110)
    print(f"{'Sira':<5} {'Coin':<8} {'MaxPoz(USDT)':>18} {'CMC MC':>18}")
    print("-" * 110)

    for idx, (symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt, mc_cmc) in enumerate(sorted_positions[:50], 1):
        max_str = grouped_currency(max_pos_usdt, decimals=0)
        cmc_str = grouped_currency(mc_cmc, decimals=0) if mc_cmc else "N/A"
        print(f"{idx:<5} {base_coin:<8} {max_str:>18} {cmc_str:>18}")

    if len(sorted_positions) > 50:
        print(f"... ve {len(sorted_positions) - 50} coin daha ...")

    # Kaydet
    total_max_pos = sum(x[6] for x in positions)
    mc_count_cmc = len([x for x in sorted_positions if x[7] is not None])

    csv_filename = "1_mexc_all_futures.csv"
    with open(csv_filename, "w", encoding="utf-8") as f:
        f.write("Rank,Symbol,BaseCoin,MaxVol,ContractSize,Price,MaxQty,MaxPosition_USDT,CMC_MC,Pretty_MaxPosition,Pretty_CMC_MC\n")
        for idx, (symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt, mc_cmc) in enumerate(sorted_positions, 1):
            cmc_str = f"{mc_cmc:.0f}" if mc_cmc else "N/A"
            pretty_max = grouped_currency(max_pos_usdt, decimals=0)
            pretty_cmc = grouped_currency(mc_cmc, decimals=0) if mc_cmc else "N/A"
            f.write(f"{idx},{symbol},{base_coin},{max_vol:.0f},{contract_size:.8f},{price:.8f},{max_qty:.2f},{max_pos_usdt:.2f},{cmc_str},{pretty_max},{pretty_cmc}\n")

    txt_filename = "1_mexc_all_futures.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write("="*110 + "\n")
        f.write("MEXC FUTURES - TUM COINLER (MAX POZISYON VE MARKET CAP)\n")
        f.write("="*110 + "\n")
        f.write(f"{'Sira':<5} {'Coin':<8} {'MaxPoz(USDT)':>18} {'CMC MC':>18}\n")
        f.write("-"*110 + "\n")
        for idx, (symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt, mc_cmc) in enumerate(sorted_positions, 1):
            max_str = grouped_currency(max_pos_usdt, decimals=0)
            cmc_str = grouped_currency(mc_cmc, decimals=0) if mc_cmc else "N/A"
            f.write(f"{idx:<5} {base_coin:<8} {max_str:>18} {cmc_str:>18}\n")
        f.write("\n" + "="*110 + "\n")
        f.write(f"Toplam Coin: {len(positions)}\n")
        f.write(f"Toplam Max Pozisyon: ${total_max_pos:,.2f} USDT\n")
        f.write(f"Market Cap Verisi Olan: {mc_count_cmc} coin\n")

    print(f"\n[OK] Dosyalar kaydedildi: {csv_filename}, {txt_filename}")
    print(f"[OZET] Toplam: {len(positions)} coin, Market Cap: {mc_count_cmc} coin")
    
    return mexc_futures_coins, mexc_positions_map  # Set ve map'i döndür


# ---------------------------------------------------------------------------
# BINANCE FUNCTIONS
# ---------------------------------------------------------------------------

def fetch_binance_futures_symbols() -> Set[str]:
    """Binance Futures'daki USDT çiftlerini çeker."""
    try:
        response = requests.get(BINANCE_FUTURES_SYMBOLS_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        symbols = set()
        for symbol_info in data.get("symbols", []):
            status = symbol_info.get("status", "")
            quote = symbol_info.get("quoteAsset", "")
            base = symbol_info.get("baseAsset", "")
            
            if status == "TRADING" and quote == "USDT" and base:
                symbols.add(base.upper())
        
        return symbols
    except Exception as e:
        print(f"[ERROR] Binance Futures API hatasi: {e}")
        return set()


def process_binance(mexc_futures_coins: Set[str], mexc_positions_map: Dict[str, float]):
    """MEXC vadeli'de olup Binance vadeli'de OLMAYAN coinleri bulur."""
    print("\n" + "=" * 80)
    print("LISTE 2: MEXC VADELI'DE VAR - BINANCE VADELI'DE YOK")
    print("=" * 80)
    
    print("\n[1/3] Binance Futures coinleri cekiliyor...")
    binance_futures = fetch_binance_futures_symbols()
    if not binance_futures:
        print("[ERROR] Binance Futures verileri alinamadi!")
        return
    print(f"[OK] {len(binance_futures)} futures coin bulundu")

    print("\n[2/3] MEXC'de olup Binance'de olmayan coinler filtreleniyor...")
    not_in_binance = sorted(list(mexc_futures_coins - binance_futures))
    print(f"[OK] {len(not_in_binance)} coin MEXC'de var, Binance'de yok")

    if not not_in_binance:
        print("[INFO] Tum MEXC coinleri Binance'de de var!")
        return

    print("\n[3/3] CoinMarketCap market cap verileri cekiliyor...")
    marketcaps = fetch_coinmarketcap_data(not_in_binance)
    print(f"[OK] {len(marketcaps)} coin icin market cap alindi")

    coins_with_mc = []
    coins_without_mc = []

    for symbol in not_in_binance:
        mc = marketcaps.get(symbol)
        max_pos = mexc_positions_map.get(symbol, 0.0)
        if mc is not None:
            coins_with_mc.append((symbol, max_pos, mc))
        else:
            coins_without_mc.append((symbol, max_pos, None))

    coins_with_mc.sort(key=lambda x: x[2], reverse=True)
    all_coins = coins_with_mc + coins_without_mc

    print("\n" + "=" * 100)
    print("MEXC VADELI'DE VAR - BINANCE VADELI'DE YOK")
    print("=" * 100)
    print(f"{'Sira':<6} {'Coin':<10} {'MEXC MaxPoz(USDT)':>25} {'CMC MC':>25}")
    print("-" * 100)

    for idx, (symbol, max_pos, mc) in enumerate(all_coins[:50], 1):
        max_str = grouped_currency(max_pos, decimals=0)
        mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
        print(f"{idx:<6} {symbol:<10} {max_str:>25} {mc_str:>25}")

    if len(all_coins) > 50:
        print(f"... ve {len(all_coins) - 50} coin daha ...")

    csv_filename = "2_mexc_yes_binance_no.csv"
    with open(csv_filename, "w", encoding="utf-8") as f:
        f.write("Rank,Symbol,MEXC_MaxPosition_USDT,MarketCap_USD,Pretty_MaxPos,Pretty_MC\n")
        for idx, (symbol, max_pos, mc) in enumerate(all_coins, 1):
            max_str = f"{max_pos:.2f}"
            mc_str = f"{mc:.0f}" if mc else "N/A"
            pretty_max = grouped_currency(max_pos, decimals=0)
            pretty_mc = grouped_currency(mc, decimals=0) if mc else "N/A"
            f.write(f"{idx},{symbol},{max_str},{mc_str},{pretty_max},{pretty_mc}\n")

    txt_filename = "2_mexc_yes_binance_no.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write("="*100 + "\n")
        f.write("MEXC VADELI'DE VAR - BINANCE VADELI'DE YOK\n")
        f.write("="*100 + "\n")
        f.write(f"{'Sira':<6} {'Coin':<10} {'MEXC MaxPoz(USDT)':>25} {'CMC MC':>25}\n")
        f.write("-"*100 + "\n")
        for idx, (symbol, max_pos, mc) in enumerate(all_coins, 1):
            max_str = grouped_currency(max_pos, decimals=0)
            mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
            f.write(f"{idx:<6} {symbol:<10} {max_str:>25} {mc_str:>25}\n")
        f.write("\n" + "="*100 + "\n")
        f.write(f"MEXC Vadeli: {len(mexc_futures_coins)}, Binance Vadeli: {len(binance_futures)}\n")
        f.write(f"MEXC'de var Binance'de yok: {len(not_in_binance)}\n")
        f.write(f"Market Cap Verisi Olan: {len(coins_with_mc)} coin\n")

    print(f"\n[OK] Dosyalar kaydedildi: {csv_filename}, {txt_filename}")
    print(f"[OZET] MEXC'de var Binance'de yok: {len(not_in_binance)} coin, Market Cap: {len(coins_with_mc)} coin")


# ---------------------------------------------------------------------------
# BYBIT FUNCTIONS
# ---------------------------------------------------------------------------

def fetch_bybit_futures_symbols() -> Set[str]:
    """Bybit Futures'daki USDT çiftlerini çeker."""
    try:
        params = {"category": "linear"}
        response = requests.get(BYBIT_FUTURES_SYMBOLS_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        symbols = set()
        if data.get("retCode") == 0:
            for item in data.get("result", {}).get("list", []):
                status = item.get("status", "")
                quote = item.get("quoteCoin", "")
                base = item.get("baseCoin", "")
                
                if status == "Trading" and quote == "USDT" and base:
                    symbols.add(base.upper())
        
        return symbols
    except Exception as e:
        print(f"[ERROR] Bybit Futures API hatasi: {e}")
        return set()


def process_bybit(mexc_futures_coins: Set[str], mexc_positions_map: Dict[str, float]):
    """MEXC vadeli'de olup Bybit vadeli'de OLMAYAN coinleri bulur."""
    print("\n" + "=" * 80)
    print("LISTE 3: MEXC VADELI'DE VAR - BYBIT VADELI'DE YOK")
    print("=" * 80)
    
    print("\n[1/3] Bybit Futures coinleri cekiliyor...")
    bybit_futures = fetch_bybit_futures_symbols()
    if not bybit_futures:
        print("[ERROR] Bybit Futures verileri alinamadi!")
        return
    print(f"[OK] {len(bybit_futures)} futures coin bulundu")

    print("\n[2/3] MEXC'de olup Bybit'te olmayan coinler filtreleniyor...")
    not_in_bybit = sorted(list(mexc_futures_coins - bybit_futures))
    print(f"[OK] {len(not_in_bybit)} coin MEXC'de var, Bybit'te yok")

    if not not_in_bybit:
        print("[INFO] Tum MEXC coinleri Bybit'te de var!")
        return

    print("\n[3/3] CoinMarketCap market cap verileri cekiliyor...")
    marketcaps = fetch_coinmarketcap_data(not_in_bybit)
    print(f"[OK] {len(marketcaps)} coin icin market cap alindi")

    coins_with_mc = []
    coins_without_mc = []

    for symbol in not_in_bybit:
        mc = marketcaps.get(symbol)
        max_pos = mexc_positions_map.get(symbol, 0.0)
        if mc is not None:
            coins_with_mc.append((symbol, max_pos, mc))
        else:
            coins_without_mc.append((symbol, max_pos, None))

    coins_with_mc.sort(key=lambda x: x[2], reverse=True)
    all_coins = coins_with_mc + coins_without_mc

    print("\n" + "=" * 100)
    print("MEXC VADELI'DE VAR - BYBIT VADELI'DE YOK")
    print("=" * 100)
    print(f"{'Sira':<6} {'Coin':<10} {'MEXC MaxPoz(USDT)':>25} {'CMC MC':>25}")
    print("-" * 100)

    for idx, (symbol, max_pos, mc) in enumerate(all_coins[:50], 1):
        max_str = grouped_currency(max_pos, decimals=0)
        mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
        print(f"{idx:<6} {symbol:<10} {max_str:>25} {mc_str:>25}")

    if len(all_coins) > 50:
        print(f"... ve {len(all_coins) - 50} coin daha ...")

    csv_filename = "3_mexc_yes_bybit_no.csv"
    with open(csv_filename, "w", encoding="utf-8") as f:
        f.write("Rank,Symbol,MEXC_MaxPosition_USDT,MarketCap_USD,Pretty_MaxPos,Pretty_MC\n")
        for idx, (symbol, max_pos, mc) in enumerate(all_coins, 1):
            max_str = f"{max_pos:.2f}"
            mc_str = f"{mc:.0f}" if mc else "N/A"
            pretty_max = grouped_currency(max_pos, decimals=0)
            pretty_mc = grouped_currency(mc, decimals=0) if mc else "N/A"
            f.write(f"{idx},{symbol},{max_str},{mc_str},{pretty_max},{pretty_mc}\n")

    txt_filename = "3_mexc_yes_bybit_no.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write("="*100 + "\n")
        f.write("MEXC VADELI'DE VAR - BYBIT VADELI'DE YOK\n")
        f.write("="*100 + "\n")
        f.write(f"{'Sira':<6} {'Coin':<10} {'MEXC MaxPoz(USDT)':>25} {'CMC MC':>25}\n")
        f.write("-"*100 + "\n")
        for idx, (symbol, max_pos, mc) in enumerate(all_coins, 1):
            max_str = grouped_currency(max_pos, decimals=0)
            mc_str = grouped_currency(mc, decimals=0) if mc else "N/A"
            f.write(f"{idx:<6} {symbol:<10} {max_str:>25} {mc_str:>25}\n")
        f.write("\n" + "="*100 + "\n")
        f.write(f"MEXC Vadeli: {len(mexc_futures_coins)}, Bybit Vadeli: {len(bybit_futures)}\n")
        f.write(f"MEXC'de var Bybit'te yok: {len(not_in_bybit)}\n")
        f.write(f"Market Cap Verisi Olan: {len(coins_with_mc)} coin\n")

    print(f"\n[OK] Dosyalar kaydedildi: {csv_filename}, {txt_filename}")
    print(f"[OZET] MEXC'de var Bybit'te yok: {len(not_in_bybit)} coin, Market Cap: {len(coins_with_mc)} coin")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def create_combined_txt():
    """Tek TXT dosyasında 3 listeyi birleştirir."""
    combined_filename = "crypto_listings.txt"
    
    try:
        with open(combined_filename, "w", encoding="utf-8") as outfile:
            # Liste 1'i ekle
            if os.path.exists("1_mexc_all_futures.txt"):
                with open("1_mexc_all_futures.txt", "r", encoding="utf-8") as f:
                    outfile.write(f.read())
                    outfile.write("\n\n")
            
            # Liste 2'yi ekle
            if os.path.exists("2_mexc_yes_binance_no.txt"):
                with open("2_mexc_yes_binance_no.txt", "r", encoding="utf-8") as f:
                    outfile.write(f.read())
                    outfile.write("\n\n")
            
            # Liste 3'ü ekle
            if os.path.exists("3_mexc_yes_bybit_no.txt"):
                with open("3_mexc_yes_bybit_no.txt", "r", encoding="utf-8") as f:
                    outfile.write(f.read())
        
        print(f"[OK] Tek TXT dosyasi olusturuldu: {combined_filename}")
    except Exception as e:
        print(f"[WARNING] Tek TXT dosyasi olusturma hatasi: {e}")


def main():
    print("\n" + "=" * 80)
    print("CRYPTO LISTINGS ALL-IN-ONE")
    print("MEXC Referans: Liste 1 Tum | Liste 2 vs Binance | Liste 3 vs Bybit")
    print("=" * 80)
    
    # Liste 1: MEXC TÜM Vadeli Coinler
    mexc_futures_coins, mexc_positions_map = process_mexc()
    
    if mexc_futures_coins is None or mexc_positions_map is None:
        print("[ERROR] MEXC verileri alinamadi, diger listeler olusturulamaz!")
        return
    
    # Liste 2: MEXC'de var, Binance'de yok
    binance_results = process_binance(mexc_futures_coins, mexc_positions_map)
    
    # Liste 3: MEXC'de var, Bybit'te yok
    bybit_results = process_bybit(mexc_futures_coins, mexc_positions_map)
    
    # TEK TXT DOSYASI OLUŞTUR
    print("\n[FINAL] Tek TXT dosyasi olusturuluyor...")
    create_combined_txt()
    
    print("\n" + "=" * 80)
    print("TUM LISTELER TAMAMLANDI!")
    print("=" * 80)
    print("\nOlusturulan dosyalar:")
    print("  crypto_listings.txt                     (TEK dosya - 3 liste)")
    print("  1_mexc_all_futures.csv                  (MEXC Vadeli TUM coinler)")
    print("  2_mexc_yes_binance_no.csv               (MEXC'de var, Binance'de yok)")
    print("  3_mexc_yes_bybit_no.csv                 (MEXC'de var, Bybit'te yok)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
