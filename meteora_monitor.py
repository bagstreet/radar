#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meteora_monitor.py — GATE 1 / Модуль C: Meteora «принты» (LP fee-APR радар, paper, $0)
=====================================================================================
Цель: найти пулы, которые много "печатают" комиссиями относительно TVL.
Meteora-API недоступен из CI -> считаем ПРОКСИ fee-APR через DexScreener:
    turnover = volume_24h / TVL
    fee_APR_est = turnover * FEE_EST * 365 * 100   (грубая оценка, помечена как est)
Ранжируем top-пулы Meteora (и Orca CLMM) по fee-APR. ВНИМАНИЕ: высокий APR != прибыль,
т.к. есть IL при выходе цены из диапазона — это paper-радар "куда смотреть", не сигнал входа.
"""
import os, csv, time, argparse
from datetime import datetime, timezone
import requests

STATE_DIR = os.getenv("YIELD_STATE_DIR", os.getenv("ARB_STATE_DIR", "./state"))
os.makedirs(STATE_DIR, exist_ok=True)
def P(n): return os.path.join(STATE_DIR, n)
H = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
SCAN_INTERVAL = 900

# хабы Solana, через которые собираем пулы Meteora/Orca
HUBS = {
  "SOL":"So11111111111111111111111111111111111111112",
  "USDC":"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "USDT":"Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
  "JUP":"JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
  "jitoSOL":"J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
  "WIF":"EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
}
WATCH_DEX = {"meteora","meteora-dlmm","orca"}
FEE_EST    = 0.0020      # грубая эффективная комиссия (DLMM динамическая) — ОЦЕНКА
MIN_TVL    = 50_000
MIN_VOL24  = 50_000
MIN_APR    = 50.0        # % fee-APR-est для пометки "горячо"

def token_pairs(addr):
    r = requests.get(f"https://api.dexscreener.com/token-pairs/v1/solana/{addr}", headers=H, timeout=25)
    try: return r.json()
    except Exception: return []

def scan_once():
    ts = datetime.now(timezone.utc).isoformat()
    seen = {}
    for sym, addr in HUBS.items():
        for p in token_pairs(addr) or []:
            if p.get("dexId") not in WATCH_DEX: continue
            pa = p.get("pairAddress")
            if not pa or pa in seen: continue
            tvl = (p.get("liquidity") or {}).get("usd") or 0
            vol = (p.get("volume") or {}).get("h24") or 0
            if tvl < MIN_TVL or vol < MIN_VOL24: continue
            turnover = vol/tvl if tvl else 0
            apr = turnover*FEE_EST*365*100
            seen[pa] = [ts, p.get("dexId"),
                        f"{p.get('baseToken',{}).get('symbol','?')}/{p.get('quoteToken',{}).get('symbol','?')}",
                        round(tvl), round(vol), round(turnover,3), round(apr,1),
                        int(apr>=MIN_APR), pa]
    rows = sorted(seen.values(), key=lambda x: -x[6])
    _append("meteora_log.csv",
            ["ts","dex","pair","tvl_usd","vol24_usd","turnover","fee_apr_est_pct","hot","pair_addr"], rows)
    hot = sum(r[7] for r in rows)
    print(f"=== METEORA/CLMM {ts} ===  пулов {len(rows)} | hot(APR≥{MIN_APR}%) {hot}")
    for r in rows[:8]:
        print(f"   {r[1]:8} {r[2]:18} TVL=${r[3]:>10,} vol24=${r[4]:>11,} turnover={r[5]:.2f} fee-APR≈{r[6]:.0f}%{' 🔥' if r[7] else ''}")

def _append(fname, header, rows):
    new = not os.path.exists(P(fname))
    with open(P(fname),"a",newline="") as f:
        w=csv.writer(f)
        if new: w.writerow(header)
        for r in rows: w.writerow(r)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--once",action="store_true")
    ap.add_argument("--burst",type=int,default=0); ap.add_argument("--interval",type=int,default=90)
    a=ap.parse_args()
    print(f"meteora_monitor GATE1/C | DexScreener turnover-proxy | state={STATE_DIR}")
    if a.burst>0:
        for i in range(a.burst):
            try: scan_once()
            except Exception as e: print("  !",e)
            if i<a.burst-1: time.sleep(a.interval)
        return
    if a.once: scan_once(); return
    while True:
        try: scan_once()
        except KeyboardInterrupt: break
        except Exception as e: print("  !",e)
        time.sleep(SCAN_INTERVAL)

if __name__=="__main__": main()
