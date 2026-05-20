# 🌅 Buongiorno — riassunto cosa è successo stanotte

## TL;DR

Phase 2 e Phase 3 sono **deployate in produzione**, ma il classifier ed expectation qualitative **dormono** finché non aggiungi una variabile a Railway. Apri Railway e in 30 secondi accendi tutto.

Apri: **https://news-finance-xi.vercel.app/clusters** — adesso vedrai 0 cluster classificati (perché manca `ANTHROPIC_API_KEY`). Dopo che la aggiungi → entro 5 min vedi i primi classificati.

## 1. Cosa ho costruito autonomamente (commit `c314c89`)

### Phase 2 — Event classifier + entity linker
- **`event_classifier.py`** — Usa Claude Haiku 4.5 via `tool_use` per JSON garantito strutturato. Estrae `event_type` (20 categorie tipo earnings/m_and_a/macro_data/...), `entities` (azienda, persona, country, commodity, ...), `novelty_score`, `summary`, `sentiment`. Prompt caching attivo.
- **`entity_linker.py`** — Risolve ogni entità estratta a un ID canonico nella tabella `entities`. Match per ticker prima, poi nome. Crea entry nuova se non esiste.
- **`agents/schemas.py`** — Pydantic models per output strutturato dei LLM.

### Phase 3 — Expectation engine (ibrido)
- **`expectation.py`** — Tre path:
  - **earnings**: pull EPS/revenue consensus da Finnhub (era già nel `raw_meta` degli earnings_calendar). Calcola direction + magnitude + z-score.
  - **macro_data**: confronto con prior release FRED. Magnitude basata su % delta.
  - **qualitative** (M&A, contract, geopolitical, regulatory, ...): Sonnet 4.6 con contesto delle ultime 10 news della stessa entità nei 90 giorni precedenti. Decide se la sorpresa è positive/negative/neutral/uncertain.
- Salva in tabella `expectations` (PK = cluster_id, quindi unique per cluster).

### Worker scheduler aggiornato
- Classifier: ogni 5 min
- Expectation engine: ogni 10 min
- Tutti i job precedenti continuano (ingestion + dedup + prezzi)

### Backend API
- `GET /api/clusters` — lista cluster classificati, filtrabile per `event_type`
- `GET /api/clusters/stats` — totali + breakdown by type
- `GET /api/clusters/{id}` — dettaglio singolo cluster con entities + expectation

### Frontend
- `/clusters` — nuova pagina con surprise badge (positive/negative + low/medium/high), entity chips primary/mentioned, filtri per tipo evento, refresh 30s
- Nav aggiornata: Status / Feed / **Clusters** / Coverage

### Test
- `tests/test_expectation_math.py` — 8 casi parametrizzati per la math dell'earnings surprise (direction + magnitude + z-score sign)
- Tutti i 11 test pytest passano

## 2. Cosa devi fare tu (30 secondi)

Vai su **Railway → service NewsFinance → tab Variables → Raw Editor**. Aggiungi UNA riga:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Se non hai una key Anthropic API:
1. Vai su https://console.anthropic.com
2. Sign in (probabilmente già loggato perché usi Claude Code)
3. Settings → API Keys → Create Key
4. Copia la chiave (inizia con `sk-ant-...`)
5. Incollala su Railway

Save. Railway redeploya in 3-5 min. **Da quel momento**:
- Classifier inizia a processare i 600+ cluster `unclassified` esistenti (al ritmo di 50 ogni 5 min → 1-2 ore per smaltire tutti)
- Expectation engine inizia in parallelo
- Su `/clusters` vedrai i risultati comparire progressivamente

## 3. Cosa controllare quando sei sveglio

```bash
# Conta cluster classificati
curl -s https://newsfinance-production.up.railway.app/api/clusters/stats | jq

# Vedi primi 5 cluster classificati
curl -s "https://newsfinance-production.up.railway.app/api/clusters?limit=5" | jq '.items[].event_type, .items[].headline_canonical'
```

Oppure più semplicemente: apri https://news-finance-xi.vercel.app/clusters

## 4. Costo stimato dopo l'attivazione

- Classifier (Haiku 4.5): ~$0.001 per cluster. Con 200 cluster/giorno → ~$6/mese
- Expectation qualitative (Sonnet 4.6): ~$0.01 per cluster. Con ~50 cluster/giorno → ~$15/mese
- **Totale Anthropic stimato: $20-30/mese** (prompt caching riduce ulteriormente)

Costo totale operativo ora: ~**$65-90/mese**.

## 5. Stato attuale del database (al momento del deploy)

```
raw_events:     1.300+ (cresce in automatico)
event_clusters: 844 (594 in più rispetto a quando hai dormito, da dedup)
prices:         24.444 (97 ticker × 252 giorni)
classified:     0 (in attesa di ANTHROPIC_API_KEY)
expectations:   0 (in attesa di ANTHROPIC_API_KEY)
```

## 6. Se qualcosa va storto

- **Railway non redeploya dopo l'aggiunta della key** → vai su Deployments tab e click `...` → Redeploy sull'ultimo deploy attivo
- **Classifier fa errori** → controlla logs Railway: i warning `classifier_*` sono espliciti
- **Costi più alti del previsto** → vai su https://console.anthropic.com → Settings → Limits e imposta uno spending cap (es. $50/mese)
- **Vuoi disattivare temporaneamente classifier/expectation** → su Railway aggiungi `WORKER_ENABLED=false`, redeploya. Tutto si ferma. Ringraziami stasera.

Buongiorno.
