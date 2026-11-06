"""
Stock universe sourcing: S&P 500 + S&P MidCap 400 + user seeds.
Caches to data/universe.json for reliability.
"""

import json
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from .config import DATA_DIR, SEED_TICKERS

UNIVERSE_FILE = DATA_DIR / "universe.json"
STALE_HOURS = 168  # refresh constituent list weekly


def get_universe() -> list[str]:
    """Return the full stock universe (1000+ tickers).

    Strategy:
    1. Load cached universe if fresh (< 7 days old)
    2. If stale or missing, scrape S&P 500 + MidCap 400 from Wikipedia
    3. Merge with user seed tickers (always included)
    4. Save cache
    """
    cached = _load_cache()
    if cached:
        return cached

    tickers = set(SEED_TICKERS)

    # S&P 500
    sp500 = _scrape_sp500()
    tickers.update(sp500)

    # S&P MidCap 400
    sp400 = _scrape_sp400()
    tickers.update(sp400)

    # Load any discovered tickers
    discovery_file = DATA_DIR / "discovered_tickers.json"
    if discovery_file.exists():
        try:
            with open(discovery_file) as f:
                tickers.update(json.load(f))
        except Exception:
            pass

    # Clean up: remove empty strings, ensure uppercase, filter valid tickers
    result = sorted(t.strip().upper() for t in tickers if t and t.strip())
    result = [t for t in result if 1 <= len(t) <= 5 and t.isalpha()]

    if len(result) >= 500:  # only cache if we got a reasonable number
        _save_cache(result)

    print(f"  Universe: {len(result)} tickers ({len(sp500)} S&P500, {len(sp400)} MidCap400, {len(SEED_TICKERS)} seeds)")
    return result


def _load_cache() -> list[str] | None:
    """Load cached universe if fresh enough."""
    if not UNIVERSE_FILE.exists():
        return None

    try:
        with open(UNIVERSE_FILE) as f:
            data = json.load(f)

        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.utcnow() - cached_at > timedelta(hours=STALE_HOURS):
            return None  # stale

        tickers = data["tickers"]
        # Always include seed tickers even if cache exists
        all_tickers = list(dict.fromkeys(list(SEED_TICKERS) + tickers))
        return all_tickers

    except Exception:
        return None


def _save_cache(tickers: list[str]):
    """Save universe to cache file."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(UNIVERSE_FILE, "w") as f:
        json.dump({
            "cached_at": datetime.utcnow().isoformat(),
            "count": len(tickers),
            "tickers": tickers,
        }, f)


_HEADERS = {
    "User-Agent": "StockTracker/1.0 (https://github.com/nckhemanth/stock-tracker)"
}


def _fetch_wiki_table(url: str) -> pd.DataFrame | None:
    """Fetch a Wikipedia page and parse its first table."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        return tables[0] if tables else None
    except Exception as e:
        print(f"  Warning: could not fetch {url}: {e}")
        return None


def _scrape_sp500() -> list[str]:
    """Scrape S&P 500 constituents from Wikipedia."""
    df = _fetch_wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    if df is None:
        return []
    symbols = df["Symbol"].tolist()
    return [s.replace(".", "-") for s in symbols if isinstance(s, str)]


def _scrape_sp400() -> list[str]:
    """Scrape S&P MidCap 400 constituents from Wikipedia."""
    df = _fetch_wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
    if df is None:
        return []
    col = "Ticker symbol" if "Ticker symbol" in df.columns else "Symbol" if "Symbol" in df.columns else df.columns[1]
    symbols = df[col].tolist()
    return [s.replace(".", "-") for s in symbols if isinstance(s, str)]
