"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import {
  apiFetch,
  type Cluster,
  type ClusterListResponse,
  type ClusterStats,
} from "@/lib/api";

const EVENT_TYPES = [
  { label: "All", value: "" },
  { label: "Earnings", value: "earnings" },
  { label: "Guidance", value: "guidance" },
  { label: "M&A", value: "m_and_a" },
  { label: "Contract", value: "contract" },
  { label: "Macro", value: "macro_data" },
  { label: "Central bank", value: "central_bank" },
  { label: "Geopolitical", value: "geopolitical" },
  { label: "Regulatory", value: "regulatory" },
  { label: "Product", value: "product" },
  { label: "Personnel", value: "personnel" },
  { label: "Analyst rating", value: "analyst_rating" },
];

export default function ClustersPage() {
  const [items, setItems] = useState<Cluster[]>([]);
  const [stats, setStats] = useState<ClusterStats | null>(null);
  const [eventType, setEventType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const evParam = eventType ? `&event_type=${encodeURIComponent(eventType)}` : "";
        const [list, statsResult] = await Promise.all([
          apiFetch<ClusterListResponse>(
            `/api/clusters?limit=50&only_classified=true${evParam}`
          ),
          apiFetch<ClusterStats>("/api/clusters/stats"),
        ]);
        if (!cancelled) {
          setItems(list.items);
          setStats(statsResult);
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
  }, [eventType]);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Nav />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Event clusters</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Cluster di eventi classificati dal LLM (Claude Haiku) con entità e
          sorpresa stimata. Aggiornamento ogni 30s.
        </p>
      </header>

      {stats && (
        <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total" value={stats.total_clusters.toLocaleString()} />
          <StatCard
            label="Classified"
            value={stats.classified.toLocaleString()}
          />
          <StatCard
            label="With expectations"
            value={stats.with_expectations.toLocaleString()}
          />
          <StatCard
            label="Coverage"
            value={
              stats.total_clusters
                ? `${Math.round((stats.classified / stats.total_clusters) * 100)}%`
                : "—"
            }
          />
        </section>
      )}

      <div className="mb-6 flex flex-wrap gap-2">
        {EVENT_TYPES.map((f) => (
          <button
            key={f.value || "all"}
            onClick={() => setEventType(f.value)}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              eventType === f.value
                ? "border-emerald-700 bg-emerald-950 text-emerald-300"
                : "border-neutral-800 bg-neutral-950 text-neutral-400 hover:border-neutral-700"
            }`}
          >
            {f.label}
          </button>
        ))}
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
          Nessun cluster classificato ancora. Il classifier richiede{" "}
          <code className="font-mono text-emerald-400">ANTHROPIC_API_KEY</code>{" "}
          configurata su Railway. Appena attivata, gira ogni 5 minuti e
          processa i cluster pendenti.
        </div>
      )}

      <ul className="space-y-3">
        {items.map((cluster) => (
          <ClusterCard key={cluster.id} cluster={cluster} />
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

function ClusterCard({ cluster }: { cluster: Cluster }) {
  const ts = new Date(cluster.first_seen);
  const primary = cluster.entities.filter((e) => e.role === "primary");
  const mentioned = cluster.entities.filter((e) => e.role === "mentioned");

  return (
    <li className="rounded-md border border-neutral-900 bg-neutral-950 p-4">
      <div className="flex flex-wrap items-baseline gap-2 text-xs text-neutral-500">
        <time className="font-mono tabular-nums">
          {ts.toLocaleString("it-IT", {
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
        <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-400">
          {cluster.event_type}
        </span>
        <span className="text-[10px] text-neutral-500">
          novelty {cluster.novelty_score.toFixed(2)} · {cluster.n_sources}{" "}
          {cluster.n_sources === 1 ? "source" : "sources"}
        </span>
      </div>

      <p className="mt-2 text-sm font-medium text-neutral-100">
        {cluster.headline_canonical}
      </p>
      {cluster.summary && (
        <p className="mt-1 text-sm text-neutral-400">{cluster.summary}</p>
      )}

      {(primary.length > 0 || mentioned.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {primary.map((e) => (
            <EntityChip key={e.id} entity={e} primary />
          ))}
          {mentioned.map((e) => (
            <EntityChip key={e.id} entity={e} />
          ))}
        </div>
      )}

      {cluster.expectation && (
        <div className="mt-3 rounded border border-neutral-900 bg-neutral-900/50 p-3 text-xs">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-neutral-500">
            <span>Surprise</span>
            <SurpriseBadge
              direction={cluster.expectation.surprise_direction}
              magnitude={cluster.expectation.surprise_magnitude}
            />
            <span className="text-neutral-600">
              · {cluster.expectation.baseline_source.replace(/_/g, " ")}
            </span>
          </div>
          {cluster.expectation.rationale && (
            <p className="mt-1.5 text-neutral-400">{cluster.expectation.rationale}</p>
          )}
        </div>
      )}
    </li>
  );
}

function EntityChip({
  entity,
  primary = false,
}: {
  entity: { name: string; ticker: string | null; type: string };
  primary?: boolean;
}) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] ${
        primary
          ? "bg-emerald-950 text-emerald-300"
          : "bg-neutral-900 text-neutral-400"
      }`}
    >
      {entity.ticker ? (
        <span className="font-mono">{entity.ticker}</span>
      ) : (
        entity.name
      )}
      <span className="ml-1 opacity-60">· {entity.type}</span>
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
      className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
        dirColor[direction] ?? "bg-neutral-900 text-neutral-400"
      }`}
    >
      {direction} · {magnitude}
    </span>
  );
}
