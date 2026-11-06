"""
Market day checker using exchange_calendars.
"""

from datetime import datetime, date
import pytz


def is_trading_day(check_date: date = None) -> bool:
    """Check if a given date is a NYSE trading day."""
    if check_date is None:
        et = pytz.timezone("US/Eastern")
        check_date = datetime.now(et).date()

    try:
        import exchange_calendars as xcals
        nyse = xcals.get_calendar("XNYS")
        return nyse.is_session(str(check_date))
    except ImportError:
        # Fallback: weekday check only (no holiday awareness)
        return check_date.weekday() < 5
    except Exception:
        return check_date.weekday() < 5


def is_market_hours() -> bool:
    """Check if we're currently in or near market hours (9:00 AM - 4:30 PM ET)."""
    et = pytz.timezone("US/Eastern")
    now = datetime.now(et)
    hour = now.hour
    minute = now.minute
    return (hour >= 9 and (hour < 16 or (hour == 16 and minute <= 30)))
