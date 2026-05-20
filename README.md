# NewsFinance

Market-impact intelligence system. Trasforma news, earnings, macro e filings in alert verificabili sulla pipeline `Evento → Sorpresa → Esposizione → Reazione anomala → Outcome`.

Vedi il piano completo in `.claude/plans/` o `CLAUDE.md` per l'architettura.

## Status

**Fase 1 — Ingestion attiva in produzione.**
- 6 ingester attivi: RSS (13 feed), SEC EDGAR 8-K, Polygon news + prezzi, Finnhub news + earnings calendar, FRED 17 serie macro
- Backfill 1 anno completato: 97 ticker × 252 giorni = 24.444 daily bars
- Dedup engine: Voyage AI voyage-3.5-lite + pgvector cosine similarity, soglia 0.85
- Worker scheduler APScheduler in-process: tutti i job girano ogni 2-30 min in automatico
- Frontend pubblico: https://news-finance-xi.vercel.app
  - `/` system status
  - `/feed` raw event stream con filtri per fonte
  - `/coverage` stato copertura prezzi per ticker

Servizi in produzione: Vercel + Railway Hobby + Neon Postgres free + Upstash Redis free. Costo operativo ~$60/mese (Polygon $29 + Railway $5-8 + LLM in Fase 2).

**Prossime fasi:** classifier evento → expectation engine → exposure graph → market reaction → confounder → scoring → outcome tracking.

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
