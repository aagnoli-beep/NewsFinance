"""GICS sector mapping per ticker + ETF settoriale corrispondente.

Volutamente compatto: solo i ticker presenti in `universe.UNIVERSE` con
classificazione GICS nota. Per i ticker non mappati l'exposure agent fa
fallback su LLM enrichment.
"""

# Mapping ticker → (sector, sector_etf)
# Sector ETF SPDR Select:
#   XLK Technology, XLF Financials, XLE Energy, XLV Health Care,
#   XLI Industrials, XLY Consumer Discretionary, XLP Consumer Staples,
#   XLU Utilities, XLB Materials, XLRE Real Estate, XLC Communication Services
TICKER_SECTOR: dict[str, tuple[str, str]] = {
    # Technology (XLK)
    "AAPL": ("Technology", "XLK"),
    "MSFT": ("Technology", "XLK"),
    "NVDA": ("Technology", "XLK"),
    "AVGO": ("Technology", "XLK"),
    "ORCL": ("Technology", "XLK"),
    "ADBE": ("Technology", "XLK"),
    "CRM": ("Technology", "XLK"),
    "ACN": ("Technology", "XLK"),
    "INTC": ("Technology", "XLK"),
    "AMD": ("Technology", "XLK"),
    "QCOM": ("Technology", "XLK"),
    "TXN": ("Technology", "XLK"),
    "INTU": ("Technology", "XLK"),
    "CSCO": ("Technology", "XLK"),
    # Communication Services (XLC)
    "GOOGL": ("Communication Services", "XLC"),
    "META": ("Communication Services", "XLC"),
    "NFLX": ("Communication Services", "XLC"),
    "CMCSA": ("Communication Services", "XLC"),
    "T": ("Communication Services", "XLC"),
    "VZ": ("Communication Services", "XLC"),
    # Consumer Discretionary (XLY)
    "AMZN": ("Consumer Discretionary", "XLY"),
    "TSLA": ("Consumer Discretionary", "XLY"),
    "HD": ("Consumer Discretionary", "XLY"),
    "LOW": ("Consumer Discretionary", "XLY"),
    "MCD": ("Consumer Discretionary", "XLY"),
    "NKE": ("Consumer Discretionary", "XLY"),
    "COST": ("Consumer Discretionary", "XLY"),
    # Financials (XLF)
    "JPM": ("Financials", "XLF"),
    "V": ("Financials", "XLF"),
    "MA": ("Financials", "XLF"),
    "BAC": ("Financials", "XLF"),
    "WFC": ("Financials", "XLF"),
    "GS": ("Financials", "XLF"),
    "MS": ("Financials", "XLF"),
    "BLK": ("Financials", "XLF"),
    "SCHW": ("Financials", "XLF"),
    "C": ("Financials", "XLF"),
    "AXP": ("Financials", "XLF"),
    "BRK.B": ("Financials", "XLF"),
    # Health Care (XLV)
    "LLY": ("Health Care", "XLV"),
    "UNH": ("Health Care", "XLV"),
    "JNJ": ("Health Care", "XLV"),
    "PFE": ("Health Care", "XLV"),
    "ABBV": ("Health Care", "XLV"),
    "MRK": ("Health Care", "XLV"),
    "TMO": ("Health Care", "XLV"),
    "ABT": ("Health Care", "XLV"),
    "DHR": ("Health Care", "XLV"),
    "BMY": ("Health Care", "XLV"),
    # Consumer Staples (XLP)
    "WMT": ("Consumer Staples", "XLP"),
    "PG": ("Consumer Staples", "XLP"),
    "KO": ("Consumer Staples", "XLP"),
    "PEP": ("Consumer Staples", "XLP"),
    "PM": ("Consumer Staples", "XLP"),
    # Industrials (XLI)
    "BA": ("Industrials", "XLI"),
    "GE": ("Industrials", "XLI"),
    "RTX": ("Industrials", "XLI"),
    "NEE": ("Industrials", "XLI"),
    # Energy (XLE)
    "XOM": ("Energy", "XLE"),
}


# Mapping commodity ETF → underlying commodity name (per exposure inversa)
COMMODITY_ETFS: dict[str, str] = {
    "GLD": "Gold",
    "SLV": "Silver",
    "USO": "WTI Crude",
    "BNO": "Brent Crude",
    "UNG": "Natural Gas",
    "DBA": "Agricultural",
    "DBC": "Broad commodities",
}


# Bond ETFs (riferimento tassi)
BOND_ETFS: dict[str, str] = {
    "TLT": "20+ Year Treasury",
    "IEF": "7-10 Year Treasury",
    "SHY": "1-3 Year Treasury",
    "HYG": "High Yield Corporate",
    "LQD": "Investment Grade Corporate",
}


# FX ETFs (proxy valute)
FX_ETFS: dict[str, str] = {
    "UUP": "US Dollar Index",
    "FXE": "Euro",
    "FXY": "Japanese Yen",
    "FXB": "British Pound",
}


# Index ETFs (mercato aggregato)
INDEX_ETFS: dict[str, str] = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "DIA": "Dow Jones",
    "VTI": "Total US Market",
    "EFA": "MSCI EAFE",
    "EEM": "MSCI Emerging Markets",
    "FXI": "China large cap",
}


# Volatility ETFs (VIX proxy)
VOL_ETFS: dict[str, str] = {
    "VIXY": "Short-term VIX futures",
    "UVXY": "Leveraged VIX",
}


def get_sector(ticker: str) -> tuple[str, str] | None:
    """Ritorna (sector_name, sector_etf_ticker) per il ticker dato."""
    return TICKER_SECTOR.get(ticker.upper())


def get_peers(ticker: str) -> list[str]:
    """Ritorna ticker dello stesso settore."""
    ticker = ticker.upper()
    sector = TICKER_SECTOR.get(ticker)
    if sector is None:
        return []
    sector_name = sector[0]
    return [
        t for t, (s, _) in TICKER_SECTOR.items() if s == sector_name and t != ticker
    ]
