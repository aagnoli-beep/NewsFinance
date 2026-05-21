"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { SystemStatus } from "@/components/system-status";
import {
  apiFetch,
  type Cluster,
  type ClusterListResponse,
  type ClusterStats,
  type CoverageResponse,
  type FeedResponse,
  type FeedStats,
  type RawEvent,
} from "@/lib/api";
import {
  eventTypeIT,
  sourceFriendlyIT,
  SURPRISE_EMOJI,
  surpriseColorIT,
  surpriseIT,
} from "@/lib/labels";

type Tab = "stato" | "eventi" | "news" | "copertura";

export default function SistemaPage() {
  const [tab, setTab] = useState<Tab>("stato");

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Nav />

      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Dietro le quinte</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Stato del sistema e dati grezzi. Utile per debug o curiosità — gli avvisi
          importanti li vedi sulla home.
        </p>
      </header>

      <div className="mb-6 flex flex-wrap gap-1 rounded-md border border-neutral-800 bg-neutral-950 p-1">
        <TabButton active={tab === "stato"} onClick={() => setTab("stato")}>
          🟢 Stato
        </TabButton>
        <TabButton active={tab === "eventi"} onClick={() => setTab("eventi")}>
          📊 Eventi classificati
        </TabButton>
        <TabButton active={tab === "news"} onClick={() => setTab("news")}>
          📰 News grezze
        </TabButton>
        <TabButton active={tab === "copertura"} onClick={() => setTab("copertura")}>
          📈 Copertura prezzi
        </TabButton>
      </div>

      {tab === "stato" && <StatoTab />}
      {tab === "eventi" && <EventiTab />}
      {tab === "news" && <NewsTab />}
      {tab === "copertura" && <CoperturaTab />}
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
      className={`rounded px-4 py-2 text-sm font-medium transition ${
        active
          ? "bg-neutral-900 text-neutral-100"
          : "text-neutral-500 hover:text-neutral-300"
      }`}
    >
      {children}
    </button>
  );
}

/* ---------- Tab Stato ---------- */
function StatoTab() {
  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-950 p-6">
      <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
        Stato del sistema
      </h2>
      <SystemStatus />
    </section>
  );
}

/* ---------- Tab Eventi ---------- */
function EventiTab() {
  const [stats, setStats] = useState<ClusterStats | null>(null);
  const [items, setItems] = useState<Cluster[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<ClusterStats>("/api/clusters/stats"),
      apiFetch<ClusterListResponse>("/api/clusters?limit=30&only_classified=true"),
    ])
      .then(([s, l]) => {
        if (!cancelled) {
          setStats(s);
          setItems(l.items);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section>
      {stats && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Totali" v={stats.total_clusters.toLocaleString("it-IT")} />
          <Stat label="Classificati" v={stats.classified.toLocaleString("it-IT")} />
          <Stat
            label="Con sorpresa"
            v={stats.with_expectations.toLocaleString("it-IT")}
          />
          <Stat
            label="Copertura AI"
            v={
              stats.total_clusters
                ? `${Math.round((stats.classified / stats.total_clusters) * 100)}%`
                : "—"
            }
          />
        </div>
      )}
      <ul className="space-y-2">
        {items.map((c) => (
          <li
            key={c.id}
            className="rounded-md border border-neutral-900 bg-neutral-950 p-3 text-sm"
          >
            <div className="flex items-baseline gap-2 text-xs text-neutral-500">
              <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] uppercase text-emerald-400">
                {eventTypeIT(c.event_type)}
              </span>
              <span>
                {new Date(c.first_seen).toLocaleString("it-IT", {
                  month: "short",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span>rilevanza {Math.round(c.novelty_score * 100)}%</span>
            </div>
            <p className="mt-1 text-neutral-100">{c.headline_canonical}</p>
            {c.expectation && (
              <p
                className={`mt-1 text-xs ${surpriseColorIT(
                  c.expectation.surprise_direction
                )}`}
              >
                {SURPRISE_EMOJI[c.expectation.surprise_direction]}{" "}
                {surpriseIT(
                  c.expectation.surprise_direction,
                  c.expectation.surprise_magnitude
                )}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ---------- Tab News grezze ---------- */
function NewsTab() {
  const [stats, setStats] = useState<FeedStats | null>(null);
  const [items, setItems] = useState<RawEvent[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<FeedStats>("/api/events/stats"),
      apiFetch<FeedResponse>("/api/events/feed?limit=30"),
    ])
      .then(([s, l]) => {
        if (!cancelled) {
          setStats(s);
          setItems(l.items);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section>
      {stats && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Totali" v={stats.total_events.toLocaleString("it-IT")} />
          <Stat
            label="Eventi unici"
            v={stats.total_clusters.toLocaleString("it-IT")}
          />
          <Stat
            label="Ultime 24h"
            v={stats.last_24h.toLocaleString("it-IT")}
          />
          <Stat label="Fonti" v={stats.sources.length.toString()} />
        </div>
      )}
      <ul className="divide-y divide-neutral-900 border-y border-neutral-900">
        {items.map((e) => (
          <li key={e.id} className="py-3 text-sm">
            <div className="flex items-baseline gap-2 text-xs text-neutral-500">
              <time className="font-mono tabular-nums">
                {new Date(e.ingested_at).toLocaleString("it-IT", {
                  month: "short",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
              <span className="rounded bg-neutral-900 px-1.5 py-0.5 text-[10px] uppercase">
                {sourceFriendlyIT(e.source)}
              </span>
            </div>
            <p className="mt-1 text-neutral-100">
              {e.source_url ? (
                <a
                  href={e.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-emerald-400"
                >
                  {e.headline}
                </a>
              ) : (
                e.headline
              )}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ---------- Tab Copertura ---------- */
function CoperturaTab() {
  const [data, setData] = useState<CoverageResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<CoverageResponse>("/api/coverage")
      .then((d) => !cancelled && setData(d))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data) return <p className="text-sm text-neutral-500">Caricamento…</p>;

  return (
    <section>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Ticker" v={data.universe_size.toLocaleString("it-IT")} />
        <Stat label="Coperti" v={data.covered_tickers.toLocaleString("it-IT")} />
        <Stat
          label="Mancanti"
          v={data.missing_tickers.length.toLocaleString("it-IT")}
        />
        <Stat
          label="Prezzi totali"
          v={data.total_bars.toLocaleString("it-IT")}
        />
      </div>
      <div className="overflow-x-auto rounded-md border border-neutral-900">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral-950 text-xs uppercase text-neutral-500">
            <tr>
              <th className="px-3 py-2">Ticker</th>
              <th className="px-3 py-2 text-right">Storico</th>
              <th className="px-3 py-2">Dal</th>
              <th className="px-3 py-2">Al</th>
              <th className="px-3 py-2 text-right">Ultima chiusura</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-900">
            {data.by_ticker.map((t) => (
              <tr key={t.ticker} className="hover:bg-neutral-950">
                <td className="px-3 py-2 font-mono text-neutral-100">{t.ticker}</td>
                <td className="px-3 py-2 text-right font-mono text-neutral-400">
                  {t.bars}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-neutral-500">
                  {t.first_ts ?? "—"}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-neutral-500">
                  {t.last_ts ?? "—"}
                </td>
                <td className="px-3 py-2 text-right font-mono text-neutral-300">
                  {t.last_close != null ? `$${t.last_close.toFixed(2)}` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Stat({ label, v }: { label: string; v: string }) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-3">
      <p className="text-xs uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{v}</p>
    </div>
  );
}
