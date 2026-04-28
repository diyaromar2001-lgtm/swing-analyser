"""
Univers de marché étendu : ~250 actifs liquides
Nasdaq 100 + S&P 100 + Leaders sectoriels (Minervini / O'Neil universe)
"""

TICKERS = {

    # ── Technology (52) ──────────────────────────────────────────────────────
    "Technology": [
        # Mega-cap / FAANG+
        "AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META", "NFLX",
        # Semis
        "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC",
        "MRVL", "ON", "NXPI", "ASML", "MCHP", "MPWR",
        # Software / Cloud
        "ADBE", "CRM", "INTU", "NOW", "ORCL", "CSCO", "ACN",
        "WDAY", "VEEV", "SNOW", "ADSK", "ANSS", "CTSH", "PTC",
        # Cyber / AI
        "PANW", "CRWD", "FTNT", "ZS", "DDOG", "PLTR", "ARM", "NET",
        # Hardware / Other
        "DELL", "SMCI", "VRT", "TEAM", "IBM", "HPE",
        # Instruments / Networking
        "ANET", "MSI", "KEYS", "GRMN",
        # Legacy / Value
        "INTC",
    ],

    # ── Healthcare (30) ──────────────────────────────────────────────────────
    "Healthcare": [
        # Large Pharma
        "UNH", "LLY", "JNJ", "MRK", "ABBV", "PFE", "BMY", "AMGN",
        # Biotech
        "GILD", "VRTX", "REGN", "MRNA", "BIIB",
        # MedTech / Devices
        "TMO", "DHR", "ISRG", "BSX", "SYK", "MDT", "ABT", "DXCM",
        "IDXX", "HOLX", "STE",
        # Managed Care
        "HUM", "ELV", "CI", "HCA", "MOH",
        # Services
        "IQV", "GEHC", "ZTS",
    ],

    # ── Financials (27) ──────────────────────────────────────────────────────
    "Financials": [
        # Banks
        "JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "TFC", "BK",
        # Payments
        "V", "MA", "AXP", "COF",
        # Asset Mgmt / Alt
        "BLK", "BX", "KKR", "SCHW",
        # Insurance
        "CB", "PGR", "AFL", "MET", "PRU", "TRV", "AIG",
        # Data / Exchanges
        "SPGI", "MCO", "ICE", "CME", "VRSK",
    ],

    # ── Consumer Discretionary (27) ──────────────────────────────────────────
    "Consumer Discretionary": [
        # E-commerce / Tech-retail
        "AMZN", "SHOP", "MELI", "ETSY",
        # Auto
        "TSLA",
        # Home Improvement
        "HD", "LOW",
        # Restaurants / Food
        "MCD", "SBUX", "CMG", "TXRH",
        # Specialty Retail
        "NKE", "LULU", "ONON", "TJX", "ROST", "WSM", "DECK",
        # Travel / Leisure
        "BKNG", "ABNB", "MAR", "RCL",
        # Auto Parts / Services
        "ORLY", "AZO",
        # Ride-share / Other
        "UBER", "LEN",
    ],

    # ── Consumer Staples (14) ────────────────────────────────────────────────
    "Consumer Staples": [
        # Food / Beverage
        "PG", "KO", "PEP", "MDLZ", "PM", "MO", "STZ", "MNST",
        # Retail Staples
        "COST", "WMT", "TGT",
        # HPC / Other
        "CL", "KMB", "EL",
    ],

    # ── Energy (15) ──────────────────────────────────────────────────────────
    "Energy": [
        # Integrated / Majors
        "XOM", "CVX", "COP", "HES",
        # E&P
        "EOG", "DVN", "OXY", "FANG",
        # Refining / Midstream
        "MPC", "PSX", "OKE", "LNG",
        # Services
        "SLB", "BKR", "HAL",
    ],

    # ── Industrials (24) ─────────────────────────────────────────────────────
    "Industrials": [
        # Machinery
        "CAT", "DE", "ETN", "EMR", "ITW", "DOV", "ROK",
        # Defense / Aerospace
        "RTX", "LMT", "NOC", "GD", "LHX", "GE",
        # Transport / Logistics
        "UPS", "FDX", "UNP", "NSC", "CSX", "ODFL",
        # Services / Tools
        "HON", "CTAS", "FAST", "URI", "WM", "PWR",
    ],

    # ── Materials (7) ────────────────────────────────────────────────────────
    "Materials": [
        "LIN", "APD", "SHW", "ECL",
        "NUE", "STLD", "FCX",
    ],

    # ── Communication (11) ───────────────────────────────────────────────────
    "Communication": [
        # Telecom
        "TMUS", "VZ", "T", "CMCSA", "CHTR",
        # Media / Streaming
        "DIS", "SPOT", "WBD",
        # Social / Gaming
        "PINS", "SNAP", "TTWO",
    ],

    # ── Real Estate (9) ──────────────────────────────────────────────────────
    "Real Estate": [
        "PLD", "AMT", "EQIX", "DLR",
        "SPG", "WELL", "PSA", "IRM", "CSGP",
    ],

    # ── Utilities (8) ────────────────────────────────────────────────────────
    "Utilities": [
        "NEE", "DUK", "SO", "AEP", "XEL",
        "CEG", "VST", "NRG",
    ],

    # ── Growth / Innovation (15) ─────────────────────────────────────────────
    "Growth / Innovation": [
        # Crypto / Fintech
        "COIN", "HOOD", "PYPL", "SQ",
        # Clean Energy
        "ENPH", "FSLR",
        # Cloud / AI Pure-play
        "APP", "TTD", "DDOG",   # DDOG also in tech, fine
        # Biotech disruptive
        "MRNA",                  # also in Healthcare, fine (dual signal)
        # Emerging Tech
        "RBLX", "IONQ", "HIMS",
        # International Leaders
        "SE", "MELI",            # MELI also in cons. disc.
    ],

}

ALL_TICKERS = list(dict.fromkeys(
    t for tickers in TICKERS.values() for t in tickers
))  # dict.fromkeys preserves order AND deduplicates

TICKER_SECTOR = {}
for sector, tickers in TICKERS.items():
    for t in tickers:
        if t not in TICKER_SECTOR:          # first sector wins on duplicates
            TICKER_SECTOR[t] = sector
