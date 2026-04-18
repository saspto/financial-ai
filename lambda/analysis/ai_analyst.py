"""
AI analyst supporting two LLM backends, selected via LLM_PROVIDER env var:
  - "bedrock"  (default) — AWS Bedrock Claude Haiku 3.5, no external API key
  - "gemini"             — Google Gemini via API key stored in SSM
"""
import json
import logging
import os
from datetime import date
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

# ── Provider selection ────────────────────────────────────────────────────────
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "bedrock").lower()  # "bedrock" | "gemini"

# ── Bedrock defaults ──────────────────────────────────────────────────────────
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-west-2")

# ── Gemini defaults ───────────────────────────────────────────────────────────
# Recommended: gemini-2.0-flash (fast + cheap), gemini-1.5-pro (higher quality)
GEMINI_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-2.0-flash")
GEMINI_KEY_SSM = os.environ.get("GEMINI_KEY_SSM_PARAM", "/financial-ai/gemini-key")

SYSTEM_PROMPT = """You are a senior financial analyst with 20+ years of experience at top Wall Street firms.
You write concise, data-driven financial intelligence reports for institutional investors.
Your tone is professional, authoritative, and actionable.
Never speculate beyond data provided. Always note that content is for informational purposes only.
Format responses as JSON exactly as instructed."""


def _get_ssm_secret(param_name: str) -> Optional[str]:
    val = os.environ.get(param_name.split("/")[-1].upper().replace("-", "_"))
    if val:
        return val
    try:
        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception as e:
        logger.warning("SSM fetch failed for %s: %s", param_name, e)
        return None


def _extract_json(text: str) -> dict | list:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


