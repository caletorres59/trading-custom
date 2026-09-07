# AURORA TRADING AI

## Autonomous Multi-Agent Quantitative Trading Platform

### Product & Technical Specification — v1.0

---

# 1. VISIÓN DEL PRODUCTO

Construir una plataforma autónoma de trading capaz de:

1. Recibir datos de mercado en tiempo real.
2. Procesar datos históricos y en streaming.
3. Analizar múltiples variables simultáneamente.
4. Detectar el régimen actual del mercado.
5. Ejecutar múltiples estrategias independientes.
6. Utilizar modelos estadísticos y Machine Learning.
7. Utilizar LLMs para interpretar información no estructurada.
8. Combinar las señales de múltiples agentes.
9. Estimar probabilidad, retorno esperado y riesgo.
10. Optimizar el tamaño de las posiciones.
11. Rechazar operaciones de baja calidad.
12. Ejecutar operaciones solamente cuando el Risk Engine las autorice.
13. Aprender de las operaciones históricas.
14. Detectar degradación de modelos.
15. Detenerse automáticamente ante condiciones peligrosas.
16. Operar inicialmente en Backtest y Paper Trading.
17. Solo permitir Live Trading después de superar criterios objetivos.

## PRINCIPIO FUNDAMENTAL

El sistema NO debe intentar maximizar operaciones.

Debe maximizar:

> Risk-adjusted expected return while preserving capital.

La plataforma debe considerar:

> NO TRADE

como una decisión válida.

---

# 2. REGLAS FUNDAMENTALES DEL SISTEMA

## Regla 1 — La IA nunca controla directamente el broker

Ningún LLM, agente o modelo ML puede enviar órdenes directamente.

Arquitectura obligatoria:

Market Data
→ Feature Engine
→ Agents
→ Signal Engine
→ Portfolio Engine
→ Risk Engine
→ Execution Engine
→ Broker

El Risk Engine es una barrera obligatoria.

---

## Regla 2 — El Risk Engine tiene autoridad absoluta

Aunque todos los modelos indiquen BUY:

si el Risk Engine dice REJECTED,

NO SE EJECUTA.

---

## Regla 3 — Ningún modelo puede cambiar sus propios límites de riesgo

Los siguientes valores deben estar protegidos:

* Maximum daily loss
* Maximum drawdown
* Maximum position
* Maximum portfolio exposure
* Maximum leverage
* Maximum number of trades
* Maximum correlated exposure
* Emergency stop

---

## Regla 4 — Primero demostrar ventaja estadística

Antes de dinero real:

1. Backtest
2. Walk-forward
3. Out-of-sample
4. Monte Carlo
5. Paper Trading
6. Live con capital mínimo
7. Escalamiento progresivo

---

# 3. MERCADO INICIAL

La arquitectura debe ser multi-market, pero la primera implementación debe utilizar:

## Mercado inicial recomendado

CRYPTO SPOT / PERPETUALS

Razones:

* Mercado 24/7
* APIs accesibles
* Datos abundantes
* Fácil paper trading
* Alta liquidez en principales activos
* Excelente entorno para experimentar

Primera versión:

BTC
ETH

Posteriormente:

SOL
BNB
XRP
y otros activos líquidos.

La arquitectura debe permitir agregar:

* Stocks
* ETFs
* Forex
* Futures

sin modificar el core.

---

# 4. STACK TECNOLÓGICO

## Backend principal

Java 21+

Spring Boot

Spring WebFlux

Project Reactor

Jackson

Lombok opcional

Gradle

JUnit 5

Testcontainers

ArchUnit

Resilience4j

---

# 5. ARQUITECTURA DE SOFTWARE

Inicialmente utilizar:

## Modular Monolith + Event Driven Architecture

NO comenzar con microservicios.

Módulos:

```text
aurora/
├── market-data
├── data-platform
├── feature-engine
├── strategy-engine
├── agent-engine
├── signal-engine
├── portfolio-engine
├── risk-engine
├── execution-engine
├── backtest-engine
├── ml-platform
├── news-engine
├── model-registry
├── monitoring
├── notification
└── api
```

Posteriormente los módulos que necesiten escalabilidad pueden convertirse en servicios independientes.

---

# 6. PYTHON

Python se utilizará para:

* Quant research
* Data Science
* ML
* Deep Learning
* Backtesting experimental
* Feature engineering experimental
* Model training

Stack:

```text
Python 3.12+

pandas
numpy
scipy
scikit-learn
xgboost
lightgbm
PyTorch
statsmodels
Optuna
MLflow
Jupyter
```

Python NO debe ejecutar órdenes de trading directamente.

---

# 7. DATABASE STACK

## PostgreSQL

Información transaccional:

```text
users
accounts
strategies
models
orders
fills
positions
trades
risk_events
signals
configuration
audit_events
```

---

## Redis

Datos de baja latencia:

* Current prices
* Current positions
* Current exposure
* Feature cache
* Risk state
* Distributed locks
* Temporary state

---

## Object Storage

AWS S3.

Guardar:

* Raw market data
* Historical datasets
* Model artifacts
* Backtest results
* Training datasets
* Reports

---

## BigQuery

Analytics:

```text
market_history
features
signals
trades
model_predictions
model_performance
risk_metrics
portfolio_metrics
```

Ideal para análisis histórico y reporting.

---

# 8. EVENT STREAMING

Primera opción:

Kafka.

Alternativa cloud:

AWS MSK / Kinesis.

Eventos:

