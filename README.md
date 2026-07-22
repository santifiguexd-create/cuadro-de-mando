# Mesa — Cuadro de mando del fondo

Dashboard en Python (Streamlit) con base de datos y snapshots automáticos.
Resuelve las tres cosas que un HTML no puede:

1. **Estado persistente y compartido** — vos y tu socio ven los mismos datos, sin recargar nada a mano (base de datos común).
2. **Tracking histórico** — cada snapshot guarda el capital total; el dashboard grafica la variación y la fluctuación semanal.
3. **Cuadro de mando real** — capital total, desplegado vs reserva, P&L por posición y curva de capital.

## Componentes

| Archivo | Rol |
|---|---|
| `app.py` | Cuadro de mando (Streamlit) |
| `snapshot.py` | Recorder de snapshots, agendable por cron |
| `db.py` | Capa de datos (SQLite por defecto, Postgres/Supabase para compartir) |
| `valuation.py` | Valoración mark-to-market (long/short) |
| `prices.py` | Precios de Binance público |

## Correr en local (un solo equipo)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Usa `mesa_fund.db` (SQLite). Sirve para probarlo ya. **No** comparte estado entre dos personas.

## Compartido entre vos y tu socio (recomendado)

El estado compartido necesita una base de datos común y un hosting siempre disponible.
La ruta más simple, sin servidor propio:

1. **Base de datos:** creá un Postgres gratis en [Supabase](https://supabase.com) y copiá su connection string.
2. **Variable de entorno:**
   ```bash
   export DATABASE_URL="postgresql+psycopg://USER:PASS@HOST:5432/postgres"
   ```
   (agregá `psycopg[binary]` a las dependencias).
3. **Hosting del dashboard:** subí el repo a GitHub y desplegalo en
   [Streamlit Community Cloud](https://streamlit.io/cloud) (gratis). Cargá `DATABASE_URL`
   como *secret*. Ambos entran por la misma URL y ven lo mismo.

## Tracking semanal automático

El gráfico se alimenta de la tabla `snapshots`. Para que se llene solo, agendá el recorder:

**cron (lunes 00:05 UTC):**
```
5 0 * * 1  cd /ruta/mesa-fund && DATABASE_URL="..." /usr/bin/python3 snapshot.py >> snapshot.log 2>&1
```

**GitHub Actions** (no depende de tu máquina) — `.github/workflows/snapshot.yml`:
```yaml
on:
  schedule: [{ cron: "5 0 * * 1" }]   # lunes 00:05 UTC
jobs:
  snap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt psycopg[binary]
      - run: python snapshot.py
        env: { DATABASE_URL: ${{ secrets.DATABASE_URL }} }
```

También podés registrar un snapshot a mano desde la pestaña **Historial** del dashboard.

## Encaje con el sistema del fondo

`DATABASE_URL` puede apuntar al **mismo Postgres** que uses en Fase 2/3. Cuando la
ingesta automatizada exponga posiciones/balances, el recorder puede leer de ahí en
lugar de la carga manual, y este dashboard queda como capa de visualización del fondo.

Denominación en USDT. Los perps se valoran con el mark de Binance como proxy; si
necesitás el mark exacto de BingX, se ajusta en `prices.py`.
