"""
Robinhood holdings integration.

Uses robin_stocks to pull the user's current positions.
Requires RH_USERNAME, RH_PASSWORD, RH_TOTP_SECRET env vars.
"""

import os
from typing import Optional


def get_robinhood_holdings() -> dict:
    """
    Pull current Robinhood positions.

    Returns dict of {ticker: {shares, avg_price, equity, pnl_pct}}
    Falls back to empty dict if auth fails.
    """
    username = os.environ.get("RH_USERNAME", "")
    password = os.environ.get("RH_PASSWORD", "")
    totp_secret = os.environ.get("RH_TOTP_SECRET", "")

    if not username or not password:
        print("  [Holdings] No Robinhood credentials, skipping holdings pull")
        return _load_cached_holdings()

    try:
        import robin_stocks.robinhood as r
        import pyotp

        totp = pyotp.TOTP(totp_secret).now() if totp_secret else None
        r.login(username, password, mfa_code=totp, store_session=True)

        positions = r.get_open_stock_positions()
        holdings = {}

        for pos in positions:
            ticker = _instrument_to_ticker(pos.get("instrument", ""), r)
            if not ticker:
                continue

            shares = float(pos.get("quantity", 0))
            avg_price = float(pos.get("average_buy_price", 0))
            equity = shares * avg_price

            holdings[ticker] = {
                "shares": round(shares, 6),
                "avg_price": round(avg_price, 4),
                "equity": round(equity, 2),
            }

        r.logout()

        # Cache holdings for offline use
        _cache_holdings(holdings)

        return holdings

    except ImportError:
        print("  [Holdings] robin_stocks not installed, using cache")
        return _load_cached_holdings()
    except Exception as e:
        print(f"  [Holdings] Robinhood auth failed: {e}, using cache")
        return _load_cached_holdings()


def _instrument_to_ticker(instrument_url: str, r) -> Optional[str]:
    """Resolve Robinhood instrument URL to ticker symbol."""
    try:
        data = r.get_instrument_by_url(instrument_url)
        return data.get("symbol")
    except Exception:
        return None


def _cache_holdings(holdings: dict):
    """Save holdings to disk as fallback."""
    import json
    from .config import DATA_DIR
    DATA_DIR.mkdir(exist_ok=True)
    cache_file = DATA_DIR / "holdings_cache.json"
    with open(cache_file, "w") as f:
        json.dump(holdings, f, indent=2)


def _load_cached_holdings() -> dict:
    """Load cached holdings from disk."""
    import json
    from .config import DATA_DIR
    cache_file = DATA_DIR / "holdings_cache.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return {}
