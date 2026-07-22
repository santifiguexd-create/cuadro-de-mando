"""
Recorder de snapshots del fondo.

Corre solo (no necesita que nadie tenga el dashboard abierto). Lee las
posiciones y la reserva de la base compartida, obtiene precios de mercado,
calcula el capital total y guarda una fila en `snapshots`. Esa serie temporal
es la que alimenta el gráfico de fluctuación semanal del capital.

Uso manual:
    python snapshot.py

Agendar semanal (lunes 00:05 UTC) con cron:
    5 0 * * 1  cd /ruta/mesa-fund && /usr/bin/python3 snapshot.py >> snapshot.log 2>&1

Para ejecución compartida y sin depender de tu máquina, se puede correr el
mismo comando en GitHub Actions (schedule) o en un worker junto al resto del
sistema de Fase 2, apuntando DATABASE_URL al Postgres del fondo.
"""
import datetime as dt

import db
import prices
import valuation


def record_snapshot(min_gap_hours=0):
    db.init_db()

    if min_gap_hours:
        last = db.last_snapshot_ts()
        if last and (dt.datetime.utcnow() - last) < dt.timedelta(hours=min_gap_hours):
            print(f"[skip] snapshot reciente ({last} UTC); gap < {min_gap_hours}h")
            return None

    positions = db.get_positions()
    cash = db.get_cash()
    pairs = [valuation.pair_of(p["symbol"]) for p in positions]
    pmap = prices.price_map(pairs)
    pf = valuation.portfolio(positions, pmap, cash)

    db.add_snapshot(pf)
    print(f"[ok] {dt.datetime.utcnow():%Y-%m-%d %H:%M} UTC  "
          f"capital=${pf['capital']:,.2f}  desplegado=${pf['deployed']:,.2f}  "
          f"reserva=${pf['reserve']:,.2f}  pnl=${pf['pnl']:,.2f}")
    return pf


if __name__ == "__main__":
    record_snapshot()
