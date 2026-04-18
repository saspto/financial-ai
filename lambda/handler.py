"""
Financial AI Daily Report - Lambda Handler
Orchestrates data collection, AI analysis, and PDF report generation.
"""
import json
import logging
import os
from datetime import datetime, timedelta
import pytz

import boto3

from data.market_data import MarketDataFetcher
from data.news_fetcher import NewsFetcher
from data.earnings_calendar import EarningsCalendar
from analysis.performance import PerformanceAnalyzer
from analysis.buy_sell_signals import BuySellSignalDetector
from analysis.ai_analyst import AIAnalyst
from report.pdf_generator import PDFReportGenerator

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ET = pytz.timezone("America/New_York")
S3_BUCKET = os.environ.get("S3_BUCKET", "financial-ai-reports")
SES_SENDER = os.environ.get("SES_SENDER", "")
SES_RECIPIENTS = os.environ.get("SES_RECIPIENTS", "").split(",")
REPORT_PREFIX = os.environ.get("REPORT_PREFIX", "reports")


def get_report_date_range() -> tuple[datetime, datetime]:
    """Return (start, end) for the report period.
    Monday → covers Friday 4pm through Sunday midnight (3 days).
    Tue–Fri → covers previous trading day.
    """
    now = datetime.now(ET)
    today = now.date()
    weekday = today.weekday()  # 0=Mon, 4=Fri

    if weekday == 0:  # Monday: go back to Friday
        start_date = today - timedelta(days=3)
    else:
        start_date = today - timedelta(days=1)

    return start_date, today


def lambda_handler(event, context):
    logger.info("Financial AI report started. Event: %s", json.dumps(event, default=str))

    test_mode = event.get("test", False)
    report_date_start, report_date_end = get_report_date_range()

    logger.info("Report period: %s to %s", report_date_start, report_date_end)

    # 1. Fetch market data
    logger.info("Step 1: Fetching market data...")
    market = MarketDataFetcher()
    stocks_df = market.get_top_movers(report_date_start, report_date_end, asset_type="stock")
    etfs_df = market.get_top_movers(report_date_start, report_date_end, asset_type="etf")
    market_summary = market.get_market_summary(report_date_start, report_date_end)

    # 2. Fetch news
    logger.info("Step 2: Fetching financial news...")
    news = NewsFetcher()
    articles = news.fetch_all(report_date_start, report_date_end)

    # 3. Earnings calendar
    logger.info("Step 3: Fetching earnings calendar...")
    earnings = EarningsCalendar()
    upcoming_earnings = earnings.get_upcoming(weeks=2)

    # 4. Performance ranking
    logger.info("Step 4: Ranking performance...")
    perf = PerformanceAnalyzer()
    top_stocks = perf.rank(stocks_df, top_n=50)
    top_etfs = perf.rank(etfs_df, top_n=50)

    # 5. Buy/sell signals
    logger.info("Step 5: Detecting buy/sell signals...")
    signals = BuySellSignalDetector()
    buy_sell_data = signals.detect(top_stocks, top_etfs)

    # 6. AI analysis
    logger.info("Step 6: Running AI analysis...")
    ai = AIAnalyst()
    analysis = ai.analyze(
        top_stocks=top_stocks,
        top_etfs=top_etfs,
        market_summary=market_summary,
        articles=articles,
        upcoming_earnings=upcoming_earnings,
        buy_sell_data=buy_sell_data,
        report_date_start=report_date_start,
        report_date_end=report_date_end,
    )

    # 7. Generate PDF
    logger.info("Step 7: Generating PDF report...")
    gen = PDFReportGenerator()
    pdf_bytes = gen.generate(
        top_stocks=top_stocks,
        top_etfs=top_etfs,
        market_summary=market_summary,
        analysis=analysis,
        upcoming_earnings=upcoming_earnings,
        buy_sell_data=buy_sell_data,
        report_date_start=report_date_start,
        report_date_end=report_date_end,
    )

    # 8. Upload to S3
    report_filename = f"financial_report_{report_date_end.strftime('%Y%m%d')}.pdf"
    s3_key = f"{REPORT_PREFIX}/{report_filename}"

    if not test_mode:
        logger.info("Step 8: Uploading to S3...")
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            ServerSideEncryption="aws:kms",
        )
        logger.info("Uploaded to s3://%s/%s", S3_BUCKET, s3_key)

        # 9. Send email
        if SES_SENDER and SES_RECIPIENTS[0]:
            logger.info("Step 9: Sending email...")
            _send_email(pdf_bytes, report_filename, report_date_end, analysis)

    logger.info("Report complete.")
    return {
        "statusCode": 200,
        "body": json.dumps({
            "report_date": report_date_end.isoformat(),
            "s3_key": s3_key,
            "top_stocks_count": len(top_stocks),
            "top_etfs_count": len(top_etfs),
        }),
    }


def _send_email(pdf_bytes: bytes, filename: str, report_date, analysis: dict):
    ses = boto3.client("ses")
    subject = f"Financial Intelligence Report — {report_date.strftime('%A, %B %d, %Y')}"

    ten_things = analysis.get("ten_things_to_know", [])
    ten_things_html = "".join(
        f"<li><strong>{item['headline']}</strong>: {item['detail']}</li>"
        for item in ten_things
    )

    body_html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 700px; margin: auto;">
    <h2 style="color:#1a3a5c;">Financial Intelligence Report</h2>
    <p style="color:#555;">{report_date.strftime('%A, %B %d, %Y')}</p>
    <h3>10 Things to Know Today</h3>
    <ol>{ten_things_html}</ol>
    <p>Full 20-page PDF report is attached.</p>
    <hr/><p style="color:#999;font-size:12px;">
    Sources: WSJ, Bloomberg, Reuters, MarketWatch, CNBC, Seeking Alpha, Yahoo Finance.
    This is for informational purposes only and not investment advice.
    </p>
    </body></html>
    """

    import base64
    ses.send_raw_email(
        Source=SES_SENDER,
        Destinations=SES_RECIPIENTS,
        RawMessage={
            "Data": _build_mime(SES_SENDER, SES_RECIPIENTS, subject, body_html, pdf_bytes, filename)
        },
    )


def _build_mime(sender, recipients, subject, html_body, pdf_bytes, pdf_filename) -> bytes:
    import email.mime.multipart as mp
    import email.mime.text as mt
    import email.mime.application as ma

    msg = mp.MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    alt = mp.MIMEMultipart("alternative")
    alt.attach(mt.MIMEText(html_body, "html"))
    msg.attach(alt)

    attachment = ma.MIMEApplication(pdf_bytes, Name=pdf_filename)
    attachment["Content-Disposition"] = f'attachment; filename="{pdf_filename}"'
    msg.attach(attachment)

    return msg.as_bytes()
