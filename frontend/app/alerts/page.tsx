"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import {
  apiFetch,
  type Alert,
  type AlertListResponse,
  type AlertsStats,
} from "@/lib/api";

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
          setError(err instanceof Error ? err.message : "fetch failed");
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
    <main className="mx-auto max-w-6xl px-6 py-12">
      <Nav />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Eventi con impact_score sopra soglia (default 0.65). Ogni alert
          aggrega evento + surprise + esposizione + reazione di mercato +
          outcome se calcolato.
        </p>
      </header>

      {stats && (
        <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          <StatCard label="Total" value={stats.total_alerts.toLocaleString()} />
          <StatCard label="Last 24h" value={stats.last_24h.toLocaleString()} />
          <StatCard label="Last 7d" value={stats.last_7d.toLocaleString()} />
          <StatCard
            label="Avg score"
            value={
              stats.avg_impact_score !== null
                ? stats.avg_impact_score.toFixed(2)
                : "—"
            }
          />
          <StatCard
            label="Precision 3d"
            value={
              stats.precision_3d !== null
                ? `${(stats.precision_3d * 100).toFixed(0)}%`
                : "—"
            }
          />
        </section>
      )}

      <div className="mb-6 flex items-center gap-3 text-sm">
        <span className="text-neutral-400">Min impact score:</span>
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
        <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400">
          Nessun alert con score &gt;= {minScore.toFixed(2)}. Il sistema
          genera alert solo quando l'intera catena (event → surprise →
          exposure → reaction) supera la soglia. Richiede{" "}
          <code className="font-mono text-emerald-400">ANTHROPIC_API_KEY</code>{" "}
          attivata per popolare classifier ed expectation.
        </div>
      )}

      <ul className="space-y-4">
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

  return (
    <li className="rounded-md border border-neutral-800 bg-neutral-950 p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2 text-xs text-neutral-500">
          <time className="font-mono tabular-nums">
            {ts.toLocaleString("it-IT", {
              month: "short",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </time>
          <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-400">
            {alert.event_type}
          </span>
          {alert.confounder_count > 0 && (
            <span className="rounded bg-amber-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-amber-400">
              ⚠ {alert.confounder_count} confounders
            </span>
          )}
        </div>
        <ImpactBadge score={alert.impact_score} />
      </div>

      <h3 className="text-base font-medium text-neutral-100">
        {alert.headline}
      </h3>
      {alert.summary && (
        <p className="mt-1 text-sm text-neutral-400">{alert.summary}</p>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {alert.expectation && (
          <Panel label="Surprise">
            <SurpriseBadge
              direction={alert.expectation.surprise_direction}
              magnitude={alert.expectation.surprise_magnitude}
            />
            {alert.expectation.rationale && (
              <p className="mt-1 text-xs text-neutral-400">
                {alert.expectation.rationale}
              </p>
            )}
          </Panel>
        )}

        {topReaction && (
          <Panel label="Market reaction">
            <div className="text-xs">
              <span className="font-mono">{topReaction.ticker}</span>
              <span
                className={`ml-2 font-mono tabular-nums ${
                  (topReaction.abnormal_return_1d || 0) >= 0
                    ? "text-emerald-400"
                    : "text-red-400"
                }`}
              >
                {((topReaction.abnormal_return_1d || 0) * 100).toFixed(2)}% (1d AR)
              </span>
              {topReaction.market_confirmation && (
                <span className="ml-2 text-neutral-500">
                  · {topReaction.market_confirmation.replace(/_/g, " ")}
                </span>
              )}
            </div>
          </Panel>
        )}

        {alert.outcome && (
          <Panel label="Outcome">
            <OutcomeBadge label={alert.outcome.outcome_label} />
            <div className="mt-1 text-xs text-neutral-400">
              1d: {fmtPct(alert.outcome.t_plus_1d_ar)} · 3d:{" "}
              {fmtPct(alert.outcome.t_plus_3d_ar)} · 7d:{" "}
              {fmtPct(alert.outcome.t_plus_7d_ar)}
            </div>
          </Panel>
        )}
      </div>

      {alert.exposures.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          <span className="text-[10px] uppercase tracking-wide text-neutral-500">
            Exposures:
          </span>
          {alert.exposures.slice(0, 8).map((e) => (
            <span
              key={`${e.asset_ticker}-${e.exposure_type}`}
              className="rounded bg-neutral-900 px-1.5 py-0.5 text-[10px] text-neutral-400"
            >
              <span className="font-mono">{e.asset_ticker}</span>
              <span className="ml-1 opacity-60">· {e.exposure_type}</span>
            </span>
          ))}
        </div>
      )}
    </li>
  );
}

function Panel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-neutral-900 bg-neutral-900/30 p-3">
      <p className="text-[10px] uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function ImpactBadge({ score }: { score: number }) {
  let color = "bg-neutral-900 text-neutral-400";
  if (score >= 0.85) color = "bg-emerald-950 text-emerald-300";
  else if (score >= 0.7) color = "bg-emerald-950 text-emerald-400";
  else if (score >= 0.5) color = "bg-amber-950 text-amber-400";
  return (
    <span
      className={`rounded-md px-2 py-1 font-mono text-sm tabular-nums ${color}`}
    >
      {score.toFixed(2)}
    </span>
  );
}

function SurpriseBadge({
  direction,
  magnitude,
}: {
  direction: string;
  magnitude: string;
}) {
  const dirColor: Record<string, string> = {
    positive: "bg-emerald-950 text-emerald-400",
    negative: "bg-red-950 text-red-400",
    neutral: "bg-neutral-900 text-neutral-400",
    uncertain: "bg-amber-950 text-amber-400",
  };
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
        dirColor[direction] ?? "bg-neutral-900 text-neutral-400"
      }`}
    >
      {direction} · {magnitude}
    </span>
  );
}

function OutcomeBadge({ label }: { label: string }) {
  const map: Record<string, string> = {
    confirmed_direction: "bg-emerald-950 text-emerald-400",
    reversed: "bg-red-950 text-red-400",
    flat: "bg-neutral-900 text-neutral-400",
    confounded: "bg-amber-950 text-amber-400",
    pending: "bg-blue-950 text-blue-300",
  };
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
        map[label] ?? "bg-neutral-900 text-neutral-400"
      }`}
    >
      {label.replace(/_/g, " ")}
    </span>
  );
}

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}
