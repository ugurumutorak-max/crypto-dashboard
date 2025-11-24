#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crypto Listings Web Dashboard

Web üzerinden canlı olarak güncellenen kripto para listeleri.
Her saniye otomatik olarak yenilenir.
"""

import requests
import time
import os
from typing import Dict, List, Set, Tuple, Optional
import warnings
from flask import Flask, render_template, jsonify, request
from threading import Thread, Lock
from datetime import datetime

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
BYBIT_FUTURES_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments"

# CoinMarketCap
COINMARKETCAP_QUOTES_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
CMC_API_KEY = "951a1c7c-4e63-466e-8db7-3f4238162fd1"
WORKER_SECRET = os.environ.get("WORKER_SECRET")
_disable_server_binance_flag = os.environ.get("DISABLE_SERVER_BINANCE", os.environ.get("DISABLE_SERVER_BINANCE_BYBIT", "0"))
DISABLE_SERVER_BINANCE = (_disable_server_binance_flag or "0") == "1"

# İstenmeyen Coinler (Blacklist)
BLACKLIST = {"SHIB", "PEPE", "XAUT", "FLOKI", "RAY"}

# ---------------------------------------------------------------------------
# FLASK APP
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Global veri deposu
data_store = {
    'mexc_list': [],
    'binance_list': [],
    'bybit_list': [],
    'last_update': None,
    'stats': {}
}
data_lock = Lock()

# Arka plan thread kontrolü
update_thread = None
update_thread_started = False

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
    
    # K, M, B, T formatı
    if v >= 1_000_000_000_000:
        return f"${v/1_000_000_000_000:.2f}T"
    elif v >= 1_000_000_000:
        return f"${v/1_000_000_000:.2f}B"
    elif v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    elif v >= 1_000:
        return f"${v/1_000:.2f}K"
    else:
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

        # Blacklist kontrolü
        if base_coin.upper() in BLACKLIST:
            continue

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
    print("\n[MEXC] Sozlesmeler cekiliyor...")
    contracts = fetch_mexc_contracts()
    if not contracts:
        print("[ERROR] MEXC sozlesmeleri alinamadi!")
        return None, None, []
    
    print(f"[MEXC] {len(contracts)} sozlesme bulundu")

    tickers = fetch_mexc_spot_prices()
    if not tickers:
        print("[ERROR] MEXC ticker verileri alinamadi!")
        return None, None, []
    
    positions = calculate_max_positions(contracts, tickers)
    if not positions:
        print("[ERROR] Hesaplama yapilamadi!")
        return None, None, []
    
    positions.sort(key=lambda x: x[6], reverse=True)

    mexc_futures_coins = set([base_coin.upper() for _, base_coin, *_ in positions])
    mexc_positions_map = {base_coin.upper(): max_pos_usdt for _, base_coin, _, _, _, _, max_pos_usdt in positions}

    symbols_list = list(mexc_futures_coins)
    marketcaps_cmc = fetch_coinmarketcap_data(symbols_list)

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

    # JSON formatına dönüştür
    mexc_list = []
    for idx, (symbol, base_coin, max_vol, contract_size, price, max_qty, max_pos_usdt, mc_cmc) in enumerate(sorted_positions, 1):
        mexc_list.append({
            'rank': idx,
            'symbol': base_coin,
            'max_position': max_pos_usdt,
            'max_position_pretty': grouped_currency(max_pos_usdt),
            'market_cap': mc_cmc if mc_cmc else 0,
            'market_cap_pretty': grouped_currency(mc_cmc) if mc_cmc else "N/A"
        })

    print(f"[MEXC] {len(mexc_list)} coin islendi")
    return mexc_futures_coins, mexc_positions_map, mexc_list


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
    print("\n[BINANCE] Futures coinleri cekiliyor...")
    binance_futures = fetch_binance_futures_symbols()
    if not binance_futures:
        print("[ERROR] Binance Futures verileri alinamadi!")
        return []
    
    not_in_binance = sorted(list(mexc_futures_coins - binance_futures))
    print(f"[BINANCE] {len(not_in_binance)} coin MEXC'de var, Binance'de yok")

    if not not_in_binance:
        return []

    marketcaps = fetch_coinmarketcap_data(not_in_binance)

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

    # JSON formatına dönüştür
    binance_list = []
    for idx, (symbol, max_pos, mc) in enumerate(all_coins, 1):
        binance_list.append({
            'rank': idx,
            'symbol': symbol,
            'max_position': max_pos,
            'max_position_pretty': grouped_currency(max_pos),
            'market_cap': mc if mc else 0,
            'market_cap_pretty': grouped_currency(mc) if mc else "N/A"
        })

    print(f"[BINANCE] {len(binance_list)} coin islendi")
    return binance_list




# ---------------------------------------------------------------------------
# BYBIT FUNCTIONS
# ---------------------------------------------------------------------------

def fetch_bybit_futures_symbols() -> Set[str]:
    """Bybit Futures'daki USDT çiftlerini çeker."""
    try:
        symbols = set()
        cursor = None
        
        while True:
            params = {'category': 'linear', 'status': 'Trading', 'limit': 1000}
            if cursor:
                params['cursor'] = cursor
            
            response = requests.get(BYBIT_FUTURES_SYMBOLS_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get('retCode') != 0:
                break
                
            result = data.get('result', {})
            list_items = result.get('list', [])
            
            for item in list_items:
                if item.get('quoteCoin') == 'USDT' and item.get('status') == 'Trading':
                    base = item.get('baseCoin')
                    if base:
                        symbols.add(base.upper())
            
            cursor = result.get('nextPageCursor')
            if not cursor:
                break
                
        return symbols
    except Exception as e:
        print(f"[ERROR] Bybit Futures API hatasi: {e}")
        return set()


def process_bybit(mexc_futures_coins: Set[str], mexc_positions_map: Dict[str, float]):
    """MEXC vadeli'de olup Bybit vadeli'de OLMAYAN coinleri bulur."""
    print("\n[BYBIT] Futures coinleri cekiliyor...")
    bybit_futures = fetch_bybit_futures_symbols()
    if not bybit_futures:
        print("[ERROR] Bybit Futures verileri alinamadi!")
        return []
    
    not_in_bybit = sorted(list(mexc_futures_coins - bybit_futures))
    print(f"[BYBIT] {len(not_in_bybit)} coin MEXC'de var, Bybit'de yok")

    if not not_in_bybit:
        return []

    marketcaps = fetch_coinmarketcap_data(not_in_bybit)

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

    # JSON formatına dönüştür
    bybit_list = []
    for idx, (symbol, max_pos, mc) in enumerate(all_coins, 1):
        bybit_list.append({
            'rank': idx,
            'symbol': symbol,
            'max_position': max_pos,
            'max_position_pretty': grouped_currency(max_pos),
            'market_cap': mc if mc else 0,
            'market_cap_pretty': grouped_currency(mc) if mc else "N/A"
        })

    print(f"[BYBIT] {len(bybit_list)} coin islendi")
    return bybit_list


# ---------------------------------------------------------------------------
# DATA UPDATE THREAD
# ---------------------------------------------------------------------------

def update_data():
    """Verileri günceller."""
    global data_store
    
    # İlk veriyi hemen topla
    print("\n" + "="*80)
    print(f"[UPDATE] Ilk veri guncelleniyor... {datetime.now().strftime('%H:%M:%S')}")
    print("="*80)
    
    try:
        mexc_futures_coins, mexc_positions_map, mexc_list = process_mexc()
        
        if mexc_futures_coins is not None and mexc_positions_map is not None:
            if not DISABLE_SERVER_BINANCE:
                binance_list = process_binance(mexc_futures_coins, mexc_positions_map)
                bybit_list = process_bybit(mexc_futures_coins, mexc_positions_map)
            else:
                binance_list = data_store.get('binance_list', [])
                bybit_list = data_store.get('bybit_list', [])
                print("[INFO] Sunucu Binance/Bybit verisini bekliyor (worker aracılığıyla).")
            
            with data_lock:
                data_store['mexc_list'] = mexc_list
                if not DISABLE_SERVER_BINANCE:
                    data_store['binance_list'] = binance_list
                    data_store['bybit_list'] = bybit_list
                data_store['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                stats = data_store.get('stats', {})
                stats['mexc_count'] = len(mexc_list)
                if not DISABLE_SERVER_BINANCE:
                    stats['binance_count'] = len(binance_list)
                    stats['bybit_count'] = len(bybit_list)
                data_store['stats'] = stats
            
            print(f"\n[SUCCESS] Ilk veri yuklendi: MEXC={len(mexc_list)}, Binance={len(data_store['binance_list'])}, Bybit={len(data_store.get('bybit_list', []))}")
    except Exception as e:
        print(f"[ERROR] Ilk veri yukleme hatasi: {e}")
    
    # Sonra döngüye gir
    while True:
        try:
            print("\n" + "="*80)
            print(f"[UPDATE] Veri guncelleniyor... {datetime.now().strftime('%H:%M:%S')}")
            print("="*80)
            
            # Verileri çek
            mexc_futures_coins, mexc_positions_map, mexc_list = process_mexc()
            
            if mexc_futures_coins is None or mexc_positions_map is None:
                print("[ERROR] MEXC verileri alinamadi!")
                time.sleep(5)
                continue
            
            if not DISABLE_SERVER_BINANCE:
                binance_list = process_binance(mexc_futures_coins, mexc_positions_map)
                bybit_list = process_bybit(mexc_futures_coins, mexc_positions_map)
            else:
                binance_list = data_store.get('binance_list', [])
                bybit_list = data_store.get('bybit_list', [])
            
            # Global veri deposunu güncelle
            with data_lock:
                data_store['mexc_list'] = mexc_list
                if not DISABLE_SERVER_BINANCE:
                    data_store['binance_list'] = binance_list
                    data_store['bybit_list'] = bybit_list
                data_store['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                stats = data_store.get('stats', {})
                stats['mexc_count'] = len(mexc_list)
                if not DISABLE_SERVER_BINANCE:
                    stats['binance_count'] = len(binance_list)
                    stats['bybit_count'] = len(bybit_list)
                data_store['stats'] = stats
            
            print(f"\n[SUCCESS] Veri guncellendi: MEXC={len(mexc_list)}, Binance={len(data_store['binance_list'])}, Bybit={len(data_store.get('bybit_list', []))}")
            
        except Exception as e:
            print(f"[ERROR] Veri guncelleme hatasi: {e}")
        
        # 1 saat bekle (3600 saniye)
        time.sleep(3600)


def start_background_updater():
    """Arka plan veri güncelleyicisini bir kez başlat."""
    global update_thread, update_thread_started
    if not update_thread_started:
        update_thread = Thread(target=update_data, daemon=True)
        update_thread.start()
        update_thread_started = True
        print("[SERVER] Background updater baslatildi")


# ---------------------------------------------------------------------------
# FLASK ROUTES
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    """Ana sayfa."""
    return render_template('dashboard.html')


@app.route('/api/data')
def get_data():
    """Tüm verileri JSON formatında döndür."""
    with data_lock:
        return jsonify(data_store)


@app.route('/api/mexc')
def get_mexc():
    """MEXC verilerini döndür."""
    with data_lock:
        return jsonify({
            'data': data_store['mexc_list'],
            'last_update': data_store['last_update']
        })


@app.route('/api/binance')
def get_binance():
    """Binance karşılaştırma verilerini döndür."""
    with data_lock:
        return jsonify({
            'data': data_store['binance_list'],
            'last_update': data_store['last_update']
        })


@app.route('/api/bybit')
def get_bybit():
    """Bybit karşılaştırma verilerini döndür."""
    with data_lock:
        return jsonify({
            'data': data_store.get('bybit_list', []),
            'last_update': data_store['last_update']
        })


@app.route('/api/health')
def health_check():
    """Sunucu yapılandırma durumunu kontrol eder."""
    return jsonify({
        'status': 'running',
        'worker_secret_configured': bool(WORKER_SECRET),
        'worker_secret_length': len(WORKER_SECRET) if WORKER_SECRET else 0,
        'server_binance_disabled': DISABLE_SERVER_BINANCE,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/api/worker/update', methods=['POST'])
def worker_update():
    """Arka plan worker'ından gelen verileri kabul eder."""
    if not WORKER_SECRET:
        return jsonify({'error': 'WORKER_SECRET tanımlı değil'}), 503

    payload = request.get_json(silent=True) or {}
    provided_secret = payload.get('secret') or request.headers.get('X-Worker-Secret')

    if provided_secret != WORKER_SECRET:
        return jsonify({'error': 'Yetkisiz erişim'}), 401

    with data_lock:
        for key in ('mexc_list', 'binance_list', 'bybit_list'):
            if isinstance(payload.get(key), list):
                data_store[key] = payload[key]

        stats = payload.get('stats')
        if isinstance(stats, dict):
            existing = data_store.get('stats', {}).copy()
            existing.update(stats)
            data_store['stats'] = existing
        else:
            data_store['stats'] = {
                'mexc_count': len(data_store.get('mexc_list', [])),
                'binance_count': len(data_store.get('binance_list', [])),
                'bybit_count': len(data_store.get('bybit_list', []))
            }

        if payload.get('last_update'):
            data_store['last_update'] = payload['last_update']
        else:
            data_store['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return jsonify({'status': 'ok'})


@app.before_request
def _ensure_updater_running():
    """Her istekten önce (gerekirse) updater thread'ini tetikle."""
    start_background_updater()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    """Ana fonksiyon."""
    print("\n" + "="*80)
    print("CRYPTO WEB DASHBOARD")
    print("Kripto para listeleri - Saatlik otomatik güncelleme")
    print("="*80)
    
    # Veri güncelleme thread'ini başlat
    start_background_updater()
    
    print("\n[SERVER] Web sunucusu baslatiliyor...")
    print("[SERVER] Dashboard: http://127.0.0.1:5000")
    print("[SERVER] API Endpoints:")
    print("  - /api/data     (Tum veriler)")
    print("  - /api/mexc     (MEXC vadeli)")
    print("  - /api/binance  (MEXC vs Binance)")
    print("  - /api/bybit    (MEXC vs Bybit)")
    print("\n[SERVER] Duraklatmak icin Ctrl+C")
    print("="*80 + "\n")
    
    # Flask sunucusunu başlat
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
