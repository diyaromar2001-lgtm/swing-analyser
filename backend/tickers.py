"""
Univers de marché étendu : ~250 actifs liquides
Nasdaq 100 + S&P 100 + Leaders sectoriels (Minervini / O'Neil universe)
"""

TICKERS = {

    # ── Technology (52 + 10 new) = 62 ────────────────────────────────────────
    "Technology": [
        # Mega-cap / FAANG+
        "AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META", "NFLX",
        # Semis
        "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC",
        "MRVL", "ON", "NXPI", "ASML", "MCHP", "MPWR",
        # Software / Cloud
        "ADBE", "CRM", "INTU", "NOW", "ORCL", "CSCO", "ACN",
        "WDAY", "VEEV", "SNOW", "ADSK", "CTSH", "PTC",
        # Cyber / AI
        "PANW", "CRWD", "FTNT", "ZS", "DDOG", "PLTR", "ARM", "NET",
        # Hardware / Other
        "DELL", "SMCI", "VRT", "TEAM", "IBM", "HPE",
        # Instruments / Networking
        "ANET", "MSI", "KEYS", "GRMN",
        # Legacy / Value
        "INTC",
        # Security / SaaS (new additions)
        "OKTA", "SNPS", "CDNS", "VRSN",
        # Cloud / Data / Collab (new additions)
        "DBX", "MDB", "ESTC",
        # Automation / Platforms (new additions)
        "MNDY", "BILL", "UPWK",
    ],

    # ── Healthcare (30 + 8 new) = 38 ────────────────────────────────────────
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
        # Diagnostics / Specialty (new additions)
        "EXAS", "LH", "ALGN",
        # Telehealth / Rehab (new additions)
        "TDOC", "EHC", "DVA",
        # Biotech specialized (new additions)
        "ALKS", "XRAY",
    ],

    # ── Financials (27 + 4 new) = 31 ────────────────────────────────────────
    "Financials": [
        # Banks
        "JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "TFC", "BK",
        # Regional Banks (new additions)
        "FITB", "WAFD",
        # Payments
        "V", "MA", "AXP", "COF",
        # Asset Mgmt / Alt / Investment Services (new additions)
        "BLK", "BX", "KKR", "SCHW", "LPLA",
        # Insurance
        "CB", "PGR", "AFL", "MET", "PRU", "TRV", "AIG",
        # Data / Exchanges
        "SPGI", "MCO", "ICE", "CME", "VRSK",
        # Digital Banking (new additions)
        "ALLY",
    ],

    # ── Consumer Discretionary (27 + 10 new) = 37 ───────────────────────────
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
        # Apparel / Fashion (new additions)
        "SKX", "CPRI", "AEO", "PVH",
        # Retail / Department Stores (new additions)
        "ULTA", "BBY",
        # Specialty / Furniture (new additions)
        "RH",
        # Wholesale Club (new additions)
        "BJ",
        # Discount Retail (new additions)
        "FIVE",
        # General Retail (new additions)
        "GPS",
    ],

    # ── Consumer Staples (14 + 3 new) = 17 ──────────────────────────────────
    "Consumer Staples": [
        # Food / Beverage
        "PG", "KO", "PEP", "MDLZ", "PM", "MO", "STZ", "MNST",
        # Retail Staples
        "COST", "WMT", "TGT",
        # HPC / Other
        "CL", "KMB", "EL",
        # Packaged Foods / Specialty (new additions)
        "SJM", "HSY", "MKC",
    ],

    # ── Energy (15 + 3 new) = 18 ────────────────────────────────────────────
    "Energy": [
        # Integrated / Majors
        "XOM", "CVX", "COP", "HES",
        # E&P (new additions)
        "EOG", "DVN", "OXY", "FANG", "MRO", "CTRA", "CNX",
        # Refining / Midstream
        "MPC", "PSX", "OKE", "LNG",
        # Services
        "SLB", "BKR", "HAL",
    ],

    # ── Industrials (24 + 10 new) = 34 ──────────────────────────────────────
    "Industrials": [
        # Machinery
        "CAT", "DE", "ETN", "EMR", "ITW", "DOV", "ROK",
        # Defense / Aerospace
        "RTX", "LMT", "NOC", "GD", "LHX", "GE",
        # Transport / Logistics / Airlines (new additions)
        "UPS", "FDX", "UNP", "NSC", "CSX", "ODFL", "ALK", "RXO",
        # Services / Tools
        "HON", "CTAS", "FAST", "URI", "WM", "PWR",
        # Equipment / Precision (new additions)
        "GGG", "IEX", "SPX", "NDSN", "AWK", "AME", "FLS", "CARR",
    ],

    # ── Materials (7 + 9 new) = 16 ──────────────────────────────────────────
    "Materials": [
        # Existing Materials Leaders
        "LIN", "APD", "SHW", "ECL",
        "NUE", "STLD", "FCX",
        # Chemicals / Specialty (new additions)
        "ALB", "LYB", "WLK", "CE",
        # Mining / Metals (new additions)
        "NEM", "SCCO", "AA",
        # Agriculture / Packaging (new additions)
        "CTVA", "PKG",
    ],

    # ── Communication (11 + 4 new) = 15 ─────────────────────────────────────
    "Communication": [
        # Telecom
        "TMUS", "VZ", "T", "CMCSA", "CHTR",
        # Media / Streaming (new additions)
        "DIS", "SPOT", "WBD", "FOX", "PARA",
        # Satellite / Radio (new additions)
        "SIRI",
        # Social / Gaming / Cinema (new additions)
        "PINS", "SNAP", "TTWO", "IMAX",
    ],

    # ── Real Estate (9 + 7 new) = 16 ────────────────────────────────────────
    "Real Estate": [
        # Existing REIT Leaders
        "PLD", "AMT", "EQIX", "DLR",
        "SPG", "WELL", "PSA", "IRM", "CSGP",
        # Dividend / Specialty REITs (new additions)
        "O",
        # Biotech / Lab REITs (new additions)
        "ARE",
        # Industrial / Warehouse (new additions)
        "STAG", "EGP",
        # Retail REITs (new additions)
        "EPRT", "ADC",
        # Agricultural / Commercial (new additions)
        "LAND",
    ],

    # ── Utilities (8 + 8 new) = 16 ──────────────────────────────────────────
    "Utilities": [
        # Existing Leaders
        "NEE", "DUK", "SO", "AEP", "XEL",
        "CEG", "VST", "NRG",
        # Regional Utilities (new additions)
        "AES", "AEE", "WEC", "EXC", "PPL", "D", "ETR", "CMS",
    ],

    # ── Growth / Innovation (15 + 4 new) = 19 ───────────────────────────────
    "Growth / Innovation": [
        # Crypto / Fintech
        "COIN", "HOOD", "PYPL", "SQ",
        # Bitcoin Mining (new additions)
        "RIOT", "MARA",
        # Clean Energy
        "ENPH", "FSLR",
        # Cloud / AI Pure-play
        "APP", "TTD", "DDOG",   # DDOG also in tech, fine
        # Biotech disruptive
        "MRNA",                  # also in Healthcare, fine (dual signal)
        # Emerging Tech
        "RBLX", "IONQ", "HIMS",
        # RPA / Game Engines (new additions)
        "PATH", "U",
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
