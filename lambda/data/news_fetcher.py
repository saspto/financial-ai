"""
News fetcher from reputed financial sources via RSS feeds and NewsAPI.
Sources: WSJ, Reuters, Bloomberg (via RSS), MarketWatch, CNBC, FT, Barron's,
         Seeking Alpha, Yahoo Finance, Motley Fool, Investopedia, Morningstar.
"""
import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

RSS_FEEDS = {
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Reuters Markets": "https://feeds.reuters.com/reuters/marketsNews",
    "MarketWatch Top": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "MarketWatch Markets": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC Finance": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "CNBC Economy": "https://www.cnbc.com/id/20910274/device/rss/rss.html",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
    "Motley Fool": "https://www.fool.com/feeds/index.aspx",
    "Investopedia": "https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline",
    "FT Markets": "https://www.ft.com/markets?format=rss",
    "Barron's": "https://www.barrons.com/xml/rss/3_7041.xml",
    "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "WSJ Economy": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "Morningstar": "https://www.morningstar.com/rss/articles",
}

NEWSAPI_KEY_PARAM = "/financial-ai/newsapi-key"


def _get_newsapi_key() -> Optional[str]:
    key = os.environ.get("NEWSAPI_KEY")
    if key:
        return key
    try:
        import boto3
        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=NEWSAPI_KEY_PARAM, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception:
        return None


class NewsFetcher:
    def fetch_all(self, start_date: date, end_date: date) -> list[dict]:
        articles = []
        articles.extend(self._fetch_rss(start_date, end_date))
        articles.extend(self._fetch_newsapi(start_date, end_date))
        # Deduplicate by title
        seen = set()
        unique = []
        for a in articles:
            key = a.get("title", "")[:80].lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(a)
        logger.info("Fetched %d unique articles", len(unique))
        return unique

    def _fetch_rss(self, start_date: date, end_date: date) -> list[dict]:
        articles = []
        cutoff = datetime(start_date.year, start_date.month, start_date.day, tzinfo=ET)
        end_cutoff = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=ET)

        for source, url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:30]:
                    pub = self._parse_date(entry)
                    if pub and not (cutoff <= pub <= end_cutoff):
                        continue
                    summary = entry.get("summary", "") or entry.get("description", "")
                    if summary:
                        soup = BeautifulSoup(summary, "html.parser")
                        summary = soup.get_text(separator=" ", strip=True)[:800]
                    articles.append({
                        "source": source,
                        "title": entry.get("title", ""),
                        "summary": summary,
                        "url": entry.get("link", ""),
                        "published": pub.isoformat() if pub else "",
                    })
            except Exception as e:
                logger.warning("RSS fetch error for %s: %s", source, e)

        return articles

    def _fetch_newsapi(self, start_date: date, end_date: date) -> list[dict]:
        api_key = _get_newsapi_key()
        if not api_key:
            return []
        articles = []
        queries = [
            "stock market stocks equities",
            "ETF funds investing",
            "Federal Reserve interest rates economy",
            "earnings quarterly results",
        ]
        try:
            for q in queries:
                resp = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": q,
                        "from": start_date.isoformat(),
                        "to": end_date.isoformat(),
                        "language": "en",
                        "sortBy": "relevancy",
                        "pageSize": 20,
                        "domains": (
                            "wsj.com,bloomberg.com,reuters.com,ft.com,"
                            "marketwatch.com,cnbc.com,barrons.com,"
                            "seekingalpha.com,fool.com,investopedia.com"
                        ),
                    },
                    headers={"X-Api-Key": api_key},
                    timeout=10,
                )
                if resp.status_code == 200:
                    for item in resp.json().get("articles", []):
                        articles.append({
                            "source": item.get("source", {}).get("name", "NewsAPI"),
                            "title": item.get("title", ""),
                            "summary": (item.get("description") or "")[:800],
                            "url": item.get("url", ""),
                            "published": item.get("publishedAt", ""),
                        })
        except Exception as e:
            logger.warning("NewsAPI error: %s", e)
        return articles

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        try:
            import time
            import email.utils as eut
            struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if struct:
                ts = time.mktime(struct)
                return datetime.fromtimestamp(ts, tz=ET)
        except Exception:
            pass
        try:
            raw = entry.get("published") or entry.get("updated") or ""
            if raw:
                parsed = eut.parsedate_to_datetime(raw)
                return parsed.astimezone(ET)
        except Exception:
            pass
        return None
