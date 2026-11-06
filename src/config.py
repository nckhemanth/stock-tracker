"""Configuration constants."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "docs"  # GitHub Pages serves from /docs

# Stock universe seed — the 100 from the ChatGPT project
SEED_TICKERS = [
    "RDDT", "LRCX", "APP", "CLS", "MRVL", "FIX", "ASML", "GEV", "ALAB", "VRT",
    "STRL", "AMD", "MU", "GOOGL", "IESC", "NU", "NVDA", "NVT", "CIEN", "FN",
    "NOW", "META", "ANET", "AMAT", "TSM", "NRG", "BWXT", "DY", "GLW", "AVGO",
    "CSCO", "PLTR", "EME", "PWR", "UBER", "DDOG", "NFLX", "COHR", "ETN", "CCJ",
    "VST", "PANW", "MOD", "AAON", "ADBE", "MELI", "CRM", "MDB", "NBIS", "ORCL",
    "AMKR", "LITE", "QCOM", "VIAV", "CRWV", "CEG", "AAOI", "OKLO", "OUST", "APLD",
    "TLN", "ZS", "NET", "BN", "CRWD", "IREN", "SNOW", "MSFT", "AMZN", "WMT",
    "FTNT", "RKLB", "ASTS", "PL", "KTOS", "AVAV", "RCAT", "LUNR", "JOBY", "ACHR",
    "COIN", "SOFI", "HOOD", "AFRM", "UPST", "XYZ", "SE", "DUOL", "BROS", "DASH",
    "ALNY", "IONS", "MDGL", "VCEL", "AXON", "MP", "ALB", "SQM", "RIVN", "TSLA",
]

# User-calibrated intuition point overrides (from voice conversation + corrections)
# These are LOCKED and never overwritten by the algorithm
USER_OVERRIDES = {
    "NU": 13.25,
    "GOOGL": 320,
    "VST": 137.5,
    "CLS": 328,  # User corrected: $250 low, $328 optimistic, $387 high
}

# Scoring weights
MIN_CROSSINGS = 3          # Minimum upward crossings to be credible
MIN_QUARTERS_SPREAD = 2    # Crossings must span at least 2 quarters
MIN_UPSIDE_PCT = 15        # Minimum % upside to motivate investing
PREFERRED_UPSIDE_PCT = 40  # Sweet spot upside range

# Schedule (ET)
CHECK_TIMES_ET = ["09:45", "12:45", "15:00"]

# Email
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_TO = "nckhemanthreddy7@gmail.com"
EMAIL_SUBJECT = "Stock Tracker Refresh | {timestamp}"

# Robinhood
RH_USERNAME = os.environ.get("RH_USERNAME", "")
RH_PASSWORD = os.environ.get("RH_PASSWORD", "")
RH_TOTP_SECRET = os.environ.get("RH_TOTP_SECRET", "")
