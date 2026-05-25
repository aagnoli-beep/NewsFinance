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

      {/* Tab Recenti = lista eventi rilevanti */}
      {tab === "recenti" && (
        <>
          {important.length > 0 ? (
            <ul className="space-y-3">
              {important.map((c) => (
                <EventCard
                  key={c.id}
                  cluster={c}
                  confirmed={confirmedClusterIds.has(c.id)}
                />
              ))}
            </ul>
          ) : loading ? (
            <p className="text-sm text-neutral-500">Caricamento…</p>
          ) : (
            <EmptyRecenti />
          )}
        </>
      )}

      {/* Tab Storico = lista alert valutati */}
      {tab === "storico" && (
        <>
          {evaluatedAlerts.length > 0 ? (
            <ul className="space-y-5">
              {evaluatedAlerts.map((alert) => (
                <AlertHistoricCard key={alert.id} alert={alert} />
              ))}
            </ul>
          ) : loading ? (
            <p className="text-sm text-neutral-500">Caricamento…</p>
          ) : (
            <EmptyStorico />
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
    .slice(0, 6);
  // Materia = entità primarie non-azienda (paese, commodity, settore, valuta, central_bank)
  const materie = primary
    .filter((e) => !e.ticker && ["country", "commodity", "sector", "currency", "central_bank"].includes(e.type))
    .map((e) => e.name)
    .slice(0, 4);

  // Calcolo score 0-100: novelty + intensità sorpresa
  const surpriseScore = scoreSurprise(cluster.expectation);
  const totalScore = Math.round((cluster.novelty_score * 0.5 + surpriseScore * 0.5) * 100);

  // Titolo: usa summary italiano se disponibile, altrimenti headline_canonical
  const titolo = cluster.summary?.trim() || cluster.headline_canonical;
  const fonteOriginale = cluster.summary?.trim() ? cluster.headline_canonical : null;

  return (
    <li className="rounded-lg border border-neutral-800 bg-neutral-950 p-5">
      {/* Riga 1: meta info + score */}
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
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
              ⭐ Confermato
            </span>
          )}
        </div>
        <ScoreBadge score={totalScore} />
      </div>

      {/* Titolo grande in italiano */}
      <h3 className="text-base font-medium leading-snug text-neutral-100">
        {titolo}
      </h3>

      {/* Strumenti + Materia */}
      {(tickers.length > 0 || materie.length > 0) && (
        <div className="mt-3 space-y-1.5 text-sm">
          {tickers.length > 0 && (
            <div className="flex flex-wrap items-baseline gap-1.5">
              <span className="text-xs text-neutral-500 min-w-[70px]">💼 Strumenti:</span>
              {tickers.map((t) => (
                <span
                  key={t}
                  className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-[11px] text-emerald-300"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          {materie.length > 0 && (
            <div className="flex flex-wrap items-baseline gap-1.5">
              <span className="text-xs text-neutral-500 min-w-[70px]">🌐 Materia:</span>
              {materie.map((m) => (
                <span
                  key={m}
                  className="rounded bg-neutral-900 px-1.5 py-0.5 text-[11px] text-neutral-200"
                >
                  {m}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sorpresa */}
      {cluster.expectation && (
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
              <p className="mt-1 text-xs text-neutral-400 leading-relaxed">
                {cluster.expectation.rationale}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Fonte originale */}
      {fonteOriginale && (
        <details className="mt-3 border-t border-neutral-900 pt-2">
          <summary className="cursor-pointer text-[11px] text-neutral-600 hover:text-neutral-400">
            Headline originale (fonte)
          </summary>
          <p className="mt-1 text-xs italic text-neutral-500">{fonteOriginale}</p>
        </details>
      )}

      <p className="mt-3 text-[10px] text-neutral-600">
        Rilevanza {Math.round(cluster.novelty_score * 100)}% ·{" "}
        {cluster.n_sources} {cluster.n_sources === 1 ? "fonte" : "fonti"}
      </p>
    </li>
  );
}

function ScoreBadge({ score }: { score: number }) {
  let color = "border-neutral-700 bg-neutral-900 text-neutral-300";
  if (score >= 75) color = "border-emerald-600 bg-emerald-950 text-emerald-300";
  else if (score >= 55) color = "border-amber-700 bg-amber-950 text-amber-300";
  else if (score >= 35) color = "border-neutral-700 bg-neutral-900 text-neutral-300";

  return (
    <div className="flex flex-col items-end">
      <span
        className={`rounded-md border px-2.5 py-1 font-mono text-lg font-semibold tabular-nums ${color}`}
      >
        {score}
      </span>
      <span className="mt-0.5 text-[9px] uppercase tracking-wide text-neutral-600">
        Punteggio
      </span>
    </div>
  );
}

function scoreSurprise(exp: Cluster["expectation"]): number {
  if (!exp) return 0;
  const isMaterial = exp.surprise_direction === "positive" || exp.surprise_direction === "negative";
  const magnitude = exp.surprise_magnitude;
  if (isMaterial) {
    if (magnitude === "high") return 1.0;
    if (magnitude === "medium") return 0.6;
    if (magnitude === "low") return 0.3;
  }
  // neutral o uncertain → bassa pesatura
  if (magnitude === "high") return 0.3;
  if (magnitude === "medium") return 0.15;
  return 0.05;
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
