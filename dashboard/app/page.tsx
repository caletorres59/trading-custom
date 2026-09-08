"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { supabase } from "@/lib/supabase";

type Signal = {
  id: string;
  symbol: string;
  strategy: string;
  direction: "LONG" | "SHORT" | "NO_TRADE";
  confidence: number;
  reason_codes: string;
  created_at: string;
};

type RiskDecision = {
  id: string;
  decision: "APPROVE" | "REDUCE" | "REJECT" | "EMERGENCY_STOP";
  approved_notional: string;
  reasons: string;
  created_at: string;
};

type Order = {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: string;
  fill_price: string;
  status: string;
  created_at: string;
};

type PortfolioState = {
  cash: string;
  peak_equity: string;
  equity_at_day_start: string;
  state_day: string;
  trades_today: number;
  updated_at: string;
};

type EquitySnapshot = {
  id: string;
  equity: string;
  cash: string;
  peak_equity: string;
  drawdown_pct: string;
  daily_pnl: string;
  created_at: string;
};

const MAX_FEED_ROWS = 20;
const MAX_CHART_POINTS = 200;

function money(value: string | number | undefined) {
  if (value === undefined || value === null || value === "") return "—";
  return `$${Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function compactMoney(value: number) {
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

function timeOnly(iso: string) {
  return new Date(iso).toLocaleTimeString("es", { hour12: false });
}

function directionColor(direction: Signal["direction"]) {
  if (direction === "LONG") return "text-emerald-400 bg-emerald-400/10";
  if (direction === "SHORT") return "text-rose-400 bg-rose-400/10";
  return "text-zinc-400 bg-zinc-400/10";
}

function decisionColor(decision: RiskDecision["decision"]) {
  if (decision === "APPROVE") return "text-emerald-400 bg-emerald-400/10";
  if (decision === "REDUCE") return "text-amber-400 bg-amber-400/10";
  if (decision === "REJECT") return "text-rose-400 bg-rose-400/10";
  return "text-white bg-rose-600";
}

function StatTile({
  label,
  value,
  accent,
  hint,
}: {
  label: string;
  value: string;
  accent?: string;
  hint?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="truncate text-[11px] uppercase tracking-wider text-zinc-500">
        {label}
      </div>
      <div
        className={`mt-1.5 truncate font-mono text-base tabular-nums tracking-tight sm:text-lg ${
          accent ?? "text-zinc-100"
        }`}
        title={value}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-0.5 truncate text-[11px] text-zinc-600">{hint}</div>
      ) : null}
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <h2 className="mb-3 text-sm font-medium text-zinc-400">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [riskDecisions, setRiskDecisions] = useState<RiskDecision[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioState | null>(null);
  const [equityHistory, setEquityHistory] = useState<EquitySnapshot[]>([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [executionCount, setExecutionCount] = useState<number | null>(null);

  useEffect(() => {
    async function loadInitialData() {
      const [signalsRes, risksRes, ordersRes, portfolioRes, equityRes, countRes] =
        await Promise.all([
          supabase
            .from("signals")
            .select("*")
            .order("created_at", { ascending: false })
            .limit(MAX_FEED_ROWS),
          supabase
            .from("risk_decisions")
            .select("*")
            .order("created_at", { ascending: false })
            .limit(MAX_FEED_ROWS),
          supabase
            .from("orders")
            .select("*")
            .order("created_at", { ascending: false })
            .limit(MAX_FEED_ROWS),
          supabase
            .from("portfolio_state")
            .select("*")
            .eq("id", "default")
            .maybeSingle(),
          supabase
            .from("equity_history")
            .select("*")
            .order("created_at", { ascending: false })
            .limit(MAX_CHART_POINTS),
          // Each run_once() writes exactly one signal per configured symbol,
          // so this count doubles as "how many times has the loop executed".
          supabase.from("signals").select("*", { count: "exact", head: true }),
        ]);

      if (signalsRes.data) setSignals(signalsRes.data as Signal[]);
      if (risksRes.data) setRiskDecisions(risksRes.data as RiskDecision[]);
      if (ordersRes.data) setOrders(ordersRes.data as Order[]);
      if (portfolioRes.data) setPortfolio(portfolioRes.data as PortfolioState);
      if (equityRes.data) {
        setEquityHistory(
          (equityRes.data as EquitySnapshot[]).slice().reverse(),
        );
      }
      if (typeof countRes.count === "number") setExecutionCount(countRes.count);
      setLoading(false);
    }

    loadInitialData();

    const channel = supabase
      .channel("aurora-dashboard")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "signals" },
        (payload) => {
          setSignals((prev) =>
            [payload.new as Signal, ...prev].slice(0, MAX_FEED_ROWS),
          );
          setExecutionCount((prev) => (prev ?? 0) + 1);
        },
      )
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "risk_decisions" },
        (payload) => {
          setRiskDecisions((prev) =>
            [payload.new as RiskDecision, ...prev].slice(0, MAX_FEED_ROWS),
          );
        },
      )
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "orders" },
        (payload) => {
          setOrders((prev) =>
            [payload.new as Order, ...prev].slice(0, MAX_FEED_ROWS),
          );
        },
      )
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "equity_history" },
        (payload) => {
          setEquityHistory((prev) =>
            [...prev, payload.new as EquitySnapshot].slice(
              -MAX_CHART_POINTS,
            ),
          );
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "portfolio_state" },
        (payload) => {
          setPortfolio(payload.new as PortfolioState);
        },
      )
      .subscribe((status) => {
        setConnected(status === "SUBSCRIBED");
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const latestEquity = equityHistory[equityHistory.length - 1];

  // The series still carries a tail from the retired $1k simulator account;
  // drop anything on a wildly different scale from the latest reading so the
  // chart auto-focuses on the live account instead of squashing it to a line
  // at the top of a 0–100k axis. Self-heals as the old points age out.
  const chartData = useMemo(() => {
    const latest = latestEquity ? Number(latestEquity.equity) : undefined;
    return equityHistory
      .filter(
        (s) => latest === undefined || Number(s.equity) > latest * 0.5,
      )
      .map((snapshot) => ({
        time: timeOnly(snapshot.created_at),
        equity: Number(snapshot.equity),
      }));
  }, [equityHistory, latestEquity]);

  const yDomain = useMemo<[number, number]>(() => {
    if (chartData.length === 0) return [0, 1];
    const values = chartData.map((d) => d.equity);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = Math.max((max - min) * 0.2, max * 0.0015, 1);
    return [min - pad, max + pad];
  }, [chartData]);

  const drawdown = latestEquity ? Number(latestEquity.drawdown_pct) : null;
  const dailyPnl = latestEquity ? Number(latestEquity.daily_pnl) : null;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 bg-zinc-950/80 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">Aurora Trading — Monitor</h1>
            <p className="text-xs text-zinc-500">
              Paper trading · dinero simulado
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span className="relative flex h-2 w-2">
              {connected ? (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              ) : null}
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  connected ? "bg-emerald-400" : "bg-zinc-600"
                }`}
              />
            </span>
            {connected ? "En vivo" : "Conectando…"}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        {loading ? (
          <p className="text-zinc-500">Cargando datos…</p>
        ) : (
          <>
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
              <StatTile
                label="Ejecuciones"
                value={executionCount === null ? "—" : String(executionCount)}
              />
              <StatTile label="Equity" value={money(latestEquity?.equity)} />
              <StatTile label="Cash" value={money(latestEquity?.cash)} />
              <StatTile
                label="Peak Equity"
                value={money(latestEquity?.peak_equity)}
              />
              <StatTile
                label="Drawdown"
                value={drawdown === null ? "—" : `${drawdown.toFixed(2)}%`}
                accent={
                  drawdown && drawdown > 0 ? "text-amber-400" : "text-zinc-100"
                }
              />
              <StatTile
                label="Daily PnL"
                value={money(latestEquity?.daily_pnl)}
                accent={
                  dailyPnl === null || dailyPnl === 0
                    ? "text-zinc-100"
                    : dailyPnl < 0
                      ? "text-rose-400"
                      : "text-emerald-400"
                }
              />
              <StatTile
                label="Trades hoy"
                value={String(portfolio?.trades_today ?? 0)}
              />
            </section>

            <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
              <h2 className="mb-3 text-sm font-medium text-zinc-400">
                Equity a través del tiempo
              </h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={chartData}
                    margin={{ top: 8, right: 12, bottom: 0, left: 0 }}
                  >
                    <CartesianGrid
                      stroke="#27272a"
                      strokeDasharray="3 3"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="time"
                      stroke="#52525b"
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      minTickGap={48}
                    />
                    <YAxis
                      stroke="#52525b"
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      domain={yDomain}
                      width={56}
                      tickFormatter={(v) => compactMoney(Number(v))}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#09090b",
                        border: "1px solid #27272a",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: "#a1a1aa" }}
                      formatter={(value) => [money(Number(value)), "Equity"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity"
                      stroke="#34d399"
                      dot={false}
                      strokeWidth={2}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Panel title="Señales recientes">
                {signals.length === 0 && (
                  <p className="text-xs text-zinc-600">Sin señales aún.</p>
                )}
                {signals.map((signal) => (
                  <div
                    key={signal.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/70 bg-zinc-950/60 px-3 py-2 text-xs"
                  >
                    <div className="flex min-w-0 flex-col">
                      <span className="font-mono">{signal.symbol}</span>
                      <span className="text-zinc-600">
                        {timeOnly(signal.created_at)}
                      </span>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="text-zinc-500">
                        {(signal.confidence * 100).toFixed(0)}%
                      </span>
                      <span
                        className={`rounded px-2 py-1 font-mono ${directionColor(
                          signal.direction,
                        )}`}
                      >
                        {signal.direction}
                      </span>
                    </div>
                  </div>
                ))}
              </Panel>

              <Panel title="Decisiones de riesgo">
                {riskDecisions.length === 0 && (
                  <p className="text-xs text-zinc-600">Sin decisiones aún.</p>
                )}
                {riskDecisions.map((decision) => (
                  <div
                    key={decision.id}
                    className="rounded-lg border border-zinc-800/70 bg-zinc-950/60 px-3 py-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-zinc-600">
                        {timeOnly(decision.created_at)}
                      </span>
                      <span
                        className={`rounded px-2 py-1 font-mono ${decisionColor(
                          decision.decision,
                        )}`}
                      >
                        {decision.decision}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-zinc-500">
                      {JSON.parse(decision.reasons || "[]").join(", ")}
                    </div>
                  </div>
                ))}
              </Panel>

              <Panel title="Órdenes ejecutadas">
                {orders.length === 0 && (
                  <p className="text-xs text-zinc-600">
                    Sin órdenes todavía — el sistema solo opera cuando hay
                    evidencia suficiente.
                  </p>
                )}
                {orders.map((order) => (
                  <div
                    key={order.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/70 bg-zinc-950/60 px-3 py-2 text-xs"
                  >
                    <div className="flex min-w-0 flex-col">
                      <span className="font-mono">{order.symbol}</span>
                      <span className="text-zinc-600">
                        {timeOnly(order.created_at)}
                      </span>
                    </div>
                    <div className="flex shrink-0 flex-col items-end">
                      <span
                        className={`font-mono tabular-nums ${
                          order.side === "BUY"
                            ? "text-emerald-400"
                            : "text-rose-400"
                        }`}
                      >
                        {order.side} {Number(order.quantity).toFixed(6)}
                      </span>
                      <span className="text-zinc-500 tabular-nums">
                        @ {money(order.fill_price)}
                      </span>
                    </div>
                  </div>
                ))}
              </Panel>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