```text
MarketTick
CandleClosed
OrderBookUpdated
FeatureUpdated
SignalGenerated
RiskEvaluated
OrderCreated
OrderSubmitted
OrderFilled
OrderRejected
PositionChanged
TradeClosed
RiskLimitBreached
ModelPrediction
NewsEvent
```

Todos los eventos deben tener:

```text
eventId
eventType
timestamp
source
correlationId
version
payload
```

---

# 9. MARKET DATA ENGINE

Responsabilidades:

* WebSocket
* REST
* Historical data
* Candles
* Trades
* Volume
* Order book
* Funding
* Open interest
* Volatility
* Market depth

Normalizar todo a un modelo interno.

Ejemplo:

```java
public record MarketTick(
    String symbol,
    Instant timestamp,
    BigDecimal price,
    BigDecimal volume
) {}
```

Nunca acoplar el core a un proveedor.

Crear:

```text
MarketDataProvider
```

Implementaciones:

```text
ExchangeAProvider
ExchangeBProvider
HistoricalProvider
PaperProvider
ReplayProvider
```

---

# 10. DATA QUALITY ENGINE

Antes de utilizar cualquier dato:

validar:

* Timestamp
* Duplicados
* Gaps
* Outliers
* Missing candles
* Invalid prices
* Invalid volume
* Timezone
* Sequence

Si la calidad no es suficiente:

```text
DATA_QUALITY_FAILED
```

y el sistema no debe operar con esos datos.

---

# 11. FEATURE ENGINE

Transformar raw market data en variables cuantificables.

## Technical Features

* SMA
* EMA
* RSI
* MACD
* ATR
* ADX
* Bollinger Bands
* VWAP
* Momentum
* Rate of Change

## Volatility

* Realized volatility
* ATR volatility
* Implied volatility si está disponible
* Volatility regime
* Volatility expansion
* Volatility contraction

## Volume

* Volume momentum
* Relative volume
* Volume imbalance
* OBV

## Market Structure

* Higher highs
* Lower lows
* Breakouts
* Support
* Resistance
* Trend strength

## Order Book

* Bid/ask imbalance
* Spread
* Depth
* Liquidity
* Microprice

## Cross Asset

* BTC correlation
* ETH correlation
* Dollar correlation
* Risk asset correlation
* Market beta

---

# 12. AGENTES DEL SISTEMA

El sistema tendrá múltiples agentes especializados.

Cada agente debe ser independiente.

---

# AGENT 1 — TECHNICAL ANALYST

Objetivo:

Analizar estructura técnica.

Inputs:

* OHLCV
* Indicators
* Market structure
* Volume
* Momentum

Output:

```json
{
  "agent": "technical",
  "direction": "LONG",
  "confidence": 0.81,
  "strength": 0.72,
  "reasonCodes": [
    "TREND_ALIGNMENT",
    "MOMENTUM_POSITIVE"
  ]
}
```

---

# AGENT 2 — TREND AGENT

Analiza:

* Trend
* Momentum
* Breakouts
* Moving averages
* Multi-timeframe confirmation

Timeframes:

```text
5m
15m
1h
4h
1d
```

Debe evitar depender de una sola temporalidad.

---

# AGENT 3 — MEAN REVERSION AGENT

Busca:

* Overextension
* Statistical deviation
* Bollinger extremes
* RSI extremes
* Mean reversion probability

No debe operar contra tendencias fuertes sin confirmación.

---

# AGENT 4 — VOLATILITY AGENT

Evalúa:

* Volatility regime
* Volatility expansion
* Volatility contraction
* ATR
* Realized volatility
* Abnormal movements

Output:

```json
{
  "regime": "HIGH_VOLATILITY",
  "riskMultiplier": 0.45
}
```

---

# AGENT 5 — MARKET REGIME AGENT

Clasifica el mercado.

Estados:

```text
STRONG_BULL
BULL
SIDEWAYS
BEAR
STRONG_BEAR
HIGH_VOLATILITY
PANIC
UNKNOWN
```

Este agente puede utilizar:

* Hidden Markov Models
* Clustering
* ML
* Volatility
* Trend
* Correlations

Si:

```text
UNKNOWN
```

el sistema reduce riesgo o no opera.

---

# AGENT 6 — STATISTICAL AGENT

No intenta “adivinar”.

Calcula:

* Expected return
* Probability of positive outcome
* Distribution of returns
* Historical conditional probability
* Expectancy

Ejemplo:

```text
Probability win: 63%
Average win: +1.8%
Average loss: -1.0%

Expected value:
0.63 × 1.8 - 0.37 × 1.0
```

El resultado alimenta el Signal Engine.

---

# AGENT 7 — MACHINE LEARNING AGENT

Modelos iniciales:

XGBoost
LightGBM
Random Forest

Posteriormente:

PyTorch
LSTM
Temporal models
Transformers

Input:

features

Output:

```text
P(up)
P(down)
expected_return
expected_volatility
```

Nunca utilizar accuracy como métrica principal.

Evaluar:

* Precision
* Recall
* ROC AUC
* Calibration
* Brier score
* Expected value
* Trading performance

---

# AGENT 8 — NEWS AGENT

Recibe noticias.

Pipeline:

```text
News
 ↓
Deduplication
 ↓
Entity extraction
 ↓
Event classification
 ↓
Sentiment
 ↓
Impact estimation
 ↓
Market signal
```

Tipos:

```text
MACRO
REGULATORY
EARNINGS
INTEREST_RATE
INFLATION
GEOPOLITICAL
EXCHANGE
SECURITY
TECHNOLOGY
OTHER
```

---

# AGENT 9 — LLM NEWS ANALYST

