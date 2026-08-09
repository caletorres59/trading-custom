# Aurora Trading MVP

Versión reducida en Python de la visión descrita en `spec.md`. No implementa
la plataforma completa (Java/Kafka/BigQuery/MLflow) — implementa el
principio que no es negociable: **ninguna estrategia puede ejecutar una
operación sin pasar por un Risk Engine determinístico** que no usa IA y que
nadie puede modificar en caliente.

## Cómo corre en producción (paper trading)

Un workflow de **GitHub Actions** (`.github/workflows/trading-loop.yml`)
despierta cada 5 minutos, ejecuta `python -m aurora.main --once` contra
datos reales de Binance, y guarda el resultado en una base **Postgres en
Supabase** (proyecto `aurora-trading-mvp`, región São Paulo). No hay ningún
servidor propio que mantener — GitHub se encarga del scheduling.

- Dispara manualmente desde la pestaña **Actions** del repo con "Run workflow"
  si quieres una corrida inmediata sin esperar el cron.
- Las credenciales de conexión viven en el secret `DATABASE_URL` del repo
  (Settings → Secrets and variables → Actions) — nunca en el código.
- GitHub apaga los workflows programados automáticamente si el repo pasa
  60 días sin actividad; si eso pasa, basta con reactivarlo desde Actions.

## Qué incluye

- `market_data`: klines públicos de Binance (sin API key).
- `strategy`: una estrategia base — cruce de medias móviles (SMA).
- `risk`: motor de riesgo duro, determinístico, con límites porcentuales
  (pérdida diaria máxima, drawdown máximo, exposición máxima, trades/día).
- `broker`: simulador de paper trading (fees incluidos), con su estado
  (caja, posiciones, equity pico, trades del día) persistido en la base de
  datos — así una ejecución "recuerda" lo que hizo la anterior, aunque cada
  corrida de GitHub Actions sea un proceso nuevo que se apaga al terminar.
- `db`: cada señal, decisión de riesgo, orden y evento de auditoría queda
  guardado con un `correlation_id` común, para poder responder "¿por qué se
  ejecutó esta operación?".

## Qué NO incluye todavía

- Conexión a Binance Testnet (matching engine real) — hoy es un simulador
  local, ver `paper_broker.py`.
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

1. Dejarlo correr varios días/semanas en GitHub Actions y revisar el estado
   del portafolio en Supabase (tabla `portfolio_state`) y el historial en
   `signals` / `risk_decisions` / `orders`.
2. Reemplazar el simulador por un broker conectado a Binance Testnet
   (misma interfaz `TradingBroker`, sin tocar el resto del sistema).
3. Calcular la distancia de stop con ATR en vez del valor fijo.
4. Agregar backtesting sobre datos históricos antes de confiar en la
   estrategia con dinero real, aunque sea de prueba.
