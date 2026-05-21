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

  // Calcolo % avverati nello storico
  const evaluated = stats
    ? (stats.outcomes.confirmed_direction || 0) + (stats.outcomes.reversed || 0)
    : 0;
  const confirmed = stats?.outcomes.confirmed_direction || 0;
  const precisionPct = evaluated > 0 ? (confirmed / evaluated) * 100 : null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Nav />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Avvisi</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Eventi finanziari rilevanti monitorati 24/7. Recenti = appena rilevati,
          Storico = già verificati dopo qualche giorno.
        </p>
      </header>

      {/* Tab switcher */}
      <div className="mb-6 flex gap-1 rounded-md border border-neutral-800 bg-neutral-950 p-1">
        <TabButton active={tab === "recenti"} onClick={() => setTab("recenti")}>
          📨 Recenti{" "}
          {stats && (
            <span className="ml-1 text-neutral-500">
              · {stats.last_7d}
            </span>
          )}
        </TabButton>
        <TabButton active={tab === "storico"} onClick={() => setTab("storico")}>
          📜 Storico verificati
          {stats && evaluated > 0 && (
            <span className="ml-1 text-neutral-500">· {evaluated}</span>
          )}
        </TabButton>
      </div>

      {/* Banner statistica precisione (solo per tab storico) */}
      {tab === "storico" && stats && evaluated > 0 && (
        <div className="mb-6 rounded-md border border-neutral-800 bg-neutral-950 p-4">
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Precisione storica
          </p>
          <p className="mt-1 text-lg">
            <span className="font-mono font-semibold text-emerald-400">
              {precisionPct?.toFixed(0)}%
            </span>{" "}
            <span className="text-sm text-neutral-400">
              degli avvisi confermati dal mercato
            </span>
          </p>
          <p className="mt-1 text-xs text-neutral-500">
            {confirmed} confermati · {stats.outcomes.reversed || 0} direzione opposta
            · {stats.outcomes.flat || 0} senza movimento
            · {stats.outcomes.confounded || 0} cause incerte
          </p>
        </div>
      )}

      {/* Slider soglia importanza */}
      <div className="mb-6 flex items-center gap-3 text-sm">
        <span className="text-neutral-400">Importanza minima:</span>
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
        <EmptyState tab={tab} minScore={minScore} />
      )}

      <ul className="space-y-6">
        {items.map((alert) => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </ul>

      <footer className="mt-16 text-xs text-neutral-500">
        Ricerca e analisi, non consulenza finanziaria personalizzata.
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
      className={`flex-1 rounded px-4 py-2 text-sm font-medium transition ${
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
          Nessun avviso ancora verificato.
        </p>
        <p className="mt-2 text-xs">
          Gli avvisi vengono verificati 3 giorni dopo l'evento, confrontando la
          previsione di sorpresa con il movimento effettivo del prezzo. Servono
          quindi almeno 3 giorni dal primo avviso generato per popolare questa
          sezione.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 p-6 text-sm text-neutral-400 leading-relaxed">
      <p className="font-medium text-neutral-200">
        Nessun avviso recente con importanza ≥ {minScore.toFixed(2)}.
      </p>
      <p className="mt-2 text-xs">
        Il sistema genera avvisi solo quando un evento ha sorpresa materiale +
        esposizione su asset noti + reazione conferma di mercato. Se vuoi vedere
        anche eventi minori, abbassa la soglia.
      </p>
    </div>
  );
}
