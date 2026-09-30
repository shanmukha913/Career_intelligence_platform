"""Generate downloadable reports for a selected meeting."""

import csv
import io
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_meeting_csv(meeting: dict[str, Any]) -> str:
    """Return a CSV report containing details for one meeting."""
    intelligence = meeting.get("intelligence", {})
    rows = [
        ["Section", "Content"],
        ["Meeting ID", meeting.get("id", "")],
        ["Meeting", meeting.get("filename", "")],
        ["Date", meeting.get("created_at", "")],
        ["Summary", intelligence.get("summary", "")],
        ["Key Decisions", "; ".join(intelligence.get("decisions", []))],
        ["Action Items", _format_records(intelligence.get("action_items", []))],
        ["Participants", _format_records(intelligence.get("participants", []))],
        ["Deadlines", _format_records(intelligence.get("deadlines", []))],
    ]
    output = io.StringIO(newline="")
    csv.writer(output).writerows(rows)
    return output.getvalue()


def build_meeting_pdf(meeting: dict[str, Any]) -> bytes:
    """Return a PDF report containing details for one meeting."""
    intelligence = meeting.get("intelligence", {})
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("ReportBody", parent=styles["BodyText"], alignment=TA_LEFT, leading=14)
    story = [
        Paragraph("Meeting Report", styles["Title"]),
        Paragraph(f"<b>Meeting:</b> {escape(str(meeting.get('filename', 'Unknown')))}", body_style),
        Paragraph(f"<b>Meeting ID:</b> {escape(str(meeting.get('id', '')))}", body_style),
        Paragraph(f"<b>Date:</b> {escape(str(meeting.get('created_at', 'Unknown')))}", body_style),
        Spacer(1, 12),
    ]
    _append_section(story, "Summary", [intelligence.get("summary", "No summary available.")], styles, body_style)
    _append_section(story, "Key Decisions", intelligence.get("decisions", []), styles, body_style)
    _append_section(story, "Action Items", [_record_text(item) for item in intelligence.get("action_items", [])], styles, body_style)
    _append_section(story, "Participants & Responsibilities", [_record_text(item) for item in intelligence.get("participants", [])], styles, body_style)
    _append_section(story, "Deadlines", [_record_text(item) for item in intelligence.get("deadlines", [])], styles, body_style)
    document.build(story)
    return output.getvalue()


def _format_records(records: list[dict[str, Any]]) -> str:
    return " | ".join(_record_text(record) for record in records)


def _record_text(record: dict[str, Any]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in record.items())


def _append_section(story: list[Any], title: str, items: list[str], styles: Any, body_style: Any) -> None:
    story.extend([Spacer(1, 8), Paragraph(escape(title), styles["Heading2"])])
    if items:
        for item in items:
            story.append(Paragraph(escape(str(item)), body_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("None recorded.", body_style))