El LLM NO decide comprar.

Su trabajo:

Convertir texto no estructurado en datos estructurados.

Output:

```json
{
  "eventType": "REGULATORY",
  "entities": ["BTC"],
  "sentiment": "NEGATIVE",
  "impact": 0.72,
  "timeHorizon": "SHORT_TERM",
  "confidence": 0.84
}
```

---

# AGENT 10 — SENTIMENT AGENT

Combina:

* News
* Social sentiment
* Market sentiment
* Fear/greed
* Search trends cuando estén disponibles

Debe detectar:

```text
EXTREME_FEAR
FEAR
NEUTRAL
GREED
EXTREME_GREED
```

No debe utilizar sentimiento como señal única.

---

# AGENT 11 — CORRELATION AGENT

Analiza:

* Asset correlations
* Sector correlations
* BTC dominance
* Cross-market risk
* Portfolio concentration

Ejemplo:

Si tenemos:

```text
BTC LONG
ETH LONG
SOL LONG
```

aunque sean tres trades diferentes,

el sistema debe reconocer que existe exposición correlacionada.

---

# AGENT 12 — PORTFOLIO AGENT

Responsable de:

* Asset allocation
* Position sizing
* Portfolio exposure
* Correlation
* Diversification
* Risk budget

Debe determinar:

```text
How much capital should be allocated?
```

No decide por sí mismo si la operación está permitida.

---

# AGENT 13 — RISK AGENT

Este es el agente más importante.

Debe calcular:

```text
Position risk
Portfolio risk
Drawdown
Volatility
Correlation
Liquidity
Slippage
Leverage
Stop distance
Expected loss
Tail risk
```

---

# 13. HARD RISK ENGINE

Además del Risk Agent habrá un:

# HARD RISK ENGINE

Este NO utiliza IA.

Es determinístico.

Ejemplo original (perfil conservador, valor por defecto — ver `config/config.conservative.yaml`):

```text
MAX_DAILY_LOSS = 0.5%

MAX_TRADE_RISK = 0.10%

MAX_POSITION = 1%

MAX_PORTFOLIO_EXPOSURE = 5%

MAX_DRAWDOWN = 8%

MAX_LEVERAGE = 2x
```

Si cualquiera se incumple:

```text
REJECT
```

**Actualización 2026-08-22 — perfil agresivo en vivo:** decisión explícita del usuario de operar con dinero simulado bajo un perfil de riesgo mucho más agresivo que el ejemplo de arriba, aceptando la posibilidad de perder toda la cuenta simulada. La estrategia (`volatility_spike`) no cambió — solo estos límites. Valores reales en vivo (`config/config.yaml`, "risk profile v2"):

```text
MAX_DAILY_LOSS = 15%

MAX_TRADE_RISK = 0.5%

MAX_POSITION = 10%

MAX_PORTFOLIO_EXPOSURE = 50%

MAX_DRAWDOWN = 30%

MAX_LEVERAGE = 1x
```

Backtesteado sobre los 90 días completos de BTC-USD/ETH-USD antes de aplicarse: BTC -3.06%, ETH +0.44% en total — ningún tamaño probado (2% a 40%) llega de forma confiable a un 7% mensual en los dos activos a la vez; tamaños mayores empeoraron el resultado en vez de mejorarlo. No es una ventaja estadística validada (ver Regla 4) — es una apuesta explícita y aceptada por el usuario, no una promesa de retorno.

**Bug encontrado y corregido el mismo día (commit `f24c524`):** el kill-switch de drawdown, una vez que aplanaba la cuenta a solo efectivo por debajo de su punto máximo histórico, quedaba permanentemente bloqueado — ese punto máximo nunca se podía volver a alcanzar sin una posición abierta, así que el sistema rechazaba cualquier señal nueva para siempre, no solo temporalmente. Todos los resultados de backtest reportados antes de esta corrección (incluyendo los que motivaron el primer cambio al perfil agresivo) estaban inflados por este bug — medían "cuánto ganó antes de congelarse por accidente", no una operación real y continua. Corregido reiniciando el punto máximo (`peak_equity`) al valor de la cuenta justo después de cada cierre de emergencia, para que el freno vuelva a ser temporal como estaba pensado.

**Segundo bug de contabilidad de drawdown, encontrado y corregido el 2026-08-25:** `max_drawdown_pct` en `BacktestResult` (`src/aurora/backtest/engine.py`) se calculaba a partir de una muestra de equity tomada solo **una vez al día**, comparada contra un pico que **nunca se reiniciaba** — aunque el kill-switch real sí reinicia su propio pico tras cada cierre de emergencia (el fix de arriba). Esto hacía que el número reportado mezclara varios episodios de caída-y-recuperación en una sola cifra inflada (ej. 37-63% reportado cuando la caída real de un único episodio nunca superó el 30.03% verificado directamente contra el mismo pico que usa el kill-switch). **No era un hueco de seguridad** — el freno del 30% en vivo y en backtest siempre funcionó correctamente, solo el número que se mostraba después estaba mal. Corregido midiendo el drawdown en cada vela usando el mismo `peak_equity` con reinicio que ya usa `check_kill_switch`. Todas las cifras de "drawdown máximo" citadas en este documento y en sesiones anteriores a esta fecha deben tratarse con cautela — miden algo distinto de lo que se pensaba.

