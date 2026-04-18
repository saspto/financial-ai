"""
Earnings calendar fetcher via yfinance and Finnhub.
Returns upcoming earnings for current and next week.
"""
import logging
import os
from datetime import date, timedelta
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

FINNHUB_KEY_PARAM = "/financial-ai/finnhub-key"

# High-profile tickers always worth highlighting
WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","JPM","BAC","WFC",
    "GS","MS","JNJ","PFE","ABBV","LLY","MRK","UNH","CVX","XOM","BP",
    "COST","WMT","HD","TGT","NKE","SBUX","MCD","DIS","NFLX","CMCSA",
    "AMD","INTC","QCOM","AVGO","TXN","CRM","ORCL","IBM","SHOP","SNOW",
    "PANW","CRWD","ZS","NOW","DDOG","PLTR","COIN","UBER","LYFT","ABNB",
]


def _get_finnhub_key() -> Optional[str]:
    key = os.environ.get("FINNHUB_KEY")
    if key:
        return key
    try:
        import boto3
        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=FINNHUB_KEY_PARAM, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception:
        return None


class EarningsCalendar:
    def get_upcoming(self, weeks: int = 2) -> list[dict]:
        today = date.today()
        end_date = today + timedelta(weeks=weeks)
        earnings = []

        # Try Finnhub first (more comprehensive)
        finnhub_data = self._fetch_finnhub(today, end_date)
        if finnhub_data:
            return finnhub_data

        # Fallback: check yfinance for watchlist tickers
        return self._fetch_yfinance_watchlist()

    def _fetch_finnhub(self, start: date, end: date) -> list[dict]:
        key = _get_finnhub_key()
        if not key:
            return []
        try:
            import finnhub
            client = finnhub.Client(api_key=key)
            raw = client.earnings_calendar(
                _from=start.isoformat(),
                to=end.isoformat(),
                symbol="",
                international=False,
            )
            results = []
            for item in (raw.get("earningsCalendar") or []):
                eps_est = item.get("epsEstimate")
                results.append({
                    "symbol": item.get("symbol", ""),
                    "date": item.get("date", ""),
                    "eps_estimate": eps_est,
                    "revenue_estimate": item.get("revenueEstimate"),
                    "time": item.get("hour", ""),  # bmo / amc
                })
            return sorted(results, key=lambda x: x["date"])
        except Exception as e:
            logger.warning("Finnhub earnings error: %s", e)
            return []

    def _fetch_yfinance_watchlist(self) -> list[dict]:
        results = []
        today = date.today()
        end_date = today + timedelta(weeks=2)
        for ticker in WATCHLIST:
            try:
                t = yf.Ticker(ticker)
                cal = t.calendar
                if cal is None or cal.empty:
                    continue
                # calendar columns: Earnings Date, Earnings Average, etc.
                for _, row in cal.iterrows():
                    ed = row.get("Earnings Date")
                    if ed and hasattr(ed, "date"):
                        d = ed.date()
                        if today <= d <= end_date:
                            results.append({
                                "symbol": ticker,
                                "date": d.isoformat(),
                                "eps_estimate": row.get("Earnings Average"),
                                "revenue_estimate": row.get("Revenue Average"),
                                "time": "",
                            })
            except Exception:
                continue
        return sorted(results, key=lambda x: x["date"])
