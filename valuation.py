"""Valoración mark-to-market. Sin estado ni I/O: fácil de testear."""


def pair_of(symbol):
    s = (symbol or "").upper().replace(" ", "")
    return s if s.endswith("USDT") else s + "USDT"


def value_position(p, price):
    """Devuelve costo, valor actual y P&L de una posición.

    Long : pnl = qty*(precio - entrada)
    Short: pnl = qty*(entrada - precio) ; valor = costo + pnl (equity mark-to-market)
    """
    cost = p["qty"] * p["entry"]
    if price is None:
        return {"cost": cost, "value": cost, "pnl": 0.0, "pnl_pct": 0.0,
                "priced": False, "mark": None}
    notional = p["qty"] * price
    if p["side"] == "Short":
        pnl = cost - notional
        value = cost + pnl
    else:
        pnl = notional - cost
        value = notional
    return {"cost": cost, "value": value, "pnl": pnl,
            "pnl_pct": (pnl / cost * 100 if cost else 0.0),
            "priced": True, "mark": price}


def portfolio(positions, price_map, cash):
    """Agrega todas las posiciones + reserva en el estado del fondo."""
    rows, deployed, pnl, cost_total = [], 0.0, 0.0, 0.0
    for p in positions:
        v = value_position(p, price_map.get(pair_of(p["symbol"])))
        rows.append({**p, **v})
        deployed += v["value"]
        pnl += v["pnl"]
        cost_total += v["cost"]
    capital = deployed + cash
    return {
        "rows": rows,
        "deployed": deployed,
        "reserve": cash,
        "capital": capital,
        "pnl": pnl,
        "cost": cost_total,
        "pnl_pct": (pnl / cost_total * 100 if cost_total else 0.0),
    }
