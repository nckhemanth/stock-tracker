#!/usr/bin/env python3
"""
Main runner. Execute this to trigger a full refresh.
Used by GitHub Actions on schedule, or can be run manually.
"""

import sys
import time
from datetime import datetime

from src.scheduler import is_trading_day, is_market_hours
from src.holdings import get_robinhood_holdings
from src.data_engine import process_all_stocks
from src.render import render_html
from src.notify import send_refresh_email


def main(force: bool = False):
    start = time.time()
    print(f"=== Stock Tracker Refresh ===")
    print(f"Time: {datetime.utcnow().isoformat()} UTC")

    # Check if today is a trading day
    if not force and not is_trading_day():
        print("Not a trading day. Skipping. (Use --force to override)")
        return

    # 1. Pull Robinhood holdings
    print("\n[1/6] Fetching Robinhood holdings...")
    holdings = get_robinhood_holdings()
    print(f"  Found {len(holdings)} positions")

    # 2-5. Process all stocks (universe, price data, fundamentals, scoring)
    stocks = process_all_stocks(holdings=holdings)

    if not stocks:
        print("ERROR: No stocks processed. Aborting.")
        sys.exit(1)

    # 6. Render HTML
    print(f"\n[5/5] Rendering HTML...")
    output = render_html(stocks)
    print(f"  Written to {output}")

    # Send email
    print("\nSending email notification...")
    send_refresh_email(len(stocks), stocks[:10])

    elapsed = time.time() - start
    print(f"\n=== Done in {elapsed:.0f}s ===")
    print(f"Top 5: {[(s['rank'], s['ticker'], s['personal_score']) for s in stocks[:5]]}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    main(force=force)
