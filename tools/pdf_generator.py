"""
PDF 리포트 생성 Tool (ReportLab 기반)
analysis.json + raw_data.json을 읽어 FILLZ 브랜드 PDF 리포트를 생성한다.
출력: .tmp/weekly_report_YYYY-MM-DD.pdf
"""

import os
import json
import base64
import io
import datetime
from pathlib import Path
from dotenv import load_dotenv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

load_dotenv()

TOOLS_DIR = Path(__file__).parent
PROJECT_DIR = TOOLS_DIR.parent
TMP_DIR = PROJECT_DIR / ".tmp"
RAW_FILE = TMP_DIR / "raw_data.json"
ANALYSIS_FILE = TMP_DIR / "analysis.json"
LOGO_FILE = PROJECT_DIR / "Fillz Basic Logo_BK.png"

# ── 브랜드 색상 ──
C_BLACK  = colors.HexColor("#111111")
C_NAVY   = colors.HexColor("#1B2A4A")
C_GRAY_D = colors.HexColor("#444444")
C_GRAY_M = colors.HexColor("#888888")
C_GRAY_L = colors.HexColor("#F4F4F4")
C_WHITE  = colors.white
C_BORDER = colors.HexColor("#E0E0E0")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def register_korean_font():
    """macOS 시스템 한국어 폰트 등록"""
    candidates = [
        ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "AppleSDGothicNeo"),
        ("/Library/Fonts/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/System/Library/Fonts/Supplemental/AppleMyungjo.ttf", "AppleMyungjo"),
    ]
    for path, name in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                pdfmetrics.registerFont(TTFont(name + "-Bold", path))
                return name
            except Exception:
                continue
    return "Helvetica"


FONT = register_korean_font()
FONT_BOLD = FONT + "-Bold" if FONT != "Helvetica" else "Helvetica-Bold"


# ── 스타일 팩토리 ──
def S(name, **kw):
    base = {
        "fontName": FONT,
        "fontSize": 10,
        "textColor": C_BLACK,
        "leading": 16,
        "spaceAfter": 0,
    }
    base.update(kw)
    return ParagraphStyle(name, **base)


STYLES = {
    "cover_brand":  S("cb", fontName=FONT_BOLD, fontSize=28, textColor=C_WHITE, leading=34),
    "cover_sub":    S("cs", fontSize=9, textColor=C_GRAY_M, leading=14),
    "cover_date":   S("cd", fontSize=9, textColor=C_GRAY_M),
    "cover_sum":    S("csm", fontSize=11, textColor=colors.HexColor("#CCCCCC"), leading=18),
    "section_lbl":  S("sl", fontName=FONT_BOLD, fontSize=7, textColor=C_GRAY_M, spaceAfter=2*mm),
    "section_ttl":  S("st", fontName=FONT_BOLD, fontSize=16, textColor=C_BLACK, leading=22, spaceAfter=4*mm),
    "body":         S("b", fontSize=9, textColor=C_GRAY_D, leading=15),
    "body_bold":    S("bb", fontName=FONT_BOLD, fontSize=9, textColor=C_BLACK),
    "summary_box":  S("sb", fontSize=10, textColor=C_WHITE, leading=18),
    "table_head":   S("th", fontName=FONT_BOLD, fontSize=8, textColor=C_WHITE),
    "table_cell":   S("tc", fontSize=8, textColor=C_GRAY_D, leading=13),
    "rec_title":    S("rt", fontName=FONT_BOLD, fontSize=11, textColor=C_BLACK),
    "rec_body":     S("rb", fontSize=9, textColor=C_GRAY_D, leading=15),
    "rec_tag":      S("rg", fontName=FONT_BOLD, fontSize=7, textColor=C_WHITE),
    "product_name": S("pn", fontName=FONT_BOLD, fontSize=11, textColor=C_BLACK),
    "product_body": S("pb", fontSize=9, textColor=C_GRAY_D, leading=15),
    "product_opp":  S("po", fontName=FONT_BOLD, fontSize=9, textColor=C_NAVY),
    "insight_box":  S("ib", fontSize=10, textColor=C_WHITE, leading=18),
}


