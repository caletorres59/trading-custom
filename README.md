# Aurora Trading MVP

Versión reducida en Python de la visión descrita en `spec.md`. No implementa
la plataforma completa (Java/Kafka/BigQuery/MLflow) — implementa el
principio que no es negociable: **ninguna estrategia puede ejecutar una
operación sin pasar por un Risk Engine determinístico** que no usa IA y que
nadie puede modificar en caliente.

## Cómo corre en producción (paper trading)

Un workflow de **GitHub Actions** (`.github/workflows/trading-loop.yml`)
ejecuta `python -m aurora.main --once` contra datos reales de Coinbase cada
vez que se dispara, y guarda el resultado en una base **Postgres en
Supabase** (proyecto `aurora-trading-mvp`, región São Paulo).

**El disparo cada 5 minutos lo hace Supabase (`pg_cron` + `pg_net`), no el
`schedule` nativo de GitHub Actions.** Se probó primero con `schedule` y
resultó poco confiable para este repo (nunca se activó solo durante más de
una hora, con todo bien configurado — un problema conocido de GitHub para
workflows programados nuevos). Ahora un cron job en Supabase
(`aurora-trigger-github-actions`, cada 5 min) llama a la API de GitHub
(`workflow_dispatch`) usando un token de acceso de alcance mínimo (solo
`Actions: read/write` en este repo) guardado en el **Vault de Supabase**.
El archivo del workflow solo declara `workflow_dispatch: {}`.

- Dispara manualmente desde la pestaña **Actions** del repo con "Run workflow"
  si quieres una corrida inmediata.
- Las credenciales viven en secrets del repo (Settings → Secrets and
  variables → Actions) — nunca en el código: `DATABASE_URL` (Postgres) y
  `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` (cuenta paper de Alpaca).
- El cron job y el token viven en Supabase, no en GitHub — para revisarlos:
  SQL Editor → `select * from cron.job;` / `cron.job_run_details`.

## Qué incluye

- `market_data`: klines públicos de Coinbase Exchange (sin API key). Se
  eligió Coinbase y no Binance porque Binance bloquea las conexiones desde
  IPs de datacenters de EE.UU. — incluidas las de los runners de GitHub
  Actions — por restricción de jurisdicción en sus términos de servicio.
- `strategy`: una estrategia base — cruce de medias móviles (SMA).
- `risk`: motor de riesgo duro, determinístico, con límites porcentuales
  (pérdida diaria máxima, drawdown máximo, exposición máxima, trades/día).
- `broker`: **ejecución en vivo contra Alpaca** (`AlpacaBroker`, cuenta
  paper — dinero simulado, infraestructura real). Órdenes, caja, posiciones
  y equity son el estado real de Alpaca. Solo el `peak_equity` con reinicio
  y el ancla de equity de inicio-de-día (que necesita el Risk Engine y que
  Alpaca no expone) se guardan en `portfolio_state`, junto con un espejo de
  la caja/posiciones para el dashboard. Cripto spot no se puede poner en
  corto: una señal SHORT solo reduce un largo existente (`execution.allow_short`).
  El `PaperSimulatorBroker` (simulador con fills propios) ahora solo lo usa
  el backtest.
- `db`: cada señal, decisión de riesgo, orden y evento de auditoría queda
  guardado con un `correlation_id` común, para poder responder "¿por qué se
  ejecutó esta operación?". `equity_history` guarda un snapshot por
  ejecución para poder graficar el equity en el tiempo.
- `backtest`: motor de backtest (`python -m aurora.backtest --days N`) que
  reproduce el mismo pipeline Strategy → HardRiskEngine → PaperSimulatorBroker
  de la app en vivo contra datos históricos reales de Coinbase (paginados,
  hasta 300 velas por request). Resultado del primer backtest (90 días,
  BTC-USD 5m, config actual): **-0.53% total / -0.18% mensual promedio**,
  628 operaciones, drawdown máximo 0.61%. La estrategia queda prácticamente
  en tablas antes de comisiones — lo que la hunde son las comisiones de
  operar tan seguido en mercado lateral (confianza de señal casi siempre
  ~0.00-0.01). Próximo experimento: filtrar señales por confianza mínima
  para reducir el "whipsaw" y volver a correr el backtest.
- `dashboard/`: app Next.js desplegada en Vercel
  (https://dashboard-ten-coral-49.vercel.app) que se conecta a Supabase con
  una llave pública de solo lectura (RLS) y usa Supabase Realtime para
  actualizarse sola — equity curve, señales, decisiones de riesgo, órdenes,
  contador de ejecuciones totales.

## Qué NO incluye todavía

- Conexión a un exchange real en modo testnet/sandbox (matching engine
  real) — hoy es un simulador local, ver `paper_broker.py`. Al elegir cuál,
  hay que verificar primero que ese testnet también sea accesible desde las
  IPs de GitHub Actions (el mismo problema que ya nos pasó con la API de
  datos de Binance).
- Agentes de ML/LLM/noticias/sentimiento del spec completo.
- Distancia de stop fija (1%) en vez de calculada por volatilidad (ATR).

## Desarrollo local

Local usa **SQLite por defecto** (`aurora.db`), separado a propósito de la
base de Supabase que usa producción — así las pruebas locales no pisan el
estado real del portafolio que corre en GitHub Actions.

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

No necesitas ninguna API key para esta fase — los datos de mercado son
públicos y el broker es un simulador local.

### Tests

```bash
pytest -q
```

### Una iteración

```bash
python -m aurora.main --once
```

### Loop continuo

```bash
python -m aurora.main
```

Repite cada `loop_interval_seconds` (configurable en `config/config.yaml`).

## Base de datos

- **Local**: SQLite (`sqlite:///./aurora.db`), cero configuración.
- **Producción**: Postgres en Supabase, vía `DATABASE_URL` (session pooler,
  compatible con las redes IPv4 de GitHub Actions). Si algún día quieres
  correr Postgres en tu máquina en vez de Supabase, `docker-compose.yml`
  levanta uno local; `psycopg2-binary` ya está entre las dependencias base.

## Próximos pasos naturales

1. Agregar un filtro de confianza mínima a `SmaCrossoverStrategy` para
   descartar señales de ruido (la mayoría de las 628 operaciones del primer
   backtest tuvieron confianza ~0.00-0.01) y volver a correr el backtest
   para ver si mejora el -0.18%/mes actual.
2. Dejarlo correr varios días/semanas y revisar el estado real del
   portafolio en Supabase (`portfolio_state`, `equity_history`) y en el
   dashboard.
3. Reemplazar el simulador por un broker conectado a un testnet real
   (misma interfaz `TradingBroker`, sin tocar el resto del sistema) —
   verificar primero que ese testnet sea accesible desde las IPs de GitHub
   Actions (mismo problema que tuvimos con la API de datos de Binance).
4. Calcular la distancia de stop con ATR en vez del valor fijo (1%).
5. Checklist de "listo para dinero real" (ver memoria del proyecto): backtest
   rentable, 30+ días corridos sin fallas, 20-30 operaciones reales,
   drawdown real dentro del límite configurado — recién ahí, con aprobación
   manual, no antes.
