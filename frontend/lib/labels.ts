/**
 * Mapping centralizzato per tradurre in italiano i label tecnici del backend.
 * Tutto quello che esce dall'API (event_type, source_quality, surprise_*, ecc.)
 * passa da qui prima di essere mostrato all'utente.
 */

export const EVENT_TYPE_IT: Record<string, string> = {
  earnings: "Risultati trimestrali",
  guidance: "Guidance aziendale",
  m_and_a: "Fusioni e acquisizioni",
  contract: "Contratti",
  regulatory: "Regolamentazione",
  macro_data: "Dati macro",
  central_bank: "Banca centrale",
  geopolitical: "Geopolitica",
  product: "Annuncio prodotto",
  clinical_trial: "Trial clinico",
  litigation: "Causa legale",
  personnel: "Cambio personale chiave",
  analyst_rating: "Rating analisti",
  buyback: "Buyback azioni",
  dividend: "Dividendi",
  partnership: "Partnership",
  layoffs: "Tagli del personale",
  bankruptcy: "Bancarotta",
  other: "Altro",
  unclassified: "Da classificare",
};

export const SURPRISE_DIRECTION_IT: Record<string, string> = {
  positive: "Sorpresa positiva",
  negative: "Sorpresa negativa",
  neutral: "In linea con attese",
  uncertain: "Da chiarire",
};

export const SURPRISE_MAGNITUDE_IT: Record<string, string> = {
  low: "lieve",
  medium: "media",
  high: "forte",
};

export const SURPRISE_EMOJI: Record<string, string> = {
  positive: "🟢",
  negative: "🔴",
  neutral: "⚪",
  uncertain: "🟡",
};

export const MARKET_CONFIRMATION_IT: Record<string, string> = {
  did_react: "Il mercato ha reagito",
  did_not_react: "Il mercato è fermo",
  unclear: "Reazione non chiara",
};

export const MARKET_CONFIRMATION_EMOJI: Record<string, string> = {
  did_react: "📈",
  did_not_react: "➖",
  unclear: "❓",
};

export const OUTCOME_LABEL_IT: Record<string, string> = {
  confirmed_direction: "Direzione confermata",
  reversed: "Direzione opposta",
  flat: "Nessun movimento",
  confounded: "Causa incerta",
  pending: "In attesa di valutazione",
};

export const OUTCOME_EMOJI: Record<string, string> = {
  confirmed_direction: "✅",
  reversed: "❌",
  flat: "➖",
  confounded: "⚠️",
  pending: "⏳",
};

export const SOURCE_QUALITY_IT: Record<string, string> = {
  official: "ufficiale",
  primary: "primaria",
  secondary: "secondaria",
  social: "social",
  rumor: "rumor",
};

export const EXPOSURE_TYPE_IT: Record<string, string> = {
  direct: "Diretto",
  peer: "Concorrente",
  supplier: "Fornitore",
  customer: "Cliente",
  etf: "ETF settore",
  commodity: "Commodity",
  country: "Paese",
  sector: "Settore",
};

export const ENTITY_TYPE_IT: Record<string, string> = {
  company: "azienda",
  person: "persona",
  country: "paese",
  commodity: "commodity",
  currency: "valuta",
  etf: "ETF",
  sector: "settore",
  central_bank: "banca centrale",
  industry_term: "termine settore",
  index: "indice",
};

export const SOURCE_FRIENDLY_IT: Record<string, string> = {
  "rss:": "Stampa",
  "polygon:": "Polygon",
  "finnhub:": "Finnhub",
  "sec_edgar:": "SEC EDGAR",
  "fred:": "Fed (FRED)",
};

export function eventTypeIT(value: string): string {
  return EVENT_TYPE_IT[value] ?? value;
}

export function surpriseIT(direction: string, magnitude: string): string {
  const dir = SURPRISE_DIRECTION_IT[direction] ?? direction;
  const mag = SURPRISE_MAGNITUDE_IT[magnitude] ?? magnitude;
  if (direction === "neutral" || direction === "uncertain") return dir;
  return `${dir} ${mag}`;
}

export function outcomeIT(label: string): string {
  return OUTCOME_LABEL_IT[label] ?? label;
}

export function exposureTypeIT(value: string): string {
  return EXPOSURE_TYPE_IT[value] ?? value;
}

export function sourceFriendlyIT(source: string): string {
  for (const [prefix, label] of Object.entries(SOURCE_FRIENDLY_IT)) {
    if (source.startsWith(prefix)) return label;
  }
  return source;
}

export function fmtPctIT(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const pct = v * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function fmtScoreIT(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}

export function impactBadgeColorIT(score: number): string {
  if (score >= 0.85) return "bg-emerald-950 text-emerald-300 border-emerald-700";
  if (score >= 0.7) return "bg-emerald-950 text-emerald-400 border-emerald-800";
  if (score >= 0.5) return "bg-amber-950 text-amber-400 border-amber-800";
  return "bg-neutral-900 text-neutral-400 border-neutral-800";
}

export function surpriseColorIT(direction: string): string {
  const map: Record<string, string> = {
    positive: "text-emerald-400",
    negative: "text-red-400",
    neutral: "text-neutral-400",
    uncertain: "text-amber-400",
  };
  return map[direction] ?? "text-neutral-400";
}
