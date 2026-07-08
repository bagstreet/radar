# bagstreet/radar — Meteora fee-APR + LST redemption радары ($0, paper)

Два независимых монитора, разные workflow со смещёнными cron (не сталкиваются push'ем).

## Файлы
- `meteora_monitor.py` — топ DLMM/CLMM пулы Solana по fee-APR (proxy = vol24/TVL × fee). Радар «куда смотреть», с поправкой на IL.
- `lst_redemption_monitor.py` — LST (jitoSOL/mSOL/bSOL/INF/…): intrinsic SOL-value (Sanctum) vs DEX-цена. Флаг, когда DEX ниже redemption = исполнимый дисконт.
- `.github/workflows/meteora.yml` — cron :10/:25/:40/:55
- `.github/workflows/lst.yml` — cron :13/:28/:43/:58

## Установка
1. Публичный репо `bagstreet/radar`.
2. В корень: `meteora_monitor.py`, `lst_redemption_monitor.py`.
3. По путям `.github/workflows/meteora.yml` и `.github/workflows/lst.yml`.
4. Settings → Actions → General → **Read and write permissions** → Save.
5. Actions → запусти оба workflow (Run workflow).
6. Логи: `state/meteora_log.csv`, `state/lst_redemption_log.csv`.

## Честные оговорки
- Meteora fee-APR — **оценка** (DexScreener не отдаёт точную комиссию пула); высокий APR ≠ прибыль из-за IL.
- LST redeem: сигнал исполним только при реальном дисконте (DEX < intrinsic) + достаточной ликвидности; учтены своп + анстейк-издержки.
