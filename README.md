# NewsFinance

Market-impact intelligence system. Trasforma news, earnings, macro e filings in alert verificabili sulla pipeline `Evento → Sorpresa → Esposizione → Reazione anomala → Outcome`.

Vedi il piano completo in `.claude/plans/` o `CLAUDE.md` per l'architettura.

## Status

**Tutte le 8 fasi completate.** MVP end-to-end attivo: ingestion → dedup → classify → expectation → exposure → market reaction → confounder → scoring → alert → outcome → calibration.

### Cosa fa il sistema end-to-end

```
[ingestion]   RSS · Polygon · SEC EDGAR · Finnhub · FRED          → raw_events
       ↓
[dedup]       Voyage AI voyage-3.5-lite + pgvector cosine 0.85    → event_clusters
       ↓
[classifier]  Claude Haiku 4.5 tool_use, 20 event types + entities → cluster.event_type
       ↓
[entity link] match per ticker/nome, create se mancante           → entities + event_entities
       ↓
[expectation] earnings via Finnhub | macro via FRED prior |
              qualitative via Sonnet 4.6 con news prior 90gg      → expectations
       ↓
[exposure]    direct + peer + supplier/customer + sector ETF
              via entity_links seedato (97 entities, 638 links)
              + Haiku enrichment per entità non nel graph         → exposures
       ↓
[reaction]    abnormal return 1d/3d vs SPY (beta=1) +
              volume z-score vs 20d baseline +
              market_confirmation: did_react / did_not / unclear  → market_reactions
       ↓
[confounder]  scan ±24h, materiality basato su entity overlap +
              systemic event types (FOMC/macro/geopolitical)      → confounders
       ↓
[scoring]     impact = 0.15·novelty + 0.30·surprise +
              0.20·exposure + 0.25·confirm + 0.10·source           → alerts (≥0.65)
              × (1 - confounder_penalty cap 0.5)
       ↓
[outcome]     AR cumulato T+1d/3d/7d/30d, label:
              confirmed | reversed | flat | confounded | pending  → outcomes
       ↓
[calibration] daily report precision_3d + alert_rate + reccs      → log structured
```

### Frontend pubblico

https://news-finance-xi.vercel.app

- `/` system status (DB + Redis + API health)
- `/feed` stream live raw_events con filtri per fonte
- `/clusters` cluster classificati (event_type, entities, surprise)
- `/alerts` alerts con impact_score, surprise, reaction, outcome, exposures
- `/coverage` copertura prezzi per i 97 ticker dell'universe

### Stack

| Layer | Tech | Hosting |
|---|---|---|
| Frontend | Next.js 15 + Tailwind + TypeScript | Vercel free |
| Backend | FastAPI + SQLAlchemy async + APScheduler | Railway Hobby |
| Database | Postgres 17 + pgvector | Neon free |
| Cache/queue | Redis | Upstash free |
| LLM | Claude Haiku 4.5 + Sonnet 4.6 + Voyage AI embeddings | Anthropic + Voyage |
| Data | Polygon Stocks Starter $29 + Finnhub free + FRED free + RSS free | — |

### Costo operativo stimato

- Polygon Stocks Starter: $29/mese
- Railway Hobby: $5-8/mese
- Anthropic Claude (Haiku + Sonnet con caching): $30-50/mese a regime
- Voyage AI: $0 (free tier sufficiente)
- Neon + Upstash + Vercel: $0

**Totale: ~$65-90/mese** a regime di funzionamento normale.

### Prossime fasi (4 → 8)

4. Exposure graph (asset diretti + indiretti via supply chain + ETF + sector)
5. Market reaction engine (abnormal return vs SPY + sector ETF + peer)
6. Confounder detection + impact scoring + alert generation
7. Outcome tracking (T+1d/3d/7d/30d) + dashboard performance
8. Calibration agent + backtest harness + auth + polish

Vedi `docs/SETUP.md` per il deploy iniziale, `docs/RUNBOOK.md` per le operazioni quotidiane.

## Layout

```
backend/    FastAPI + agenti (Python 3.12, uv)
frontend/   Next.js 15 + Tailwind + shadcn/ui
workers/    Cron entry points
infra/      Env templates e configurazioni deploy
docs/       Setup, runbook, schema dati
```

## Quick start locale

Prerequisiti: Python 3.12+, Node 20+, [uv](https://docs.astral.sh/uv/), account Neon (Postgres) e Upstash (Redis).

```bash
# 1. Crea il file .env in backend/ partendo da backend/.env.example
#    e popolalo con DATABASE_URL (Neon) e REDIS_URL (Upstash).

# 2. Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 3. Frontend (in un altro terminale)
cd frontend
npm install
npm run dev
```

Backend su `http://localhost:8000`, frontend su `http://localhost:3000`.

## Disclaimer

Questo è uno strumento di ricerca e analisi, **non** consulenza finanziaria personalizzata. Le segnalazioni del sistema sono ipotesi statistiche su movimenti di mercato, non raccomandazioni di trading.