**Actualización 2026-08-29 — ajuste de estrategia (`spike_multiplier` 2.0 → 3.0):** tras una semana en vivo (2026-08-22 a 08-29) con `spike_multiplier: 2.0` — 56 operaciones, -1.17% neto, sin tendencia clara — se re-backtesteó `volatility_spike` sobre la misma ventana de 90 días (perfil de riesgo v2 sin cambios, tamaño de posición en 10%). `spike_multiplier: 3.0` superó a 2.0 en BTC y ETH simultáneamente en los 5 tamaños de ventana probados (10/15/20/30/40), en dos corridas independientes con datos de días distintos — filtra velas "grandes pero normales" y solo opera ante movimientos verdaderamente atípicos, bajando de ~1,530-1,600 operaciones a ~420-500 en la ventana de 90 días. Se probó también subir el tamaño de posición a 15%/20% junto con este cambio de estrategia: empeora el resultado en vez de mejorarlo (BTC pasa de +1.25% a -3.48%/-8.57% con el mismo número de operaciones), así que el tamaño de posición se mantuvo en 10%. Sigue siendo evidencia de un solo backtest histórico, no una ventaja validada (ver Regla 4).

**Actualización 2026-09-07 — ejecución en vivo migrada a Alpaca (paper), fin del simulador propio en producción:** el loop en vivo dejó de usar `PaperSimulatorBroker` (fills inventados por nosotros) y ahora opera contra la **plataforma de paper trading de Alpaca** vía `AlpacaBroker` (nuevo, `src/aurora/broker/alpaca_broker.py`) — infraestructura real de un bróker regulado en EE.UU., libro de órdenes real, latencia real, dinero simulado ($100k). Cuenta paper `PA3OA821KKKD`. Se eligió Alpaca porque es lo único que combina: alcanzable desde las IPs de GitHub Actions (Bybit y Binance están geo-bloqueados, igual que motivó salir de Binance para los datos), soporte de cripto spot, cuenta de práctica sin KYC completo, y ser un bróker regulado. Las velas siguen viniendo de Coinbase (el volumen de los datos cripto de Alpaca es muy fino); Alpaca es solo ejecución + cuenta + posiciones.

- **`TradingBroker` es la única interfaz** (sección 18): `AlpacaBroker` es la implementación `CryptoBroker`. `PaperSimulatorBroker` se conserva pero **solo lo usa el backtest** (un backtest necesita un simulador por definición).
- **`peak_equity` y el ancla de equity de inicio-de-día-UTC** (que necesita el HardRiskEngine para los kill-switch de drawdown y pérdida diaria) los mantiene `AlpacaBroker` y se persisten en `portfolio_state` — Alpaca no los expone. Todo lo demás (efectivo, posiciones, equity) se lee en vivo de Alpaca en cada llamada. El resto de `portfolio_state` (`cash`, `positions_json`) es un espejo de Alpaca para que el dashboard siga funcionando sin cambios.
- **Cripto spot no se puede poner en corto en Alpaca.** Nueva opción de config `execution.allow_short` (por defecto `false`): con corto deshabilitado, una señal SHORT solo puede *reducir un largo existente* (un SELL limitado a la cantidad en cartera); una señal SHORT sin nada que reducir es un no-op (evento de auditoría `SHORT_SKIPPED_SPOT_LONG_ONLY`). Esto vuelve a `volatility_spike` **efectivamente solo-largo en vivo** — un cambio real de comportamiento. Los engines de backtest (`engine.py`, `multi_engine.py`) honran el mismo flag para que sus números sigan siendo comparables con lo que hace la app en vivo.
- **Fees reales de Alpaca (~0.25% cripto)**, más altas que el 0.1% del simulador — más realista/conservador.
- `starting_equity` en `config/config.yaml` subió a 100000 para coincidir con la cuenta paper. El equity_history del dashboard muestra un escalón único de ~$997 a ~$100k en el momento de la migración (esperado).
- Credenciales: `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` como secrets de GitHub Actions (permisos de solo-trading, nunca retiros — sección 28). `mode: PAPER` → endpoint paper; `mode: LIVE` → endpoint real (sigue siendo un switch manual y humano — Regla 3 / sección 27).

---

# 14. SIGNAL ENGINE

Combina todos los agentes.

Ejemplo:

```text
Technical       0.78
Trend           0.82
Mean Reversion  0.31
Volatility      0.64
Statistics      0.76
ML              0.73
News            0.55
Sentiment       0.61
Regime          0.80
```

Pero NO hacer simplemente un promedio.

Usar un Ensemble Model.

Output:

```json
{
  "symbol": "BTCUSDT",
  "action": "LONG",
  "confidence": 0.76,
  "expectedReturn": 0.014,
  "expectedRisk": 0.006,
  "riskReward": 2.33
}
```

---

# 15. DECISION ENGINE

Estados:

```text
BUY
SELL
HOLD
NO_TRADE
REDUCE
EXIT
```

Debe tener:

```text
Signal
+
Expected Return
+
Confidence
+
Regime
+
Liquidity
+
Portfolio exposure
+
Risk
```

---

# 16. POSITION SIZING

Nunca:

```text
BUY $1000
```

sin calcular riesgo.

El tamaño debe depender de:

* Account equity
* Stop distance
* Volatility
* Risk budget
* Portfolio exposure
* Correlation

El sistema debe poder reducir automáticamente:

```text
Normal risk = 100%

High volatility = 50%

Extreme volatility = 20%

Unknown regime = 0%
```

---

# 17. EXECUTION ENGINE

Responsabilidades:

* Order creation
* Order validation
* Order submission
* Order status
* Partial fills
* Retry
* Slippage tracking
* Fees
* Cancel/replace

Tipos:

```text
MARKET
LIMIT
STOP
STOP_LIMIT
```

