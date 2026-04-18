"""
ReportLab styles and page canvas for the financial report.
"""
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics

BRAND_NAVY = colors.HexColor("#1a3a5c")
BRAND_GOLD = colors.HexColor("#c9a227")
BRAND_GREEN = colors.HexColor("#2d6a4f")
BRAND_RED = colors.HexColor("#c1121f")
BRAND_LIGHT = colors.HexColor("#f0f4f8")
BRAND_MID = colors.HexColor("#4a6fa5")
BRAND_GRAY = colors.HexColor("#6b7280")


class ReportStyles:
    def __init__(self):
        self.title = ParagraphStyle(
            "Title",
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=BRAND_NAVY,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        self.subtitle = ParagraphStyle(
            "Subtitle",
            fontName="Helvetica",
            fontSize=13,
            textColor=BRAND_MID,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
        self.cover_headline = ParagraphStyle(
            "CoverHeadline",
            fontName="Helvetica-BoldOblique",
            fontSize=13,
            textColor=BRAND_NAVY,
            alignment=TA_CENTER,
            leading=18,
        )
        self.section_header = ParagraphStyle(
            "SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=colors.white,
            backColor=BRAND_NAVY,
            alignment=TA_LEFT,
            leftIndent=6,
            spaceAfter=4,
            spaceBefore=8,
            leading=20,
        )
        self.subheader = ParagraphStyle(
            "Subheader",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=BRAND_NAVY,
            spaceAfter=2,
            spaceBefore=4,
        )
        self.section_label = ParagraphStyle(
            "SectionLabel",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BRAND_MID,
            spaceAfter=4,
            spaceBefore=6,
        )
        self.section_label_green = ParagraphStyle(
            "SectionLabelGreen",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BRAND_GREEN,
            spaceAfter=4,
            spaceBefore=6,
        )
        self.section_label_red = ParagraphStyle(
            "SectionLabelRed",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BRAND_RED,
            spaceAfter=4,
            spaceBefore=6,
        )
        self.body = ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            spaceAfter=3,
            leading=13,
        )
        self.body_justified = ParagraphStyle(
            "BodyJustified",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_JUSTIFY,
            spaceAfter=3,
            leading=13,
        )
        self.body_small = ParagraphStyle(
            "BodySmall",
            fontName="Helvetica",
            fontSize=8,
            textColor=BRAND_GRAY,
            spaceAfter=2,
            leading=11,
        )
        self.bullet = ParagraphStyle(
            "Bullet",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            leftIndent=12,
            spaceAfter=2,
        )
        self.number_badge = ParagraphStyle(
            "NumberBadge",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=BRAND_NAVY,
            alignment=TA_CENTER,
        )
        self.disclaimer = ParagraphStyle(
            "Disclaimer",
            fontName="Helvetica-Oblique",
            fontSize=7,
            textColor=BRAND_GRAY,
            alignment=TA_JUSTIFY,
            leading=10,
        )


def header_footer_canvas(canvas, doc, report_date: date):
    canvas.saveState()
    width, height = doc.pagesize

    # Header bar
    canvas.setFillColor(BRAND_NAVY)
    canvas.rect(0, height - 0.55 * inch, width, 0.55 * inch, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(0.6 * inch, height - 0.35 * inch, "FINANCIAL INTELLIGENCE REPORT")

    canvas.setFont("Helvetica", 9)
    date_str = report_date.strftime("%B %d, %Y")
    canvas.drawRightString(width - 0.6 * inch, height - 0.35 * inch, date_str)

    # Gold accent line
    canvas.setStrokeColor(BRAND_GOLD)
    canvas.setLineWidth(2)
    canvas.line(0, height - 0.57 * inch, width, height - 0.57 * inch)

    # Footer
    canvas.setFillColor(BRAND_LIGHT)
    canvas.rect(0, 0, width, 0.5 * inch, fill=1, stroke=0)
    canvas.setFillColor(BRAND_GRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        0.6 * inch, 0.18 * inch,
        "For informational purposes only. Not investment advice. Sources: WSJ, Bloomberg, Reuters, MarketWatch, CNBC, Seeking Alpha, FT, Barron's.",
    )
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawRightString(width - 0.6 * inch, 0.18 * inch, f"Page {doc.page}")

    canvas.restoreState()