class AIAnalyst:
    def __init__(self):
        if LLM_PROVIDER == "gemini":
            self._init_gemini()
        else:
            self._init_bedrock()

    def _init_bedrock(self):
        self._bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        self._gemini_model = None
        logger.info("LLM provider: Bedrock (%s)", BEDROCK_MODEL_ID)

    def _init_gemini(self):
        import google.generativeai as genai
        api_key = _get_ssm_secret(GEMINI_KEY_SSM)
        if not api_key:
            raise RuntimeError(
                "Gemini API key not found. Store it in SSM at "
                f"{GEMINI_KEY_SSM} or set GEMINI_KEY env var."
            )
        genai.configure(api_key=api_key)
        self._gemini_model = genai.GenerativeModel(
            model_name=GEMINI_MODEL_ID,
            system_instruction=SYSTEM_PROMPT,
        )
        self._bedrock = None
        logger.info("LLM provider: Gemini (%s)", GEMINI_MODEL_ID)

    # ── Public entrypoint ─────────────────────────────────────────────────────

    def analyze(
        self,
        top_stocks: list[dict],
        top_etfs: list[dict],
        market_summary: dict,
        articles: list[dict],
        upcoming_earnings: list[dict],
        buy_sell_data: dict,
        report_date_start: date,
        report_date_end: date,
    ) -> dict:
        date_range = f"{report_date_start.strftime('%B %d')} – {report_date_end.strftime('%B %d, %Y')}"
        analysis = {}
        analysis["market_overview"] = self._market_overview(market_summary, articles, date_range)
        analysis["stock_analysis"] = self._analyze_movers(top_stocks[:15], "stocks", articles)
        analysis["etf_analysis"] = self._analyze_movers(top_etfs[:10], "ETFs", articles)
        analysis["buy_sell_commentary"] = self._buy_sell_commentary(buy_sell_data, market_summary)
        analysis["earnings_preview"] = self._earnings_preview(upcoming_earnings, articles)
        analysis["ten_things_to_know"] = self._ten_things(
            market_summary, top_stocks[:10], top_etfs[:5],
            articles, upcoming_earnings, buy_sell_data, date_range
        )
        return analysis

    # ── Provider dispatch ─────────────────────────────────────────────────────

    def _invoke(self, prompt: str, max_tokens: int = 1500) -> dict | list:
        if LLM_PROVIDER == "gemini":
            return self._invoke_gemini(prompt)
        return self._invoke_bedrock(prompt, max_tokens)

    def _invoke_bedrock(self, prompt: str, max_tokens: int) -> dict | list:
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            text = json.loads(resp["body"].read())["content"][0]["text"]
            return _extract_json(text)
        except Exception as e:
            logger.error("Bedrock invoke error: %s", e)
            return {}

    def _invoke_gemini(self, prompt: str) -> dict | list:
        try:
            resp = self._gemini_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
            )
            return _extract_json(resp.text)
        except Exception as e:
            logger.error("Gemini invoke error: %s", e)
            return {}

    # ── Prompt methods (provider-agnostic) ────────────────────────────────────

    def _market_overview(self, market_summary: dict, articles: list[dict], date_range: str) -> dict:
        top_articles = [f"- {a['title']} ({a['source']})" for a in articles[:20]]
        prompt = f"""Analyze the market performance for {date_range}.

Market Index Performance:
{json.dumps(market_summary, indent=2)}

Top News Headlines:
{chr(10).join(top_articles)}

Return ONLY valid JSON:
{{
  "headline": "one-sentence market summary",
  "overview": "3-4 sentence market narrative covering index moves, macro drivers, and sentiment",
  "key_themes": ["theme1", "theme2", "theme3"],
  "market_mood": "Bullish|Bearish|Mixed|Cautious",
  "major_drivers": ["driver1", "driver2", "driver3"]
}}"""
        return self._invoke(prompt, 800) or {
            "headline": f"Markets active {date_range}",
            "overview": "Market data collected and analyzed.",
            "key_themes": [],
            "market_mood": "Mixed",
            "major_drivers": [],
        }

    def _analyze_movers(self, movers: list[dict], asset_class: str, articles: list[dict]) -> list[dict]:
        symbols = [m["symbol"] for m in movers]
        relevant_articles = [
            f"- {a['title']}: {a['summary'][:100]}"
            for a in articles
            if any(s.lower() in (a.get("title", "") + a.get("summary", "")).lower() for s in symbols)
        ][:15]

        movers_text = json.dumps([{
            "symbol": m["symbol"],
            "name": m.get("name", m["symbol"]),
            "sector": m.get("sector", "N/A"),
            "pct_change": m["pct_change"],
            "description": m.get("description", "")[:150],
        } for m in movers], indent=2)

        prompt = f"""Analyze why these top {asset_class} performed well and their future prospects.

Top Performers:
{movers_text}

Relevant News:
{chr(10).join(relevant_articles) if relevant_articles else "No specific news found."}

Return ONLY valid JSON array with one object per {asset_class[:-1]}:
[
  {{
    "symbol": "TICKER",
    "why_performed": "2-3 sentence explanation of why this performed well",
    "catalysts": ["catalyst1", "catalyst2"],
    "future_prospects": "2 sentence forward-looking view",
    "risk_factors": ["risk1"],
    "outlook": "Positive|Neutral|Cautious"
  }}
]"""
        result = self._invoke(prompt, 2000)
        return result if isinstance(result, list) else []

    def _buy_sell_commentary(self, buy_sell_data: dict, market_summary: dict) -> dict:
        buy_items = [
            f"{b['symbol']}: {', '.join(b.get('signals', []))}"
            for b in buy_sell_data.get("buy", [])[:10]
        ]
        sell_items = [
            f"{s['symbol']}: {', '.join(s.get('signals', []))}"
            for s in buy_sell_data.get("sell", [])[:10]
        ]
        prompt = f"""Provide buy and sell point commentary for traders.

Stocks/ETFs Reaching Buy Points (technical signals):
{chr(10).join(buy_items) if buy_items else "None identified"}

Stocks/ETFs Reaching Sell Points (technical signals):
{chr(10).join(sell_items) if sell_items else "None identified"}

Return ONLY valid JSON:
{{
  "buy_commentary": "2-3 sentence overall commentary on buy opportunities",
  "sell_commentary": "2-3 sentence commentary on sell/take-profit levels",
  "strategy_note": "One actionable strategic note for today",
  "disclaimer": "Technical signals are not guarantees; always do your own research."
}}"""
        return self._invoke(prompt, 600) or {
            "buy_commentary": "Technical buy signals identified based on RSI, moving averages, and price action.",
            "sell_commentary": "Overbought conditions and technical resistance noted for select names.",
            "strategy_note": "Monitor key levels and volume for confirmation.",
            "disclaimer": "Technical signals are not guarantees; always do your own research.",
        }

    def _earnings_preview(self, upcoming_earnings: list[dict], articles: list[dict]) -> dict:
        if not upcoming_earnings:
            return {"commentary": "No major earnings scheduled in the next two weeks.", "highlights": []}

        top_earnings = upcoming_earnings[:20]
        symbols = [e["symbol"] for e in top_earnings]
        rel_articles = [
            f"- {a['title']}"
            for a in articles
            if any(s in (a.get("title", "") + a.get("summary", "")) for s in symbols)
        ][:10]

        prompt = f"""Preview upcoming earnings for this week and next week.

Upcoming Earnings:
{json.dumps(top_earnings, indent=2)}

Related News:
{chr(10).join(rel_articles) if rel_articles else "None found."}

Return ONLY valid JSON:
{{
  "commentary": "2-3 sentence overview of earnings season expectations",
  "highlights": [
    {{
      "symbol": "TICKER",
      "date": "YYYY-MM-DD",
      "time": "bmo or amc",
      "what_to_watch": "Key metric or theme to watch",
      "consensus_view": "Analyst expectations summary"
    }}
  ]
}}"""
        return self._invoke(prompt, 1000) or {"commentary": "Earnings season continues.", "highlights": []}

    def _ten_things(
        self,
        market_summary: dict,
        top_stocks: list[dict],
        top_etfs: list[dict],
        articles: list[dict],
        upcoming_earnings: list[dict],
        buy_sell_data: dict,
        date_range: str,
    ) -> list[dict]:
        top_articles = [f"- {a['title']} ({a['source']})" for a in articles[:25]]
        top_stock_names = ", ".join(f"{s['symbol']} ({s['pct_change']:+.1f}%)" for s in top_stocks[:5])
        top_etf_names = ", ".join(f"{e['symbol']} ({e['pct_change']:+.1f}%)" for e in top_etfs[:5])
        buy_syms = ", ".join(b["symbol"] for b in buy_sell_data.get("buy", [])[:5])
        sell_syms = ", ".join(s["symbol"] for s in buy_sell_data.get("sell", [])[:5])
        next_earnings = ", ".join(f"{e['symbol']} ({e['date']})" for e in upcoming_earnings[:5])

        prompt = f"""Generate "10 Things to Know Today" for financial professionals. Date range: {date_range}.

Market Summary: {json.dumps({k: v.get('change_pct') for k, v in market_summary.items()}, indent=2)}
Top Stocks: {top_stock_names}
Top ETFs: {top_etf_names}
Buy Points: {buy_syms or "None"}
Sell Points: {sell_syms or "None"}
Upcoming Earnings: {next_earnings or "None"}
Top Headlines:
{chr(10).join(top_articles)}

Return ONLY a valid JSON array of exactly 10 items:
[
  {{
    "number": 1,
    "headline": "Short punchy headline (max 10 words)",
    "detail": "2-3 sentence explanation with data and context",
    "category": "Markets|Stocks|ETFs|Macro|Earnings|Technical|Sector|Global|Crypto|Commodities"
  }}
]"""
        result = self._invoke(prompt, 2000)
        return result if isinstance(result, list) else [
            {"number": i + 1, "headline": f"Point {i + 1}", "detail": "See full report.", "category": "Markets"}
            for i in range(10)
        ]
