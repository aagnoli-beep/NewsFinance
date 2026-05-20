"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { apiFetch, type FeedResponse, type FeedStats, type RawEvent } from "@/lib/api";

const SOURCE_FILTERS = [
  { label: "All", value: "" },
  { label: "RSS", value: "rss" },
  { label: "Polygon", value: "polygon" },
  { label: "Finnhub", value: "finnhub" },
  { label: "SEC", value: "sec_edgar" },
  { label: "FRED", value: "fred" },
];

export default function FeedPage() {
  const [items, setItems] = useState<RawEvent[]>([]);
  const [stats, setStats] = useState<FeedStats | null>(null);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const sourceParam = source ? `&source=${encodeURIComponent(source)}` : "";
        const [feed, statsResult] = await Promise.all([
          apiFetch<FeedResponse>(`/api/events/feed?limit=50${sourceParam}`),
          apiFetch<FeedStats>("/api/events/stats"),
        ]);
        if (!cancelled) {
          setItems(feed.items);
          setStats(statsResult);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "fetch failed");
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
  }, [source]);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <Nav />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Raw feed</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Stream live di tutti i raw_events ingeriti dalle fonti. Ogni 30s.
        </p>
      </header>

      {stats && (
        <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Events" value={stats.total_events.toLocaleString()} />
          <StatCard label="Clusters" value={stats.total_clusters.toLocaleString()} />
          <StatCard label="Pending dedup" value={stats.pending_dedup.toLocaleString()} />
          <StatCard label="Last 24h" value={stats.last_24h.toLocaleString()} />
        </section>
      )}

      <div className="mb-6 flex flex-wrap gap-2">
        {SOURCE_FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            onClick={() => setSource(f.value)}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              source === f.value
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
          Errore caricamento: <span className="font-mono">{error}</span>
        </p>
      )}

      {loading && items.length === 0 ? (
        <p className="text-sm text-neutral-500">Caricamento…</p>
      ) : (
        <ul className="divide-y divide-neutral-900 border-y border-neutral-900">
          {items.map((item) => (
            <FeedItem key={item.id} event={item} />
          ))}
        </ul>
      )}
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

function FeedItem({ event }: { event: RawEvent }) {
  const ts = event.published_at ?? event.ingested_at;
  const date = new Date(ts);
  const tickers = (event.raw_meta?.tickers as string[] | undefined) ?? [];

  return (
    <li className="py-4">
      <div className="flex items-baseline gap-3 text-xs text-neutral-500">
        <time className="font-mono tabular-nums">
          {date.toLocaleString("it-IT", {
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
        <span className="rounded bg-neutral-900 px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
          {event.source}
        </span>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
            event.source_quality === "primary"
              ? "bg-emerald-950 text-emerald-400"
              : "bg-neutral-900 text-neutral-400"
          }`}
        >
          {event.source_quality}
        </span>
        {event.cluster_id !== null && (
          <span className="text-[10px] text-neutral-600">cluster #{event.cluster_id}</span>
        )}
      </div>
      <p className="mt-1.5 text-sm text-neutral-100">
        {event.source_url ? (
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-emerald-400"
          >
            {event.headline}
          </a>
        ) : (
          event.headline
        )}
      </p>
      {tickers.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {tickers.slice(0, 6).map((t) => (
            <span
              key={t}
              className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-[10px] text-neutral-400"
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </li>
  );
}
