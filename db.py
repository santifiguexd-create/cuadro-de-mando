"""
Capa de datos del fondo. Fuente de verdad compartida.

Por defecto usa SQLite (un archivo local). Para uso compartido entre vos y tu
socio, apuntá a un Postgres/Supabase con la variable de entorno DATABASE_URL:

    export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/mesa"

El resto del sistema (dashboard y recorder de snapshots) no cambia.
"""
import os
import json
import datetime as dt

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Float,
    DateTime, Text, select, insert, update, delete, func,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mesa_fund.db")
engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

positions = Table(
    "positions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String(32), nullable=False),
    Column("exchange", String(32), default="Binance"),
    Column("side", String(8), default="Long"),        # Long | Short
    Column("qty", Float, nullable=False),
    Column("entry", Float, nullable=False),            # precio de entrada (USDT)
    Column("buy_date", String(16)),                    # YYYY-MM-DD
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
    Column("capital", Float),    # capital total del fondo (desplegado + reserva)
    Column("deployed", Float),   # valor de mercado de las posiciones
    Column("reserve", Float),    # cash sin invertir
    Column("pnl", Float),        # P&L no realizado
    Column("detail", Text),      # JSON con el desglose por posición
)


def init_db():
    metadata.create_all(engine)


# ---------- posiciones ----------
def get_positions():
    with engine.begin() as c:
        rows = c.execute(select(positions).order_by(positions.c.created_at)).fetchall()
    return [dict(r._mapping) for r in rows]


def add_position(p):
    with engine.begin() as c:
        c.execute(insert(positions).values(
            symbol=p["symbol"].strip().upper(), exchange=p.get("exchange", "Binance"),
            side=p.get("side", "Long"), qty=float(p["qty"]), entry=float(p["entry"]),
            buy_date=p.get("buy_date"),
        ))


def update_position(pid, p):
    with engine.begin() as c:
        c.execute(update(positions).where(positions.c.id == pid).values(
            symbol=p["symbol"].strip().upper(), exchange=p.get("exchange", "Binance"),
            side=p.get("side", "Long"), qty=float(p["qty"]), entry=float(p["entry"]),
            buy_date=p.get("buy_date"),
        ))


def delete_position(pid):
    with engine.begin() as c:
        c.execute(delete(positions).where(positions.c.id == pid))


# ---------- reserva (cash) ----------
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


# ---------- snapshots ----------
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
