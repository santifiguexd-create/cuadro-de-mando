"""
Valoración mark-to-market. Sin estado ni I/O: fácil de testear.

Regla clave del capital del fondo:
  - spot    -> aporta su valor de mercado (cantidad * precio).
  - futuros -> aporta MARGEN + PnL (no el notional). El notional es exposición,
               no capital propio; incluirlo infla el fondo. Con margen aislado,
               el capital en riesgo es el margen (inicial + agregado).
"""


def pair_of(symbol):
    s = (symbol or "").upper().replace(" ", "")
    return s if s.endswith("USDT") else s + "USDT"


def _pnl(side, qty, entry, price):
    return qty * (entry - price) if side == "Short" else qty * (price - entry)


def value_position(p, price):
    market = p.get("market_type", "spot") or "spot"
    side = p.get("side", "Long")
    qty, entry = p["qty"], p["entry"]
    notional = qty * entry

    if market == "futures":
        lev = p.get("leverage") or 1.0
        init_margin = notional / lev if lev else notional
        total_margin = init_margin + (p.get("added_margin") or 0.0)
        base = {
            "market_type": "futures", "notional": notional, "leverage": lev,
            "init_margin": init_margin, "added_margin": (p.get("added_margin") or 0.0),
            "total_margin": total_margin, "liq_price": p.get("liq_price"),
            "cost": total_margin,   # capital comprometido = margen
        }
        if price is None:
            base.update(value=total_margin, pnl=0.0, pnl_pct=0.0,
                        pnl_pct_notional=0.0, priced=False, mark=None)
            return base
        pnl = _pnl(side, qty, entry, price)
        base.update(
            value=total_margin + pnl, pnl=pnl,
            pnl_pct=(pnl / total_margin * 100 if total_margin else 0.0),   # sobre margen
            pnl_pct_notional=(pnl / notional * 100 if notional else 0.0),  # sobre notional
            priced=True, mark=price,
        )
        return base

    # spot
    base = {"market_type": "spot", "notional": notional, "leverage": 1.0,
            "cost": notional, "liq_price": None}
    if price is None:
        base.update(value=notional, pnl=0.0, pnl_pct=0.0,
                    pnl_pct_notional=0.0, priced=False, mark=None)
        return base
    pnl = _pnl(side, qty, entry, price)
    base.update(
        value=qty * price, pnl=pnl,
        pnl_pct=(pnl / notional * 100 if notional else 0.0),
        pnl_pct_notional=(pnl / notional * 100 if notional else 0.0),
        priced=True, mark=price,
    )
    return base


def portfolio(positions, price_map, cash):
    rows, deployed, pnl, cost_total, exposure = [], 0.0, 0.0, 0.0, 0.0
    for p in positions:
        v = value_position(p, price_map.get(pair_of(p["symbol"])))
        rows.append({**p, **v})
        deployed += v["value"]
        pnl += v["pnl"]
        cost_total += v["cost"]
        exposure += v.get("notional", 0.0)
    capital = deployed + cash
    return {
        "rows": rows, "deployed": deployed, "reserve": cash, "capital": capital,
        "pnl": pnl, "cost": cost_total, "exposure": exposure,
        "pnl_pct": (pnl / cost_total * 100 if cost_total else 0.0),
    }

