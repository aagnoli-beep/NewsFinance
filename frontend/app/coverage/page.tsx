"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { apiFetch, type CoverageResponse } from "@/lib/api";

export default function CoveragePage() {
  const [data, setData] = useState<CoverageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<CoverageResponse>("/api/coverage")
      .then((d) => !cancelled && setData(d))
      .catch((err) =>
        !cancelled &&
        setError(err instanceof Error ? err.message : "fetch failed")
      );
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <Nav />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Coverage</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Stato del backfill prezzi per i 97 ticker dell'universe iniziale.
        </p>
      </header>

      {error && (
        <p className="text-sm text-red-400">
          Errore: <span className="font-mono">{error}</span>
        </p>
      )}

      {!data ? (
        <p className="text-sm text-neutral-500">Caricamento…</p>
      ) : (
        <>
          <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Universe" value={data.universe_size.toLocaleString()} />
            <StatCard label="Covered" value={data.covered_tickers.toLocaleString()} />
            <StatCard label="Missing" value={data.missing_tickers.length.toLocaleString()} />
            <StatCard label="Total bars" value={data.total_bars.toLocaleString()} />
          </section>

          {data.missing_tickers.length > 0 && (
            <section className="mb-6 rounded-md border border-amber-900 bg-amber-950/30 p-4 text-sm">
              <p className="font-medium text-amber-400">Ticker senza prezzi:</p>
              <p className="mt-2 font-mono text-xs text-amber-300">
                {data.missing_tickers.join(", ")}
              </p>
            </section>
          )}

          <div className="overflow-x-auto rounded-md border border-neutral-900">
            <table className="w-full text-left text-sm">
              <thead className="bg-neutral-950 text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-3 py-2">Ticker</th>
                  <th className="px-3 py-2 text-right">Bars</th>
                  <th className="px-3 py-2">From</th>
                  <th className="px-3 py-2">To</th>
                  <th className="px-3 py-2 text-right">Last close</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-900">
                {data.by_ticker.map((t) => (
                  <tr key={t.ticker} className="hover:bg-neutral-950">
                    <td className="px-3 py-2 font-mono text-neutral-100">{t.ticker}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-neutral-400">
                      {t.bars}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-neutral-500">
                      {t.first_ts ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-neutral-500">
                      {t.last_ts ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-neutral-300">
                      {t.last_close != null ? `$${t.last_close.toFixed(2)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
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