class ColorRect(Flowable):
    """배경색 채운 직사각형 + 내부 Paragraph"""
    def __init__(self, content, bg_color, width, height, padding=5*mm, text_style=None):
        super().__init__()
        self.content = content
        self.bg = bg_color
        self.w = width
        self.h = height
        self.pad = padding
        self.style = text_style or STYLES["body"]

    def draw(self):
        self.canv.setFillColor(self.bg)
        self.canv.rect(0, 0, self.w, self.h, fill=1, stroke=0)
        p = Paragraph(self.content, self.style)
        pw = self.w - 2 * self.pad
        p.wrapOn(self.canv, pw, self.h)
        p.drawOn(self.canv, self.pad, self.pad)

    def wrap(self, aw, ah):
        return self.w, self.h


def fmt_num(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def make_chart_channels(top_channels: list[dict]) -> io.BytesIO:
    """채널별 주간 조회수 가로 막대 차트"""
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NotoSansCJK-Regular.ttc",
    ]
    for fp in candidates:
        if Path(fp).exists():
            fm.fontManager.addfont(fp)
            prop = fm.FontProperties(fname=fp)
            plt.rcParams["font.family"] = prop.get_name()
            break

    channels = top_channels[:8]
    names = [c["channel_title"][:10] for c in channels]
    views = [c["total_views_this_week"] for c in channels]

    fig, ax = plt.subplots(figsize=(9, 3.5), dpi=130)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    bar_colors = ["#1B2A4A" if i == 0 else "#888888" for i in range(len(names))]
    bars = ax.barh(names[::-1], views[::-1], color=bar_colors[::-1], height=0.55)
    max_v = max(views) if views else 1
    for bar, view in zip(bars, views[::-1]):
        ax.text(bar.get_width() + max_v * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{view:,}", va="center", ha="left", fontsize=8, color="#111111")
    ax.set_xlabel("주간 조회수", fontsize=8, color="#888888")
    ax.tick_params(labelsize=8, colors="#111111")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#E0E0E0")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlim(0, max_v * 1.25)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    return buf


# ════════════════════════════════════════
# 커버 페이지 빌더
# ════════════════════════════════════════
def build_cover(story, raw, analysis_data):
    analysis = analysis_data.get("analysis", {})
    collected = raw.get("collected_at", datetime.datetime.utcnow().isoformat())
    date_str = collected[:10]

    usable_w = PAGE_W - 2 * MARGIN

    # 검정 배경 전체 커버 블록
    cover_elements = []

    # 로고
    if LOGO_FILE.exists():
        logo = Image(str(LOGO_FILE), width=40*mm, height=14*mm)
        cover_elements.append(logo)
        cover_elements.append(Spacer(1, 6*mm))

    cover_elements.append(Paragraph("FISHING GEAR · MARKET INTELLIGENCE", STYLES["cover_sub"]))
    cover_elements.append(Spacer(1, 20*mm))
    cover_elements.append(Paragraph("주간 루어낚시", STYLES["cover_sum"]))
    cover_elements.append(Paragraph("트렌드 리포트", STYLES["cover_brand"]))
    cover_elements.append(Spacer(1, 8*mm))
    summary = analysis.get("weekly_summary", "이번 주 트렌드를 분석했습니다.")
    cover_elements.append(Paragraph(summary, STYLES["cover_sum"]))
    cover_elements.append(Spacer(1, 20*mm))
    cover_elements.append(HRFlowable(width=usable_w, color=colors.HexColor("#333333")))
    cover_elements.append(Spacer(1, 4*mm))
    cover_elements.append(Paragraph(f"{date_str}  ·  KR + JP 마켓 분석", STYLES["cover_date"]))

    # 검정 배경 테이블로 커버 효과
    cover_tbl = Table([[cover_elements]], colWidths=[usable_w])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 20*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(cover_tbl)
    story.append(PageBreak())


# ════════════════════════════════════════
# P2: 요약 + 채널 TOP10
# ════════════════════════════════════════
def build_channels_page(story, raw, analysis_data):
    usable_w = PAGE_W - 2 * MARGIN
    analysis = analysis_data.get("analysis", {})
    top_channels = analysis_data.get("top_channels", [])[:10]

    story.append(Paragraph("Executive Summary", STYLES["section_lbl"]))
    story.append(Paragraph("이번 주 요약", STYLES["section_ttl"]))

    summary = analysis.get("weekly_summary", "")
    box = ColorRect(summary, C_NAVY, usable_w, 24*mm, 5*mm, STYLES["summary_box"])
    story.append(box)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("Top Channels", STYLES["section_lbl"]))
    story.append(Paragraph("인기 채널 TOP 10", STYLES["section_ttl"]))

    headers = ["#", "채널명", "국가", "구독자", "주간 조회수", "업로드"]
    col_widths = [10*mm, 55*mm, 14*mm, 28*mm, 28*mm, 18*mm]
    data = [[Paragraph(h, STYLES["table_head"]) for h in headers]]
    for i, ch in enumerate(top_channels, 1):
        country = ch.get("channel_country", "")
        flag = "🇰🇷" if country == "KR" else ("🇯🇵" if country == "JP" else country)
        data.append([
            Paragraph(str(i), STYLES["table_cell"]),
            Paragraph(ch["channel_title"][:20], STYLES["table_cell"]),
            Paragraph(flag, STYLES["table_cell"]),
            Paragraph(fmt_num(ch.get("subscriber_count", 0)), STYLES["table_cell"]),
            Paragraph(fmt_num(ch.get("total_views_this_week", 0)), STYLES["table_cell"]),
            Paragraph(f"{ch.get('video_count_this_week', 0)}편", STYLES["table_cell"]),
        ])

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_BLACK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAY_L]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 4*mm),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
    ]))
    story.append(tbl)
    story.append(PageBreak())


