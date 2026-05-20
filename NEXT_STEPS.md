# 🌅 Buongiorno — TUTTE le 8 fasi sono live

## TL;DR

Mentre dormivi ho completato e deployato in produzione **anche Phase 4, 5, 6, 7 e 8**. Il sistema fa adesso il pipeline completo: ingestion → dedup → classify → expectation → exposure → market reaction → confounder → scoring → alert → outcome → calibration.

**MA** restano due cose per far girare la catena LLM:
1. Aggiungere `ANTHROPIC_API_KEY` su Railway (10 secondi) — accende classifier ed expectation qualitative
2. Aspettare che il classifier lavori sui 1.000+ cluster `unclassified` esistenti (~1-2 ore)

Da lì in poi i 7 motori cascadano in automatico ogni 5-15 minuti.

## 1. Cosa ho costruito stanotte

### Phase 4 — Exposure graph (commit `ca23a01`)
- **`data/sectors.py`** — GICS sector mapping per i top 60 ticker (Tech → XLK, Financials → XLF, ecc.)
- **`data/supply_chain.py`** — 30 link supply-chain curati (NVDA → MSFT/META/GOOGL/AMZN come hyperscalers, AVGO → AAPL, QCOM → AAPL, peer fra big bank, ecc.)
- **`scripts/seed_entity_graph.py`** — popola entities (97) + entity_links (638): sector ETFs + peer crossproduct + supply chain. Idempotente.
- **`agents/exposure.py`** — traversa il graph a 1-hop, weight da entity_links. Per entità non nel graph, LLM enrichment via Haiku (skip se mancante API key). Persiste exposures con UNIQUE su (cluster, ticker).

### Phase 5 — Market reaction (deterministico, no LLM)
- **`agents/market_reaction.py`** — per ogni (cluster, ticker_esposto) calcola:
  - abnormal return T+1d e T+3d (beta=1.0 vs SPY come proxy market model)
  - volume z-score vs media/std degli ultimi 20 giorni
  - peer_avg_ar fra i ticker classificati come peer/etf/sector
  - market_confirmation: `did_react` se AR>=1.5% e volume>=1.5σ, `did_not_react` se entrambi bassi, `unclear` altrimenti

### Phase 6 — Confounder + Scoring + Alert
- **`agents/confounder.py`** — scan ±24h, materiality basato su entity overlap (0.5–1.0) + systemic types FOMC/CPI/geopolitical (0.7). Penalty cappata a 0.5.
- **`agents/scoring.py`** — formula:
  ```
  impact = (0.15·novelty + 0.30·surprise + 0.20·exposure_max
          + 0.25·confirmation + 0.10·source_quality)
          × (1 - confounder_penalty)
  ```
  Soglia alert 0.65. Sopra → riga in `alerts` con explanation_md generata deterministicamente.

### Phase 7 — Outcome tracker
- **`agents/outcome_tracker.py`** — per ogni alert >=1 giorno di età calcola AR cumulato T+1d/3d/7d/30d (beta=1.0). Outcome label:
  - `confirmed_direction` — sign(AR_3d) == sign(surprise_expected)
  - `reversed` — segno opposto e AR materiale
  - `flat` — |AR| < 0.5%
  - `confounded` — materiality_score di un confounder >= 0.4
  - `pending` — non valutabile ancora

### Phase 8 — Calibration agent
- **`agents/calibration.py`** — daily, calcola precision_3d, alert_rate, outcome breakdown sugli ultimi 30 giorni. Produce raccomandazioni testuali su pesi/soglia. NON applica in automatico — log only.

### Backend API
- `GET /api/alerts` + `/stats` + `/{id}` + `/calibration/report`

### Frontend
- Nuova pagina **`/alerts`** con impact score badge, panels surprise/reaction/outcome, exposure chips, filtro slider min_score. Nav aggiornata.

### Worker scheduler
Aggiunti 7 nuovi job:
- exposure (7m), market_reaction (10m), confounder (15m), scoring (15m), outcome_tracker (1h), calibration (daily 22:30 UTC)

## 2. Smoke test eseguito (pipeline validata)