El Execution Engine NO puede saltarse Risk Engine.

---

# 18. BROKER ADAPTER

Crear interfaz:

```java
public interface TradingBroker {

    OrderResult submit(Order order);

    void cancel(String orderId);

    OrderStatus getStatus(String orderId);

    AccountSnapshot getAccount();

    List<Position> getPositions();
}
```

Implementaciones independientes:

```text
PaperBroker      -> PaperSimulatorBroker (solo backtest desde 2026-09-07)
CryptoBroker     -> AlpacaBroker (ejecución en vivo, paper o real según base_url)
StockBroker
FutureBroker
```

---

# 19. BACKTEST ENGINE

Debe poder reproducir exactamente:

```text
Historical Market Data
→ Features
→ Agents
→ Signal
→ Risk
→ Portfolio
→ Execution Simulator
```

El backtester debe simular:

* Fees
* Spread
* Slippage
* Latency
* Partial fills
* Stops
* Liquidity
* Position limits

---

# 20. WALK-FORWARD TESTING

Nunca entrenar y evaluar sobre exactamente el mismo período.

Ejemplo:

```text
Train
2021 → 2023

Validation
2024 Q1

Test
2024 Q2
```

Después mover la ventana:

```text
Train
2021 → 2023 Q1

Validation
2023 Q2

Test
2023 Q3
```

Repetir.

---

# 21. MONTE CARLO

Simular:

* Trade ordering
* Slippage
* Loss clusters
* Randomized returns
* Execution variation

Objetivo:

Estimar:

```text
Worst likely drawdown
Probability of ruin
Expected return distribution
```

---

# 22. OVERFITTING PROTECTION

Obligatorio:

* Out-of-sample
* Walk-forward
* Feature selection
* Regularization
* Simplicity preference
* Parameter stability
* Monte Carlo
* Stress testing

El sistema debe penalizar estrategias que solo funcionen en un período específico.

---

# 23. MODEL REGISTRY

MLflow.

Registrar:

```text
model_id
version
training_data
features
parameters
metrics
date
dataset_hash
git_commit
status
```

Estados:

```text
EXPERIMENTAL
VALIDATED
PAPER
PRODUCTION
DEPRECATED
FAILED
```

---

# 24. MODEL GOVERNANCE

Nunca desplegar un modelo automáticamente solo porque tenga mayor retorno.

Debe superar:

```text
Minimum Sharpe
Maximum Drawdown
Minimum number of trades
Minimum out-of-sample performance
Stability threshold
Calibration threshold
```

---

# 25. DRIFT DETECTION

Detectar:

* Feature drift
* Prediction drift
* Performance drift
* Market regime drift

Ejemplo:

```text
Expected win rate = 62%

Actual rolling win rate = 43%

DRIFT DETECTED
```

Entonces:

```text
Reduce exposure
```

o:

```text
Disable strategy
```

---

# 26. CIRCUIT BREAKERS

Debe existir:

```text
DAILY_LOSS_LIMIT
MAX_DRAWDOWN
BROKER_FAILURE
DATA_FAILURE
DATA_STALE
MODEL_DRIFT
EXTREME_VOLATILITY
UNEXPECTED_SLIPPAGE
API_FAILURE
```

Cualquier evento crítico puede generar:

```text
PAUSE_TRADING
```

---

# 27. MODOS DEL SISTEMA

```text
BACKTEST
REPLAY
PAPER
LIVE_SAFE
LIVE_LIMITED
LIVE_NORMAL
EMERGENCY_STOP
```

Nunca pasar automáticamente de:

```text
PAPER → LIVE
```

sin aprobación.

---

# 28. OBSERVABILIDAD

Stack:

Prometheus
Grafana
OpenTelemetry
Loki

Métricas:

```text
PnL
Drawdown
Sharpe
Win rate
Profit factor
Trade count
Slippage
Fees
Latency
Signal confidence
Model performance
Risk utilization
API errors
Data freshness
```

---

# 29. ALERTAS

Telegram/email/Slack.

Alertas:

```text
Trade executed
Risk rejection
Daily loss threshold
Drawdown threshold
Model drift
Broker disconnected
Data stale
Emergency stop
Unexpected volatility
```

---

# 30. SEGURIDAD

Nunca almacenar API keys en código.

Utilizar:

AWS Secrets Manager

o

HashiCorp Vault.

Separar:

```text
READ_ONLY_KEY
TRADING_KEY
```

Durante desarrollo:

READ_ONLY.

Paper trading:

PAPER KEY.

Live:

LIVE KEY con permisos mínimos.

Nunca habilitar retiros mediante API.

---

# 31. AUDIT TRAIL

Toda decisión debe poder explicarse.

Guardar:

```text
Signal
Features
Agent outputs
Risk decision
Order
Execution
Fill
Result
```

Debe ser posible preguntar:

> ¿Por qué el sistema compró BTC a las 14:32?

Y obtener:

```text
Technical: LONG
Trend: LONG
ML probability: 73%
Regime: BULL
Expected return: 1.4%
Risk: acceptable
Portfolio exposure: acceptable
Risk Engine: APPROVED
```

---

# 32. LLM ARCHITECTURE

El LLM debe utilizarse en áreas donde sea bueno:

### Bueno para:

* News analysis
* Event extraction
* Research assistance
* Strategy documentation
* Log analysis
* Natural-language explanations
* Anomaly investigation
* Generación de hipótesis

### NO utilizarlo directamente para:

* Determinar tamaño de posición
* Saltarse risk limits
* Ejecutar órdenes
* Cambiar stop arbitrariamente
* Modificar capital allocation sin controles

