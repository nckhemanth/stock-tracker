#!/usr/bin/env python3
"""Quick test: process 5 stocks including CLS to validate the algorithm."""

import sys
sys.path.insert(0, ".")

from src.intuition import get_daily_closes, compute_intuition_point, compute_scores
from src.config import USER_OVERRIDES

TEST_TICKERS = ["CLS", "NVDA", "RDDT", "APP", "TSLA"]

for ticker in TEST_TICKERS:
    print(f"\n{'='*60}")
    print(f"  {ticker}")
    print(f"{'='*60}")

    closes = get_daily_closes(ticker, days=365)
    if not closes:
        print("  No data!")
        continue

    current = closes[-1][1]
    high_52w = max(c for _, c in closes)
    low_52w = min(c for _, c in closes)

    override = USER_OVERRIDES.get(ticker)
    result = compute_intuition_point(closes, current, high_52w, override)

    print(f"  Price: ${current:.2f}")
    print(f"  52W: ${low_52w:.2f} - ${high_52w:.2f}")
    print(f"  Intuition Point: ${result['optimistic_point']}" if result['optimistic_point'] else "  Intuition Point: None")
    print(f"  Low/High: ${result.get('low_point')} / ${result.get('high_point')}")
    print(f"  Upside: {result['upside_pct']}%")
    print(f"  Crossings: {result['crossings']} across {result['quarters']} quarters")
    print(f"  Source: {result.get('source')}")
    if result.get('crossing_dates'):
        print(f"  Dates: {', '.join(result['crossing_dates'][:8])}{'...' if len(result['crossing_dates']) > 8 else ''}")

    personal, evidence = compute_scores(
        ticker, current, 50, result,
        {"1Y": -20}, high_52w, low_52w,
    )
    print(f"  Scores: Personal={personal}/10, Evidence={evidence}/10")