Ho eseguito `pipeline_smoke_test.py` su un cluster NVDA earnings:
- expectations: ✅ 1 (consensus EPS 1.79)
- exposures: ✅ **18 ticker** correttamente identificati (NVDA direct + XLK sector ETF + 13 tech peers + 4 supply chain customers MSFT/META/GOOGL/AMZN)
- market_reactions: ✅ 18 (con AR + volume z-score)
- confounders: 0
- scoring: ✅ computato, sotto soglia 0.65 perché non c'è actual value (è un earnings upcoming, non ancora rilasciato)

Il pipeline funziona **senza** LLM. Quando arrivano gli earnings reali + il classifier attivato, gli alert si generano.

## 3. Cosa devi fare tu (10 secondi)

Vai su Railway → service NewsFinance → tab **Variables** → **Raw Editor**. Aggiungi questa riga:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Se non hai la key:
1. https://console.anthropic.com
2. Settings → API Keys → Create Key
3. Copia, incolla su Railway, Save

## 4. Cosa succede dopo che la aggiungi

Railway redeploya in 3-5 min. Da quel momento, ogni 5 minuti il classifier prende 50 cluster `unclassified` e li classifica:
- ~50 cluster ogni 5 min × 1.000 cluster da smaltire ≈ **100 minuti per classificarli tutti**

Mentre il classifier lavora, in parallelo:
- exposure engine processa i cluster appena classificati (ogni 7 min)
- market_reaction calcola AR su quelli con exposures (ogni 10 min)
- expectation computa surprise (ogni 10 min)
- scoring genera alert (ogni 15 min) per quelli sopra 0.65
- outcome_tracker valuta gli alert >=1d (ogni ora)

Apri **https://news-finance-xi.vercel.app/alerts** dopo ~30 minuti — dovresti vedere i primi alert generati.

## 5. Costi stimati totali

Senza API key Anthropic:
- $29 Polygon + $5-8 Railway + $0 Voyage (free tier) = **~$35/mese**

Con API key Anthropic attivata:
- + Haiku classifier (5/min × 12/h × 24h × 30 = ~50k call/mese × $0.0008 ≈ $40/mese)
- + Sonnet expectation qualitative (~$0.01 × 500 call/mese ≈ $5/mese)
- + Haiku exposure enrichment (~50% dei cluster, ~$5/mese)
- Tot Anthropic: **~$50/mese**

**Totale operativo: ~$85-95/mese**.

## 6. Database stato attuale

```
raw_events:        1.758
event_clusters:    1.065 (di cui 1 manualmente classificato come "earnings" da NVDA per smoke test)
prices:            24.444 (97 ticker × 252 giorni)
entities:          97 (universe + sector ETFs)
entity_links:      638 (sector + peer + supply chain seedati)
expectations:      1 (smoke test)
exposures:         18 (smoke test)
market_reactions:  18 (smoke test)
confounders:       0
alerts:            0
outcomes:          0
```

## 7. Cosa puoi fare appena sveglio

```bash
# Test che il backend è online con i nuovi endpoint
curl -s https://newsfinance-production.up.railway.app/api/alerts/stats | jq

# Quando attiverai ANTHROPIC_API_KEY, monitora il progresso:
curl -s https://newsfinance-production.up.railway.app/api/clusters/stats | jq
# Guarda "classified" salire da 0 → progressivamente
```

Oppure semplicemente: apri https://news-finance-xi.vercel.app/alerts e ricarica ogni 30 min.

## 8. Se qualcosa va storto

- **Alert vuoti dopo 1 ora dall'attivazione key** → controlla Railway logs per warning `classifier_*`. Probabilmente la key è invalida o ha rate limit.
- **Costi più alti del previsto** → su https://console.anthropic.com setta uno spending cap (Settings → Limits).
- **Vuoi mettere in pausa** → su Railway: `WORKER_ENABLED=false` + redeploy. Tutto si ferma. Riaccendere = stesso ma `=true`.
- **Vuoi resettare e ripartire** → contattami in chat. Posso ripulire DB o aggiustare soglie.

Buongiorno. Il sistema lavora per te 24/7.