---

# 33. PROMPT — MASTER SYSTEM AGENT

```text
You are Aurora Trading Intelligence.

You are one component of a multi-agent quantitative trading system.

Your objective is NOT to maximize the number of trades.

Your objective is to identify statistically supported opportunities while preserving capital.

You must:

1. Never claim certainty about market direction.
2. Never bypass risk controls.
3. Never invent market data.
4. Explicitly identify uncertainty.
5. Return structured outputs.
6. Distinguish facts from inference.
7. Prefer NO_TRADE when evidence is insufficient.
8. Never directly execute trades.
9. Never modify hard risk limits.
10. Never recommend leverage without risk calculations.

You must evaluate:
- market regime
- volatility
- trend
- momentum
- liquidity
- correlation
- expected return
- expected risk
- confidence

Your output must be machine-readable JSON.
```

---

# 34. PROMPT — TECHNICAL AGENT

```text
Analyze the supplied market data as a quantitative technical analyst.

Evaluate:

- trend
- momentum
- support/resistance
- volatility
- volume
- multi-timeframe confirmation
- breakout/reversal conditions

Do not make decisions based on one indicator.

Return:

direction
confidence
trendStrength
momentumStrength
riskFactors
reasonCodes

If evidence is contradictory, reduce confidence.

If evidence is insufficient, return NO_TRADE.
```

---

# 35. PROMPT — NEWS AGENT

```text
Analyze the supplied financial news.

Do not predict price directly.

Extract:

- entities
- event type
- event severity
- sentiment
- expected market impact
- time horizon
- confidence

Separate confirmed facts from interpretation.

Do not invent information.

Return JSON only.
```

---

# 36. PROMPT — MARKET REGIME AGENT

```text
Classify the current market regime.

Possible regimes:

STRONG_BULL
BULL
SIDEWAYS
BEAR
STRONG_BEAR
HIGH_VOLATILITY
PANIC
UNKNOWN

Use the supplied quantitative features.

Do not infer regime from a single indicator.

Return:

regime
confidence
supportingSignals
contradictingSignals
riskMultiplier
```

---

# 37. PROMPT — RESEARCH AGENT

```text
You are a quantitative research assistant.

Your job is to generate testable hypotheses.

Never present a hypothesis as proven.

For every strategy idea provide:

1. Hypothesis
2. Market rationale
3. Required data
4. Features
5. Entry conditions
6. Exit conditions
7. Risk conditions
8. Expected failure modes
9. Backtest methodology
10. Possible sources of overfitting

Do not recommend live deployment.
```

---

# 38. PROMPT — MODEL REVIEW AGENT

```text
Review the supplied model evaluation.

Check:

- overfitting
- data leakage
- look-ahead bias
- survivorship bias
- train/test contamination
- unstable parameters
- insufficient sample size
- unrealistic execution assumptions

Do not approve a model simply because returns are high.

Return:

APPROVE
REJECT
REQUIRES_MORE_TESTING

and explain the reasons.
```

---

# 39. PROMPT — TRADE EXPLANATION AGENT

```text
Explain why the trading system generated this decision.

Use only the supplied evidence.

Do not invent reasons.

Explain:

- market regime
- technical evidence
- statistical evidence
- ML evidence
- news evidence
- portfolio exposure
- risk decision

Clearly distinguish signal generation from final risk approval.
```

---

# 40. MULTI-AGENT DECISION FLOW

```text
                    MARKET DATA
                         │
                         ▼
                 FEATURE ENGINE
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   TECHNICAL          STATISTICAL        NEWS
        │                │                │
        ▼                ▼                ▼
      TREND              ML            SENTIMENT
        │                │                │
        └────────────────┼────────────────┘
                         ▼
                  REGIME AGENT
                         │
                         ▼
                   SIGNAL ENGINE
                         │
                         ▼
                 PORTFOLIO ENGINE
                         │
                         ▼
                  HARD RISK ENGINE
                         │
                 ┌───────┴───────┐
                 │               │
              REJECT           APPROVE
                                 │
                                 ▼
                         POSITION SIZING
                                 │
                                 ▼
                         EXECUTION ENGINE
                                 │
                                 ▼
                              BROKER
```

---

# 41. FASES DE IMPLEMENTACIÓN

## PHASE 0 — Architecture

Objetivo:

Definir:

* repositories
* modules
* coding standards
* domain models
* events
* configuration
* CI/CD

No trading.

---

## PHASE 1 — Market Data

Construir:

```text
MarketDataProvider
HistoricalProvider
ReplayProvider
DataQualityEngine
```

Resultado:

Datos históricos reproducibles.

---

## PHASE 2 — Feature Engine

Construir:

```text
TechnicalFeatures
VolatilityFeatures
VolumeFeatures
MarketStructureFeatures
CorrelationFeatures
```

Resultado:

Dataset de features.

---

## PHASE 3 — Backtesting

Construir:

```text
BacktestEngine
ExecutionSimulator
PortfolioSimulator
FeeSimulator
SlippageSimulator
```

Resultado:

Primer backtest reproducible.

---

## PHASE 4 — Baseline Strategy

Antes de IA:

Crear estrategias sencillas.

Ejemplo:

```text
Trend following
Mean reversion
Breakout
```

El objetivo es crear baseline.

Si la IA no mejora el baseline después de costos:

NO tiene sentido desplegarla.

---

## PHASE 5 — Risk Engine

Construir:

```text
RiskEngine
PositionSizer
ExposureManager
DrawdownMonitor
CircuitBreaker
```

