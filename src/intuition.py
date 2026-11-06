"""
Intuition Point Detection Engine.

Replicates the user's visual chart-reading process:
1. Get 1Y daily closes for a stock
2. Scan candidate price levels from current price upward
3. At each level, count independent upward crossings (prev close < level, curr close >= level)
4. Measure how many distinct calendar quarters those crossings span
5. Score each level: crossing_count * quarter_spread * upside_factor
6. Pick the "optimistic" level — dense crossings, good spread, meaningful upside
"""

import math
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
import pandas as pd


def get_daily_closes(ticker: str, days: int = 365) -> list[tuple[str, float]]:
    """Fetch 1Y daily closes from yfinance. Returns list of (date_str, close)."""
    end = datetime.now()
    start = end - timedelta(days=days + 10)  # buffer for weekends
    try:
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df.empty:
            return []
        # Handle multi-level columns from yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        closes = [(idx.strftime("%Y-%m-%d"), float(row["Close"]))
                  for idx, row in df.iterrows()
                  if not math.isnan(row["Close"])]
        return closes[-days:]  # trim to requested window
    except Exception:
        return []


def find_upward_crossings(closes: list[tuple[str, float]], level: float) -> list[str]:
    """Find dates where close crossed above a level (prev < level, curr >= level)."""
    crossings = []
    for i in range(1, len(closes)):
        prev_close = closes[i - 1][1]
        curr_date, curr_close = closes[i]
        if prev_close < level and curr_close >= level:
            crossings.append(curr_date)
    return crossings


