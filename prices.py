"""Precios de mercado desde el endpoint público de Binance (server-side)."""
import requests

BINANCE_24H = "https://api.binance.com/api/v3/ticker/24hr"


def fetch_prices(symbols, timeout=8):
    """{ 'BTCUSDT': {'price': float, 'chg': float} | None }"""
    out = {}
    for s in sorted(set(symbols)):
        try:
            r = requests.get(BINANCE_24H, params={"symbol": s}, timeout=timeout)
            r.raise_for_status()
            d = r.json()
            out[s] = {"price": float(d["lastPrice"]), "chg": float(d["priceChangePercent"])}
        except Exception:
            out[s] = None
    return out


def price_map(symbols):
    """{ 'BTCUSDT': price | None } — lo que consume valuation.portfolio()."""
    return {k: (v["price"] if v else None) for k, v in fetch_prices(symbols).items()}
