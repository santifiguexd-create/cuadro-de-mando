"""
Capa de datos del fondo. Fuente de verdad compartida.

Por defecto usa SQLite (un archivo local). Para uso compartido, apuntá a un
Postgres/Supabase con la variable de entorno DATABASE_URL.

Soporta dos tipos de posición:
  - spot     : contado. Aporta al fondo su valor de mercado.
  - futures  : perpetuo con margen aislado. Aporta al fondo margen + PnL.
"""
import os
import json
import datetime as dt

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Float,
    DateTime, Text, select, insert, update, delete, func, inspect, text,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mesa_fund.db")
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
metadata = MetaData()

positions = Table(
    "positions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String(32), nullable=False),
    Column("exchange", String(32), default="Binance"),
    Column("side", String(8), default="Long"),
    Column("qty", Float, nullable=False),
    Column("entry", Float, nullable=False),
    Column("buy_date", String(16)),
    Column("market_type", String(16), default="spot"),
    Column("leverage", Float, default=1.0),
    Column("added_margin", Float, default=0.0),
    Column("liq_price", Float),
    Column("created_at", DateTime, default=dt.datetime.utcnow),
)

meta = Table(
    "meta", metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text),
)

snapshots = Table(
    "snapshots", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", DateTime, default=dt.datetime.utcnow),
    Column("capital", Float),
    Column("deployed", Float),
    Column("reserve", Float),
    Column("pnl", Float),
    Column("detail", Text),
)

_NEW_COLUMNS = {
    "market_type": "VARCHAR(16) DEFAULT 'spot'",
    "leverage": "FLOAT DEFAULT 1",
    "added_margin": "FLOAT DEFAULT 0",
    "liq_price": "FLOAT",
}


def init_db():
    metadata.create_all(engine)
    _migrate()


def _migrate():
    """Agrega columnas nuevas sin borrar datos existentes (spot ya cargado)."""
    insp = inspect(engine)
    existing = {c["name"] for c in insp.get_columns("positions")}
    with engine.begin() as c:
        for col, ddl in _NEW_COLUMNS.items():
            if col not in existing:
                c.execute(text(f"ALTER TABLE positions ADD COLUMN {col} {ddl}"))


def get_positions():
    with engine.begin() as c:
        rows = c.execute(select(positions).order_by(positions.c.created_at)).fetchall()
    return [dict(r._mapping) for r in rows]


def _clean(p):
    return dict(
        symbol=p["symbol"].strip().upper(),
        exchange=p.get("exchange", "Binance"),
        side=p.get("side", "Long"),
        qty=float(p["qty"]),
        entry=float(p["entry"]),
        buy_date=p.get("buy_date"),
        market_type=p.get("market_type", "spot"),
        leverage=float(p.get("leverage") or 1.0),
        added_margin=float(p.get("added_margin") or 0.0),
        liq_price=(float(p["liq_price"]) if p.get("liq_price") not in (None, "", 0) else None),
    )


def add_position(p):
    with engine.begin() as c:
        c.execute(insert(positions).values(**_clean(p)))


def update_position(pid, p):
    with engine.begin() as c:
        c.execute(update(positions).where(positions.c.id == pid).values(**_clean(p)))


def delete_position(pid):
    with engine.begin() as c:
        c.execute(delete(positions).where(positions.c.id == pid))


def get_cash():
    with engine.begin() as c:
        r = c.execute(select(meta.c.value).where(meta.c.key == "cash")).fetchone()
    return float(r[0]) if r else 0.0


def set_cash(amount):
    with engine.begin() as c:
        exists = c.execute(select(meta.c.key).where(meta.c.key == "cash")).fetchone()
        if exists:
            c.execute(update(meta).where(meta.c.key == "cash").values(value=str(amount)))
        else:
            c.execute(insert(meta).values(key="cash", value=str(amount)))


def add_snapshot(pf, ts=None):
    with engine.begin() as c:
        c.execute(insert(snapshots).values(
            ts=ts or dt.datetime.utcnow(),
            capital=pf["capital"], deployed=pf["deployed"],
            reserve=pf["reserve"], pnl=pf["pnl"],
            detail=json.dumps(pf.get("rows", []), default=str),
        ))


def get_snapshots():
    with engine.begin() as c:
        rows = c.execute(select(snapshots).order_by(snapshots.c.ts)).fetchall()
    return [dict(r._mapping) for r in rows]


def last_snapshot_ts():
    with engine.begin() as c:
        r = c.execute(select(func.max(snapshots.c.ts))).fetchone()
    return r[0] if r else None
