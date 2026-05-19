# NewsFinance

Market-impact intelligence system. Trasforma news, earnings, macro e filings in alert verificabili sulla pipeline `Evento → Sorpresa → Esposizione → Reazione anomala → Outcome`.

Vedi il piano completo in `.claude/plans/` o `CLAUDE.md` per l'architettura.

## Status

**Fase 0 — Foundation completata in locale.** Backend FastAPI + frontend Next.js compilano e funzionano; lo schema DB completo (13 tabelle) è in Alembic. Mancano solo i deploy effettivi che richiedono i tuoi account su Neon, Upstash, Railway e Vercel — segui `docs/SETUP.md` passo passo.

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
