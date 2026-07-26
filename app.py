"""
Mesa — Cuadro de mando del fondo (Streamlit).

Ejecutar:  streamlit run app.py
Comparte estado real entre socios cuando DATABASE_URL apunta a Postgres/Supabase.
Snapshots del historial: manuales (botón) o automáticos (GitHub Actions, viernes 6am ART).
"""
import datetime as dt

import pandas as pd
import streamlit as st

import db
import prices
import valuation

st.set_page_config(page_title="Mesa · Fondo", page_icon="◆", layout="wide")
db.init_db()

st.markdown("""
<style>
:root{--gold:#D9A84E;--pos:#4FC08D;--neg:#E86A72;}
.stApp{background:#0A0F1A;}
h1,h2,h3{font-family:'Space Grotesk',system-ui,sans-serif;letter-spacing:.01em;}
.block-container{padding-top:2.2rem;max-width:1280px;}
.mesa-eyebrow{font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:#5A6884;}
.mesa-cap{font-family:'Space Grotesk',sans-serif;font-size:44px;font-weight:600;
  color:#EAEFF7;font-variant-numeric:tabular-nums;line-height:1;margin:6px 0 2px;}
.mesa-cur{font-size:15px;color:#8493AE;margin-left:8px;}
.pos{color:#4FC08D;} .neg{color:#E86A72;}
hr{border-color:#1C2740;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def cached_prices(pairs):
    return prices.fetch_prices(list(pairs))


def money(n):
    return ("-" if n < 0 else "") + "$" + f"{abs(n):,.2f}"


def signed(n):
    return ("+" if n >= 0 else "−") + "$" + f"{abs(n):,.2f}"


# ---------- estado ----------
positions = db.get_positions()
cash = db.get_cash()
pairs = tuple(sorted({valuation.pair_of(p["symbol"]) for p in positions}))
price_full = cached_prices(pairs) if pairs else {}
pmap = {k: (v["price"] if v else None) for k, v in price_full.items()}
pf = valuation.portfolio(positions, pmap, cash)
snaps = db.get_snapshots()

# ---------- encabezado ----------
left, right = st.columns([3, 2], vertical_alignment="bottom")
with left:
    st.markdown('<div class="mesa-eyebrow">Mesa · Cuadro de mando del fondo</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="mesa-cap">{money(pf["capital"])}'
                f'<span class="mesa-cur">USDT · capital total</span></div>',
                unsafe_allow_html=True)
    cls = "pos" if pf["pnl"] >= 0 else "neg"
    st.markdown(f'<span class="{cls}">P&L no realizado {signed(pf["pnl"])} '
                f'· {pf["pnl_pct"]:+.2f}%</span> '
                f'<span style="color:#5A6884">· exposición {money(pf["exposure"])}</span>',
                unsafe_allow_html=True)
with right:
    c1, c2 = st.columns(2)
    c1.metric("Desplegado", money(pf["deployed"]),
              f'{(pf["deployed"]/pf["capital"]*100 if pf["capital"] else 0):.1f}% del fondo')
    c2.metric("Reserva", money(pf["reserve"]),
              f'{(pf["reserve"]/pf["capital"]*100 if pf["capital"] else 0):.1f}% del fondo')

st.divider()
tab_res, tab_pos, tab_hist = st.tabs(["Resumen", "Posiciones", "Historial"])

# ============================ RESUMEN ============================
with tab_res:
    if snaps:
        sdf = pd.DataFrame(snaps)
        sdf["ts"] = pd.to_datetime(sdf["ts"])
        sdf = sdf.sort_values("ts")
        latest = sdf.iloc[-1]
        prev = sdf.iloc[-2] if len(sdf) > 1 else None
        wk_ago = sdf[sdf["ts"] <= latest["ts"] - pd.Timedelta(days=7)]
        base7 = wk_ago.iloc[-1] if len(wk_ago) else sdf.iloc[0]
        mo_ago = sdf[sdf["ts"] <= latest["ts"] - pd.Timedelta(days=30)]
        base30 = mo_ago.iloc[-1] if len(mo_ago) else sdf.iloc[0]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Capital (último)", money(latest["capital"]))
        d7 = latest["capital"] - base7["capital"]
        m2.metric("Δ ~7 días", money(d7),
                  f'{(d7/base7["capital"]*100 if base7["capital"] else 0):+.2f}%')
        d30 = latest["capital"] - base30["capital"]
        m3.metric("Δ ~30 días", money(d30),
                  f'{(d30/base30["capital"]*100 if base30["capital"] else 0):+.2f}%')
        m4.metric("Rango histórico",
                  f'{money(sdf["capital"].min())} → {money(sdf["capital"].max())}')

        st.markdown("###### Evolución del capital del fondo")
        chart = sdf.set_index("ts")[["capital", "deployed", "reserve"]]
        chart.columns = ["Capital total", "Desplegado", "Reserva"]
        st.line_chart(chart, height=300, color=["#D9A84E", "#4F78C0", "#3A4763"])

        colw, colm = st.columns(2)
        with colw:
            st.markdown("###### Fluctuación semanal")
            wk = sdf.set_index("ts")["capital"].resample("W").last().dropna()
            wtab = pd.DataFrame({
                "Semana": wk.index.strftime("%Y-%m-%d"),
                "Capital": wk.values,
                "Δ": wk.diff().values,
                "Δ %": (wk.diff() / wk.shift(1) * 100).values,
            })
            st.dataframe(wtab.style.format(
                {"Capital": "${:,.0f}", "Δ": "${:,.0f}", "Δ %": "{:+.2f}%"}, na_rep="—"),
                use_container_width=True, hide_index=True)
        with colm:
            st.markdown("###### Fluctuación mensual")
            mo = sdf.set_index("ts")["capital"].resample("ME").last().dropna()
            mtab = pd.DataFrame({
                "Mes": mo.index.strftime("%Y-%m"),
                "Capital": mo.values,
                "Δ": mo.diff().values,
                "Δ %": (mo.diff() / mo.shift(1) * 100).values,
            })
            st.dataframe(mtab.style.format(
                {"Capital": "${:,.0f}", "Δ": "${:,.0f}", "Δ %": "{:+.2f}%"}, na_rep="—"),
                use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay snapshots. El tracking aparece cuando se registra el "
                "primer punto: generalo en la pestaña **Historial**, o esperá al "
                "snapshot automático del viernes.")

# ============================ POSICIONES ============================
with tab_pos:
    st.markdown("#### Reserva (capital sin invertir)")
    rc1, rc2 = st.columns([2, 3])
    new_cash = rc1.number_input("Efectivo / stablecoins (USDT)", value=float(cash),
                                min_value=0.0, step=100.0, label_visibility="collapsed")
    if rc2.button("Guardar reserva"):
        db.set_cash(new_cash)
        st.rerun()

    st.markdown("#### Posiciones abiertas")
    if positions:
        table = []
        for r in pf["rows"]:
            fut = r["market_type"] == "futures"
            priced = r["priced"]
            table.append({
                "Activo": r["symbol"],
                "Tipo": "Futuros" if fut else "Spot",
                "Lado": r["side"],
                "Cantidad": r["qty"],
                "Entrada": r["entry"],
                "Precio": r["mark"] if priced else None,
                "Apal": r.get("leverage") if fut else None,
                "Notional": r["notional"],
                "Margen": r.get("total_margin") if fut else None,
                "Valor": r["value"],
                "P&L": r["pnl"] if priced else None,
                "P&L% marg": r["pnl_pct"] if priced else None,
                "P&L% noc": r["pnl_pct_notional"] if priced else None,
                "Liq": r.get("liq_price") if fut else None,
                "Fecha": r.get("buy_date"),
            })
        tdf = pd.DataFrame(table)

        def color_pnl(v):
            if pd.isna(v):
                return ""
            return f'color:{"#4FC08D" if v >= 0 else "#E86A72"}'

        sty = tdf.style.format({
            "Cantidad": "{:,.6g}", "Entrada": "${:,.4g}", "Precio": "${:,.4g}",
            "Apal": "{:.0f}x", "Notional": "${:,.0f}", "Margen": "${:,.2f}",
            "Valor": "${:,.2f}", "P&L": "{:+,.2f}", "P&L% marg": "{:+.2f}%",
            "P&L% noc": "{:+.2f}%", "Liq": "${:,.4g}",
        }, na_rep="—").map(color_pnl, subset=["P&L", "P&L% marg", "P&L% noc"])
        st.dataframe(sty, use_container_width=True, hide_index=True)

        if not any(r["priced"] for r in pf["rows"]):
            st.warning("No se pudieron obtener precios de ninguna fuente. Reintentá en "
                       "un momento o verificá el símbolo (debe existir como SYMBOL/USDT).")
    else:
        st.caption("Sin posiciones cargadas.")

    # ---- alta / edición / borrado ----
    with st.expander("➕ Añadir o editar posición", expanded=not positions):
        opts = {0: "— Nueva posición —"}
        opts.update({p["id"]: f'#{p["id"]} · {p["symbol"]} '
                              f'{"FUT" if p.get("market_type")=="futures" else "SPOT"} {p["side"]}'
                     for p in positions})
        pid = st.selectbox("Registro a editar", list(opts), format_func=lambda k: opts[k])
        cur = next((p for p in positions if p["id"] == pid), None)

        exch_list = ["Binance", "BingX", "Bybit", "OKX", "Otro"]
        f1, f2, f3, f4 = st.columns(4)
        sym = f1.text_input("Activo", value=cur["symbol"] if cur else "")
        market = f2.selectbox("Tipo", ["Spot", "Futuros"],
                              index=1 if cur and cur.get("market_type") == "futures" else 0)
        exch = f3.selectbox("Exchange", exch_list,
                            index=exch_list.index(cur["exchange"])
                            if cur and cur["exchange"] in exch_list else 0)
        side = f4.selectbox("Lado", ["Long", "Short"],
                            index=0 if not cur or cur["side"] == "Long" else 1)

        g1, g2, g3 = st.columns(3)
        qty = g1.number_input("Cantidad", value=float(cur["qty"]) if cur else 0.0,
                              min_value=0.0, format="%.8f")
        entry = g2.number_input("Precio entrada (USDT)", value=float(cur["entry"]) if cur else 0.0,
                                min_value=0.0, format="%.6f")
        bdate = g3.date_input("Fecha de compra",
                              value=pd.to_datetime(cur["buy_date"]).date()
                              if cur and cur.get("buy_date") else dt.date.today())

        leverage, added_margin, liq_price = 1.0, 0.0, None
        if market == "Futuros":
            h1, h2, h3 = st.columns(3)
            leverage = h1.number_input("Apalancamiento (x)",
                                       value=float(cur["leverage"]) if cur and cur.get("leverage") else 1.0,
                                       min_value=1.0, step=1.0)
            added_margin = h2.number_input("Margen agregado (USDT)",
                                           value=float(cur["added_margin"]) if cur and cur.get("added_margin") else 0.0,
                                           min_value=0.0, step=50.0)
            liq_price = h3.number_input("Precio de liquidación (de BingX)",
                                        value=float(cur["liq_price"]) if cur and cur.get("liq_price") else 0.0,
                                        min_value=0.0, format="%.6f")
            if qty > 0 and entry > 0 and leverage > 0:
                notional = qty * entry
                st.caption(f"Notional: ${notional:,.2f}  ·  Margen inicial: "
                           f"${notional/leverage:,.2f}  ·  Margen total: "
                           f"${notional/leverage + added_margin:,.2f}")

        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Guardar", type="primary"):
            if sym.strip() and qty > 0 and entry > 0:
                payload = {
                    "symbol": sym, "exchange": exch, "side": side, "qty": qty, "entry": entry,
                    "buy_date": bdate.isoformat(),
                    "market_type": "futures" if market == "Futuros" else "spot",
                    "leverage": leverage, "added_margin": added_margin,
                    "liq_price": liq_price if (market == "Futuros" and liq_price > 0) else None,
                }
                db.update_position(pid, payload) if pid else db.add_position(payload)
                st.rerun()
            else:
                st.error("Activo, cantidad (>0) y precio de entrada (>0) son obligatorios.")
        if cur and b2.button("🗑 Eliminar"):
            db.delete_position(pid)
            st.rerun()

# ============================ HISTORIAL ============================
with tab_hist:
    hc1, hc2 = st.columns([1, 3])
    if hc1.button("📸 Registrar snapshot ahora", type="primary"):
        db.add_snapshot(pf)
        st.success(f"Snapshot guardado · capital {money(pf['capital'])}")
        st.rerun()
    hc2.caption("El snapshot automático corre por GitHub Actions todos los viernes "
                "a las 6:00 (Argentina). No requiere tener el tablero abierto.")

    if snaps:
        hdf = pd.DataFrame(snaps)[["ts", "capital", "deployed", "reserve", "pnl"]]
        hdf["ts"] = pd.to_datetime(hdf["ts"])
        hdf = hdf.sort_values("ts", ascending=False)
        st.dataframe(
            hdf.rename(columns={"ts": "Fecha (UTC)", "capital": "Capital",
                                "deployed": "Desplegado", "reserve": "Reserva", "pnl": "P&L"})
            .style.format({"Capital": "${:,.2f}", "Desplegado": "${:,.2f}",
                           "Reserva": "${:,.2f}", "P&L": "{:+,.2f}",
                           "Fecha (UTC)": lambda t: t.strftime("%Y-%m-%d %H:%M")}),
            use_container_width=True, hide_index=True)
    else:
        st.caption("Sin snapshots todavía.")
