"""
Precios de mercado con múltiples fuentes y respaldo automático.

Binance bloquea las consultas provenientes de servidores en EE.UU. (donde corre
Streamlit Cloud), por eso se consultan varias fuentes en orden hasta obtener
respuesta:

    1. Binance Data (data-api.binance.vision) — espejo público de datos
    2. Bybit
    3. OKX
    4. Binance (endpoint original, funciona bien en local)

Todas son APIs públicas de solo lectura: no requieren clave ni tocan cuentas.
"""
import requests

TIMEOUT = 8


def _binance_vision(base):
    r = requests.get("https://data-api.binance.vision/api/v3/ticker/24hr",
                     params={"symbol": base + "USDT"}, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return {"price": float(d["lastPrice"]), "chg": float(d["priceChangePercent"])}


def _bybit(base):
    r = requests.get("https://api.bybit.com/v5/market/tickers",
                     params={"category": "spot", "symbol": base + "USDT"}, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    item = d["result"]["list"][0]
    return {"price": float(item["lastPrice"]),
            "chg": float(item.get("price24hPcnt", 0)) * 100}


def _okx(base):
    r = requests.get("https://www.okx.com/api/v5/market/ticker",
                     params={"instId": f"{base}-USDT"}, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    item = d["data"][0]
    last, open24 = float(item["last"]), float(item["open24h"])
    chg = ((last - open24) / open24 * 100) if open24 else 0.0
    return {"price": last, "chg": chg}


def _binance(base):
    r = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                     params={"symbol": base + "USDT"}, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return {"price": float(d["lastPrice"]), "chg": float(d["priceChangePercent"])}


SOURCES = [
    ("binance-data", _binance_vision),
    ("bybit", _bybit),
    ("okx", _okx),
    ("binance", _binance),
]


def fetch_one(symbol):
    """Precio de un activo probando cada fuente hasta que alguna responda."""
    base = (symbol or "").upper().replace(" ", "")
    if base.endswith("USDT"):
        base = base[:-4]
    for name, fn in SOURCES:
        try:
            out = fn(base)
            if out and out.get("price"):
                out["source"] = name
                return out
        except Exception:
            continue
    return None


def fetch_prices(symbols, timeout=TIMEOUT):
    """{ 'BTCUSDT': {'price': float, 'chg': float, 'source': str} | None }"""
    out = {}
    for s in sorted(set(symbols)):
        out[s] = fetch_one(s)
    return out


def price_map(symbols):
    """{ 'BTCUSDT': price | None } — lo que consume valuation.portfolio()."""
    return {k: (v["price"] if v else None) for k, v in fetch_prices(symbols).items()}
