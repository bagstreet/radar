#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lst_redemption_monitor.py — GATE 1 / Модуль E+G: LST redemption-радар (paper, $0)
=================================================================================
Идея: LST (jitoSOL, mSOL, ...) имеет ВНУТРЕННЮЮ стоимость в SOL (redemption у протокола).
Если DEX-цена ниже intrinsic -> купить на DEX и погасить у протокола = исполнимый профит
(в отличие от чистого DEX-спреда). Ловим именно такие окна.

Источники (бесплатно, без ключа):
  - Sanctum extra-api: intrinsic SOL-value LST   -> https://extra-api.sanctum.so/v1/sol-value/current
  - DexScreener: рыночная цена LST в SOL (priceNative)
"""
import os, csv, time, argparse
from datetime import datetime, timezone
import requests

STATE_DIR = os.getenv("YIELD_STATE_DIR", os.getenv("ARB_STATE_DIR", "./state"))
os.makedirs(STATE_DIR, exist_ok=True)
def P(n): return os.path.join(STATE_DIR, n)
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
SCAN_INTERVAL = 900

LSTS = ["jitoSOL","mSOL","bSOL","INF","jupSOL","bnSOL","hSOL","dSOL"]
# издержки погашения: своп-комиссия + анстейк (instant unstake fee ~ доли %); консервативно
SWAP_FEE   = 0.0010    # 0.10% за своп на DEX
UNSTAKE_FEE= 0.0010    # 0.10% за instant-redeem (или ждать эпоху бесплатно)
MIN_LIQ_USD= 250_000
MIN_NET_DISC = 0.30    # % чистого дисконта для actionable

def sanctum_values(lsts):
    q = "&".join(f"lst={x}" for x in lsts)
    r = requests.get(f"https://extra-api.sanctum.so/v1/sol-value/current?{q}", headers=H, timeout=25)
    return {k: int(v)/1e9 for k, v in r.json().get("solValues", {}).items()}

def best_sol_pool(lst):
    r = requests.get(f"https://api.dexscreener.com/latest/dex/search?q={lst}%20SOL", headers=H, timeout=25).json()
    cands = []
    for p in r.get("pairs", []):
        if p.get("chainId") != "solana": continue
        if (p.get("baseToken",{}).get("symbol","")).lower() != lst.lower(): continue
        if (p.get("quoteToken",{}).get("symbol","")).upper() not in ("SOL","WSOL"): continue
        pn = p.get("priceNative"); liq = p.get("liquidity",{}).get("usd",0) or 0
        if pn: cands.append((float(pn), float(liq), p.get("dexId","")))
    cands.sort(key=lambda x: -x[1])
    return cands[0] if cands else None

def scan_once():
    ts = datetime.now(timezone.utc).isoformat()
    intr = sanctum_values(LSTS)
    rows = []
    for lst in LSTS:
        iv = intr.get(lst)
        pool = best_sol_pool(lst)
        if iv is None or pool is None: continue
        dex_price, liq, dex = pool
        disc = (iv - dex_price)/iv*100          # + => DEX дешевле intrinsic = арб купить+погасить
        net = disc - (SWAP_FEE+UNSTAKE_FEE)*100
        actionable = int(disc > 0 and net >= MIN_NET_DISC and liq >= MIN_LIQ_USD)
        rows.append([ts, lst, round(iv,6), round(dex_price,6), round(disc,4),
                     dex, round(liq), round(net,4), actionable])
    _append("lst_redemption_log.csv",
            ["ts","lst","intrinsic_sol","dex_price_sol","disc_pct","dex","pool_liq_usd","net_after_costs_pct","actionable"], rows)
    act = sum(r[-1] for r in rows)
    print(f"=== LST-REDEMPTION {ts} ===  LST {len(rows)} | actionable {act}")
    for r in sorted(rows, key=lambda x: -x[4]):
        tag = "🟢ARB" if r[-1] else ("дисконт" if r[4]>0 else "премия")
        print(f"   {r[1]:8} intrinsic={r[2]:.4f} dex={r[3]:.4f}  {r[4]:+.3f}% net={r[7]:+.3f}% liq=${r[6]:,} [{tag}]")

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
    print(f"lst_redemption_monitor GATE1/E+G | Sanctum+DexScreener | state={STATE_DIR}")
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
