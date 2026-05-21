"use client";

import { useEffect, useState } from "react";

type HealthCheck = {
  status: string;
  checks?: { database: boolean; redis: boolean };
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function SystemStatus() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(`${API_URL}/api/health/full`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as HealthCheck;
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "fetch failed");
      }
    }

    load();
    const handle = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, []);

  if (error) {
    return (
      <p className="mt-4 text-sm text-red-400">
        Backend non raggiungibile: <span className="font-mono">{error}</span>
      </p>
    );
  }

  if (!health) {
    return <p className="mt-4 text-sm text-neutral-500">Caricamento…</p>;
  }

  return (
    <div className="mt-4 space-y-2 text-sm">
      <StatusRow label="API (backend)" ok={health.status === "ok"} />
      <StatusRow label="Database (Postgres)" ok={health.checks?.database ?? false} />
      <StatusRow label="Cache (Redis)" ok={health.checks?.redis ?? false} />
    </div>
  );
}

function StatusRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-neutral-900 px-3 py-2">
      <span className="text-neutral-300">{label}</span>
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
          ok ? "bg-emerald-950 text-emerald-400" : "bg-red-950 text-red-400"
        }`}
      >
        {ok ? "attivo" : "offline"}
      </span>
    </div>
  );
}
