"""
Main data engine. Fetches market data, computes everything, produces the table.
Optimized for 1000+ stocks with batch downloads and fundamentals caching.
"""

import json
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf
import pandas as pd

from .config import (
    DATA_DIR, SEED_TICKERS, USER_OVERRIDES,
)
from .intuition import (
    get_daily_closes, compute_intuition_point, compute_scores,
)
from .universe import get_universe


DB_PATH = DATA_DIR / "tracker.db"
FUNDAMENTALS_CACHE = DATA_DIR / "fundamentals_cache.json"
FUNDAMENTALS_STALE_HOURS = 8  # re-fetch fundamentals every 8 hours


def init_db():
    """Initialize SQLite database for storing overrides and history."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS intuition_overrides (
            ticker TEXT PRIMARY KEY,
            optimistic_point REAL,
            updated_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS refresh_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            stocks_processed INTEGER,
            status TEXT
        )
    """)
    conn.commit()

    # Seed user overrides
    for ticker, point in USER_OVERRIDES.items():
        c.execute("""
            INSERT OR REPLACE INTO intuition_overrides (ticker, optimistic_point, updated_at)
            VALUES (?, ?, ?)
        """, (ticker, point, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_override(ticker: str) -> Optional[float]:
    """Get user override for a ticker if it exists."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT optimistic_point FROM intuition_overrides WHERE ticker = ?", (ticker,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


# ── Fundamentals caching ──────────────────────────────────────────────────

def _load_fundamentals_cache() -> dict:
    """Load cached fundamentals."""
    if not FUNDAMENTALS_CACHE.exists():
        return {}
    try:
        with open(FUNDAMENTALS_CACHE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_fundamentals_cache(cache: dict):
    """Save fundamentals cache."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(FUNDAMENTALS_CACHE, "w") as f:
        json.dump(cache, f)


def _is_cache_fresh(entry: dict) -> bool:
    """Check if a cached fundamentals entry is still fresh."""
    try:
        cached_at = datetime.fromisoformat(entry.get("_cached_at", "2000-01-01"))
        return datetime.utcnow() - cached_at < timedelta(hours=FUNDAMENTALS_STALE_HOURS)
    except Exception:
        return False


def fetch_fundamentals_cached(ticker: str, cache: dict) -> dict:
    """Fetch fundamentals with caching. Returns cached data if fresh."""
    if ticker in cache and _is_cache_fresh(cache[ticker]):
        return cache[ticker]

    data = _fetch_fundamentals_raw(ticker)
    data["_cached_at"] = datetime.utcnow().isoformat()
    cache[ticker] = data
    return data


def _fetch_fundamentals_raw(ticker: str) -> dict:
    """Fetch fundamental data for a single ticker from yfinance."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "market_cap_b": info.get("marketCap", 0) / 1e9 if info.get("marketCap") else 0,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margin": info.get("profitMargins"),
            "52w_high": info.get("fiftyTwoWeekHigh", 0),
            "52w_low": info.get("fiftyTwoWeekLow", 0),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "short_name": info.get("shortName", ticker),
            "analyst_target": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey", ""),
        }
    except Exception:
        return {
            "market_cap_b": 0, "pe_ratio": None, "forward_pe": None,
            "revenue_growth": None, "profit_margin": None,
            "52w_high": 0, "52w_low": 0, "sector": "", "industry": "",
            "short_name": ticker, "analyst_target": None, "recommendation": "",
        }


# ── Batch price fetching ─────────────────────────────────────────────────

def batch_download_closes(tickers: list[str], days: int = 1300) -> dict[str, list[tuple[str, float]]]:
    """Batch download daily closes for all tickers. Much faster than individual calls.

    Returns: {ticker: [(date_str, close), ...]}
    """
    result = {}
    end = datetime.now()
    start = end - timedelta(days=days + 10)

    chunk_size = 50
    total_chunks = (len(tickers) + chunk_size - 1) // chunk_size
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        chunk_num = i // chunk_size + 1
        print(f"    chunk {chunk_num}/{total_chunks} ({len(chunk)} tickers)...", flush=True)
        try:
            df = yf.download(
                chunk,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
            )

            if df.empty:
                continue

            for ticker in chunk:
                try:
                    if len(chunk) == 1:
                        ticker_df = df
                    else:
                        if isinstance(df.columns, pd.MultiIndex):
                            ticker_df = df[ticker]
                        else:
                            ticker_df = df

                    if ticker_df.empty:
                        continue

                    # Handle multi-level columns
                    if isinstance(ticker_df.columns, pd.MultiIndex):
                        ticker_df.columns = ticker_df.columns.get_level_values(0)

                    closes = []
                    for idx, row in ticker_df.iterrows():
                        try:
                            close_val = float(row["Close"])
                            if not math.isnan(close_val):
                                closes.append((idx.strftime("%Y-%m-%d"), close_val))
                        except (ValueError, KeyError):
                            continue

                    if closes:
                        result[ticker] = closes[-days:]

                except Exception:
                    continue

        except Exception as e:
            print(f"  Batch download error for chunk starting at {i}: {e}")
            continue

    return result


# ── Market indices ────────────────────────────────────────────────────────

def fetch_market_indices() -> dict:
    """Fetch major market index data for the dashboard."""
    indices = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^DJI": "Dow Jones",
        "^VIX": "VIX",
        "^RUT": "Russell 2000",
    }
    result = {}
    try:
        df = yf.download(
            list(indices.keys()), period="5d", progress=False,
            auto_adjust=True, group_by="ticker", threads=True,
        )
        for symbol, name in indices.items():
            try:
                if len(indices) > 1 and isinstance(df.columns, pd.MultiIndex):
                    ticker_df = df[symbol]
                else:
                    ticker_df = df

                if ticker_df.empty:
                    continue

                if isinstance(ticker_df.columns, pd.MultiIndex):
                    ticker_df.columns = ticker_df.columns.get_level_values(0)

                last = float(ticker_df.iloc[-1]["Close"])
                prev = float(ticker_df.iloc[-2]["Close"]) if len(ticker_df) > 1 else last
                change_pct = round((last / prev - 1) * 100, 2) if prev else 0

                result[name] = {
                    "value": round(last, 2),
                    "change_pct": change_pct,
                }
            except Exception:
                continue
    except Exception as e:
        print(f"  Warning: could not fetch indices: {e}")

    return result


# ── Main processing ──────────────────────────────────────────────────────

def process_all_stocks(holdings: Optional[dict] = None) -> list[dict]:
    """
    Main processing loop. Fetches data and computes everything for all stocks.

    Args:
        holdings: dict of {ticker: {shares, avg_price, equity}} from Robinhood

    Returns:
        List of dicts, one per stock, sorted by personal score descending.
    """
    init_db()

    # Step 1: Get the full universe
    print("\n[1/5] Building stock universe...")
    tickers = get_universe()
    total = len(tickers)
    print(f"  {total} tickers to process")

    # Step 2: Batch download price data
    print(f"\n[2/5] Batch downloading price data ({total} tickers)...")
    all_closes = batch_download_closes(tickers, days=1300)
    print(f"  Got price data for {len(all_closes)}/{total} tickers")

    # Step 3: Load fundamentals cache
    print(f"\n[3/5] Fetching fundamentals (cached where fresh)...")
    fund_cache = _load_fundamentals_cache()
    stale_count = sum(1 for t in tickers if t not in fund_cache or not _is_cache_fresh(fund_cache.get(t, {})))
    print(f"  {total - stale_count} cached, {stale_count} to fetch fresh")

    # Step 4: Process each stock
    print(f"\n[4/5] Computing intuition points and scores...")
    results = []
    errors = 0

    for idx, ticker in enumerate(tickers):
        if (idx + 1) % 100 == 0 or idx == 0:
            print(f"  [{idx + 1}/{total}]...")

        try:
            closes = all_closes.get(ticker)
            if not closes:
                continue

            # Fundamentals (with caching)
            fundamentals = fetch_fundamentals_cached(ticker, fund_cache)
            current_price = closes[-1][1]

            # 52W range from data
            closes_1y = closes[-260:]
            data_high = max(c for _, c in closes_1y) if closes_1y else 0
            data_low = min(c for _, c in closes_1y) if closes_1y else 0
            high_52w = fundamentals.get("52w_high", 0) or data_high
            low_52w = fundamentals.get("52w_low", 0) or data_low

            # Returns
            returns = compute_returns(closes, current_price)

            # Intuition point
            override = get_override(ticker)
            intuition = compute_intuition_point(closes_1y, current_price, high_52w, override)

            # Scores
            personal_score, evidence_score = compute_scores(
                ticker, current_price, fundamentals["market_cap_b"],
                intuition, returns, high_52w, low_52w,
            )

            # Holdings info
            holding = holdings.get(ticker, {}) if holdings else {}

            # Above 52W low
            above_52w_low = round((current_price / low_52w - 1) * 100, 1) if low_52w > 0 else None

            row = {
                "ticker": ticker,
                "name": fundamentals["short_name"],
                "sector": fundamentals["sector"],
                "industry": fundamentals["industry"],
                "price": round(current_price, 2),
                "market_cap_b": round(fundamentals["market_cap_b"], 1),
                "52w_low": round(low_52w, 2),
                "52w_high": round(high_52w, 2),
                "above_52w_low_pct": above_52w_low,
                "1D": returns.get("1D"),
                "1W": returns.get("1W"),
                "1M": returns.get("1M"),
                "3M": returns.get("3M"),
                "6M": returns.get("6M"),
                "1Y": returns.get("1Y"),
                "3Y": returns.get("3Y"),
                "5Y": returns.get("5Y"),
                "intuition_point": intuition["optimistic_point"],
                "intuition_low": intuition.get("low_point"),
                "intuition_high": intuition.get("high_point"),
                "upside_pct": intuition["upside_pct"],
                "crossings": intuition["crossings"],
                "crossing_quarters": intuition["quarters"],
                "crossing_dates": intuition.get("crossing_dates", []),
                "intuition_source": intuition.get("source", "algorithm"),
                "personal_score": personal_score,
                "evidence_score": evidence_score,
                "pe_ratio": fundamentals.get("pe_ratio"),
                "forward_pe": fundamentals.get("forward_pe"),
                "revenue_growth": fundamentals.get("revenue_growth"),
                "profit_margin": fundamentals.get("profit_margin"),
                "analyst_target": fundamentals.get("analyst_target"),
                "recommendation": fundamentals.get("recommendation"),
                # Holdings
                "i_hold": bool(holding),
                "shares_held": holding.get("shares", 0),
                "avg_price": holding.get("avg_price", 0),
                "invested": holding.get("equity", 0),
                "holding_pnl_pct": round((current_price / holding["avg_price"] - 1) * 100, 1) if holding.get("avg_price") else None,
                # Metadata
                "last_updated": datetime.utcnow().isoformat(),
            }
            results.append(row)

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error: {ticker}: {e}")
            continue

    # Save fundamentals cache
    _save_fundamentals_cache(fund_cache)
    if errors > 5:
        print(f"  ({errors} total errors)")

    # Sort by personal score descending, then evidence score
    results.sort(key=lambda r: (-r["personal_score"], -r["evidence_score"]))

    # Assign ranks
    for i, r in enumerate(results, 1):
        r["rank"] = i

    print(f"  Processed {len(results)} stocks ({errors} errors)")

    # Log refresh
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO refresh_history (timestamp, stocks_processed, status) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), len(results), "success"),
    )
    conn.commit()
    conn.close()

    return results


def compute_returns(closes: list[tuple[str, float]], current_price: float) -> dict:
    """Compute returns over standard windows from daily closes."""
    if not closes or current_price <= 0:
        return {}

    returns = {}
    windows = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260}

    for label, days in windows.items():
        if len(closes) > days:
            ref_price = closes[-(days + 1)][1]
            if ref_price > 0:
                returns[label] = round((current_price / ref_price - 1) * 100, 2)
            else:
                returns[label] = None
        else:
            returns[label] = None

    return returns
