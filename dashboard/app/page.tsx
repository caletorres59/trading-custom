"use client";

import { useEffect, useState } from "react";
import {
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
  if (value === undefined) return "—";
  return `$${Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function timeOnly(iso: string) {
  return new Date(iso).toLocaleTimeString("en-US", { hour12: false });
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
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-mono ${accent ?? "text-zinc-100"}`}>
        {value}
      </div>
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

  useEffect(() => {
    async function loadInitialData() {
      const [signalsRes, risksRes, ordersRes, portfolioRes, equityRes] =
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
  const chartData = equityHistory.map((snapshot) => ({
    time: timeOnly(snapshot.created_at),
    equity: Number(snapshot.equity),
  }));

  return (
    <div className="min-h-screen bg-black text-zinc-100">
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Aurora Trading — Monitor</h1>
            <p className="text-xs text-zinc-500">
              Paper trading · dinero simulado
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-zinc-600"}`}
            />
            {connected ? "En vivo" : "Conectando…"}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
        {loading ? (
          <p className="text-zinc-500">Cargando datos…</p>
        ) : (
          <>
            <section className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              <StatTile label="Equity" value={money(latestEquity?.equity)} />
              <StatTile label="Cash" value={money(latestEquity?.cash)} />
              <StatTile
                label="Peak Equity"
                value={money(latestEquity?.peak_equity)}
              />
              <StatTile
                label="Drawdown"
                value={
                  latestEquity
                    ? `${Number(latestEquity.drawdown_pct).toFixed(2)}%`
                    : "—"
                }
                accent={
                  latestEquity && Number(latestEquity.drawdown_pct) > 0
                    ? "text-amber-400"
                    : undefined
                }
              />
              <StatTile
                label="Daily PnL"
                value={money(latestEquity?.daily_pnl)}
                accent={
                  latestEquity && Number(latestEquity.daily_pnl) < 0
                    ? "text-rose-400"
                    : "text-emerald-400"
                }
              />
              <StatTile
                label="Trades hoy"
                value={String(portfolio?.trades_today ?? 0)}
              />
            </section>

            <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
              <h2 className="mb-3 text-sm font-medium text-zinc-400">
                Equity a través del tiempo
              </h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <XAxis
                      dataKey="time"
                      stroke="#52525b"
                      tick={{ fontSize: 11 }}
                      minTickGap={40}
                    />
                    <YAxis
                      stroke="#52525b"
                      tick={{ fontSize: 11 }}
                      domain={["auto", "auto"]}
                      width={70}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#09090b",
                        border: "1px solid #27272a",
                        fontSize: 12,
                      }}
                      formatter={(value) => money(Number(value))}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity"
                      stroke="#34d399"
                      dot={false}
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                <h2 className="mb-3 text-sm font-medium text-zinc-400">
                  Señales recientes
                </h2>
                <div className="space-y-2">
                  {signals.length === 0 && (
                    <p className="text-xs text-zinc-600">Sin señales aún.</p>
                  )}
                  {signals.map((signal) => (
                    <div
                      key={signal.id}
                      className="flex items-center justify-between rounded border border-zinc-900 bg-black px-3 py-2 text-xs"
                    >
                      <div className="flex flex-col">
                        <span className="font-mono">{signal.symbol}</span>
                        <span className="text-zinc-600">
                          {timeOnly(signal.created_at)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500">
                          {(signal.confidence * 100).toFixed(0)}%
                        </span>
                        <span
                          className={`rounded px-2 py-1 font-mono ${directionColor(signal.direction)}`}
                        >
                          {signal.direction}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                <h2 className="mb-3 text-sm font-medium text-zinc-400">
                  Decisiones de riesgo
                </h2>
                <div className="space-y-2">
                  {riskDecisions.length === 0 && (
                    <p className="text-xs text-zinc-600">
                      Sin decisiones aún.
                    </p>
                  )}
                  {riskDecisions.map((decision) => (
                    <div
                      key={decision.id}
                      className="rounded border border-zinc-900 bg-black px-3 py-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-600">
                          {timeOnly(decision.created_at)}
                        </span>
                        <span
                          className={`rounded px-2 py-1 font-mono ${decisionColor(decision.decision)}`}
                        >
                          {decision.decision}
                        </span>
                      </div>
                      <div className="mt-1 truncate text-zinc-500">
                        {JSON.parse(decision.reasons || "[]").join(", ")}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                <h2 className="mb-3 text-sm font-medium text-zinc-400">
                  Órdenes ejecutadas
                </h2>
                <div className="space-y-2">
                  {orders.length === 0 && (
                    <p className="text-xs text-zinc-600">
                      Sin órdenes todavía — el sistema solo opera cuando hay
                      evidencia suficiente.
                    </p>
                  )}
                  {orders.map((order) => (
                    <div
                      key={order.id}
                      className="flex items-center justify-between rounded border border-zinc-900 bg-black px-3 py-2 text-xs"
                    >
                      <div className="flex flex-col">
                        <span className="font-mono">{order.symbol}</span>
                        <span className="text-zinc-600">
                          {timeOnly(order.created_at)}
                        </span>
                      </div>
                      <div className="flex flex-col items-end">
                        <span
                          className={
                            order.side === "BUY"
                              ? "text-emerald-400"
                              : "text-rose-400"
                          }
                        >
                          {order.side} {Number(order.quantity).toFixed(6)}
                        </span>
                        <span className="text-zinc-500">
                          @ {money(order.fill_price)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
