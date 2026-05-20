# CLAUDE.md — istruzioni per Claude sul progetto NewsFinance

## Cosa è

Sistema di market-impact intelligence. Trasforma news/earnings/macro/filings in alert verificabili attraverso 7 motori: eventi → sorpresa → esposizione → reazione mercato → confondenti → scoring → outcome tracking. Il piano completo è in `.claude/plans/senti-ho-creato-un-attenzione-cheerful-orbit.md`.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy async, Alembic, Celery+Redis per workers, `uv` come package manager.
- **DB**: Postgres (Neon in cloud) con estensione `pgvector` per embeddings.
- **Cache/queue**: Redis (Upstash in cloud).
- **LLM**: Claude API (Haiku 4.5 per classifier/extractor ad alto volume, Sonnet 4.6 per ragionamento — exposure, confounder, alert explanation). Prompt caching attivo.
- **Embeddings**: Voyage AI `voyage-3-lite` (più economico di OpenAI).
- **Frontend**: Next.js 15 App Router, Tailwind, shadcn/ui, recharts/tremor.
- **Hosting**: Railway (backend+workers), Vercel (frontend), Neon (Postgres), Upstash (Redis).
- **Auth**: magic link via Resend, single user.

## Layout repo

```
backend/
  app/
    api/          # endpoint REST FastAPI
    agents/       # 9 agenti pipeline (classifier, expectation, exposure, ...)
    ingestion/    # connector per fonte (polygon, marketaux, rss, sec_edgar, fred, ...)
    models/       # SQLAlchemy
    core/         # config, db, redis_client, llm_client
  alembic/        # migrations
  tests/
frontend/
  app/(dashboard)/...
  components/
workers/          # entry point cron per outcome tracker e calibration
infra/            # env templates, railway.toml
docs/             # SETUP.md, RUNBOOK.md
```

## Universo iniziale

S&P 500 + macro USA + commodity principali (Brent, WTI, oro, DXY, TNX). Niente azioni italiane in fase MVP.

## Vincoli importanti

- **Budget API**: ~54 $/mese (Polygon Starter $29 + Marketaux $25 + Finnhub free). Non superare senza approvazione.
- **Soglia alert iniziale alta** (`impact_score ≥ 0.65`): meglio pochi alert buoni che molti rumorosi.
- **L'agente di scoring NON deve vedere prezzi futuri**. Outcome valutato in cron separato, temporalmente posteriore.
- **Dedup aggressivo**: una stessa news riportata da 3 fonti = 1 cluster, non 3 alert.
- **Confidenza esplicita**: ogni alert ha "did react / did not react / unclear" — niente forzature.

## Stato attuale

**Fase 3 completata.** Sistema in produzione con:
- 5 fonti di ingestion (RSS, Polygon news, SEC EDGAR, Finnhub, FRED) + 1 di prezzi (Polygon)
- Dedup semantico via Voyage AI voyage-3.5-lite + pgvector cosine similarity (soglia 0.85)
- Event classifier (Claude Haiku 4.5, tool_use): event_type 20 cat, entities, novelty, summary
- Entity linker che popola `entities` canonical IDs
- Expectation engine ibrido: earnings via Finnhub consensus, macro via FRED prior, qualitative via Sonnet 4.6
- Frontend Next.js: pagine Status/Feed/Clusters/Coverage
- APScheduler in-process, tutti i job ogni 2-30 min

Code paths:
- `backend/app/ingestion/` — 6 ingester + dedup
- `backend/app/agents/` — classifier + entity_linker + expectation
- `backend/app/worker/scheduler.py` — APScheduler
- `backend/app/api/` — health, events, coverage, clusters

Vedi `README.md` per il delivery. Il piano in `.claude/plans/` ha la roadmap fasi (0→8).

## Note operative per Claude in nuove sessioni

- **API key richieste**: `ANTHROPIC_API_KEY` è obbligatoria per attivare classifier/expectation qualitative. Le altre key (Polygon, Voyage, Finnhub, FRED) sono già su Railway.
- **Test classifier locale**: aggiungi `ANTHROPIC_API_KEY=sk-ant-...` in `backend/.env`, poi `uv run python -m app.scripts.classify_clusters --limit 5`.
- **Test expectation locale**: dopo classifier, `uv run python -m app.scripts.compute_expectations --limit 5`.
- **Smoke test produzione**: `curl https://newsfinance-production.up.railway.app/api/clusters/stats` e `/api/coverage`.
- **Frontend**: https://news-finance-xi.vercel.app — pagine `/feed`, `/clusters`, `/coverage`.

## Convenzioni

- **Niente commenti tranne dove il "perché" non è ovvio**. Codice ben nominato si auto-documenta.
- **Niente abbreviazioni "TODO" senza ticket**: se serve un follow-up, vale la pena aprire un task chiaro.
- **Migration Alembic**: una per fase, mai modificare migration già applicate in produzione.
- **Test**: pytest per backend, almeno smoke test per ogni endpoint API e agent.
- **Logging strutturato JSON** (loguru) — necessario per Sentry e per debug post-mortem.

## Disclaimer da preservare

Tutto l'output del prodotto deve includere o presupporre il disclaimer: "ricerca e analisi, non consulenza finanziaria personalizzata".
