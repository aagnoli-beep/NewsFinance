/**
 * Client API condiviso. Punta al backend Railway in prod, localhost in dev.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const response = await fetch(url, {
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export type RawEvent = {
  id: number;
  source: string;
  source_quality: string;
  headline: string;
  body: string | null;
  source_url: string | null;
  published_at: string | null;
  ingested_at: string;
  cluster_id: number | null;
  raw_meta: Record<string, unknown>;
};

export type FeedResponse = {
  items: RawEvent[];
  total: number;
  has_more: boolean;
};

export type SourceCount = {
  source: string;
  count: number;
};

export type FeedStats = {
  total_events: number;
  total_clusters: number;
  pending_dedup: number;
  last_24h: number;
  sources: SourceCount[];
};

export type TickerCoverage = {
  ticker: string;
  bars: number;
  first_ts: string | null;
  last_ts: string | null;
  last_close: number | null;
};

export type CoverageResponse = {
  universe_size: number;
  covered_tickers: number;
  missing_tickers: string[];
  total_bars: number;
  by_ticker: TickerCoverage[];
};

export type ClusterEntity = {
  id: number;
  type: string;
  name: string;
  ticker: string | null;
  role: string;
};

export type ClusterExpectation = {
  baseline_source: string;
  expected_value: string | null;
  actual_value: string | null;
  surprise_direction: string;
  surprise_magnitude: string;
  surprise_zscore: number | null;
  rationale: string | null;
};

export type Cluster = {
  id: number;
  first_seen: string;
  event_type: string;
  headline_canonical: string;
  summary: string | null;
  novelty_score: number;
  n_sources: number;
  entities: ClusterEntity[];
  expectation: ClusterExpectation | null;
};

export type ClusterListResponse = {
  items: Cluster[];
  total: number;
};

export type ClusterStats = {
  total_clusters: number;
  classified: number;
  with_expectations: number;
  by_type: Array<{ event_type: string; count: number }>;
};

export type AlertEntity = {
  id: number;
  name: string;
  ticker: string | null;
  role: string;
};

export type AlertExposure = {
  asset_ticker: string;
  exposure_type: string;
  hop_distance: number;
  weight: number;
  rationale: string | null;
};

export type AlertReaction = {
  ticker: string;
  abnormal_return_1d: number | null;
  abnormal_return_3d: number | null;
  volume_zscore: number | null;
  market_confirmation: string | null;
};

export type AlertExpectation = {
  surprise_direction: string;
  surprise_magnitude: string;
  rationale: string | null;
};

export type AlertOutcome = {
  t_plus_1d_ar: number | null;
  t_plus_3d_ar: number | null;
  t_plus_7d_ar: number | null;
  t_plus_30d_ar: number | null;
  outcome_label: string;
  evaluated_at: string | null;
};

export type Alert = {
  id: number;
  cluster_id: number;
  created_at: string;
  impact_score: number;
  confidence: number;
  explanation_md: string;
  components: Record<string, unknown>;
  event_type: string;
  headline: string;
  summary: string | null;
  first_seen: string;
  novelty_score: number;
  primary_entities: AlertEntity[];
  exposures: AlertExposure[];
  reactions: AlertReaction[];
  expectation: AlertExpectation | null;
  outcome: AlertOutcome | null;
  confounder_count: number;
  max_confounder_score: number | null;
};

export type AlertListResponse = {
  items: Alert[];
  total: number;
};

export type AlertsStats = {
  total_alerts: number;
  last_24h: number;
  last_7d: number;
  avg_impact_score: number | null;
  outcomes: Record<string, number>;
  precision_3d: number | null;
};