# ════════════════════════════════════════
# P3: 트렌딩 주제 + 키워드 + 포맷
# ════════════════════════════════════════
def build_trends_page(story, raw, analysis_data):
    usable_w = PAGE_W - 2 * MARGIN
    analysis = analysis_data.get("analysis", {})
    top_keywords = analysis_data.get("top_keywords", [])[:15]

    story.append(Paragraph("Trending Keywords", STYLES["section_lbl"]))
    story.append(Paragraph("급상승 키워드", STYLES["section_ttl"]))

    kw_text = "  ·  ".join([
        f"{'<b>' if i < 3 else ''}{k['keyword']}{'</b>' if i < 3 else ''}"
        for i, k in enumerate(top_keywords)
    ])
    story.append(Paragraph(kw_text, STYLES["body"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("Hot Topics", STYLES["section_lbl"]))
    story.append(Paragraph("트렌딩 주제", STYLES["section_ttl"]))

    topics = analysis.get("trending_topics", [])
    topic_col_w = (usable_w - 4*mm) / min(len(topics), 3) if topics else usable_w
    topic_cells = []
    for i, topic in enumerate(topics[:3]):
        cell_content = [
            Paragraph(f"0{i+1}", S("tn", fontName=FONT_BOLD, fontSize=20, textColor=C_GRAY_L, leading=24)),
            Spacer(1, 2*mm),
            Paragraph(topic.get("topic", ""), STYLES["body_bold"]),
            Spacer(1, 1*mm),
            Paragraph(topic.get("reason", ""), STYLES["body"]),
            Spacer(1, 1*mm),
            Paragraph(f"<i>{topic.get('evidence', '')}</i>", S("ev", fontSize=7, textColor=C_GRAY_M, leading=12)),
        ]
        topic_cells.append(cell_content)

    if topic_cells:
        topic_tbl = Table([topic_cells], colWidths=[topic_col_w] * len(topic_cells))
        topic_tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (0, 0), 1, C_BORDER),
            ("BOX", (1, 0), (1, 0), 1, C_BORDER) if len(topic_cells) > 1 else ("", (0, 0), (0, 0), 0, C_WHITE),
            ("BOX", (2, 0), (2, 0), 1, C_BORDER) if len(topic_cells) > 2 else ("", (0, 0), (0, 0), 0, C_WHITE),
            ("TOPPADDING", (0, 0), (-1, -1), 4*mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4*mm),
            ("LEFTPADDING", (0, 0), (-1, -1), 4*mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4*mm),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(topic_tbl)

    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Format Analysis", STYLES["section_lbl"]))
    story.append(Paragraph("잘 되는 포맷 분석", STYLES["section_ttl"]))

    fmt = analysis.get("format_analysis", {})
    fmt_items = [
        ("쇼츠 vs 롱폼", fmt.get("shorts_vs_longform", "—")),
        ("인기 영상 길이", fmt.get("best_performing_length", "—")),
        ("제목 패턴", fmt.get("title_patterns", "—")),
        ("썸네일 패턴", fmt.get("thumbnail_patterns", "—")),
    ]
    half_w = (usable_w - 4*mm) / 2
    fmt_rows = [fmt_items[:2], fmt_items[2:]]
    for row in fmt_rows:
        cells = []
        for label, value in row:
            cells.append([
                Paragraph(label, STYLES["section_lbl"]),
                Paragraph(value, STYLES["body"]),
            ])
        if cells:
            fmt_tbl = Table(cells, colWidths=[half_w, half_w])
            fmt_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), C_GRAY_L),
                ("TOPPADDING", (0, 0), (-1, -1), 3*mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 4*mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4*mm),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(fmt_tbl)
            story.append(Spacer(1, 2*mm))

    story.append(PageBreak())


