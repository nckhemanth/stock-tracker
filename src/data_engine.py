"""
Main data engine. Fetches market data, computes everything, produces the table.
"""

import json
import math
import sqlite3
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


DB_PATH = DATA_DIR / "tracker.db"


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


def get_stock_universe() -> list[str]:
    """Get the full stock universe: seed list + any auto-discovered tickers."""
    tickers = list(SEED_TICKERS)
    # Load any additional tickers from discovery
    discovery_file = DATA_DIR / "discovered_tickers.json"
    if discovery_file.exists():
        with open(discovery_file) as f:
            extra = json.load(f)
            for t in extra:
                if t not in tickers:
                    tickers.append(t)
    return tickers


def discover_trending() -> list[str]:
    """Auto-discover trending stocks from Yahoo Finance."""
    trending = []
    try:
        # Get trending tickers from yfinance
        gainers = yf.Tickers("SPY QQQ").tickers  # placeholder
        # Use Yahoo Finance screeners for day gainers and most active
        for screen_name in ["day_gainers", "most_actives"]:
            try:
                screener = yf.Screen(screen_name)
                if hasattr(screener, 'symbols'):
                    trending.extend(screener.symbols[:20])
            except Exception:
                pass
    except Exception:
        pass

    # Filter to US stocks with reasonable market cap
    filtered = []
    for t in set(trending):
        if t not in SEED_TICKERS and len(t) <= 5:
            filtered.append(t)

    # Save discovered
    discovery_file = DATA_DIR / "discovered_tickers.json"
    existing = []
    if discovery_file.exists():
        with open(discovery_file) as f:
            existing = json.load(f)

    combined = list(set(existing + filtered))[:50]  # cap at 50 extra
    DATA_DIR.mkdir(exist_ok=True)
    with open(discovery_file, "w") as f:
        json.dump(combined, f)

    return combined


def fetch_quote_data(tickers: list[str]) -> dict:
    """Batch fetch current quotes for all tickers via yfinance."""
    result = {}
    # Process in chunks of 20
    for i in range(0, len(tickers), 20):
        chunk = tickers[i:i + 20]
        try:
            data = yf.download(chunk, period="5d", progress=False, auto_adjust=True, group_by="ticker")
            if isinstance(data.columns, pd.MultiIndex):
                for ticker in chunk:
                    try:
                        ticker_data = data[ticker] if len(chunk) > 1 else data
                        if not ticker_data.empty:
                            last_row = ticker_data.iloc[-1]
                            prev_row = ticker_data.iloc[-2] if len(ticker_data) > 1 else last_row
                            result[ticker] = {
                                "price": float(last_row["Close"]),
                                "prev_close": float(prev_row["Close"]),
                                "volume": float(last_row["Volume"]) if "Volume" in last_row else 0,
                            }
                    except Exception:
                        pass
            else:
                # Single ticker
                if not data.empty:
                    cols = data.columns
                    if isinstance(cols, pd.MultiIndex):
                        cols = cols.get_level_values(0)
                    last_row = data.iloc[-1]
                    prev_row = data.iloc[-2] if len(data) > 1 else last_row
                    t = chunk[0]
                    result[t] = {
                        "price": float(last_row["Close"]) if "Close" in data.columns or ("Close" in str(data.columns)) else 0,
                        "prev_close": float(prev_row["Close"]) if "Close" in data.columns or ("Close" in str(data.columns)) else 0,
                    }
        except Exception:
            pass
    return result


def fetch_fundamentals(ticker: str) -> dict:
    """Fetch fundamental data for a single ticker."""
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


def process_all_stocks(holdings: Optional[dict] = None) -> list[dict]:
    """
    Main processing loop. Fetches data and computes everything for all stocks.

    Args:
        holdings: dict of {ticker: {shares, avg_price, equity}} from Robinhood

    Returns:
        List of dicts, one per stock, sorted by personal score descending.
    """
    init_db()
    tickers = get_stock_universe()

    # Try to discover new trending stocks (best effort)
    try:
        discover_trending()
        tickers = get_stock_universe()  # reload with discoveries
    except Exception:
        pass

    results = []
    total = len(tickers)

    for idx, ticker in enumerate(tickers):
        try:
            print(f"[{idx + 1}/{total}] Processing {ticker}...")

            # Fetch 1Y+ daily closes (get extra for 3Y/5Y returns if available)
            closes = get_daily_closes(ticker, days=1300)
            if not closes:
                print(f"  Skipping {ticker}: no data")
                continue

            # Fundamentals
            fundamentals = fetch_fundamentals(ticker)
            current_price = closes[-1][1]
            high_52w = fundamentals.get("52w_high", 0) or max(c for _, c in closes[-252:]) if len(closes) >= 252 else max(c for _, c in closes)
            low_52w = fundamentals.get("52w_low", 0) or min(c for _, c in closes[-252:]) if len(closes) >= 252 else min(c for _, c in closes)

            # Returns
            returns = compute_returns(closes, current_price)

            # Intuition point (use 1Y closes only for crossing detection)
            closes_1y = closes[-260:]  # ~1 year
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
            print(f"  Error processing {ticker}: {e}")
            continue

    # Sort by personal score descending, then evidence score
    results.sort(key=lambda r: (-r["personal_score"], -r["evidence_score"]))

    # Assign ranks
    for i, r in enumerate(results, 1):
        r["rank"] = i

    # Log refresh
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO refresh_history (timestamp, stocks_processed, status) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), len(results), "success"),
    )
    conn.commit()
    conn.close()

    return results
