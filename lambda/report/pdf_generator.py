"""
PDF report generator using ReportLab.
Produces a professional 15-20 page financial intelligence report.
"""
import io
import logging
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, PageBreak, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable

from report.templates import ReportStyles, header_footer_canvas

logger = logging.getLogger(__name__)

BRAND_NAVY = colors.HexColor("#1a3a5c")
BRAND_GOLD = colors.HexColor("#c9a227")
BRAND_GREEN = colors.HexColor("#2d6a4f")
BRAND_RED = colors.HexColor("#c1121f")
BRAND_LIGHT = colors.HexColor("#f0f4f8")
BRAND_MID = colors.HexColor("#4a6fa5")


class PDFReportGenerator:
    def generate(
        self,
        top_stocks: list[dict],
        top_etfs: list[dict],
        market_summary: dict,
        analysis: dict,
        upcoming_earnings: list[dict],
        buy_sell_data: dict,
        report_date_start: date,
        report_date_end: date,
    ) -> bytes:
        buf = io.BytesIO()
        styles = ReportStyles()

        doc = BaseDocTemplate(
            buf,
            pagesize=letter,
            rightMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            topMargin=0.9 * inch,
            bottomMargin=0.7 * inch,
        )

        # Page template with header/footer
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id="main",
        )
        template = PageTemplate(
            id="main",
            frames=[frame],
            onPage=lambda canvas, doc: header_footer_canvas(canvas, doc, report_date_end),
        )
        doc.addPageTemplates([template])

        story = []

        # Cover page
        story.extend(self._cover_page(styles, report_date_start, report_date_end, analysis, market_summary))
        story.append(PageBreak())

        # Market Overview
        story.extend(self._market_overview_section(styles, market_summary, analysis))
        story.append(PageBreak())

        # 10 Things to Know
        story.extend(self._ten_things_section(styles, analysis.get("ten_things_to_know", [])))
        story.append(PageBreak())

        # Top 50 Stocks
        story.extend(self._movers_table_section(styles, top_stocks, "Top 50 Performing Stocks", "stock"))
        story.append(PageBreak())

        # Stock Analysis (AI narrative)
        story.extend(self._ai_narrative_section(
            styles, analysis.get("stock_analysis", []), top_stocks, "Stock Performance Analysis"
        ))
        story.append(PageBreak())

        # Top 50 ETFs
        story.extend(self._movers_table_section(styles, top_etfs, "Top 50 Performing ETFs", "etf"))
        story.append(PageBreak())

        # ETF Analysis
        story.extend(self._ai_narrative_section(
            styles, analysis.get("etf_analysis", []), top_etfs, "ETF Performance Analysis"
        ))
        story.append(PageBreak())

        # Buy/Sell Signals
        story.extend(self._buy_sell_section(styles, buy_sell_data, analysis.get("buy_sell_commentary", {})))
        story.append(PageBreak())

        # Earnings Calendar
        story.extend(self._earnings_section(styles, upcoming_earnings, analysis.get("earnings_preview", {})))
        story.append(PageBreak())

        # Recommendations
        story.extend(self._recommendations_section(styles, analysis, buy_sell_data, top_stocks, top_etfs))

        doc.build(story)
        return buf.getvalue()

    # ─── Cover Page ─────────────────────────────────────────────────────────────
    def _cover_page(self, styles, start_date, end_date, analysis, market_summary):
        story = []
        story.append(Spacer(1, 0.8 * inch))

        story.append(Paragraph("FINANCIAL INTELLIGENCE REPORT", styles.title))
        story.append(Spacer(1, 0.15 * inch))

        if start_date != end_date:
            date_str = f"{start_date.strftime('%B %d')} – {end_date.strftime('%B %d, %Y')}"
        else:
            date_str = end_date.strftime("%A, %B %d, %Y")
        story.append(Paragraph(date_str, styles.subtitle))
        story.append(Spacer(1, 0.2 * inch))
        story.append(HRFlowable(width="100%", thickness=3, color=BRAND_GOLD))
        story.append(Spacer(1, 0.3 * inch))

        # Market overview headline
        overview = analysis.get("market_overview", {})
        headline = overview.get("headline", "Daily financial intelligence briefing")
        story.append(Paragraph(headline, styles.cover_headline))
        story.append(Spacer(1, 0.3 * inch))

        # Market snapshot table
        if market_summary:
            story.extend(self._mini_market_table(styles, market_summary))

        story.append(Spacer(1, 0.3 * inch))

        # Key themes
        themes = overview.get("key_themes", [])
        if themes:
            story.append(Paragraph("KEY THEMES", styles.section_label))
            theme_text = "  •  ".join(themes)
            story.append(Paragraph(theme_text, styles.body))

        story.append(Spacer(1, 0.4 * inch))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_MID))
        story.append(Spacer(1, 0.1 * inch))

        disclaimer = (
            "This report is for informational purposes only and does not constitute investment advice. "
            "Sources: WSJ, Bloomberg, Reuters, MarketWatch, CNBC, Seeking Alpha, Yahoo Finance, FT, Barron's. "
            "Past performance is not indicative of future results."
        )
        story.append(Paragraph(disclaimer, styles.disclaimer))

        return story

    def _mini_market_table(self, styles, market_summary):
        key_indices = ["S&P 500", "Nasdaq 100", "Dow Jones", "Russell 2000", "VIX", "10Y Treasury", "Gold", "Bitcoin"]
        rows = [["Index / Asset", "Value", "Change"]]
        for name in key_indices:
            if name in market_summary:
                d = market_summary[name]
                chg = d.get("change_pct", 0)
                chg_str = f"{chg:+.2f}%"
                rows.append([name, f"{d['value']:,.2f}", chg_str])

        if len(rows) < 2:
            return []

        t = Table(rows, colWidths=[2.8 * inch, 1.5 * inch, 1.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        # Color change cells
        for i, name in enumerate(key_indices):
            if name in market_summary:
                chg = market_summary[name].get("change_pct", 0)
                row_idx = i + 1
                color = BRAND_GREEN if chg >= 0 else BRAND_RED
                t.setStyle(TableStyle([("TEXTCOLOR", (2, row_idx), (2, row_idx), color)]))

        return [t]

    # ─── Market Overview ────────────────────────────────────────────────────────
    def _market_overview_section(self, styles, market_summary, analysis):
        story = [Paragraph("MARKET OVERVIEW", styles.section_header), Spacer(1, 0.1 * inch)]
        overview = analysis.get("market_overview", {})

        mood = overview.get("market_mood", "Mixed")
        mood_color = BRAND_GREEN if mood == "Bullish" else (BRAND_RED if mood == "Bearish" else BRAND_MID)
        story.append(Paragraph(f'Market Mood: <font color="#{mood_color.hexval()}">{mood}</font>', styles.subheader))
        story.append(Spacer(1, 0.08 * inch))

        overview_text = overview.get("overview", "")
        if overview_text:
            story.append(Paragraph(overview_text, styles.body_justified))
        story.append(Spacer(1, 0.15 * inch))

        # Full market table
        story.extend(self._full_market_table(styles, market_summary))

        drivers = overview.get("major_drivers", [])
        if drivers:
            story.append(Spacer(1, 0.15 * inch))
            story.append(Paragraph("MAJOR MARKET DRIVERS", styles.section_label))
            for d in drivers:
                story.append(Paragraph(f"• {d}", styles.bullet))

        return story

    def _full_market_table(self, styles, market_summary):
        if not market_summary:
            return []
        rows = [["Asset / Index", "Last Price", "Period Change", "Ticker"]]
        for name, d in market_summary.items():
            chg = d.get("change_pct", 0)
            rows.append([name, f"{d['value']:,.2f}", f"{chg:+.2f}%", d.get("ticker", "")])

        t = Table(rows, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch, 1.2 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        for i, (name, d) in enumerate(market_summary.items()):
            chg = d.get("change_pct", 0)
            color = BRAND_GREEN if chg >= 0 else BRAND_RED
            t.setStyle(TableStyle([("TEXTCOLOR", (2, i + 1), (2, i + 1), color)]))
        return [t]

    # ─── 10 Things ──────────────────────────────────────────────────────────────
    def _ten_things_section(self, styles, ten_things):
        story = [Paragraph("10 THINGS TO KNOW TODAY", styles.section_header), Spacer(1, 0.1 * inch)]

        CATEGORY_COLORS = {
            "Markets": BRAND_NAVY, "Stocks": BRAND_MID, "ETFs": BRAND_GREEN,
            "Macro": colors.HexColor("#6a0572"), "Earnings": BRAND_GOLD,
            "Technical": colors.HexColor("#2b6cb0"), "Sector": colors.HexColor("#276749"),
            "Global": colors.HexColor("#744210"), "Crypto": colors.HexColor("#1a202c"),
            "Commodities": colors.HexColor("#7b341e"),
        }

        for item in ten_things:
            num = item.get("number", "")
            headline = item.get("headline", "")
            detail = item.get("detail", "")
            category = item.get("category", "Markets")
            cat_color = CATEGORY_COLORS.get(category, BRAND_NAVY)

            # Number + headline in a colored block
            row = [[
                Paragraph(f"<b>{num}</b>", styles.number_badge),
                Paragraph(
                    f'<font color="#{cat_color.hexval()}"><b>{headline}</b></font><br/>'
                    f'<font size="9">{detail}</font>',
                    styles.body,
                ),
            ]]
            t = Table(row, colWidths=[0.4 * inch, 6.5 * inch])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(KeepTogether([t, Spacer(1, 0.05 * inch)]))

        return story

    # ─── Top Movers Table ───────────────────────────────────────────────────────
    def _movers_table_section(self, styles, movers, title, asset_type):
        story = [Paragraph(title.upper(), styles.section_header), Spacer(1, 0.1 * inch)]

        if not movers:
            story.append(Paragraph("No data available.", styles.body))
            return story

        # Split into two tables of 25 each for readability
        for chunk_start in range(0, min(50, len(movers)), 25):
            chunk = movers[chunk_start:chunk_start + 25]
            label = f"Rank {chunk_start + 1}–{chunk_start + len(chunk)}"
            story.append(Paragraph(label, styles.section_label))
            story.append(self._movers_table(chunk, chunk_start, styles))
            story.append(Spacer(1, 0.2 * inch))

        return story

    def _movers_table(self, movers, offset, styles):
        headers = ["#", "Symbol", "Name", "Sector", "Change", "Price", "Mkt Cap"]
        rows = [headers]
        for i, m in enumerate(movers):
            cap = m.get("market_cap")
            cap_str = f"${cap/1e9:.1f}B" if cap and cap > 1e9 else (f"${cap/1e6:.0f}M" if cap else "N/A")
            name = (m.get("name") or m["symbol"])[:22]
            sector = (m.get("sector") or "N/A")[:14]
            rows.append([
                str(offset + i + 1),
                m["symbol"],
                name,
                sector,
                f"{m['pct_change']:+.2f}%",
                f"${m['close_price']:,.2f}" if m.get("close_price") else "N/A",
                cap_str,
            ])

        col_widths = [0.3 * inch, 0.7 * inch, 1.9 * inch, 1.2 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch]
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        for i, m in enumerate(movers):
            chg = m["pct_change"]
            color = BRAND_GREEN if chg >= 0 else BRAND_RED
            t.setStyle(TableStyle([("TEXTCOLOR", (4, i + 1), (4, i + 1), color)]))
        return t

    # ─── AI Narrative ───────────────────────────────────────────────────────────
    def _ai_narrative_section(self, styles, ai_items, all_movers, title):
        story = [Paragraph(title.upper(), styles.section_header), Spacer(1, 0.1 * inch)]

        # Map AI analysis back to mover details
        mover_map = {m["symbol"]: m for m in all_movers}
        analyzed_syms = {item["symbol"] for item in ai_items}

        # For symbols not in AI analysis, show brief stats
        for item in ai_items:
            sym = item.get("symbol", "")
            mover = mover_map.get(sym, {})
            name = mover.get("name", sym)
            chg = mover.get("pct_change", 0)
            outlook = item.get("outlook", "Neutral")
            outlook_color = BRAND_GREEN if outlook == "Positive" else (BRAND_RED if outlook == "Cautious" else BRAND_MID)

            block = [
                Paragraph(
                    f'<b>{sym}</b> — {name} '
                    f'<font color="#{(BRAND_GREEN if chg >= 0 else BRAND_RED).hexval()}">{chg:+.2f}%</font>  '
                    f'<font color="#{outlook_color.hexval()}">({outlook})</font>',
                    styles.subheader,
                ),
                Spacer(1, 0.04 * inch),
            ]

            why = item.get("why_performed", "")
            if why:
                block.append(Paragraph(f"<b>Performance:</b> {why}", styles.body_justified))

            catalysts = item.get("catalysts", [])
            if catalysts:
                block.append(Paragraph(f"<b>Catalysts:</b> {' | '.join(catalysts)}", styles.body))

            prospects = item.get("future_prospects", "")
            if prospects:
                block.append(Paragraph(f"<b>Prospects:</b> {prospects}", styles.body_justified))

            risks = item.get("risk_factors", [])
            if risks:
                block.append(Paragraph(f"<b>Risks:</b> {' | '.join(risks)}", styles.body_small))

            block.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            block.append(Spacer(1, 0.08 * inch))
            story.append(KeepTogether(block))

        return story

    # ─── Buy / Sell Signals ─────────────────────────────────────────────────────
    def _buy_sell_section(self, styles, buy_sell_data, commentary):
        story = [Paragraph("BUY & SELL SIGNALS — TECHNICAL ANALYSIS", styles.section_header), Spacer(1, 0.1 * inch)]

        # Commentary
        buy_text = commentary.get("buy_commentary", "")
        sell_text = commentary.get("sell_commentary", "")
        strategy = commentary.get("strategy_note", "")
        if buy_text:
            story.append(Paragraph(f"<b>Buy Opportunities:</b> {buy_text}", styles.body_justified))
        if sell_text:
            story.append(Paragraph(f"<b>Sell / Take-Profit:</b> {sell_text}", styles.body_justified))
        if strategy:
            story.append(Paragraph(f"<b>Strategy Note:</b> {strategy}", styles.body))
        story.append(Spacer(1, 0.15 * inch))

        # Buy table
        story.append(Paragraph("STOCKS/ETFs REACHING BUY POINTS", styles.section_label_green))
        story.append(self._signal_table(buy_sell_data.get("buy", []), "buy", styles))
        story.append(Spacer(1, 0.2 * inch))

        # Sell table
        story.append(Paragraph("STOCKS/ETFs REACHING SELL POINTS", styles.section_label_red))
        story.append(self._signal_table(buy_sell_data.get("sell", []), "sell", styles))

        disclaimer = commentary.get("disclaimer", "Technical analysis signals are not investment advice.")
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"⚠ {disclaimer}", styles.disclaimer))

        return story

    def _signal_table(self, signals, signal_type, styles):
        if not signals:
            return Paragraph("No signals identified.", styles.body)

        headers = ["Symbol", "Name", "Change", "RSI", "Price", "Key Signal"]
        rows = [headers]
        for s in signals[:20]:
            sig_list = s.get("signals", [])
            top_signal = sig_list[0] if sig_list else "Technical"
            name = (s.get("name") or s["symbol"])[:20]
            rows.append([
                s["symbol"],
                name,
                f"{s.get('pct_change', 0):+.2f}%",
                str(s.get("signals_detail", {}).get("rsi", s.get("rsi", "N/A"))),
                f"${s.get('close_price', 0):,.2f}" if s.get("close_price") else "N/A",
                top_signal[:40],
            ])

        col_widths = [0.7 * inch, 1.5 * inch, 0.7 * inch, 0.5 * inch, 0.7 * inch, 2.8 * inch]
        t = Table(rows, colWidths=col_widths)
        hdr_color = BRAND_GREEN if signal_type == "buy" else BRAND_RED
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), hdr_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ALIGN", (2, 0), (4, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    # ─── Earnings ───────────────────────────────────────────────────────────────
    def _earnings_section(self, styles, upcoming_earnings, preview):
        story = [Paragraph("EARNINGS CALENDAR — THIS WEEK & NEXT", styles.section_header), Spacer(1, 0.1 * inch)]

        commentary = preview.get("commentary", "")
        if commentary:
            story.append(Paragraph(commentary, styles.body_justified))
            story.append(Spacer(1, 0.1 * inch))

        if not upcoming_earnings:
            story.append(Paragraph("No upcoming earnings data available.", styles.body))
            return story

        # Group by week
        from datetime import date as date_type
        today = date_type.today()
        week_end = today + __import__("datetime").timedelta(days=6 - today.weekday())

        this_week = [e for e in upcoming_earnings if e.get("date", "") <= week_end.isoformat()]
        next_week = [e for e in upcoming_earnings if e.get("date", "") > week_end.isoformat()]

        for week_label, week_data in [("THIS WEEK", this_week), ("NEXT WEEK", next_week)]:
            if not week_data:
                continue
            story.append(Paragraph(week_label, styles.section_label))
            headers = ["Symbol", "Date", "Time", "EPS Estimate", "Rev. Estimate"]
            rows = [headers]
            for e in week_data[:25]:
                eps = e.get("eps_estimate")
                rev = e.get("revenue_estimate")
                rows.append([
                    e.get("symbol", ""),
                    e.get("date", ""),
                    e.get("time", "").upper() or "N/A",
                    f"${eps:.2f}" if eps is not None else "N/A",
                    f"${rev/1e9:.2f}B" if rev and rev > 1e9 else (f"${rev/1e6:.0f}M" if rev else "N/A"),
                ])
            t = Table(rows, colWidths=[1 * inch, 1.1 * inch, 0.6 * inch, 1.2 * inch, 1.5 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2 * inch))

        # Highlights
        highlights = preview.get("highlights", [])
        if highlights:
            story.append(Paragraph("EARNINGS HIGHLIGHTS TO WATCH", styles.section_label))
            for h in highlights[:8]:
                sym = h.get("symbol", "")
                d = h.get("date", "")
                time_str = h.get("time", "").upper()
                what = h.get("what_to_watch", "")
                consensus = h.get("consensus_view", "")
                story.append(Paragraph(
                    f"<b>{sym}</b> ({d} {time_str}) — {what}",
                    styles.subheader,
                ))
                if consensus:
                    story.append(Paragraph(consensus, styles.body))
                story.append(Spacer(1, 0.05 * inch))

        return story

    # ─── Recommendations ────────────────────────────────────────────────────────
    def _recommendations_section(self, styles, analysis, buy_sell_data, top_stocks, top_etfs):
        story = [Paragraph("RECOMMENDATIONS FOR TODAY", styles.section_header), Spacer(1, 0.1 * inch)]

        bs_comment = analysis.get("buy_sell_commentary", {})
        strategy = bs_comment.get("strategy_note", "")
        if strategy:
            story.append(Paragraph(f"<b>Today's Strategy Note:</b> {strategy}", styles.body_justified))
            story.append(Spacer(1, 0.1 * inch))

        # Top buy recommendations
        story.append(Paragraph("TOP BUY CANDIDATES", styles.section_label_green))
        for item in buy_sell_data.get("buy", [])[:10]:
            sym = item["symbol"]
            name = item.get("name", sym)
            chg = item.get("pct_change", 0)
            signals = item.get("signals", [])
            sig_text = " | ".join(signals[:3])
            story.append(Paragraph(
                f"<b>{sym}</b> ({name}) — <font color='#{BRAND_GREEN.hexval()}'>{chg:+.2f}%</font>",
                styles.subheader,
            ))
            story.append(Paragraph(f"Technical triggers: {sig_text}", styles.body_small))
            story.append(Spacer(1, 0.05 * inch))

        story.append(Spacer(1, 0.1 * inch))

        # Top sell recommendations
        story.append(Paragraph("TAKE-PROFIT / SELL CANDIDATES", styles.section_label_red))
        for item in buy_sell_data.get("sell", [])[:10]:
            sym = item["symbol"]
            name = item.get("name", sym)
            chg = item.get("pct_change", 0)
            signals = item.get("signals", [])
            sig_text = " | ".join(signals[:3])
            story.append(Paragraph(
                f"<b>{sym}</b> ({name}) — <font color='#{BRAND_RED.hexval()}'>{chg:+.2f}%</font>",
                styles.subheader,
            ))
            story.append(Paragraph(f"Technical triggers: {sig_text}", styles.body_small))
            story.append(Spacer(1, 0.05 * inch))

        story.append(Spacer(1, 0.2 * inch))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_MID))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            "DISCLAIMER: This report is generated by an AI system using publicly available financial data and news. "
            "It is for informational purposes only and does not constitute investment advice. "
            "Always consult a qualified financial advisor before making investment decisions. "
            "Past performance is not indicative of future results.",
            styles.disclaimer,
        ))

        return story