# ════════════════════════════════════════
# P4: 차트 + 시장 인사이트
# ════════════════════════════════════════
def build_chart_page(story, raw, analysis_data):
    usable_w = PAGE_W - 2 * MARGIN
    analysis = analysis_data.get("analysis", {})
    top_channels = analysis_data.get("top_channels", [])[:8]

    story.append(Paragraph("Channel Performance", STYLES["section_lbl"]))
    story.append(Paragraph("채널별 주간 조회수", STYLES["section_ttl"]))

    if top_channels:
        chart_buf = make_chart_channels(top_channels)
        chart_img = Image(chart_buf, width=usable_w, height=60*mm)
        story.append(chart_img)

    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Market Insight", STYLES["section_lbl"]))
    story.append(Paragraph("시장 인사이트", STYLES["section_ttl"]))

    insight = analysis.get("market_insight", "")
    box = ColorRect(insight, C_NAVY, usable_w, 28*mm, 5*mm, STYLES["insight_box"])
    story.append(box)
    story.append(PageBreak())


# ════════════════════════════════════════
# P5: 추천
# ════════════════════════════════════════
def build_recommendations_page(story, raw, analysis_data):
    usable_w = PAGE_W - 2 * MARGIN
    analysis = analysis_data.get("analysis", {})

    story.append(Paragraph("Content Strategy", STYLES["section_lbl"]))
    story.append(Paragraph("콘텐츠 주제 추천", STYLES["section_ttl"]))

    for rec in analysis.get("content_recommendations", []):
        kw_box = ColorRect(rec.get("target_keyword", ""), C_BLACK, 30*mm, 6*mm, 2*mm, STYLES["rec_tag"])
        story.append(KeepTogether([
            kw_box,
            Spacer(1, 1*mm),
            Paragraph(rec.get("title", ""), STYLES["rec_title"]),
            Paragraph(rec.get("reason", ""), STYLES["rec_body"]),
            Spacer(1, 3*mm),
            HRFlowable(width=usable_w, color=C_BORDER, thickness=0.5),
            Spacer(1, 3*mm),
        ]))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Product Opportunity", STYLES["section_lbl"]))
    story.append(Paragraph("제품 추천", STYLES["section_ttl"]))

    for i, rec in enumerate(analysis.get("product_recommendations", []), 1):
        num_cell = Paragraph(f"0{i}", S(f"pnum{i}", fontName=FONT_BOLD, fontSize=22, textColor=C_GRAY_L, leading=28))
        content_cell = [
            Paragraph(rec.get("product", ""), STYLES["product_name"]),
            Paragraph(rec.get("reason", ""), STYLES["product_body"]),
            Paragraph(f"→ {rec.get('opportunity', '')}", STYLES["product_opp"]),
        ]
        prod_tbl = Table([[num_cell, content_cell]], colWidths=[15*mm, usable_w - 15*mm])
        prod_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3*mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, C_BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(prod_tbl)

    story.append(PageBreak())


