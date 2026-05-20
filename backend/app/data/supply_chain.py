"""Lista curata di link supply-chain noti.

Triple (from_ticker, to_ticker, link_type) — l'orientamento è "from impatta to":
- supplier: from fornisce a to (notizia su from → to potenzialmente impattata)
- customer: from è cliente di to (notizia su from → to potenzialmente impattata)
- peer: from e to competono direttamente (per casi non coperti dal mapping settoriale)
- subsidiary: from controlla to

Le coppie qui sono volutamente conservative e ad alta confidenza. La maggior
parte dell'arricchimento verrà fatta in seguito da LLM enrichment quando il
classifier identifica entità nuove.
"""

SUPPLY_CHAIN_LINKS: list[tuple[str, str, str]] = [
    # Semiconductor supply chain
    ("NVDA", "MSFT", "supplier"),     # NVDA → Microsoft (Azure AI)
    ("NVDA", "META", "supplier"),     # NVDA → Meta (training infra)
    ("NVDA", "GOOGL", "supplier"),    # NVDA → Google Cloud
    ("NVDA", "AMZN", "supplier"),     # NVDA → AWS
    ("AVGO", "AAPL", "supplier"),     # Broadcom → Apple (chip)
    ("QCOM", "AAPL", "supplier"),     # Qualcomm → Apple (modem)
    # Cloud / SaaS
    ("ORCL", "MSFT", "peer"),         # Oracle vs Azure
    ("AMZN", "MSFT", "peer"),         # AWS vs Azure
    ("AMZN", "GOOGL", "peer"),        # AWS vs GCP
    ("CRM", "ORCL", "peer"),          # CRM vs Oracle Apps
    ("CRM", "ADBE", "peer"),          # Salesforce vs Adobe (marketing)
    # Payment networks
    ("V", "MA", "peer"),
    ("AXP", "V", "peer"),
    # Streaming / media
    ("NFLX", "AMZN", "peer"),
    ("NFLX", "META", "peer"),
    # E-commerce / retail
    ("AMZN", "WMT", "peer"),
    ("AMZN", "COST", "peer"),
    # Big banks
    ("JPM", "BAC", "peer"),
    ("JPM", "C", "peer"),
    ("JPM", "WFC", "peer"),
    ("GS", "MS", "peer"),
    # Tech megacaps mutually
    ("AAPL", "MSFT", "peer"),
    ("AAPL", "GOOGL", "peer"),
    ("GOOGL", "META", "peer"),
    # Health Care
    ("PFE", "MRK", "peer"),
    ("JNJ", "PFE", "peer"),
    ("LLY", "PFE", "peer"),
    # Energy
    ("XOM", "GLD", "commodity_exposure"),     # placeholder; tipica esposizione oro/oil cross
    # Aerospace
    ("BA", "RTX", "peer"),
    # Telecom
    ("T", "VZ", "peer"),
    ("T", "CMCSA", "peer"),
]
