"""
Performance ranking: returns top N by percentage gain,
enriches with sector, industry, and basic fundamental data.
"""
import logging
from typing import Literal

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    def rank(self, df: pd.DataFrame, top_n: int = 50) -> list[dict]:
        if df.empty:
            return []

        top = df.head(top_n).copy()
        symbols = top["symbol"].tolist()

        info_map = self._fetch_info(symbols)

        results = []
        for _, row in top.iterrows():
            sym = row["symbol"]
            info = info_map.get(sym, {})
            results.append({
                "symbol": sym,
                "name": info.get("shortName") or info.get("longName", sym),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "pct_change": round(float(row["pct_change"]), 2),
                "close_price": round(float(row["close_price"]), 2) if pd.notna(row["close_price"]) else None,
                "prev_close": round(float(row["prev_close"]), 2) if pd.notna(row["prev_close"]) else None,
                "avg_volume": int(row["avg_volume"]) if pd.notna(row["avg_volume"]) else None,
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "analyst_target": info.get("targetMeanPrice"),
                "description": (info.get("longBusinessSummary") or "")[:400],
            })
        return results

    def _fetch_info(self, symbols: list[str]) -> dict:
        info_map = {}
        # yfinance Tickers (batch) is faster than individual Ticker calls
        try:
            tickers = yf.Tickers(" ".join(symbols))
            for sym in symbols:
                try:
                    t = tickers.tickers.get(sym)
                    if t:
                        info_map[sym] = t.info
                except Exception:
                    info_map[sym] = {}
        except Exception as e:
            logger.warning("Info fetch error: %s", e)
        return info_map