# ════════════════════════════════════════
# P6: TOP 20 영상 목록
# ════════════════════════════════════════
def build_videos_page(story, raw, analysis_data):
    usable_w = PAGE_W - 2 * MARGIN
    videos = raw.get("videos", [])[:20]

    story.append(Paragraph("Video Ranking", STYLES["section_lbl"]))
    story.append(Paragraph("급상승 영상 TOP 20", STYLES["section_ttl"]))

    headers = ["#", "영상 제목", "채널", "조회수", "참여율"]
    col_widths = [10*mm, 80*mm, 35*mm, 22*mm, 16*mm]
    data = [[Paragraph(h, STYLES["table_head"]) for h in headers]]

    for i, v in enumerate(videos, 1):
        country = v.get("channel_country", "")
        flag = "🇰🇷" if country == "KR" else ("🇯🇵" if country == "JP" else "")
        title = v.get("title", "")[:40]
        shorts_mark = " #S" if v.get("is_short") else ""
        data.append([
            Paragraph(str(i), STYLES["table_cell"]),
            Paragraph(title + shorts_mark, STYLES["table_cell"]),
            Paragraph(f"{flag} {v.get('channel_title', '')[:14]}", STYLES["table_cell"]),
            Paragraph(fmt_num(v.get("view_count", 0)), STYLES["table_cell"]),
            Paragraph(f"{v.get('engagement_rate', 0)}%", STYLES["table_cell"]),
        ])

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_BLACK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAY_L]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3*mm),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)


# ════════════════════════════════════════
# 헤더/푸터 콜백
# ════════════════════════════════════════
def make_on_page(date_str):
    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            canvas.restoreState()
            return
        # 헤더
        canvas.setFillColor(C_BLACK)
        canvas.setFont(FONT_BOLD, 7)
        canvas.drawString(MARGIN, PAGE_H - 12*mm, "FILLZ · WEEKLY TREND REPORT")
        canvas.setFont(FONT, 7)
        canvas.setFillColor(C_GRAY_M)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 12*mm, date_str)
        canvas.setStrokeColor(C_BLACK)
        canvas.setLineWidth(1)
        canvas.line(MARGIN, PAGE_H - 13*mm, PAGE_W - MARGIN, PAGE_H - 13*mm)
        # 푸터
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 10*mm, PAGE_W - MARGIN, 10*mm)
        canvas.setFont(FONT, 7)
        canvas.setFillColor(C_GRAY_M)
        canvas.drawString(MARGIN, 7*mm, "FILLZ FISHING GEAR — 주간 트렌드 리포트")
        canvas.drawRightString(PAGE_W - MARGIN, 7*mm, f"{date_str}  |  기밀 문서")
        canvas.restoreState()
    return on_page


def main():
    if not RAW_FILE.exists():
        print(f"[오류] {RAW_FILE} 없음.")
        return
    if not ANALYSIS_FILE.exists():
        print(f"[오류] {ANALYSIS_FILE} 없음.")
        return

    TMP_DIR.mkdir(exist_ok=True)
    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    analysis_data = json.loads(ANALYSIS_FILE.read_text(encoding="utf-8"))

    collected = raw.get("collected_at", datetime.datetime.utcnow().isoformat())
    date_str = collected[:10]
    output_file = TMP_DIR / f"weekly_report_{date_str}.pdf"

    print(f"PDF 생성 중 ({date_str})...")

    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16*mm, bottomMargin=16*mm,
        title=f"FILLZ 주간 루어낚시 트렌드 리포트 {date_str}",
        author="FILLZ FISHING GEAR",
    )

    story = []
    build_cover(story, raw, analysis_data)
    build_channels_page(story, raw, analysis_data)
    build_trends_page(story, raw, analysis_data)
    build_chart_page(story, raw, analysis_data)
    build_recommendations_page(story, raw, analysis_data)
    build_videos_page(story, raw, analysis_data)

    doc.build(story, onFirstPage=make_on_page(date_str), onLaterPages=make_on_page(date_str))

    size_kb = output_file.stat().st_size // 1024
    print(f"완료. 저장: {output_file} ({size_kb} KB)")


if __name__ == "__main__":
    main()
