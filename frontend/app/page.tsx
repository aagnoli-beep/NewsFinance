"use client";

import { useEffect, useState } from "react";
import { AlertCard } from "@/components/alert-card";
import { Nav } from "@/components/nav";
import {
  apiFetch,
  type Alert,
  type AlertListResponse,
  type AlertsStats,
} from "@/lib/api";

type Tab = "recenti" | "storico";

export default function HomePage() {
  const [tab, setTab] = useState<Tab>("recenti");
  const [items, setItems] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertsStats | null>(null);
  const [minScore, setMinScore] = useState(0.65);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const outcomeParam = tab === "storico" ? "evaluated" : "recent";
        const [list, s] = await Promise.all([
          apiFetch<AlertListResponse>(
            `/api/alerts?limit=50&min_score=${minScore}&outcome_state=${outcomeParam}`
          ),
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
  }, [tab, minScore]);

  const evaluated = stats
    ? (stats.outcomes.confirmed_direction || 0) + (stats.outcomes.reversed || 0)
    : 0;
  const confirmed = stats?.outcomes.confirmed_direction || 0;
  const precisionPct = evaluated > 0 ? (confirmed / evaluated) * 100 : null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Nav />

      {/* Tab switcher prominente */}
      <div className="mb-6 flex gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        <TabButton active={tab === "recenti"} onClick={() => setTab("recenti")}>
          📨 Recenti
          {stats && stats.last_7d > 0 && (
            <span className="ml-1.5 text-neutral-500">· {stats.last_7d}</span>
          )}
        </TabButton>
        <TabButton active={tab === "storico"} onClick={() => setTab("storico")}>
          📜 Storico
          {stats && evaluated > 0 && (
            <span className="ml-1.5 text-neutral-500">· {evaluated}</span>
          )}
        </TabButton>
      </div>

      {/* Banner precisione storica */}
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

      {/* Pannello filtri collassabile */}
      <div className="mb-6">
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="text-xs text-neutral-500 hover:text-neutral-300"
        >
          {filtersOpen ? "▾" : "▸"} Filtri
        </button>
        {filtersOpen && (
          <div className="mt-2 flex items-center gap-3 text-sm">
            <span className="text-xs text-neutral-400">Importanza minima:</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              className="w-40"
            />
            <span className="font-mono text-xs tabular-nums text-neutral-200">
              {minScore.toFixed(2)}
            </span>
          </div>
        )}
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
        <EmptyState tab={tab} minScore={minScore} />
      )}

      <ul className="space-y-5">
        {items.map((alert) => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </ul>

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

function EmptyState({ tab, minScore }: { tab: Tab; minScore: number }) {
  if (tab === "storico") {
    return (
      <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400 leading-relaxed">
        <p className="font-medium text-neutral-200">
          Lo storico è ancora vuoto.
        </p>
        <p className="mt-2 text-xs">
          Gli avvisi vengono verificati 3 giorni dopo l'evento, confrontando la
          previsione con il movimento effettivo del prezzo. Serve quindi qualche
          giorno dal primo avviso generato per popolare questa sezione.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400 leading-relaxed">
      <p className="font-medium text-neutral-200">
        Nessun avviso al momento.
      </p>
      <p className="mt-2 text-xs">
        Il sistema sta monitorando news, dati macro e prezzi 24/7. Genera un
        avviso solo quando un evento ha sorpresa materiale + reazione di
        mercato confermata. Importanza minima attuale:{" "}
        <span className="font-mono">{minScore.toFixed(2)}</span>.
      </p>
    </div>
  );
}
