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

Vedi `README.md` per lo status di fase. Il piano in `.claude/plans/` ha la roadmap completa per fasi (0→8).

## Convenzioni

- **Niente commenti tranne dove il "perché" non è ovvio**. Codice ben nominato si auto-documenta.
- **Niente abbreviazioni "TODO" senza ticket**: se serve un follow-up, vale la pena aprire un task chiaro.
- **Migration Alembic**: una per fase, mai modificare migration già applicate in produzione.
- **Test**: pytest per backend, almeno smoke test per ogni endpoint API e agent.
- **Logging strutturato JSON** (loguru) — necessario per Sentry e per debug post-mortem.

## Disclaimer da preservare

Tutto l'output del prodotto deve includere o presupporre il disclaimer: "ricerca e analisi, non consulenza finanziaria personalizzata".
