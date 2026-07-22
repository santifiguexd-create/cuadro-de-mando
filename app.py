"""
Mesa — Cuadro de mando del fondo (Streamlit).

Ejecutar:
    streamlit run app.py

Comparte estado real entre vos y tu socio cuando DATABASE_URL apunta a un
Postgres/Supabase común. El gráfico de capital se alimenta de la tabla
`snapshots`, que llena snapshot.py de forma programada (ver README).
"""
import datetime as dt

import pandas as pd
import streamlit as st

import db
import prices
import valuation

st.set_page_config(page_title="Mesa · Fondo", page_icon="◆", layout="wide")
db.init_db()

# ---------- estilo (cuadro de mando oscuro / oro tesorería) ----------
st.markdown("""
<style>
:root{--gold:#D9A84E;--pos:#4FC08D;--neg:#E86A72;}
.stApp{background:#0A0F1A;}
h1,h2,h3{font-family:'Space Grotesk',system-ui,sans-serif;letter-spacing:.01em;}
[data-testid="stMetricValue"]{font-variant-numeric:tabular-nums;}
.block-container{padding-top:2.2rem;max-width:1200px;}
.mesa-eyebrow{font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:#5A6884;}
.mesa-cap{font-family:'Space Grotesk',sans-serif;font-size:46px;font-weight:600;
  color:#EAEFF7;font-variant-numeric:tabular-nums;line-height:1;margin:6px 0 2px;}
.mesa-cur{font-size:16px;color:#8493AE;margin-left:8px;}
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


# ---------- carga de estado ----------
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
                f'· {pf["pnl_pct"]:+.2f}%</span>', unsafe_allow_html=True)
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

        # variación vs snapshot anterior y vs ~7 días atrás
        prev = sdf.iloc[-2] if len(sdf) > 1 else None
        wk_ago = sdf[sdf["ts"] <= latest["ts"] - pd.Timedelta(days=7)]
        base7 = wk_ago.iloc[-1] if len(wk_ago) else (sdf.iloc[0] if len(sdf) else None)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Capital (último snapshot)", money(latest["capital"]))
        if prev is not None:
            d = latest["capital"] - prev["capital"]
            m2.metric("Δ vs snapshot previo", money(d),
                      f'{(d/prev["capital"]*100 if prev["capital"] else 0):+.2f}%')
        if base7 is not None:
            d7 = latest["capital"] - base7["capital"]
            m3.metric("Δ ~7 días", money(d7),
                      f'{(d7/base7["capital"]*100 if base7["capital"] else 0):+.2f}%')
        m4.metric("Rango histórico",
                  f'{money(sdf["capital"].min())} → {money(sdf["capital"].max())}')

        st.markdown("###### Evolución del capital del fondo")
        chart = sdf.set_index("ts")[["capital", "deployed", "reserve"]]
        chart.columns = ["Capital total", "Desplegado", "Reserva"]
        st.line_chart(chart, height=320, color=["#D9A84E", "#4F78C0", "#3A4763"])

        st.markdown("###### Fluctuación semanal")
        wk = sdf.set_index("ts")["capital"].resample("W").last().dropna()
        wk_delta = wk.diff()
        wtab = pd.DataFrame({
            "Semana": wk.index.strftime("%Y-%m-%d"),
            "Capital": wk.values,
            "Δ semana": wk_delta.values,
            "Δ %": (wk_delta / wk.shift(1) * 100).values,
        })
        st.dataframe(
            wtab.style.format({"Capital": "${:,.0f}", "Δ semana": "${:,.0f}", "Δ %": "{:+.2f}%"}),
            use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay snapshots. El tracking semanal aparece cuando el "
                "recorder registra el primer punto. Podés generar uno ahora en la "
                "pestaña **Historial** o agendar `snapshot.py` (ver README).")

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
            table.append({
                "Activo": r["symbol"], "Exch": r["exchange"], "Lado": r["side"],
                "Cantidad": r["qty"], "Entrada": r["entry"],
                "Precio actual": r["mark"] if r["priced"] else None,
                "Costo": r["cost"], "Valor": r["value"],
                "P&L": r["pnl"] if r["priced"] else None,
                "P&L %": r["pnl_pct"] if r["priced"] else None,
                "Fecha": r.get("buy_date"),
            })
        tdf = pd.DataFrame(table)
        st.dataframe(
            tdf.style.format({
                "Cantidad": "{:,.6g}", "Entrada": "${:,.2f}", "Precio actual": "${:,.2f}",
                "Costo": "${:,.2f}", "Valor": "${:,.2f}", "P&L": "{:+,.2f}", "P&L %": "{:+.2f}%",
            }, na_rep="—").map(
                lambda v: f'color:{"#4FC08D" if v >= 0 else "#E86A72"}' if isinstance(v, (int, float)) else "",
                subset=["P&L", "P&L %"]),
            use_container_width=True, hide_index=True)
        if not any(r["priced"] for r in pf["rows"]):
            st.warning("No se pudieron obtener precios de Binance. Verificá conexión "
                       "o el símbolo del par (debe existir como SYMBOL/USDT).")
    else:
        st.caption("Sin posiciones cargadas.")

    # alta / edición / borrado
    with st.expander("➕ Añadir o editar posición", expanded=not positions):
        opts = {0: "— Nueva posición —"}
        opts.update({p["id"]: f'#{p["id"]} · {p["symbol"]} {p["side"]}' for p in positions})
        pid = st.selectbox("Registro", list(opts), format_func=lambda k: opts[k])
        cur = next((p for p in positions if p["id"] == pid), None)

        f1, f2, f3 = st.columns(3)
        sym = f1.text_input("Activo", value=cur["symbol"] if cur else "")
        exch = f2.selectbox("Exchange", ["Binance", "BingX", "Bybit", "OKX", "Otro"],
                            index=(["Binance", "BingX", "Bybit", "OKX", "Otro"].index(cur["exchange"])
                                   if cur and cur["exchange"] in ["Binance", "BingX", "Bybit", "OKX", "Otro"] else 0))
        side = f3.selectbox("Lado", ["Long", "Short"],
                            index=0 if not cur or cur["side"] == "Long" else 1)
        g1, g2, g3 = st.columns(3)
        qty = g1.number_input("Cantidad", value=float(cur["qty"]) if cur else 0.0,
                              min_value=0.0, format="%.8f")
        entry = g2.number_input("Precio entrada (USDT)", value=float(cur["entry"]) if cur else 0.0,
                                min_value=0.0, format="%.6f")
        bdate = g3.date_input("Fecha de compra",
                              value=pd.to_datetime(cur["buy_date"]).date()
                              if cur and cur.get("buy_date") else dt.date.today())

        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Guardar", type="primary"):
            if sym.strip() and qty > 0 and entry > 0:
                payload = {"symbol": sym, "exchange": exch, "side": side,
                           "qty": qty, "entry": entry, "buy_date": bdate.isoformat()}
                db.update_position(pid, payload) if pid else db.add_position(payload)
                st.rerun()
            else:
                st.error("Activo, cantidad (>0) y precio de entrada (>0) son obligatorios.")
        if cur and b2.button("Eliminar"):
            db.delete_position(pid)
            st.rerun()

# ============================ HISTORIAL ============================
with tab_hist:
    hc1, hc2 = st.columns([1, 3])
    if hc1.button("📸 Registrar snapshot ahora", type="primary"):
        db.add_snapshot(pf)
        st.success(f"Snapshot guardado · capital {money(pf['capital'])}")
        st.rerun()
    hc2.caption("Para el tracking automático, agendá `snapshot.py` semanalmente "
                "(cron / GitHub Actions). No requiere tener el dashboard abierto.")

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
