"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import {
  apiFetch,
  type Alert,
  type AlertListResponse,
  type AlertsStats,
  type Cluster,
  type ClusterListResponse,
} from "@/lib/api";
import {
  eventTypeIT,
  fmtPctIT,
  SURPRISE_EMOJI,
  surpriseColorIT,
  surpriseIT,
} from "@/lib/labels";

type Tab = "recenti" | "storico";

export default function HomePage() {
  const [tab, setTab] = useState<Tab>("recenti");
  const [important, setImportant] = useState<Cluster[]>([]);
  const [confirmedAlerts, setConfirmedAlerts] = useState<Alert[]>([]);
  const [evaluatedAlerts, setEvaluatedAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      const results = await Promise.allSettled([
        apiFetch<ClusterListResponse>(
          `/api/clusters/important?limit=30&min_novelty=0.55&days=7`
        ),
        apiFetch<AlertListResponse>(
          `/api/alerts?limit=10&min_score=0.65&outcome_state=recent`
        ),
        apiFetch<AlertListResponse>(
          `/api/alerts?limit=30&min_score=0.0&outcome_state=evaluated`
        ),
        apiFetch<AlertsStats>("/api/alerts/stats"),
      ]);

      if (cancelled) return;

      const [impRes, confRes, evalRes, statsRes] = results;
      const errors: string[] = [];

      if (impRes.status === "fulfilled") setImportant(impRes.value.items);
      else errors.push(`important: ${impRes.reason}`);

      if (confRes.status === "fulfilled") setConfirmedAlerts(confRes.value.items);
      else errors.push(`alerts/recent: ${confRes.reason}`);

      if (evalRes.status === "fulfilled") setEvaluatedAlerts(evalRes.value.items);
      else errors.push(`alerts/evaluated: ${evalRes.reason}`);

      if (statsRes.status === "fulfilled") setStats(statsRes.value);
      else errors.push(`alerts/stats: ${statsRes.reason}`);

      setError(errors.length > 0 ? errors.join(" · ") : null);
      setLoading(false);
    }

    load();
    const handle = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, []);

  const evaluated = stats
    ? (stats.outcomes.confirmed_direction || 0) + (stats.outcomes.reversed || 0)
    : 0;
  const confirmed = stats?.outcomes.confirmed_direction || 0;
  const precisionPct = evaluated > 0 ? (confirmed / evaluated) * 100 : null;

  // Cluster ID che hanno un alert formale → highlight nella lista
  const confirmedClusterIds = new Set(confirmedAlerts.map((a) => a.cluster_id));

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Nav />

      {/* Tab switcher */}
      <div className="mb-6 flex gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        <TabButton active={tab === "recenti"} onClick={() => setTab("recenti")}>
          📨 Recenti
          {important.length > 0 && (
            <span className="ml-1.5 text-neutral-500">· {important.length}</span>
          )}
        </TabButton>
        <TabButton active={tab === "storico"} onClick={() => setTab("storico")}>
          📜 Storico
          {evaluated > 0 && (
            <span className="ml-1.5 text-neutral-500">· {evaluated}</span>
          )}
        </TabButton>
      </div>

      {/* Banner storico precisione */}
      {tab === "storico" && stats && evaluated > 0 && (
        <div className="mb-6 rounded-md border border-neutral-800 bg-neutral-950 p-4">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-neutral-500">
                Avvisi confermati dal mercato
              </p>
              <p className="mt-1 text-2xl font-mono font-semibold text-emerald-400 tabular-nums">
                {precisionPct?.toFixed(0)}%
              </p>
            </div>
            <div className="text-right text-xs text-neutral-500 leading-relaxed">
              <p>{confirmed} confermati</p>
              <p>{stats.outcomes.reversed || 0} direzione opposta</p>
              {(stats.outcomes.flat || 0) > 0 && (
                <p>{stats.outcomes.flat} senza movimento</p>
              )}
              {(stats.outcomes.confounded || 0) > 0 && (
                <p>{stats.outcomes.confounded} cause incerte</p>
              )}
            </div>
          </div>
        </div>
      )}

      {error && (
        <p className="mb-4 text-sm text-red-400">
          Errore: <span className="font-mono">{error}</span>
        </p>
      )}

      {loading && important.length === 0 && (
        <p className="text-sm text-neutral-500">Caricamento…</p>
      )}

      {/* Tab Recenti = lista eventi rilevanti */}
      {tab === "recenti" && !loading && (
        <>
          {important.length === 0 ? (
            <EmptyRecenti />
          ) : (
            <ul className="space-y-3">
              {important.map((c) => (
                <EventCard
                  key={c.id}
                  cluster={c}
                  confirmed={confirmedClusterIds.has(c.id)}
                />
              ))}
            </ul>
          )}
        </>
      )}

      {/* Tab Storico = lista alert valutati */}
      {tab === "storico" && !loading && (
        <>
          {evaluatedAlerts.length === 0 ? (
            <EmptyStorico />
          ) : (
            <ul className="space-y-5">
              {evaluatedAlerts.map((alert) => (
                <AlertHistoricCard key={alert.id} alert={alert} />
              ))}
            </ul>
          )}
        </>
      )}

      <footer className="mt-20 text-xs text-neutral-600 leading-relaxed">
        Ricerca e analisi automatizzata. Non consulenza finanziaria personalizzata.
      </footer>
    </main>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-md px-4 py-2.5 text-sm font-medium transition ${
        active
          ? "bg-neutral-900 text-neutral-100"
          : "text-neutral-500 hover:text-neutral-300"
      }`}
    >
      {children}
    </button>
  );
}

function EventCard({
  cluster,
  confirmed,
}: {
  cluster: Cluster;
  confirmed: boolean;
}) {
  const ts = new Date(cluster.first_seen);
  const primary = cluster.entities.filter((e) => e.role === "primary");
  const tickers = primary
    .filter((e) => e.ticker)
    .map((e) => e.ticker as string)
    .slice(0, 4);
  const novPct = Math.round(cluster.novelty_score * 100);

  return (
    <li className="rounded-lg border border-neutral-800 bg-neutral-950 p-5">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <time className="font-mono">
          {ts.toLocaleString("it-IT", {
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
        <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-400">
          {eventTypeIT(cluster.event_type)}
        </span>
        {confirmed && (
          <span className="rounded bg-amber-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-amber-300">
            ⭐ Confermato dal mercato
          </span>
        )}
        <span className="ml-auto text-[10px] text-neutral-600">
          rilevanza {novPct}% · {cluster.n_sources}{" "}
          {cluster.n_sources === 1 ? "fonte" : "fonti"}
        </span>
      </div>

      <h3 className="text-base font-medium leading-snug text-neutral-100">
        {cluster.headline_canonical}
      </h3>

      {cluster.summary && (
        <p className="mt-1.5 text-sm text-neutral-400">{cluster.summary}</p>
      )}

      {tickers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {tickers.map((t) => (
            <span
              key={t}
              className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-[11px] text-neutral-300"
            >
              {t}
            </span>
          ))}
        </div>
      )}

      {cluster.expectation && cluster.expectation.surprise_direction !== "neutral" && (
        <div className="mt-3 flex gap-2 border-t border-neutral-900 pt-3">
          <span>{SURPRISE_EMOJI[cluster.expectation.surprise_direction] ?? "⚪"}</span>
          <div className="flex-1 text-sm">
            <p
              className={`font-medium ${surpriseColorIT(
                cluster.expectation.surprise_direction
              )}`}
            >
              {surpriseIT(
                cluster.expectation.surprise_direction,
                cluster.expectation.surprise_magnitude
              )}
            </p>
            {cluster.expectation.rationale && (
              <p className="mt-1 text-xs text-neutral-400">
                {cluster.expectation.rationale}
              </p>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function AlertHistoricCard({ alert }: { alert: Alert }) {
  const ts = new Date(alert.created_at);
  const outcomeLabels: Record<string, { icon: string; text: string; color: string }> = {
    confirmed_direction: {
      icon: "✅",
      text: "Direzione confermata",
      color: "text-emerald-400",
    },
    reversed: { icon: "❌", text: "Direzione opposta", color: "text-red-400" },
    flat: { icon: "➖", text: "Senza movimento", color: "text-neutral-400" },
    confounded: { icon: "⚠️", text: "Causa incerta", color: "text-amber-400" },
    pending: { icon: "⏳", text: "In valutazione", color: "text-blue-400" },
  };
  const o = alert.outcome
    ? outcomeLabels[alert.outcome.outcome_label] || outcomeLabels.pending
    : outcomeLabels.pending;

  return (
    <li className="rounded-lg border border-neutral-800 bg-neutral-950 p-5">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <time className="font-mono">
          {ts.toLocaleString("it-IT", {
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
        <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-400">
          {eventTypeIT(alert.event_type)}
        </span>
        <span className={`text-xs font-medium ${o.color}`}>
          {o.icon} {o.text}
        </span>
      </div>

      <h3 className="text-base font-medium leading-snug text-neutral-100">
        {alert.headline}
      </h3>
      {alert.summary && (
        <p className="mt-1.5 text-sm text-neutral-400">{alert.summary}</p>
      )}

      {alert.outcome && alert.outcome.outcome_label !== "pending" && (
        <p className="mt-3 border-t border-neutral-900 pt-3 text-xs text-neutral-400">
          <span className="text-neutral-500">A 1 giorno:</span>{" "}
          <ARSpan v={alert.outcome.t_plus_1d_ar} />
          <span className="text-neutral-600"> · </span>
          <span className="text-neutral-500">3 giorni:</span>{" "}
          <ARSpan v={alert.outcome.t_plus_3d_ar} />
          <span className="text-neutral-600"> · </span>
          <span className="text-neutral-500">7 giorni:</span>{" "}
          <ARSpan v={alert.outcome.t_plus_7d_ar} />
        </p>
      )}
    </li>
  );
}

function ARSpan({ v }: { v: number | null }) {
  if (v === null || v === undefined)
    return <span className="font-mono text-neutral-500">—</span>;
  return (
    <span
      className={`font-mono tabular-nums ${
        v >= 0 ? "text-emerald-400" : "text-red-400"
      }`}
    >
      {fmtPctIT(v)}
    </span>
  );
}

function EmptyRecenti() {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400 leading-relaxed">
      <p className="font-medium text-neutral-200">
        Nessun evento rilevante nelle ultime 24 ore.
      </p>
      <p className="mt-2 text-xs">
        Il sistema sta monitorando news, dati macro e prezzi 24/7 ma sta
        ancora processando il backlog iniziale. Riprova tra qualche minuto.
      </p>
    </div>
  );
}

function EmptyStorico() {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400 leading-relaxed">
      <p className="font-medium text-neutral-200">Lo storico è ancora vuoto.</p>
      <p className="mt-2 text-xs">
        Gli avvisi vengono verificati 3 giorni dopo l'evento, confrontando la
        previsione di sorpresa con il movimento effettivo del prezzo. Serve
        quindi qualche giorno dal primo avviso per popolare questa sezione.
      </p>
    </div>
  );
}
