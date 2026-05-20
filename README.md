# NewsFinance

Market-impact intelligence system. Trasforma news, earnings, macro e filings in alert verificabili sulla pipeline `Evento → Sorpresa → Esposizione → Reazione anomala → Outcome`.

Vedi il piano completo in `.claude/plans/` o `CLAUDE.md` per l'architettura.

## Status

**Fase 3 completata.** Ingestion + classification + expectation engine attivi.

### Cosa fa già il sistema

- **Ingestion (24/7)** — 6 fonti: RSS (13 feed), SEC EDGAR 8-K, Polygon news + prezzi, Finnhub news + earnings calendar, FRED 17 serie macro
- **Dedup semantico** — Voyage AI `voyage-3.5-lite` (1024d) + pgvector cosine, soglia 0.85, lookback 24h
- **Event classifier** — Claude Haiku 4.5 con tool_use structured output, 20 categorie evento + entity extraction + novelty score
- **Entity linker** — popola tabella `entities` canonical IDs (match per ticker poi name, create se nuovo)
- **Expectation engine ibrido**:
  - earnings → consensus EPS/revenue da Finnhub, calcolo surprise direction+magnitude+z-score
  - macro_data → confronto con FRED prior release come baseline
  - qualitative (M&A, contract, geopolitical, ...) → Sonnet 4.6 con contesto news ultime 90 giorni
- **APScheduler in-process**: classifier ogni 5 min, expectation ogni 10 min, ingestion ogni 2-30 min, prezzi update daily

### Frontend pubblico

https://news-finance-xi.vercel.app

- `/` system status (DB + Redis + API health)
- `/feed` stream live raw_events con filtri per fonte
- `/clusters` cluster classificati con event_type, entities, surprise direction/magnitude
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