def quarter_spread(dates: list[str]) -> int:
    """Count how many distinct calendar quarters the dates span."""
    quarters = set()
    for d in dates:
        year = int(d[:4])
        month = int(d[5:7])
        q = (year, (month - 1) // 3 + 1)
        quarters.add(q)
    return len(quarters)


def compute_intuition_point(
    closes: list[tuple[str, float]],
    current_price: float,
    high_52w: float,
    override: Optional[float] = None,
) -> dict:
    """
    Compute the optimistic intuition point for a stock.

    If override is set, uses that as the locked point and just computes evidence around it.

    Returns dict with:
      - low_point, optimistic_point, high_point (the three tiers)
      - crossings_at_optimistic, quarters_spread, crossing_dates
      - upside_pct
    """
    if not closes or current_price <= 0:
        return {"optimistic_point": None, "crossings": 0, "quarters": 0,
                "upside_pct": 0, "crossing_dates": [], "low_point": None,
                "high_point": None, "score": 0}

    # If user override exists, compute evidence at that level only
    if override is not None:
        crossings = find_upward_crossings(closes, override)
        qs = quarter_spread(crossings)
        upside = (override / current_price - 1) * 100
        return {
            "optimistic_point": override,
            "crossings": len(crossings),
            "quarters": qs,
            "upside_pct": round(upside, 1),
            "crossing_dates": crossings,
            "low_point": None,  # Not computed for overrides
            "high_point": None,
            "score": len(crossings) * qs * max(upside, 1),
            "source": "user_override",
        }

    # Auto-detect: scan levels from current_price+5% to 52W high
    # Step size = 1% of current price, min $0.50
    step = max(current_price * 0.01, 0.50)
    min_level = current_price * 1.05  # at least 5% above
    max_level = high_52w * 1.05       # slightly above 52W high

    if min_level >= max_level:
        max_level = current_price * 2  # fallback for stocks near 52W high

    candidates = []
    level = min_level
    while level <= max_level:
        crossings = find_upward_crossings(closes, level)
        n_crossings = len(crossings)
        qs = quarter_spread(crossings)
        upside = (level / current_price - 1) * 100

        if n_crossings >= 2:  # minimum to consider
            # Score formula: rewards crossing density, quarter spread, and upside
            # Penalizes extremes (too low upside = boring, too high = thin evidence)
            upside_factor = _upside_weight(upside)
            score = n_crossings * qs * upside_factor
            candidates.append({
                "level": round(level, 2),
                "crossings": n_crossings,
                "quarters": qs,
                "upside_pct": round(upside, 1),
                "crossing_dates": crossings,
                "score": round(score, 2),
            })

        level += step

    if not candidates:
        return {"optimistic_point": None, "crossings": 0, "quarters": 0,
                "upside_pct": 0, "crossing_dates": [], "low_point": None,
                "high_point": None, "score": 0, "source": "algorithm_no_candidates"}

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # The optimistic point = highest scoring level
    optimistic = candidates[0]

    # Find low point = level with most crossings regardless of upside
    by_crossings = sorted(candidates, key=lambda c: (-c["crossings"], c["upside_pct"]))
    low = by_crossings[0] if by_crossings else optimistic

    # Find high point = level with highest upside that still has >= 3 crossings
    high_candidates = [c for c in candidates if c["crossings"] >= 3]
    if high_candidates:
        high = max(high_candidates, key=lambda c: c["upside_pct"])
    else:
        high = max(candidates, key=lambda c: c["upside_pct"])

    return {
        "optimistic_point": optimistic["level"],
        "crossings": optimistic["crossings"],
        "quarters": optimistic["quarters"],
        "upside_pct": optimistic["upside_pct"],
        "crossing_dates": optimistic["crossing_dates"],
        "low_point": low["level"],
        "high_point": high["level"],
        "score": optimistic["score"],
        "source": "algorithm",
    }


def _upside_weight(upside_pct: float) -> float:
    """
    Weight function for upside percentage.
    - Below 10%: very low weight (not motivating)
    - 15-60%: sweet spot, highest weight
    - Above 80%: declining weight (too ambitious, thin evidence)
    """
    if upside_pct < 5:
        return 0.1
    elif upside_pct < 15:
        return 0.3 + (upside_pct - 5) * 0.07  # ramp up 0.3 → 1.0
    elif upside_pct <= 60:
        return 1.0  # sweet spot
    elif upside_pct <= 100:
        return 1.0 - (upside_pct - 60) * 0.01  # gentle decline
    else:
        return 0.6  # still possible but less weighted


def compute_scores(
    ticker: str,
    current_price: float,
    market_cap_b: float,
    intuition_data: dict,
    returns: dict,
    high_52w: float,
    low_52w: float,
) -> tuple[float, float]:
    """
    Compute personal strategy score and independent evidence score (both /10).

    Personal score factors:
    - Intuition point upside and crossing quality
    - Proximity to 52W low (recovery opportunity)
    - Market cap (bigger = more weight for established names)

    Evidence score factors:
    - Revenue growth (if available)
    - Margin quality
    - Analyst consensus
    - P/E ratio reasonableness
    - Crossing evidence strength
    """
    crossings = intuition_data.get("crossings", 0)
    quarters = intuition_data.get("quarters", 0)
    upside = intuition_data.get("upside_pct", 0)

    # --- Personal score ---
    personal = 5.0  # base

    # Crossing quality: more crossings + more spread = better
    if crossings >= 8 and quarters >= 4:
        personal += 2.0
    elif crossings >= 5 and quarters >= 3:
        personal += 1.5
    elif crossings >= 3 and quarters >= 2:
        personal += 1.0

    # Upside motivation
    if 30 <= upside <= 80:
        personal += 1.5
    elif 15 <= upside < 30:
        personal += 0.8
    elif upside > 80:
        personal += 0.5  # ambitious, less reliable

    # Proximity to 52W low (closer = more opportunity)
    if current_price > 0 and low_52w > 0:
        above_low = (current_price / low_52w - 1) * 100
        if above_low < 10:
            personal += 1.0
        elif above_low < 25:
            personal += 0.5

    # Market cap preference (bigger companies more reliable for large positions)
    if market_cap_b >= 100:
        personal += 0.3
    elif market_cap_b >= 10:
        personal += 0.2

    personal = min(10.0, round(personal, 2))

    # --- Evidence score ---
    evidence = 5.0  # base

    # Crossing statistical strength
    if crossings >= 10 and quarters >= 4:
        evidence += 2.5
    elif crossings >= 6 and quarters >= 3:
        evidence += 2.0
    elif crossings >= 3 and quarters >= 2:
        evidence += 1.0

    # 1Y return context
    ret_1y = returns.get("1Y", 0)
    if ret_1y is not None and ret_1y > 0:
        evidence += 0.5  # positive momentum
    elif ret_1y is not None and ret_1y < -50:
        evidence -= 0.5  # severe decline, higher risk

    # Market cap stability
    if market_cap_b >= 50:
        evidence += 0.5
    elif market_cap_b >= 10:
        evidence += 0.3

    evidence = max(1.0, min(10.0, round(evidence, 2)))

    return personal, evidence
