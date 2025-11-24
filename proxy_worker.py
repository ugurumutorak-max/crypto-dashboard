#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proxy Worker

Binance ve Bybit API'leri Render gibi ortamlarda engellendiğinde, bu script
kendi bilgisayarınızdan (veya erişim izni olan bir sunucudan) verileri çeker ve
sonuçları ana dashboard uygulamasına gönderir.

Kullanım:
    WORKER_SECRET=xxxx DASHBOARD_URL=https://crypto-dashboard-... \
    python proxy_worker.py

Ortam değişkenleri:
    WORKER_SECRET   -> Dashboard tarafında render hizmetine tanımlanan gizli token
    DASHBOARD_URL   -> Varsayılan https://crypto-dashboard-uh1e.onrender.com
    WORKER_INTERVAL -> Döngüler arası saniye (varsayılan 3600)
    WORKER_ONCE     -> "1" ise sadece bir kez çalışır.
"""

import os
import time
import requests
from datetime import datetime

from crypto_web_dashboard import (
    process_mexc,
    process_binance,
    process_bybit
)

DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://crypto-dashboard-uh1e.onrender.com')
WORKER_SECRET = os.environ.get('WORKER_SECRET')
WORKER_INTERVAL = int(os.environ.get('WORKER_INTERVAL', '3600'))
RUN_ONCE = os.environ.get('WORKER_ONCE', '0') == '1'


def push_payload(payload):
    """Dashboard API'sine payload gönder."""
    url = DASHBOARD_URL.rstrip('/') + '/api/worker/update'
    headers = {'X-Worker-Secret': WORKER_SECRET}
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    print(f"[WORKER] Payload gönderildi -> {url}")


def build_payload():
    """MEXC + Binance + Bybit verilerini hazırla."""
    mexc_futures_coins, mexc_positions_map, mexc_list = process_mexc()
    if mexc_futures_coins is None or mexc_positions_map is None:
        raise RuntimeError("MEXC verileri alınamadı, worker durdu.")

    binance_list = process_binance(mexc_futures_coins, mexc_positions_map) or []
    bybit_list = process_bybit(mexc_futures_coins, mexc_positions_map) or []

    payload = {
        'secret': WORKER_SECRET,
        'mexc_list': mexc_list,
        'binance_list': binance_list,
        'bybit_list': bybit_list,
        'stats': {
            'mexc_count': len(mexc_list),
            'binance_count': len(binance_list),
            'bybit_count': len(bybit_list)
        },
        'last_update': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    return payload


def run_once():
    payload = build_payload()
    push_payload(payload)


def main():
    if not WORKER_SECRET:
        raise SystemExit("WORKER_SECRET tanımlanmadan worker çalıştırılamaz.")

    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"[WORKER][ERROR] {exc}")
            if RUN_ONCE:
                raise
            # hata sonrası 5 dk bekle
            time.sleep(300)
            continue

        if RUN_ONCE:
            break

        print(f"[WORKER] {WORKER_INTERVAL} saniye sonra yeniden çalışacak...")
        time.sleep(WORKER_INTERVAL)


if __name__ == '__main__':
    main()
