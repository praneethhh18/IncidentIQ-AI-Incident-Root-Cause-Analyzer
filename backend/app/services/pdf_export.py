"""Polished PDF post-mortem report generator.

Built on ReportLab (pure Python — no system dependencies). The output is
intentionally minimal but on-brand: dark accent bar, monospaced evidence
blocks, clearly grouped sections. Drops cleanly into Confluence / Notion.
"""

from __future__ import annotations

from io import BytesIO
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import AnalyzeResponse, Severity

BRAND = colors.HexColor("#6366F1")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
SUBTLE = colors.HexColor("#E2E8F0")

SEVERITY_COLORS = {
    Severity.P1: colors.HexColor("#DC2626"),
    Severity.P2: colors.HexColor("#F59E0B"),
    Severity.P3: colors.HexColor("#10B981"),
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=BRAND,
            spaceBefore=14,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=INK,
            spaceAfter=4,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            textColor=INK,
            leftIndent=8,
            backColor=colors.HexColor("#F1F5F9"),
            borderPadding=6,
            spaceAfter=4,
        ),
    }


def render_pdf(analysis: AnalyzeResponse) -> bytes:
    """Render an AnalyzeResponse into a polished PDF and return the bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"IncidentIQ — {analysis.incident_id}",
        author="IncidentIQ",
    )
    styles = _styles()
    story = []

    story.append(_header(analysis, styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Executive summary", styles["h2"]))
    story.append(Paragraph(_escape(analysis.summary), styles["body"]))

    story.append(Paragraph("Root cause", styles["h2"]))
    story.append(Paragraph(_escape(analysis.root_cause), styles["body"]))
    story.append(
        Paragraph(
            f"Model confidence: <b>{int(analysis.confidence * 100)}%</b> · "
            f"Severity: <b>{analysis.severity.value}</b> · "
            f"Model: {analysis.model}",
            styles["muted"],
        )
    )
    story.append(Paragraph(_escape(analysis.severity_rationale), styles["body"]))

    if analysis.affected_services:
        story.append(Paragraph("Affected services", styles["h2"]))
        story.append(_services_table(analysis, styles))

    if analysis.timeline:
        story.append(Paragraph("Incident timeline", styles["h2"]))
        story.append(_timeline_table(analysis, styles))

    if analysis.fixes:
        story.append(Paragraph("Fix recommendations", styles["h2"]))
        for fix in sorted(analysis.fixes, key=lambda f: f.priority):
            story.append(
                Paragraph(
                    f"<b>#{fix.priority} · {_escape(fix.title)}</b>",
                    styles["body"],
                )
            )
            story.append(Paragraph(_escape(fix.rationale), styles["muted"]))
            story.append(Paragraph(f"<i>Action:</i> {_escape(fix.action)}", styles["body"]))
            if fix.snippet:
                story.append(Paragraph(_escape_pre(fix.snippet), styles["mono"]))
            story.append(Spacer(1, 4))

    if analysis.evidence:
        story.append(Paragraph("Supporting evidence (raw log lines)", styles["h2"]))
        for line in analysis.evidence:
            story.append(Paragraph(_escape_pre(line), styles["mono"]))

    if analysis.forensic:
        story.append(Paragraph("Forensic report", styles["h2"]))
        f = analysis.forensic
        story.append(
            Paragraph(
                f"<b>Patient zero</b> ({f.patient_zero.timestamp.strftime('%H:%M:%S')}, "
                f"{f.patient_zero.severity.value}): {_escape(f.patient_zero.label)}",
                styles["body"],
            )
        )
        story.append(Paragraph(_escape(f.patient_zero.detail), styles["muted"]))
        if f.propagation_path:
            story.append(
                Paragraph(
                    f"<b>Propagation path:</b> {_escape(' &rarr; '.join(f.propagation_path))}",
                    styles["body"],
                )
            )
        if f.blast_radius:
            story.append(
                Paragraph(
                    f"<b>Blast radius ({len(f.blast_radius)} entities):</b>",
                    styles["body"],
                )
            )
            for entity in f.blast_radius:
                sev = entity.severity.value if entity.severity else "—"
                story.append(
                    Paragraph(
                        f"&bull; [{_escape(entity.kind)}] <b>{_escape(entity.name)}</b> "
                        f"({sev}) — {_escape(entity.impact)}",
                        styles["muted"],
                    )
                )
        story.append(
            Paragraph(
                f"<b>Trigger hypothesis</b> "
                f"({int(f.trigger_confidence * 100)}% confidence): "
                f"{_escape(f.trigger_hypothesis)}",
                styles["body"],
            )
        )
        if f.minutes_to_detection is not None:
            story.append(
                Paragraph(
                    f"<b>Mean time to detection (MTTD):</b> {f.minutes_to_detection} minutes",
                    styles["muted"],
                )
            )

    if analysis.agent_steps:
        story.append(Paragraph("Agent reasoning trail", styles["h2"]))
        for step in analysis.agent_steps:
            label = f"#{step.step:02d} · {step.kind.upper()}"
            tool_suffix = f" · {step.tool}()" if step.tool else ""
            story.append(
                Paragraph(
                    f"<b>{_escape(label)}{_escape(tool_suffix)} — {_escape(step.title)}</b>",
                    styles["body"],
                )
            )
            story.append(Paragraph(_escape(step.detail), styles["muted"]))
            story.append(Spacer(1, 2))

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Generated by IncidentIQ · "
            f"{analysis.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            styles["muted"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _header(analysis: AnalyzeResponse, styles: dict[str, ParagraphStyle]) -> Table:
    sev_color = SEVERITY_COLORS.get(analysis.severity, BRAND)
    data: List[List[object]] = [
        [
            Paragraph(
                f"<font color='#94A3B8'>INCIDENT</font> <b>{analysis.incident_id}</b>"
                f"  ·  <font color='#94A3B8'>SOURCE</font> {analysis.source.value.upper()}",
                styles["muted"],
            ),
            Paragraph(
                f"<font color='white'><b>{analysis.severity.value}</b></font>",
                ParagraphStyle(
                    "sev",
                    parent=styles["body"],
                    fontSize=11,
                    leading=14,
                    alignment=2,
                    textColor=colors.white,
                ),
            ),
        ],
        [
            Paragraph(_escape(analysis.title), styles["h1"]),
            "",
        ],
    ]
    table = Table(data, colWidths=[5.8 * inch, 1.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (1, 0), (1, 0), sev_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("SPAN", (0, 1), (1, 1)),
                ("LINEBELOW", (0, 1), (-1, 1), 1, SUBTLE),
            ]
        )
    )
    return table


def _services_table(analysis: AnalyzeResponse, styles: dict[str, ParagraphStyle]) -> Table:
    header = [
        Paragraph("<b>Service</b>", styles["body"]),
        Paragraph("<b>Role</b>", styles["body"]),
        Paragraph("<b>Health</b>", styles["body"]),
        Paragraph("<b>Impact</b>", styles["body"]),
    ]
    rows = [header]
    for service in analysis.affected_services:
        rows.append(
            [
                Paragraph(_escape(service.name), styles["body"]),
                Paragraph(_escape(service.role), styles["muted"]),
                Paragraph(_escape(service.health), styles["muted"]),
                Paragraph(_escape(service.impact), styles["body"]),
            ]
        )
    table = Table(
        rows,
        colWidths=[1.7 * inch, 0.9 * inch, 0.9 * inch, 3.5 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, SUBTLE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, SUBTLE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _timeline_table(analysis: AnalyzeResponse, styles: dict[str, ParagraphStyle]) -> Table:
    rows = []
    for event in analysis.timeline:
        sev_color = SEVERITY_COLORS.get(event.severity, MUTED)
        rows.append(
            [
                Paragraph(event.timestamp.strftime("%H:%M:%S"), styles["muted"]),
                Paragraph(
                    f"<font color='{sev_color.hexval()}'><b>●</b></font> "
                    f"<b>{_escape(event.label)}</b><br/>"
                    f"<font size='9' color='#475569'>{_escape(event.detail)}</font>",
                    styles["body"],
                ),
            ]
        )
    table = Table(rows, colWidths=[0.9 * inch, 6.1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, SUBTLE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _escape_pre(value: str) -> str:
    return _escape(value).replace("\n", "<br/>").replace(" ", "&nbsp;")
