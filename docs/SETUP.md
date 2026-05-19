# Setup — Fase 0 (Foundation)

Questa guida ti porta da repo vuoto a backend + frontend pubblicati online. Tutti i servizi della Fase 0 sono **gratuiti** — la spesa inizia dalla Fase 1 quando attivi le API dati.

Hai 4 account da creare (tutti free tier). L'ordine conta perché alcuni passi dipendono da output di passi precedenti.

## 1. Neon (Postgres) — ~5 min

Postgres serverless gratuito (0.5 GB storage, sufficiente per mesi di dati).

1. Vai su https://neon.tech e fai signup con GitHub (più semplice).
2. Crea un nuovo project: nome `newsfinance`, regione **AWS us-east-1** (vicino a dove deployeremo il backend).
3. Una volta creato, copia la **connection string** dalla dashboard. Sarà nel formato:
   ```
   postgresql://user:pass@ep-xxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
4. **Trasformala** per asyncpg (driver async che usiamo):
   - Sostituisci `postgresql://` con `postgresql+asyncpg://`
   - Sostituisci `?sslmode=require` con `?ssl=require`
   - Esempio finale:
     ```
     postgresql+asyncpg://user:pass@ep-xxx-pooler.us-east-1.aws.neon.tech/neondb?ssl=require
     ```
5. Tieni questa stringa da parte — sarà la variabile `DATABASE_URL`.

**Importante**: Neon ha già l'estensione `pgvector` installata, ma è disabilitata per default. La migration `0001_initial_schema.py` esegue `CREATE EXTENSION IF NOT EXISTS vector` quindi si attiva da sola al primo `alembic upgrade head`.

## 2. Upstash (Redis) — ~3 min

Redis serverless gratuito (10k comandi/giorno + 256MB).

1. Vai su https://upstash.com e fai signup con GitHub.
2. Crea un nuovo Redis database: nome `newsfinance-redis`, regione **us-east-1**, tipo **Regional**, Eviction **disabled**.
3. Nella sezione "Connect" copia il **TLS Connection String** (inizia con `rediss://`, doppia s per TLS):
   ```
   rediss://default:xxxxxxx@us1-loyal-mole-12345.upstash.io:6379
   ```
4. Tieni questa stringa da parte — sarà la variabile `REDIS_URL`.

## 3. Backend in locale — verifica che tutto funzioni

Prima di deployare, valida in locale che lo stack veda i database cloud.

```bash
cd backend
cp .env.example .env
```

Apri `backend/.env` e sostituisci:
- `DATABASE_URL=...` con la stringa Neon (formato asyncpg)
- `REDIS_URL=...` con la stringa Upstash

Poi:

```bash
# Installa dipendenze + applica migration
uv sync
uv run alembic upgrade head

# Verifica che le 13 tabelle siano state create su Neon
uv run python -c "
import asyncio
from sqlalchemy import text
from app.core.db import engine
async def show():
    async with engine.connect() as conn:
        result = await conn.execute(text(
            \"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename\"
        ))
        for row in result:
            print(row[0])
asyncio.run(show())
"

# Avvia il server
uv run uvicorn app.main:app --reload
```

Apri http://localhost:8000/api/health/full — dovresti vedere `{"status":"ok","checks":{"database":true,"redis":true}}`.

In un altro terminale:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Apri http://localhost:3000 — dovresti vedere "API / Database / Redis" tutti **online**.

## 4. Push iniziale su GitHub

```bash
git add .
git commit -m "phase 0: foundation scaffold"
git push -u origin main
```

(Da qui partirà la CI su GitHub Actions.)

## 5. Railway (backend deploy) — ~10 min

1. Vai su https://railway.app e fai signup con GitHub.
2. Crea un nuovo project → "Deploy from GitHub repo" → seleziona `aagnoli-beep/NewsFinance`.
3. Railway rileverà il repo. Imposta nelle **Settings** del service:
   - **Root Directory**: `backend`
   - Build/Start command: lascia vuoti — verranno letti automaticamente da `backend/Procfile` e `backend/railway.toml` (Nixpacks rileva `uv.lock` e usa uv).
   - La migration Alembic gira automaticamente al deploy via il `release:` step del Procfile.
4. Nella sezione **Variables** aggiungi:
   ```
   DATABASE_URL=<la tua stringa Neon asyncpg>
   REDIS_URL=<la tua stringa Upstash>
   ENV=production
   CORS_ORIGINS=https://newsfinance.vercel.app
   AUTH_SECRET=<genera con: openssl rand -hex 32>
   ```
   Le altre variabili (API keys) le aggiungeremo in Fase 1, possono restare vuote ora.
5. Una volta deployato, Railway ti dà un dominio tipo `https://newsfinance-production.up.railway.app`. Aprilo + `/api/health` per verificare.
6. Annota questo URL — sarà `NEXT_PUBLIC_API_URL` per il frontend.

**Costo**: hobby tier $5/mese di crediti gratuiti per i primi 30 giorni, poi ~$5–10/mese per traffico basso. Niente fattura senza azione manuale.

## 6. Vercel (frontend deploy) — ~5 min

1. Vai su https://vercel.com e fai signup con GitHub.
2. New Project → seleziona `aagnoli-beep/NewsFinance`.
3. Configurazione:
   - **Framework Preset**: Next.js (auto-rilevato)
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` (default)
4. **Environment Variables**:
   ```
   NEXT_PUBLIC_API_URL=https://<il-tuo-url-railway>
   ```
5. Deploy. Vercel ti dà un dominio tipo `https://newsfinance.vercel.app`.

Apri quell'URL: dovresti vedere la dashboard "System status" con API/Database/Redis tutti online. **Questo è il sito che hai chiesto**.

## 7. Aggiorna CORS sul backend

Torna su Railway → Variables → assicurati che `CORS_ORIGINS` contenga l'URL esatto Vercel (es. `https://newsfinance.vercel.app`). Se cambia, redeploya.

## Checklist finale Fase 0

- [ ] Neon project creato, connection string asyncpg pronta
- [ ] Upstash Redis creato, rediss:// pronta
- [ ] Backend in locale risponde `/api/health/full` con tutto `true`
- [ ] Frontend in locale a localhost:3000 mostra tutto online
- [ ] Push iniziale fatto, GitHub Actions verde
- [ ] Railway deploy verde, backend pubblico raggiungibile
- [ ] Vercel deploy verde, frontend pubblico raggiungibile e collegato al backend
- [ ] CORS Vercel→Railway funziona (no errori in DevTools console)

Quando questa checklist è completa, Fase 0 è chiusa. Passiamo alla Fase 1 (ingestion).

## Prossima fase — preview costi

Da Fase 1 in poi servono API a pagamento:

| Servizio | Costo/mese | Quando |
|---|---|---|
| Polygon Stocks Starter | ~$29 | Inizio Fase 1 |
| Marketaux News | ~$25 | Inizio Fase 1 |
| Finnhub | $0 (free tier) | Inizio Fase 3 |
| FRED | $0 | Inizio Fase 1 |
| Trading Economics | $0 (free tier) | Inizio Fase 3 |
| Anthropic API (Claude) | ~$30–50 stimati | Inizio Fase 2 |
| Voyage AI (embeddings) | $0 (free tier 50M token/mese) | Inizio Fase 1 |
| Resend (magic link auth) | $0 (free tier 3k email/mese) | Fase 8 |

Totale realistico operativo a regime: **~$100–130/mese** (~95–125 €).
