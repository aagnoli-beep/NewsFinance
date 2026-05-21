"use client";

import type { Alert, AlertExposure } from "@/lib/api";
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

export function AlertCard({ alert }: { alert: Alert }) {
  const ts = new Date(alert.created_at);
  const topReaction = alert.reactions
    .filter((r) => r.abnormal_return_1d !== null)
    .sort(
      (a, b) =>
        Math.abs(b.abnormal_return_1d || 0) - Math.abs(a.abnormal_return_1d || 0)
    )[0];

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

      <h3 className="text-base font-medium leading-snug text-neutral-100">
        {alert.headline}
      </h3>
      {alert.summary && (
        <p className="mt-1 text-sm text-neutral-400">{alert.summary}</p>
      )}

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

      {alert.exposures.length > 0 && (
        <Section icon="🎯">
          <SectionTitle>Aziende potenzialmente impattate</SectionTitle>
          <div className="mt-1.5 space-y-1 text-sm text-neutral-300">
            {expGroups.map(({ type, tickers }) => (
              <div key={type} className="flex gap-2">
                <span className="text-neutral-500 min-w-[110px]">
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

      {alert.outcome && (
        <Section icon={OUTCOME_EMOJI[alert.outcome.outcome_label] || "⏳"}>
          <SectionTitle
            className={outcomeColorIT(alert.outcome.outcome_label)}
          >
            {outcomeIT(alert.outcome.outcome_label)}
          </SectionTitle>
          {alert.outcome.outcome_label !== "pending" && (
            <p className="mt-1 text-sm text-neutral-300">
              <span className="text-neutral-500">1 giorno:</span>{" "}
              <ARSpan v={alert.outcome.t_plus_1d_ar} />
              <span className="text-neutral-600"> · </span>
              <span className="text-neutral-500">3 giorni:</span>{" "}
              <ARSpan v={alert.outcome.t_plus_3d_ar} />
              <span className="text-neutral-600"> · </span>
              <span className="text-neutral-500">7 giorni:</span>{" "}
              <ARSpan v={alert.outcome.t_plus_7d_ar} />
              {alert.outcome.t_plus_30d_ar !== null && (
                <>
                  <span className="text-neutral-600"> · </span>
                  <span className="text-neutral-500">30 giorni:</span>{" "}
                  <ARSpan v={alert.outcome.t_plus_30d_ar} />
                </>
              )}
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

function ARSpan({ v }: { v: number | null }) {
  if (v === null || v === undefined)
    return <span className="font-mono text-neutral-500">—</span>;
  const sign = v >= 0;
  return (
    <span
      className={`font-mono tabular-nums ${
        sign ? "text-emerald-400" : "text-red-400"
      }`}
    >
      {fmtPctIT(v)}
    </span>
  );
}

function outcomeColorIT(label: string): string {
  const map: Record<string, string> = {
    confirmed_direction: "text-emerald-400",
    reversed: "text-red-400",
    flat: "text-neutral-400",
    confounded: "text-amber-400",
    pending: "text-blue-400",
  };
  return map[label] ?? "text-neutral-200";
}

function groupExposuresByType(
  exposures: AlertExposure[]
): { type: string; tickers: string[] }[] {
  const groups: Record<string, string[]> = {};
  const order = [
    "direct",
    "peer",
    "etf",
    "supplier",
    "customer",
    "sector",
    "commodity",
    "country",
  ];
  for (const exp of exposures) {
    const t = exp.exposure_type;
    if (!groups[t]) groups[t] = [];
    if (!groups[t].includes(exp.asset_ticker)) groups[t].push(exp.asset_ticker);
  }
  return order
    .filter((t) => groups[t])
    .map((t) => ({ type: t, tickers: groups[t] }));
}