Este módulo debe tener cobertura de tests extremadamente alta.

---

## PHASE 6 — Multi-Agent System

Implementar:

```text
TechnicalAgent
TrendAgent
MeanReversionAgent
VolatilityAgent
RegimeAgent
StatisticalAgent
MLAgent
NewsAgent
SentimentAgent
CorrelationAgent
PortfolioAgent
```

---

## PHASE 7 — Signal Ensemble

Crear:

```text
SignalEngine
DecisionEngine
ConfidenceEngine
```

Combinar señales.

---

## PHASE 8 — ML Platform

Crear:

```text
TrainingPipeline
FeatureStore
ModelRegistry
ModelEvaluator
ModelDeployment
DriftDetector
```

---

## PHASE 9 — News + LLM

Crear:

```text
NewsCollector
NewsClassifier
LLMAnalyzer
SentimentEngine
EventImpactEngine
```

---

## PHASE 10 — Paper Trading

Conectar:

```text
PaperBroker
```

Operar en tiempo real sin dinero.

Objetivo:

Mínimo varios meses de observación antes de considerar LIVE.

---

## PHASE 11 — Dashboard

Crear dashboard con:

* Equity
* PnL
* Drawdown
* Trades
* Signals
* Agent decisions
* Risk
* Models
* Market regime
* System status

---

## PHASE 12 — Live Safe

Capital extremadamente pequeño.

Restricciones:

```text
Low position size
No high leverage
Strict daily loss
Strict drawdown
Manual approval initially
```

---

## PHASE 13 — Autonomous Trading

Solo si se cumplen todos los criterios:

```text
Backtest PASSED
Walk-forward PASSED
Monte Carlo PASSED
Paper PASSED
Drift PASSED
Risk PASSED
Execution PASSED
Operational stability PASSED
```

---

# 42. CI/CD

GitHub Actions.

Pipeline:

```text
git push
 ↓
compile
 ↓
unit tests
 ↓
integration tests
 ↓
architecture tests
 ↓
security scan
 ↓
backtest regression
 ↓
build image
 ↓
deploy
```

Nunca desplegar automáticamente una estrategia nueva a LIVE.

---

# 43. TESTING

## Unit

> 80% coverage objetivo.

## Integration

Testcontainers:

* PostgreSQL
* Redis
* Kafka

## Contract

Broker APIs.

## Backtest Regression

Una modificación de código no debe alterar resultados históricos inesperadamente.

## Risk Tests

Casos extremos:

```text
100% loss
flash crash
API timeout
missing data
duplicate order
duplicate event
broker disconnect
negative balance
stale market data
```

---

# 44. REPOSITORY

```text
aurora-trading-ai/

├── apps/
│   ├── api/
│   ├── trading-engine/
│   └── scheduler/
│
├── modules/
│   ├── market-data/
│   ├── data-quality/
│   ├── features/
│   ├── agents/
│   ├── signals/
│   ├── portfolio/
│   ├── risk/
│   ├── execution/
│   ├── backtest/
│   ├── news/
│   ├── ml/
│   └── monitoring/
│
├── research/
│   ├── notebooks/
│   ├── datasets/
│   └── experiments/
│
├── infrastructure/
│   ├── docker/
│   ├── terraform/
│   ├── kafka/
│   ├── postgres/
│   └── monitoring/
│
├── docs/
│
└── tests/
```

---

# 45. MASTER PROMPT PARA CURSOR / CLAUDE CODE

```text
You are the principal software architect and senior quantitative engineer for Aurora Trading AI.

Build the system according to the Aurora Trading AI specification.

CRITICAL RULES:

1. Do not implement live trading initially.
2. Start with market data and backtesting.
3. Never bypass the Risk Engine.
4. Never allow an LLM to directly execute trades.
5. Never hardcode broker-specific logic into the domain.
6. Use clean architecture.
7. Prefer modular monolith initially.
8. Use Java 21+ and Spring Boot.
9. Use reactive programming where streaming/IO benefits from it.
10. Use Python for ML/research.
11. Use PostgreSQL for transactional state.
12. Use Redis for low-latency state.
13. Use S3 for historical/raw datasets.
14. Use BigQuery for analytics.
15. Use Kafka for event streaming.
16. Use MLflow for model registry.
17. Use Docker for local development.
18. Use Testcontainers for integration tests.
19. Implement comprehensive auditability.
20. Every trading decision must be reproducible.

Development strategy:

PHASE 1:
Implement project skeleton.

PHASE 2:
Implement domain models.

PHASE 3:
Implement market data interfaces.

PHASE 4:
Implement historical data ingestion.

PHASE 5:
Implement data quality validation.

PHASE 6:
Implement feature engine.

PHASE 7:
Implement backtesting.

PHASE 8:
Implement baseline strategies.

PHASE 9:
Implement Risk Engine.

Do not skip phases.

For each phase:

- Explain architecture
- Create code
- Create tests
- Update documentation
- Verify build
- Do not implement future functionality prematurely.

Before writing code, inspect the repository and determine what already exists.

Never invent APIs or classes that do not exist.

When an external dependency is required, isolate it behind an interface.

All configuration must be externalized.

All important decisions must be logged.

The system must fail safely.

If uncertain about a financial decision, return NO_TRADE rather than inventing confidence.
```

---

# 46. PROMPT PARA EL AGENTE DE ARQUITECTURA

