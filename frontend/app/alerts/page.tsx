"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import {
  apiFetch,
  type Alert,
  type AlertExposure,
  type AlertListResponse,
  type AlertsStats,
} from "@/lib/api";
import {
  eventTypeIT,
  exposureTypeIT,
  fmtPctIT,
  impactBadgeColorIT,
  MARKET_CONFIRMATION_EMOJI,
  MARKET_CONFIRMATION_IT,
  OUTCOME_EMOJI,
  outcomeIT,
  surpriseColorIT,
  SURPRISE_EMOJI,
  surpriseIT,
} from "@/lib/labels";

export default function AlertsPage() {
  const [items, setItems] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertsStats | null>(null);
  const [minScore, setMinScore] = useState(0.65);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const [list, s] = await Promise.all([
          apiFetch<AlertListResponse>(`/api/alerts?limit=50&min_score=${minScore}`),
          apiFetch<AlertsStats>("/api/alerts/stats"),
        ]);
        if (!cancelled) {
          setItems(list.items);
          setStats(s);
          setError(null);
        }
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "errore caricamento");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const handle = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [minScore]);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Nav />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Avvisi del giorno</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Eventi che hanno superato la soglia di rilevanza. Per ognuno: cosa è
          successo, quanto è importante, quali aziende sono coinvolte e come ha
          reagito il mercato.
        </p>
      </header>

      {stats && (
        <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Totali" value={stats.total_alerts.toLocaleString("it-IT")} />
          <StatCard label="Ultime 24h" value={stats.last_24h.toLocaleString("it-IT")} />
          <StatCard label="Ultimi 7 giorni" value={stats.last_7d.toLocaleString("it-IT")} />
          <StatCard
            label="Precisione (3gg)"
            value={
              stats.precision_3d !== null
                ? `${(stats.precision_3d * 100).toFixed(0)}%`
                : "—"
            }
          />
        </section>
      )}

      <div className="mb-6 flex items-center gap-3 text-sm">
        <span className="text-neutral-400">Soglia minima importanza:</span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={minScore}
          onChange={(e) => setMinScore(parseFloat(e.target.value))}
          className="w-48"
        />
        <span className="font-mono tabular-nums text-neutral-100">
          {minScore.toFixed(2)}
        </span>
        <span className="text-xs text-neutral-500">
          (default 0.65 = solo avvisi importanti)
        </span>
      </div>

      {error && (
        <p className="mb-4 text-sm text-red-400">
          Errore: <span className="font-mono">{error}</span>
        </p>
      )}

      {loading && items.length === 0 && (
        <p className="text-sm text-neutral-500">Caricamento…</p>
      )}

      {!loading && items.length === 0 && (
        <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400 leading-relaxed">
          <p className="font-medium text-neutral-200">
            Nessun avviso con importanza ≥ {minScore.toFixed(2)}.
          </p>
          <p className="mt-2 text-xs">
            Il sistema genera avvisi solo quando un evento ha sorpresa
            materiale + esposizione su asset noti + reazione conferma di mercato.
            Se vuoi vedere anche eventi sotto soglia, abbassa lo slider qui sopra.
          </p>
        </div>
      )}

      <ul className="space-y-6">
        {items.map((alert) => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </ul>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-3">
      <p className="text-xs uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function AlertCard({ alert }: { alert: Alert }) {
  const ts = new Date(alert.created_at);
  const topReaction = alert.reactions
    .filter((r) => r.abnormal_return_1d !== null)
    .sort(
      (a, b) =>
        Math.abs(b.abnormal_return_1d || 0) - Math.abs(a.abnormal_return_1d || 0)
    )[0];

  // Raggruppa exposures per tipo per il riassunto
  const expGroups = groupExposuresByType(alert.exposures);

  return (
    <li className="rounded-lg border border-neutral-800 bg-neutral-950 p-5">
      {/* Riga superiore: tipo evento + importanza */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs">
          <time className="font-mono text-neutral-500">
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
          {alert.confounder_count > 0 && (
            <span className="rounded bg-amber-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-amber-400">
              ⚠️ {alert.confounder_count} eventi concorrenti
            </span>
          )}
        </div>
        <ImpactBadge score={alert.impact_score} />
      </div>

      {/* Headline grande */}
      <h3 className="text-base font-medium leading-snug text-neutral-100">
        {alert.headline}
      </h3>
      {alert.summary && (
        <p className="mt-1 text-sm text-neutral-400">{alert.summary}</p>
      )}

      {/* Sezione 1: Cos'è la sorpresa */}
      {alert.expectation && (
        <Section icon={SURPRISE_EMOJI[alert.expectation.surprise_direction] ?? "⚪"}>
          <SectionTitle
            className={surpriseColorIT(alert.expectation.surprise_direction)}
          >
            {surpriseIT(
              alert.expectation.surprise_direction,
              alert.expectation.surprise_magnitude
            )}
          </SectionTitle>
          {alert.expectation.rationale && (
            <p className="mt-1 text-sm text-neutral-300">
              {alert.expectation.rationale}
            </p>
          )}
        </Section>
      )}

      {/* Sezione 2: Reazione del mercato */}
      {topReaction && (
        <Section
          icon={MARKET_CONFIRMATION_EMOJI[topReaction.market_confirmation || "unclear"] || "📈"}
        >
          <SectionTitle>
            {MARKET_CONFIRMATION_IT[topReaction.market_confirmation || "unclear"] ||
              "Reazione di mercato"}
          </SectionTitle>
          <p className="mt-1 text-sm text-neutral-300">
            <span className="font-mono font-semibold">{topReaction.ticker}</span>{" "}
            <span
              className={
                (topReaction.abnormal_return_1d || 0) >= 0
                  ? "text-emerald-400"
                  : "text-red-400"
              }
            >
              {fmtPctIT(topReaction.abnormal_return_1d)}
            </span>{" "}
            <span className="text-neutral-500">
              il giorno dopo l'evento (al netto del mercato)
            </span>
          </p>
        </Section>
      )}

      {/* Sezione 3: Aziende potenzialmente impattate */}
      {alert.exposures.length > 0 && (
        <Section icon="🎯">
          <SectionTitle>Aziende potenzialmente impattate</SectionTitle>
          <div className="mt-1.5 space-y-1 text-sm text-neutral-300">
            {expGroups.map(({ type, tickers }) => (
              <div key={type} className="flex gap-2">
                <span className="text-neutral-500 min-w-[100px]">
                  {exposureTypeIT(type)}:
                </span>
                <span className="font-mono text-neutral-200">
                  {tickers.slice(0, 8).join(" · ")}
                  {tickers.length > 8 && (
                    <span className="text-neutral-500">
                      {" "}
                      +{tickers.length - 8} altri
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Sezione 4: Esito (se valutato) */}
      {alert.outcome && (
        <Section icon={OUTCOME_EMOJI[alert.outcome.outcome_label] || "⏳"}>
          <SectionTitle>{outcomeIT(alert.outcome.outcome_label)}</SectionTitle>
          {alert.outcome.outcome_label !== "pending" && (
            <p className="mt-1 text-sm text-neutral-300">
              <span className="text-neutral-500">1 giorno:</span>{" "}
              <span className="font-mono">{fmtPctIT(alert.outcome.t_plus_1d_ar)}</span>
              <span className="text-neutral-600"> · </span>
              <span className="text-neutral-500">3 giorni:</span>{" "}
              <span className="font-mono">{fmtPctIT(alert.outcome.t_plus_3d_ar)}</span>
              <span className="text-neutral-600"> · </span>
              <span className="text-neutral-500">7 giorni:</span>{" "}
              <span className="font-mono">{fmtPctIT(alert.outcome.t_plus_7d_ar)}</span>
            </p>
          )}
        </Section>
      )}
    </li>
  );
}

function Section({
  icon,
  children,
}: {
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-4 flex gap-3 border-t border-neutral-900 pt-3">
      <span className="mt-0.5 text-base leading-none">{icon}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function SectionTitle({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p className={`text-sm font-medium ${className ?? "text-neutral-200"}`}>
      {children}
    </p>
  );
}

function ImpactBadge({ score }: { score: number }) {
  return (
    <div className="flex flex-col items-end">
      <span
        className={`rounded-md border px-2.5 py-1 font-mono text-lg tabular-nums ${impactBadgeColorIT(
          score
        )}`}
      >
        {score.toFixed(2)}
      </span>
      <span className="mt-0.5 text-[9px] uppercase tracking-wide text-neutral-600">
        Importanza
      </span>
    </div>
  );
}

function groupExposuresByType(
  exposures: AlertExposure[]
): { type: string; tickers: string[] }[] {
  const groups: Record<string, string[]> = {};
  // Ordine fisso di visualizzazione: prima direct, poi peer, ETF, supplier, ecc.
  const order = ["direct", "peer", "etf", "supplier", "customer", "sector", "commodity", "country"];
  for (const exp of exposures) {
    const t = exp.exposure_type;
    if (!groups[t]) groups[t] = [];
    if (!groups[t].includes(exp.asset_ticker)) groups[t].push(exp.asset_ticker);
  }
  return order
    .filter((t) => groups[t])
    .map((t) => ({ type: t, tickers: groups[t] }));
}
