"""
Market data fetcher using yfinance for stocks and ETFs.
Pulls S&P 500 stocks + major ETFs, computes multi-day returns.
"""
import logging
from datetime import date, timedelta
from typing import Literal

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Representative universe — extended S&P 500 + small/mid cap
SP500_SAMPLE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","BRK-B","LLY","AVGO",
    "JPM","V","TSLA","UNH","XOM","MA","JNJ","PG","HD","MRK","ABBV","COST",
    "CVX","CRM","NFLX","AMD","ORCL","ACN","LIN","TXN","MCD","NEE","ABT",
    "DHR","WMT","BMY","AMGN","PFE","INTC","QCOM","RTX","GE","HON","UNP",
    "IBM","SBUX","SPGI","ELV","MDT","DE","CAT","BA","GS","MS","BLK","AXP",
    "ISRG","SYK","VRTX","REGN","ZTS","TMO","ILMN","BIIB","GILD","MRNA",
    "NOW","SNOW","CRWD","ZS","PANW","DDOG","MDB","PLTR","COIN","RBLX",
    "UBER","LYFT","ABNB","DASH","ZM","SPOT","SHOP","SQ","PYPL","AFRM",
    "F","GM","RIVN","LCID","NIO","XPEV","LI","TSLA","STLA","TTM",
    "WFC","C","BAC","USB","TFC","SCHW","COF","DFS","SYF","AIG",
    "CLX","KO","PEP","PM","MO","BTI","TAP","STZ","BUD","DEO",
    "DIS","CMCSA","PARA","WBD","NFLX","AMC","CNK","LYV","SIX","EPD",
]
SP500_SAMPLE = list(dict.fromkeys(SP500_SAMPLE))  # deduplicate

ETF_UNIVERSE = [
    # Broad market
    "SPY","IVV","VOO","QQQ","DIA","IWM","MDY","IJH","IJR","VTI","ITOT",
    # Sector ETFs
    "XLK","XLF","XLV","XLE","XLI","XLC","XLY","XLP","XLU","XLRE","XLB",
    # Factor / thematic
    "VGT","VFH","VHT","VDE","VIS","VCR","VDC","ARKK","ARKW","ARKF","ARKG",
    "BOTZ","AIQ","ROBO","SKYY","CLOU","WCLD","FINX","IPAY","CIBR","HACK",
    # International
    "EFA","EEM","VEA","VWO","IEMG","FXI","EWJ","EWZ","EWG","EWC","INDA",
    # Fixed Income
    "AGG","BND","TLT","IEF","SHY","LQD","HYG","JNK","MUB","TIP","VTIP",
    # Commodities
    "GLD","IAU","SLV","USO","DBO","PDBC","CORN","WEAT","SOYB","DJP",
    # Leveraged / Inverse
    "TQQQ","SQQQ","UPRO","SPXU","UDOW","SDOW","LABU","LABD","TECL","SOXL",
    # Dividend
    "VYM","SCHD","DVY","HDV","DGRO","NOBL","JEPI","JEPQ","DIVO","PFFD",
    # Real Assets
    "VNQ","SCHH","REZ","MORT","REM","IYR","XLRE","O","AMT","PLD",
]
ETF_UNIVERSE = list(dict.fromkeys(ETF_UNIVERSE))


class MarketDataFetcher:
    def get_top_movers(
        self,
        start_date: date,
        end_date: date,
        asset_type: Literal["stock", "etf"] = "stock",
    ) -> pd.DataFrame:
        universe = SP500_SAMPLE if asset_type == "stock" else ETF_UNIVERSE

        # Fetch from 5 days before start to capture prior close
        fetch_start = start_date - timedelta(days=7)
        fetch_end = end_date + timedelta(days=1)

        logger.info("Fetching %d %s tickers from %s to %s", len(universe), asset_type, fetch_start, fetch_end)

        try:
            raw = yf.download(
                universe,
                start=fetch_start.isoformat(),
                end=fetch_end.isoformat(),
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as e:
            logger.error("yfinance download error: %s", e)
            return pd.DataFrame()

        if raw.empty:
            return pd.DataFrame()

        close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

        # Period return = close on last available day vs close before period start
        period_close = close[close.index.date >= start_date]
        prior_close = close[close.index.date < start_date]

        if period_close.empty or prior_close.empty:
            return pd.DataFrame()

        end_prices = period_close.iloc[-1]
        start_prices = prior_close.iloc[-1]

        pct_change = ((end_prices - start_prices) / start_prices * 100).dropna()
        volume = raw["Volume"] if "Volume" in raw.columns else raw.xs("Volume", axis=1, level=0)
        avg_volume = volume[volume.index.date >= start_date].mean()

        df = pd.DataFrame({
            "symbol": pct_change.index,
            "pct_change": pct_change.values,
            "close_price": end_prices.reindex(pct_change.index).values,
            "prev_close": start_prices.reindex(pct_change.index).values,
            "avg_volume": avg_volume.reindex(pct_change.index).values,
        })
        df["asset_type"] = asset_type
        return df.sort_values("pct_change", ascending=False).reset_index(drop=True)

    def get_market_summary(self, start_date: date, end_date: date) -> dict:
        indices = {
            "S&P 500": "^GSPC",
            "Nasdaq 100": "^NDX",
            "Dow Jones": "^DJI",
            "Russell 2000": "^RUT",
            "VIX": "^VIX",
            "10Y Treasury": "^TNX",
            "USD Index": "DX-Y.NYB",
            "Gold": "GC=F",
            "Oil (WTI)": "CL=F",
            "Bitcoin": "BTC-USD",
        }
        fetch_start = start_date - timedelta(days=7)
        summary = {}

        try:
            raw = yf.download(
                list(indices.values()),
                start=fetch_start.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

            period_close = close[close.index.date >= start_date]
            prior_close = close[close.index.date < start_date]

            if not period_close.empty and not prior_close.empty:
                for name, ticker in indices.items():
                    if ticker in close.columns:
                        end_val = period_close[ticker].dropna().iloc[-1] if not period_close[ticker].dropna().empty else None
                        start_val = prior_close[ticker].dropna().iloc[-1] if not prior_close[ticker].dropna().empty else None
                        if end_val and start_val:
                            summary[name] = {
                                "value": round(float(end_val), 2),
                                "change_pct": round(float((end_val - start_val) / start_val * 100), 2),
                                "ticker": ticker,
                            }
        except Exception as e:
            logger.error("Market summary error: %s", e)

        return summary
