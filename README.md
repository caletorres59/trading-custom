# Aurora Trading MVP

Versión reducida en Python de la visión descrita en `spec.md`. No implementa
la plataforma completa (Java/Kafka/BigQuery/MLflow) — implementa el
principio que no es negociable: **ninguna estrategia puede ejecutar una
operación sin pasar por un Risk Engine determinístico** que no usa IA y que
nadie puede modificar en caliente.

Objetivo de esta primera versión: correr hoy, gratis, sin credenciales, con
datos reales de mercado y dinero simulado, para tener un loop completo
(datos → estrategia → riesgo → ejecución simulada → auditoría) antes de
agregar nada más.

## Qué incluye

- `market_data`: klines públicos de Binance (sin API key).
- `strategy`: una estrategia base — cruce de medias móviles (SMA).
- `risk`: motor de riesgo duro, determinístico, con límites porcentuales
  (pérdida diaria máxima, drawdown máximo, exposición máxima, trades/día).
- `broker`: simulador de paper trading en memoria (fees incluidos).
- `db`: SQLite por defecto — cada señal, decisión de riesgo, orden y evento
  de auditoría queda guardado con un `correlation_id` común, para poder
  responder "¿por qué se ejecutó esta operación?".

## Qué NO incluye todavía

- Conexión a Binance Testnet (matching engine real) — hoy es un simulador
  local, ver `paper_broker.py`.
- Agentes de ML/LLM/noticias/sentimiento del spec completo.
- `trades_today` se reinicia solo por ejecución del proceso, no por día
  calendario real (suficiente para pruebas cortas).
- Distancia de stop fija (1%) en vez de calculada por volatilidad (ATR).

## Setup

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

No necesitas ninguna API key para esta fase — los datos de mercado son
públicos y el broker es un simulador local.

## Correr los tests

```bash
pytest -q
```

## Correr una iteración

```bash
python -m aurora.main --once
```

Esto trae velas reales de BTCUSDT desde Binance, calcula la señal, la pasa
por el Risk Engine y, si se aprueba, simula la orden — todo se guarda en
`aurora.db` (SQLite).

## Correr en loop continuo

```bash
python -m aurora.main
```

Repite cada `loop_interval_seconds` (configurable en `config/config.yaml`).

## Base de datos: cambiar a Postgres (opcional, más adelante)

```bash
docker compose up -d
pip install -e ".[postgres]"
# en .env:
# DATABASE_URL=postgresql+psycopg2://aurora:aurora@localhost:5432/aurora
```

## Próximos pasos naturales

1. Validar que el pipeline corre limpio por varios días en modo simulador.
2. Reemplazar el simulador por un broker conectado a Binance Testnet
   (misma interfaz `TradingBroker`, sin tocar el resto del sistema).
3. Calcular la distancia de stop con ATR en vez del valor fijo.
4. Agregar backtesting sobre datos históricos antes de confiar en la
   estrategia con dinero real, aunque sea de prueba.
