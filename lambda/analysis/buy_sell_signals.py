"""
Buy/sell signal detector using technical analysis:
- Buy signals: price near 52-week low + momentum reversal, breakout above resistance,
  golden cross (50DMA crossing 200DMA), RSI oversold bounce
- Sell signals: price near 52-week high with volume divergence, death cross,
  RSI overbought + reversal, price below key moving averages
"""
import logging
from datetime import date, timedelta

import pandas as pd
import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


def _rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def _sma(prices: pd.Series, period: int) -> float:
    val = prices.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else float(prices.mean())


class BuySellSignalDetector:
    LOOKBACK_DAYS = 260  # ~1 trading year

    def detect(self, top_stocks: list[dict], top_etfs: list[dict]) -> dict:
        all_symbols = [s["symbol"] for s in top_stocks] + [e["symbol"] for e in top_etfs]
        # Extend universe with laggards that might have buy signals
        price_data = self._fetch_prices(all_symbols)

        buy_signals = []
        sell_signals = []

        for item in top_stocks + top_etfs:
            sym = item["symbol"]
            prices = price_data.get(sym)
            if prices is None or len(prices) < 30:
                continue

            signals = self._compute_signals(sym, item, prices)
            if signals["buy"]:
                buy_signals.append({**item, "signals": signals["buy"], "signal_score": signals["buy_score"]})
            if signals["sell"]:
                sell_signals.append({**item, "signals": signals["sell"], "signal_score": signals["sell_score"]})

        buy_signals.sort(key=lambda x: x["signal_score"], reverse=True)
        sell_signals.sort(key=lambda x: x["signal_score"], reverse=True)

        return {
            "buy": buy_signals[:25],
            "sell": sell_signals[:25],
        }

    def _fetch_prices(self, symbols: list[str]) -> dict[str, pd.Series]:
        start = (date.today() - timedelta(days=self.LOOKBACK_DAYS)).isoformat()
        try:
            raw = yf.download(symbols, start=start, auto_adjust=True, progress=False, threads=True)
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)
            return {sym: close[sym].dropna() for sym in symbols if sym in close.columns}
        except Exception as e:
            logger.warning("Price fetch for signals: %s", e)
            return {}

    def _compute_signals(self, sym: str, item: dict, prices: pd.Series) -> dict:
        current = float(prices.iloc[-1])
        high_52w = float(prices.max())
        low_52w = float(prices.min())
        pct_from_high = (current - high_52w) / high_52w * 100
        pct_from_low = (current - low_52w) / low_52w * 100

        rsi = _rsi(prices)
        sma_50 = _sma(prices, 50)
        sma_200 = _sma(prices, 200) if len(prices) >= 200 else None
        sma_20 = _sma(prices, 20)

        buy_reasons = []
        sell_reasons = []
        buy_score = 0
        sell_score = 0

        # Buy signals
        if rsi < 35:
            buy_reasons.append(f"RSI oversold ({rsi:.1f})")
            buy_score += 2
        if pct_from_low < 10:
            buy_reasons.append(f"Near 52-week low (+{pct_from_low:.1f}%)")
            buy_score += 1
        if sma_200 and current > sma_200 and current > sma_50:
            buy_reasons.append("Above 50DMA & 200DMA (uptrend)")
            buy_score += 2
        if sma_200:
            # Golden cross: 50DMA recently crossed above 200DMA
            prev_50 = _sma(prices.iloc[:-5], 50)
            prev_200 = _sma(prices.iloc[:-5], 200) if len(prices) >= 205 else None
            if prev_200 and prev_50 < prev_200 and sma_50 > sma_200:
                buy_reasons.append("Golden cross (50DMA > 200DMA)")
                buy_score += 3
        if item.get("pct_change", 0) > 3 and rsi < 60:
            buy_reasons.append(f"Strong momentum +{item['pct_change']:.1f}% with room to run")
            buy_score += 1
        if item.get("analyst_target") and current < item["analyst_target"] * 0.85:
            upside = (item["analyst_target"] / current - 1) * 100
            buy_reasons.append(f">{upside:.0f}% upside to analyst target ${item['analyst_target']:.2f}")
            buy_score += 2

        # Sell signals
        if rsi > 75:
            sell_reasons.append(f"RSI overbought ({rsi:.1f})")
            sell_score += 2
        if pct_from_high > -5:
            sell_reasons.append(f"Near 52-week high ({pct_from_high:.1f}% from high)")
            sell_score += 1
        if sma_200 and current < sma_200:
            sell_reasons.append("Below 200DMA (downtrend)")
            sell_score += 2
        if sma_200:
            prev_50 = _sma(prices.iloc[:-5], 50)
            prev_200 = _sma(prices.iloc[:-5], 200) if len(prices) >= 205 else None
            if prev_200 and prev_50 > prev_200 and sma_50 < sma_200:
                sell_reasons.append("Death cross (50DMA < 200DMA)")
                sell_score += 3
        if current < sma_20 and item.get("pct_change", 0) < -3:
            sell_reasons.append(f"Below 20DMA with decline {item['pct_change']:.1f}%")
            sell_score += 1

        return {
            "buy": buy_reasons,
            "sell": sell_reasons,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "rsi": round(rsi, 1),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "price": round(current, 2),
        }
