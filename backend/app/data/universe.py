"""Universe iniziale di ticker tracciati.

Volutamente compatto al primo giro (~100 ticker): top S&P 500 per market cap,
tutti i sector ETF SPDR e i principali proxy macro/commodity/FX/bond/vol via ETF.
Il piano Polygon Stocks Starter copre tutti via singolo prodotto.

Da Fase 4 in poi questa lista verrà estesa caricando le componenti complete
dell'S&P 500 da SPY holdings.
"""

# Sector ETF SPDR — copertura settoriale (GICS).
SECTOR_ETFS = [
    "XLE",   # Energy
    "XLF",   # Financials
    "XLK",   # Technology
    "XLI",   # Industrials
    "XLV",   # Health Care
    "XLY",   # Consumer Discretionary
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLB",   # Materials
    "XLRE",  # Real Estate
    "XLC",   # Communication Services
]

# Indici / aggregati di mercato via ETF.
INDEX_ETFS = [
    "SPY",   # S&P 500
    "QQQ",   # Nasdaq 100
    "IWM",   # Russell 2000
    "DIA",   # Dow Jones
    "VTI",   # Total US market
    "EFA",   # MSCI EAFE (Europe/Asia developed)
    "EEM",   # MSCI Emerging Markets
    "FXI",   # China large cap
]

# Bond ETF — proxy per i tassi.
BOND_ETFS = [
    "TLT",   # 20+ year Treasury
    "IEF",   # 7-10 year Treasury
    "SHY",   # 1-3 year Treasury
    "HYG",   # High Yield corporate
    "LQD",   # Investment Grade corporate
]

# FX via ETF (DXY proxy + majors).
FX_ETFS = [
    "UUP",   # US Dollar Index (DXY proxy)
    "FXE",   # Euro
    "FXY",   # Japanese Yen
    "FXB",   # British Pound
]

# Commodity ETF.
COMMODITY_ETFS = [
    "GLD",   # Gold
    "SLV",   # Silver
    "USO",   # WTI Crude
    "BNO",   # Brent Crude
    "UNG",   # Natural Gas
    "DBA",   # Agricultural
    "DBC",   # Broad commodity basket
]

# Volatility ETF — proxy per VIX.
VOL_ETFS = [
    "VIXY",  # Short-term VIX futures
    "UVXY",  # Leveraged VIX
]

# Top S&P 500 per market cap (~50 nomi). Estesa in fasi future.
SP500_TOP = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK.B",
    "JPM", "V", "LLY", "UNH", "XOM", "MA", "JNJ", "WMT", "PG", "HD", "BAC",
    "AVGO", "COST", "PFE", "ABBV", "MRK", "KO", "PEP", "ADBE", "NFLX", "CRM",
    "ORCL", "TMO", "ACN", "MCD", "CSCO", "ABT", "LIN", "WFC", "CMCSA", "DHR",
    "VZ", "NEE", "INTC", "BMY", "PM", "AMD", "RTX", "INTU", "T", "NKE", "QCOM",
    "LOW", "TXN", "BA", "GE", "GS", "MS", "BLK", "SCHW", "C", "AXP",
]

# Universe completo concatenato (deduplicato in ordine).
UNIVERSE: list[str] = list(
    dict.fromkeys(
        SP500_TOP
        + SECTOR_ETFS
        + INDEX_ETFS
        + BOND_ETFS
        + FX_ETFS
        + COMMODITY_ETFS
        + VOL_ETFS
    )
)
