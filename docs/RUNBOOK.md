# Runbook

Procedure operative comuni per riprendere il lavoro o intervenire in caso di problemi.

## Sviluppo quotidiano

### Avviare lo stack in locale

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload

# Frontend (altro terminale)
cd frontend && npm run dev
```

### Creare una nuova migration Alembic

Dopo aver modificato i modelli SQLAlchemy:

```bash
cd backend
uv run alembic revision --autogenerate -m "descrizione breve"
# Ispeziona il file generato in alembic/versions/ prima di applicare
uv run alembic upgrade head
```

### Eseguire ruff + test

```bash
cd backend
uv run ruff check . --fix
uv run pytest -q
```

```bash
cd frontend
npm run typecheck
npm run build
```

## Deploy

### Force redeploy del backend Railway

Push qualunque commit su `main`. Railway riavvia in 1–2 minuti. Se serve forzare senza commit: dashboard Railway → "Deployments" → "..." → Redeploy.

### Verificare che la migration sia stata applicata

```bash
# In locale puntando al DB di produzione (temporaneo, NO commit del .env)
cd backend
DATABASE_URL="<neon-url-asyncpg>" uv run alembic current
```

### Rollback di una migration

```bash
DATABASE_URL="<neon-url-asyncpg>" uv run alembic downgrade -1
```

Mai farlo in produzione senza prima fare un dump:

```bash
pg_dump "<neon-url-without-asyncpg-prefix>" > backup-$(date +%Y%m%d).sql
```

## Debug comune

### "asyncpg.exceptions.InvalidAuthorizationSpecificationError"

Probabilmente la connection string Neon non è stata trasformata correttamente. Verifica:
- prefisso `postgresql+asyncpg://`
- parametro `?ssl=require` (non `?sslmode=require`, che è il formato libpq sincrono)

### Frontend mostra "Backend non raggiungibile"

1. Apri DevTools → Network: cerca la chiamata a `/api/health/full`.
2. Se è CORS: aggiorna `CORS_ORIGINS` su Railway per includere il dominio Vercel.
3. Se è 502/504: il backend Railway è down, controlla logs su Railway.

### Embedding query lenta

L'indice HNSW su `event_clusters.embedding` viene creato in migration 0001. Se le query a similarità sono lente, verifica:

```sql
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'event_clusters';
```

Dovresti vedere `ix_event_clusters_embedding USING hnsw`.

## Quando rivolgersi a Claude in una nuova sessione

Apri Claude Code nella cartella `~/Desktop/Github NewsFinanze/` e inizia con:

> Sto lavorando al progetto NewsFinance. Leggi CLAUDE.md e il piano in .claude/plans/ per il contesto. Siamo a Fase X.

Il file `CLAUDE.md` contiene stack + convenzioni; il piano contiene la roadmap completa.
