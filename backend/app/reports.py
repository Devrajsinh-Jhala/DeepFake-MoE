from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf_report(result: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="AI Deepfake Analyzer Report",
    )
    styles = getSampleStyleSheet()
    title = styles["Title"]
    heading = styles["Heading2"]
    body = styles["BodyText"]
    small = ParagraphStyle("Small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#334155"))

    verdict = result["verdict"]
    explainability = result.get("explainability") or {}
    decision_support = explainability.get("decision_support") or {}
    decision_standard = explainability.get("decision_standard") or {}
    story = [
        Paragraph("AI Deepfake Analyzer Report", title),
        Spacer(1, 0.15 * inch),
        Paragraph(result["summary"]["headline"], heading),
        Paragraph(result["summary"]["plain_language"], body),
        Spacer(1, 0.15 * inch),
        _kv_table(
            [
                ("Verdict", verdict["label"]),
                ("Confidence", verdict["confidence"]),
                ("AI Probability", f"{verdict['ai_probability']:.0%}"),
                ("Manipulation Probability", f"{verdict['manipulation_probability']:.0%}"),
                ("Detector Disagreement", f"{verdict['disagreement']:.0%}"),
            ]
        ),
        Spacer(1, 0.2 * inch),
    ]

    if decision_support:
        story.extend(
            [
                Paragraph("Decision Summary", heading),
                Paragraph(_safe_text(decision_support.get("plain_summary", "")), body),
                Spacer(1, 0.08 * inch),
                _decision_table(decision_support),
                Spacer(1, 0.2 * inch),
            ]
        )

    if decision_standard:
        story.extend(
            [
                Paragraph("Calibration Gate", heading),
                Paragraph(_safe_text(f"Policy: {decision_standard.get('policy', 'not available')}"), body),
                _kv_table(
                    [
                        ("Likely AI requires", "; ".join(decision_standard.get("likely_ai_requires", [])[:3])),
                        ("False-positive controls", "; ".join(decision_standard.get("false_positive_controls", [])[:3])),
                        (
                            "Input quality risk",
                            str((decision_standard.get("input_quality") or {}).get("risk_band", "not available")),
                        ),
                    ]
                ),
                Spacer(1, 0.2 * inch),
            ]
        )

    expert_opinions = explainability.get("expert_opinions") or []
    if expert_opinions:
        story.extend([Paragraph("Mixture Of Experts", heading), _expert_table(expert_opinions), Spacer(1, 0.2 * inch)])

    story.append(Paragraph("Evidence Layers", heading))
    for layer in result["layers"]:
        story.append(Paragraph(_safe_text(f"{layer['name']} - {layer['status']}"), styles["Heading3"]))
        for finding in layer["findings"][:5]:
            story.append(Paragraph(_safe_text(f"- {finding}"), body))

    story.extend([Spacer(1, 0.2 * inch), Paragraph("Explainable AI Trace", heading)])
    for item in explainability.get("decision_trace", [])[:6]:
        story.append(Paragraph(_safe_text(f"- {item}"), body))

    regional_map = explainability.get("regional_evidence_map")
    if regional_map:
        story.extend([Spacer(1, 0.15 * inch), Paragraph("Region Evidence Map", heading)])
        story.append(Paragraph(_safe_text(regional_map.get("interpretation", "")), small))
        story.append(_region_map_table(regional_map, small))

    layer_ledger = explainability.get("layer_ledger", {})
    analytical_layers = layer_ledger.get("layers") or result.get("analytical_layers") or []
    if analytical_layers:
        story.extend([Spacer(1, 0.15 * inch), Paragraph("Analytical Layer Breakdown", heading)])
        rows = [("Layer", "Conclusion", "AI", "Manip.")]
        for layer in analytical_layers:
            rows.append(
                (
                    str(layer.get("name", ""))[:32],
                    str(layer.get("conclusion", ""))[:34],
                    f"{float(layer.get('ai_signal') or 0):.0%}",
                    f"{float(layer.get('manipulation_signal') or 0):.0%}",
                )
            )
        story.append(_kv_matrix(rows))
        for layer in analytical_layers[:8]:
            story.append(Paragraph(_safe_text(f"{layer.get('name')}: {layer.get('method')}"), small))
            for finding in (layer.get("evidence") or [])[:2]:
                story.append(Paragraph(_safe_text(f"- {finding}"), small))

    story.extend([Spacer(1, 0.2 * inch), Paragraph("Limitations", heading)])
    for limitation in result["summary"]["limitations"]:
        story.append(Paragraph(_safe_text(f"- {limitation}"), body))

    story.extend([Spacer(1, 0.2 * inch), Paragraph("Technical Appendix", heading)])
    appendix = result["technical_appendix"]
    story.append(Paragraph(_safe_text(f"SHA-256: {appendix['hashes']['sha256']}"), small))
    story.append(Paragraph(_safe_text(f"Average hash: {appendix['hashes']['average_hash']}"), small))
    story.append(Paragraph(_safe_text(f"Difference hash: {appendix['hashes']['difference_hash']}"), small))
    story.append(Paragraph(_safe_text(f"Runtime: {appendix['runtime_ms']} ms"), small))
    story.append(
        Paragraph(
            "This report is an evidence summary. It is not legal advice and does not certify authenticity.",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table(rows, colWidths=[2.2 * inch, 4.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _decision_table(decision_support: dict[str, Any]) -> Table:
    rows = [
        ("Primary drivers", decision_support.get("primary_drivers", [])[:4]),
        ("Counter-evidence", decision_support.get("counter_evidence", [])[:4]),
        ("Uncertainty", decision_support.get("uncertainty_factors", [])[:4]),
        ("What would help", decision_support.get("what_would_help", [])[:4]),
    ]
    label_style = ParagraphStyle("DecisionLabel", fontName="Helvetica-Bold", fontSize=8, leading=10)
    value_style = ParagraphStyle("DecisionValue", fontSize=8, leading=10)
    table = Table(
        [
            (
                Paragraph(_safe_text(label), label_style),
                _line_paragraph(value, value_style),
            )
            for label, value in rows
        ],
        colWidths=[1.45 * inch, 4.75 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _expert_table(opinions: list[dict[str, Any]]) -> Table:
    rows = [("Expert", "Opinion", "Stance", "Score")]
    for opinion in opinions[:8]:
        score = opinion.get("score")
        rows.append(
            (
                str(opinion.get("expert", ""))[:28],
                str(opinion.get("opinion", ""))[:32],
                str(opinion.get("stance", ""))[:22],
                f"{float(score):.0%}" if isinstance(score, (int, float)) else "",
            )
        )
    return _kv_matrix(rows)


def _region_map_table(regional_map: dict[str, Any], small_style: ParagraphStyle) -> Table:
    tiles = regional_map.get("tiles") or []
    by_position = {(int(tile.get("row", 0)), int(tile.get("col", 0))): tile for tile in tiles}
    rows = []
    for row in range(1, 5):
        cells = []
        for col in range(1, 5):
            tile = by_position.get((row, col), {})
            score = float(tile.get("severity") or 0)
            band = str(tile.get("severity_band") or "low")
            cells.append(Paragraph(f"R{row} C{col}<br/>{score:.0%}<br/>{_safe_text(band)}", small_style))
        rows.append(cells)

    table = Table(rows, colWidths=[1.08 * inch] * 4, rowHeights=[0.48 * inch] * 4)
    style_commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]
    for row in range(1, 5):
        for col in range(1, 5):
            tile = by_position.get((row, col), {})
            band = tile.get("severity_band")
            color = "#fee2e2" if band == "high" else "#fef3c7" if band == "medium" else "#ecfdf5"
            style_commands.append(("BACKGROUND", (col - 1, row - 1), (col - 1, row - 1), colors.HexColor(color)))
    table.setStyle(TableStyle(style_commands))
    return table


def _line_paragraph(lines: list[str], style: ParagraphStyle) -> Paragraph:
    if not lines:
        return Paragraph("Not available.", style)
    return Paragraph("<br/>".join(_safe_text(line) for line in lines), style)


def _kv_matrix(rows: list[tuple[str, ...]]) -> Table:
    table = Table(rows, colWidths=[1.9 * inch, 2.4 * inch, 0.8 * inch, 0.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _safe_text(value: str) -> str:
    return escape(str(value), quote=False)