```text
Review the current Aurora Trading AI architecture.

Identify:

- coupling
- scalability problems
- security risks
- data consistency risks
- event ordering problems
- failure modes
- latency bottlenecks
- architectural violations

Do not modify code.

Return:

1. Critical issues
2. High priority issues
3. Medium priority issues
4. Recommended improvements

Do not recommend microservices unless justified by measurable requirements.
```

---

# 47. PROMPT PARA EL AGENTE QUANT

```text
You are a senior quantitative researcher.

Evaluate trading strategies scientifically.

Never optimize solely for total return.

Always evaluate:

- risk-adjusted return
- drawdown
- volatility
- Sharpe
- Sortino
- Calmar
- profit factor
- expectancy
- trade count
- stability
- out-of-sample performance

Check for:

- look-ahead bias
- data leakage
- overfitting
- survivorship bias
- unrealistic execution
- insufficient sample size

Prefer robust strategies over highly optimized strategies.
```

---

# 48. PROMPT PARA EL AGENTE DE RIESGO

```text
You are the independent risk authority.

Your primary objective is capital preservation.

You are allowed to reject every trade.

Evaluate:

- account exposure
- position exposure
- portfolio exposure
- correlation
- volatility
- drawdown
- liquidity
- slippage
- leverage
- stop distance
- daily loss

Hard risk limits cannot be overridden by AI, ML, LLM, strategy, portfolio manager or user request during automated operation.

Return:

APPROVE
REDUCE
REJECT
EMERGENCY_STOP
```

---

# 49. PROMPT PARA EL AGENTE DE CODE REVIEW

```text
Review this code as a principal engineer responsible for a financial trading platform.

Focus on:

- correctness
- concurrency
- race conditions
- idempotency
- resilience
- security
- financial calculation errors
- decimal precision
- event duplication
- transaction consistency
- test coverage
- observability

Pay special attention to money calculations.

Do not use floating point for monetary values where exact decimal arithmetic is required.

Return findings ordered by severity.
```

---

# 50. PROMPT PARA EL AGENTE DE BACKTEST REVIEW

```text
Review this backtest implementation.

Determine whether the result can be trusted.

Check:

- look-ahead bias
- future data leakage
- execution assumptions
- transaction costs
- slippage
- spread
- latency
- survivorship bias
- missing data
- timestamp alignment
- train/test contamination

If any major issue exists, classify the result as INVALID.

Never approve a backtest simply because it is profitable.
```

---

# 51. PROMPT PARA EL AGENTE DE OPERACIONES

```text
You are the production reliability engineer.

Monitor:

- broker connectivity
- market data freshness
- event lag
- Kafka lag
- database health
- Redis health
- execution latency
- API errors
- failed orders
- unexpected fills
- risk state

If system integrity cannot be guaranteed:

PAUSE TRADING.

Safety is more important than uptime.
```

---

# 52. CRITERIOS DE ÉXITO

El proyecto NO será considerado exitoso porque:

```text
"Ganó dinero durante una semana."
```

Debe demostrar:

### Statistical robustness

### Out-of-sample robustness

### Risk control

### Execution reliability

### Model stability

### Operational reliability

### Explainability

### Reproducibility

---

# 53. MÉTRICAS DEL SISTEMA

Dashboard mínimo:

```text
Total Equity
Daily PnL
Weekly PnL
Monthly PnL
Max Drawdown
Current Drawdown
Sharpe
Sortino
Profit Factor
Win Rate
Average Win
Average Loss
Expectancy
Trades
Fees
Slippage
Exposure
Leverage
Risk Utilization
Model Confidence
Model Drift
```

---

# 54. PRINCIPIO DE AUTONOMÍA

El sistema debe ser autónomo para:

* recopilar datos
* procesarlos
* analizar
* generar señales
* calcular riesgo
* dimensionar posiciones
* ejecutar órdenes autorizadas
* monitorizar resultados
* detectar anomalías
* detenerse

Pero NO debe ser autónomo para:

* cambiar hard risk limits
* activar retiros
* aumentar capital
* habilitar leverage ilimitado
* desplegar modelos no validados
* eliminar logs
* desactivar circuit breakers

---

# 55. EVOLUCIÓN FUTURA

Después de tener una plataforma estable:

### V2

Multi-market.

### V3

Reinforcement Learning experimental.

### V4

Dynamic strategy allocation.

### V5

Meta-model que determina qué estrategia utilizar según régimen.

### V6

Automatic strategy discovery.

### V7

Distributed multi-agent research system.

---

# 56. PRINCIPIO FINAL

Aurora no debe buscar:

> "Predecir el mercado perfectamente."

Debe buscar:

> "Encontrar pequeñas ventajas estadísticas, explotarlas disciplinadamente y sobrevivir cuando la ventaja desaparezca."

El sistema debe estar diseñado bajo una premisa:

```text
NO PREDICTION IS CERTAIN.
NO STRATEGY WORKS FOREVER.
CAPITAL PRESERVATION COMES FIRST.
```

El objetivo final no es tener la IA que más operaciones realiza.

El objetivo es construir una máquina cuantitativa capaz de:

```text
OBSERVE
→ ANALYZE
→ ESTIMATE
→ QUESTION
→ CONTROL RISK
→ ACT
→ MEASURE
→ LEARN
→ ADAPT
→ STOP WHEN NECESSARY
```

Y cada operación debe poder responder:

> ¿Por qué entramos?

> ¿Qué evidencia teníamos?

> ¿Cuánto podíamos perder?

> ¿Por qué el Risk Engine la aprobó?

> ¿Qué ocurrió realmente?

> ¿La estrategia sigue teniendo ventaja?

Si no podemos responder esas preguntas, el sistema no está preparado para operar dinero real.
