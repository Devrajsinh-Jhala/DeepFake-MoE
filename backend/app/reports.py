from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#122036")
INK = colors.HexColor("#233349")
MUTED = colors.HexColor("#5b6b80")
LINE = colors.HexColor("#d6e0e9")
PAPER = colors.HexColor("#f6f9fb")
TEAL = colors.HexColor("#137d70")
TEAL_LIGHT = colors.HexColor("#e9f7f4")
RED = colors.HexColor("#96344a")
RED_LIGHT = colors.HexColor("#faedf0")
AMBER = colors.HexColor("#a66b0b")
AMBER_LIGHT = colors.HexColor("#fff5df")
BLUE = colors.HexColor("#506b87")
BLUE_LIGHT = colors.HexColor("#edf3f8")


class ScoreBar(Flowable):
    def __init__(self, label: str, value: float, color: colors.Color, width: float = 6.45 * inch):
        super().__init__()
        self.label = label
        self.value = max(0.0, min(1.0, float(value)))
        self.bar_color = color
        self.width = width
        self.height = 0.42 * inch

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(INK)
        canvas.drawString(0, self.height - 10, self.label)
        value_text = f"{self.value:.0%}"
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(self.width - stringWidth(value_text, "Helvetica-Bold", 8.5), self.height - 10, value_text)
        y = 3
        canvas.setFillColor(colors.HexColor("#e1e8ef"))
        canvas.roundRect(0, y, self.width, 7, 3.5, fill=1, stroke=0)
        canvas.setFillColor(self.bar_color)
        canvas.roundRect(0, y, self.width * self.value, 7, 3.5, fill=1, stroke=0)


def build_pdf_report(result: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.68 * inch,
        bottomMargin=0.58 * inch,
        title="AI Deepfake Analyzer Evidence Report",
        author="AI Deepfake Analyzer",
        subject="Explainable synthetic-media authenticity analysis",
    )
    styles = _report_styles()
    verdict = result["verdict"]
    explainability = result.get("explainability") or {}
    decision_support = explainability.get("decision_support") or {}
    decision_standard = explainability.get("decision_standard") or {}
    appendix = result.get("technical_appendix") or {}

    story: list[Any] = [
        Paragraph("AUTHENTICITY EVIDENCE REPORT", styles["eyebrow"]),
        Paragraph("AI Deepfake Analyzer", styles["title"]),
        Paragraph(
            "A privacy-first, explainable assessment of synthetic-generation, manipulation, provenance, and uncertainty signals.",
            styles["lead"],
        ),
        Spacer(1, 0.16 * inch),
        _verdict_banner(verdict, styles),
        Spacer(1, 0.16 * inch),
        ScoreBar("AI evidence score", verdict.get("ai_probability", 0), _verdict_color(verdict.get("label"))),
        ScoreBar("Manipulation evidence", verdict.get("manipulation_probability", 0), AMBER),
        ScoreBar("Cross-layer evidence disagreement", verdict.get("disagreement", 0), BLUE),
        Spacer(1, 0.06 * inch),
        _callout(
            "How to read this score",
            verdict.get("score_interpretation")
            or "This is evidence strength for cautious triage. It is not the probability that a person or image is fake.",
            styles,
            BLUE_LIGHT,
        ),
        Spacer(1, 0.16 * inch),
        Paragraph("Decision Summary", styles["h2"]),
        Paragraph(_safe_text(decision_support.get("plain_summary") or result["summary"]["plain_language"]), styles["body"]),
        Spacer(1, 0.08 * inch),
        _decision_table(decision_support, styles),
        Spacer(1, 0.14 * inch),
        Paragraph("Evidence Path", styles["h2"]),
        _evidence_path(styles),
        Spacer(1, 0.14 * inch),
        _callout(
            "Safety boundary",
            "No face search, identity inference, private-account access, or hidden attribution was performed. A public URL is used only for visible source context.",
            styles,
            TEAL_LIGHT,
        ),
        PageBreak(),
        Paragraph("MODEL AND ARBITRATION TRACE", styles["eyebrow"]),
        Paragraph("How the model panel reached its stance", styles["section_title"]),
        Paragraph(
            "Each detector is treated as an expert with its own thresholds. Raw outputs inside an expert's abstention band become neutral evidence before the arbiter combines them.",
            styles["lead"],
        ),
        Spacer(1, 0.12 * inch),
        _model_consensus_table(explainability.get("model_consensus") or {}, styles),
        Spacer(1, 0.16 * inch),
        Paragraph("Model Stability And Calibration", styles["h2"]),
        _model_stability_table(explainability.get("model_consensus") or {}, styles),
        Spacer(1, 0.16 * inch),
        Paragraph("Expert Opinions", styles["h2"]),
        _expert_table(explainability.get("expert_opinions") or [], styles),
        PageBreak(),
        Paragraph("CALIBRATION AND ABSTENTION", styles["eyebrow"]),
        Paragraph("When the system refuses to overclaim", styles["section_title"]),
        Paragraph(
            "The arbiter applies model-specific gates, input-quality penalties, real-photo protections, and an explicit abstention policy before a label can be emitted.",
            styles["lead"],
        ),
        Spacer(1, 0.12 * inch),
        _calibration_table(decision_standard, styles),
        Spacer(1, 0.14 * inch),
        _callout(
            "Why inconclusive can be the correct result",
            "When models disagree, input quality is weak, or no independent provenance supports a visual score, the arbiter preserves uncertainty instead of making a harmful accusation.",
            styles,
            AMBER_LIGHT,
        ),
        Spacer(1, 0.18 * inch),
        Paragraph("Explanation Contract", styles["h2"]),
        _explanation_contract_table(explainability.get("explanation_contract") or {}, styles),
        PageBreak(),
        Paragraph("LAYER-BY-LAYER EXPLAINABILITY", styles["eyebrow"]),
        Paragraph("Independent evidence ledger", styles["section_title"]),
        Paragraph(
            "These layers decompose the file into provenance, model, luminance, color, edge, noise, compression, frequency, and regional evidence. Weak heuristic layers cannot independently prove AI generation.",
            styles["lead"],
        ),
        Spacer(1, 0.12 * inch),
        Paragraph("What Actually Influenced The Arbiter", styles["h2"]),
        _attribution_table(explainability.get("decision_attribution") or [], styles),
        Spacer(1, 0.16 * inch),
        _layer_ledger(result.get("analytical_layers") or [], styles),
        Spacer(1, 0.16 * inch),
        Paragraph("Decision Trace", styles["h2"]),
        _numbered_lines(explainability.get("decision_trace") or [], styles),
    ]

    regional_map = explainability.get("regional_evidence_map") or {}
    if regional_map.get("tiles"):
        story.extend(
            [
                PageBreak(),
                Paragraph("REGIONAL FORENSIC MAP", styles["eyebrow"]),
                Paragraph("Where local anomalies were measured", styles["section_title"]),
                Paragraph(_safe_text(regional_map.get("interpretation", "")), styles["lead"]),
                Spacer(1, 0.14 * inch),
                _region_map_table(regional_map, styles),
                Spacer(1, 0.16 * inch),
                _callout(
                    "Map limitation",
                    "A highlighted tile means its brightness, edge, or residual statistics differ from other tiles. It does not identify a pasted object or prove a deepfake without corroborating evidence.",
                    styles,
                    BLUE_LIGHT,
                ),
            ]
        )

    story.extend(
        [
            PageBreak(),
            Paragraph("TECHNICAL APPENDIX", styles["eyebrow"]),
            Paragraph("Reproducibility and file facts", styles["section_title"]),
            _technical_summary(appendix, styles),
            Spacer(1, 0.16 * inch),
            Paragraph("Detector Outputs", styles["h2"]),
            _detector_table(appendix.get("detectors") or [], styles),
            Spacer(1, 0.16 * inch),
            Paragraph("Metadata And Provenance", styles["h2"]),
            _metadata_table(appendix.get("metadata") or {}, appendix.get("c2pa") or {}, styles),
            PageBreak(),
            Paragraph("RESPONSIBLE USE", styles["eyebrow"]),
            Paragraph("Limitations and practical next steps", styles["section_title"]),
            Paragraph(
                "Automated authenticity analysis can support triage and documentation, but it cannot establish identity, consent, or legal truth from pixels alone.",
                styles["lead"],
            ),
            Spacer(1, 0.12 * inch),
            *_bullet_lines(result.get("summary", {}).get("limitations") or [], styles),
            Spacer(1, 0.08 * inch),
            *_bullet_lines(result.get("next_steps") or [], styles, prefix="Next step: "),
            Spacer(1, 0.16 * inch),
            _callout(
                "Report status",
                "This report is an automated evidence summary. It is not legal advice, identity proof, or a forensic certificate of authenticity.",
                styles,
                RED_LIGHT,
            ),
        ]
    )

    doc.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)
    return buffer.getvalue()


def _report_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=NAVY, alignment=TA_LEFT, spaceAfter=4),
        "section_title": ParagraphStyle("SectionTitle", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=NAVY, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=NAVY, spaceBefore=3, spaceAfter=6),
        "h3": ParagraphStyle("H3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=NAVY, spaceAfter=3),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=INK),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.4, leading=9.5, textColor=MUTED),
        "table": ParagraphStyle("TableText", parent=base["BodyText"], fontName="Helvetica", fontSize=7.4, leading=9.4, textColor=INK),
        "table_bold": ParagraphStyle("TableBold", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.4, leading=9.4, textColor=INK),
        "table_header": ParagraphStyle("TableHeader", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.4, leading=9.4, textColor=colors.white),
        "lead": ParagraphStyle("Lead", parent=base["BodyText"], fontName="Helvetica", fontSize=10.2, leading=14.5, textColor=MUTED),
        "eyebrow": ParagraphStyle("Eyebrow", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=TEAL, spaceAfter=5),
        "banner_label": ParagraphStyle("BannerLabel", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white),
        "banner_score": ParagraphStyle("BannerScore", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=25, leading=27, textColor=colors.white, alignment=TA_CENTER),
        "callout_title": ParagraphStyle("CalloutTitle", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, textColor=NAVY),
        "callout_body": ParagraphStyle("CalloutBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=INK),
        "tile": ParagraphStyle("Tile", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=NAVY, alignment=TA_CENTER),
    }


def _decorate_page(canvas, doc) -> None:
    width, height = letter
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, height - 0.42 * inch, width - doc.rightMargin, height - 0.42 * inch)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(NAVY)
    canvas.drawString(doc.leftMargin, height - 0.31 * inch, "AI DEEPFAKE ANALYZER")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - doc.rightMargin, height - 0.31 * inch, "Explainable authenticity evidence")
    canvas.line(doc.leftMargin, 0.39 * inch, width - doc.rightMargin, 0.39 * inch)
    canvas.drawString(doc.leftMargin, 0.24 * inch, "Privacy-first automated triage report")
    canvas.drawRightString(width - doc.rightMargin, 0.24 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _verdict_banner(verdict: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    label = str(verdict.get("label", "inconclusive")).replace("_", " ").upper()
    confidence = str(verdict.get("confidence", "low")).upper()
    score = f"{float(verdict.get('ai_probability') or 0):.0%}"
    table = Table(
        [[Paragraph(f"{label}<br/><font size='8'>{confidence} CONFIDENCE</font>", styles["banner_label"]), Paragraph(score, styles["banner_score"])]],
        colWidths=[4.75 * inch, 1.7 * inch],
        rowHeights=[0.82 * inch],
    )
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _verdict_color(verdict.get("label"))), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 16), ("RIGHTPADDING", (1, 0), (1, 0), 14)]))
    return table


def _verdict_color(label: str | None) -> colors.Color:
    if label == "likely_ai_generated":
        return RED
    if label == "likely_manipulated_or_deepfake":
        return AMBER
    if label == "likely_real":
        return TEAL
    return BLUE


def _callout(title: str, body: str, styles: dict[str, ParagraphStyle], background: colors.Color) -> Table:
    table = Table([[Paragraph(_safe_text(title), styles["callout_title"]), Paragraph(_safe_text(body), styles["callout_body"])]], colWidths=[1.45 * inch, 5.0 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), background), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return table


def _decision_table(decision: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("Primary drivers", decision.get("primary_drivers") or ["No single strong driver was available."]),
        ("Counter-evidence", decision.get("counter_evidence") or ["No strong counter-evidence was recorded."]),
        ("Uncertainty", decision.get("uncertainty_factors") or ["Automated image analysis remains uncertain."]),
        ("What would help", decision.get("what_would_help") or ["Original media and signed provenance."]),
    ]
    data = [[Paragraph(_safe_text(label), styles["table_bold"]), _line_paragraph(values, styles["table"])] for label, values in rows]
    table = Table(data, colWidths=[1.38 * inch, 5.07 * inch], splitByRow=True)
    table.setStyle(_base_table_style(first_column=True))
    return table


def _evidence_path(styles: dict[str, ParagraphStyle]) -> Table:
    labels = ["Validated input", ">", "Independent experts", ">", "Calibration gate", ">", "Safety arbiter", ">", "Report"]
    widths = [0.88, 0.22, 1.10, 0.22, 0.92, 0.22, 0.88, 0.22, 0.88]
    data = [[Paragraph(label, styles["table_bold"] if label != ">" else styles["table"]) for label in labels]]
    table = Table(data, colWidths=[width * inch for width in widths], rowHeights=[0.52 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PAPER), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TEXTCOLOR", (1, 0), (1, 0), TEAL), ("TEXTCOLOR", (3, 0), (3, 0), TEAL), ("TEXTCOLOR", (5, 0), (5, 0), TEAL), ("TEXTCOLOR", (7, 0), (7, 0), TEAL)]))
    return table


def _model_consensus_table(consensus: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("Enabled experts", str(consensus.get("enabled_models", 0))),
        ("AI / real / abstain votes", f"{consensus.get('ai_votes', 0)} / {consensus.get('real_votes', 0)} / {consensus.get('inconclusive_votes', 0)}"),
        ("Experts leaning AI", f"{consensus.get('lean_ai_votes', 0)} / {consensus.get('enabled_models', 0)}"),
        ("Primary-anchored alignment", "yes" if consensus.get("primary_anchored_alignment") else "no"),
        ("Calibrated model evidence", _percent_or_na(consensus.get("average_ai_probability"))),
        ("Raw output average", _percent_or_na(consensus.get("raw_average_ai_probability"))),
        ("Calibrated stance disagreement", _percent_or_na(consensus.get("calibrated_stance_disagreement"))),
        ("Raw score range (diagnostic)", _percent_or_na(consensus.get("raw_score_range"))),
        ("Ensemble stance", str(consensus.get("ensemble_label") or "not available").replace("_", " ")),
    ]
    return _two_column_table(rows, styles)


def _model_stability_table(consensus: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [
            Paragraph(text, styles["table_header"])
            for text in ("Model", "Calibrated stance", "Views", "Stability", "AI / real gates", "Weight")
        ]
    ]
    for model in consensus.get("models") or []:
        details = model.get("details") or {}
        model_name = str(model.get("name") or "").removeprefix("hf:")
        stability = (
            f"range {_percent_or_na(details.get('stability_range'))}; "
            f"MAD {_percent_or_na(details.get('median_absolute_deviation'))}"
            if details.get("view_count")
            else "single view"
        )
        gates = f"{_percent_or_na(details.get('ai_threshold'))} / {_percent_or_na(details.get('real_threshold'))}"
        data.append(
            [
                Paragraph(_safe_text(model_name), styles["table_bold"]),
                Paragraph(
                    f"{_safe_text(str(model.get('label') or '').replace('_', ' '))}<br/>"
                    f"{_percent_or_na(model.get('calibrated_stance_score'))}",
                    styles["table"],
                ),
                Paragraph(str(details.get("view_count") or 1), styles["table"]),
                Paragraph(_safe_text(stability), styles["table"]),
                Paragraph(_safe_text(gates), styles["table"]),
                Paragraph(f"{float(model.get('reliability_weight') or 0):.2f}", styles["table"]),
            ]
        )
    if len(data) == 1:
        data.append([Paragraph("No model diagnostics were available.", styles["table"]), "", "", "", "", ""])
    table = Table(
        data,
        colWidths=[1.62 * inch, 1.40 * inch, 0.42 * inch, 1.18 * inch, 1.18 * inch, 0.65 * inch],
        repeatRows=1,
        splitByRow=True,
    )
    table.setStyle(_base_table_style(header=True))
    return table


def _attribution_table(attributions: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [
            Paragraph(text, styles["table_header"])
            for text in ("Source", "Decision role", "Direction", "Influence", "Finding")
        ]
    ]
    for item in attributions:
        used = "used" if item.get("used_by_arbiter") else "context only"
        role = f"{str(item.get('role') or '').replace('_', ' ')}<br/><font color='#5b6b80'>{used}</font>"
        data.append(
            [
                Paragraph(_safe_text(item.get("source", "")), styles["table_bold"]),
                Paragraph(role, styles["table"]),
                Paragraph(_safe_text(str(item.get("direction") or "neutral").replace("_", " ")), styles["table"]),
                Paragraph(_percent_or_na(item.get("strength")), styles["table"]),
                Paragraph(_safe_text(item.get("finding", "")), styles["table"]),
            ]
        )
    if len(data) == 1:
        data.append([Paragraph("No decision attributions were available.", styles["table"]), "", "", "", ""])
    table = Table(
        data,
        colWidths=[1.42 * inch, 1.12 * inch, 1.08 * inch, 0.62 * inch, 2.21 * inch],
        repeatRows=1,
        splitByRow=True,
    )
    table.setStyle(_base_table_style(header=True))
    return table


def _expert_table(opinions: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(text, styles["table_header"]) for text in ("Expert", "Stance", "Confidence", "Evidence score")]]
    for opinion in opinions[:10]:
        score = opinion.get("score")
        data.append(
            [
                Paragraph(_safe_text(opinion.get("expert", "")), styles["table_bold"]),
                Paragraph(_safe_text(str(opinion.get("stance", "neutral")).replace("_", " ")), styles["table"]),
                Paragraph(_safe_text(opinion.get("confidence", "")), styles["table"]),
                Paragraph(_percent_or_na(score), styles["table"]),
            ]
        )
    if len(data) == 1:
        data.append([Paragraph("No expert outputs were available.", styles["table"]), "", "", ""])
    table = Table(data, colWidths=[2.3 * inch, 1.65 * inch, 1.15 * inch, 1.35 * inch], repeatRows=1, splitByRow=True)
    table.setStyle(_base_table_style(header=True))
    return table


def _calibration_table(standard: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("Policy", [str(standard.get("policy") or "victim-safe calibrated triage")]),
        ("A strong AI claim requires", standard.get("likely_ai_requires") or []),
        ("False-positive controls", standard.get("false_positive_controls") or []),
        ("Input quality risk", [str((standard.get("input_quality") or {}).get("risk_band", "not available"))]),
    ]
    data = [[Paragraph(_safe_text(label), styles["table_bold"]), _line_paragraph(values, styles["table"])] for label, values in rows]
    table = Table(data, colWidths=[1.55 * inch, 4.90 * inch], splitByRow=True)
    table.setStyle(_base_table_style(first_column=True))
    return table


def _explanation_contract_table(contract: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    arbiter_inputs = contract.get("arbiter_inputs") or []
    context_layers = contract.get("context_only_layers") or []
    rows = [
        ("Score semantics", contract.get("score_semantics") or "Evidence strength, not probability of truth."),
        ("Arbiter inputs", "; ".join(str(item) for item in arbiter_inputs) or "No decision inputs were recorded."),
        (
            "Context-only layers",
            f"{len(context_layers)} diagnostic layer(s): " + (", ".join(str(item) for item in context_layers) or "none"),
        ),
        ("Abstention rule", contract.get("abstention_rule") or "Conflicted evidence remains inconclusive."),
        ("Human-review boundary", contract.get("human_review_boundary") or "Automated analysis cannot establish legal truth."),
    ]
    return _two_column_table(rows, styles)


def _layer_ledger(layers: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(text, styles["table_header"]) for text in ("Layer", "Conclusion", "AI", "Manip.", "Method and strongest evidence")]]
    for layer in layers:
        evidence = (layer.get("evidence") or ["No finding recorded."])[0]
        detail = (
            f"{_safe_text(layer.get('method', ''))}<br/>"
            f"<font color='#5b6b80'>{_safe_text(evidence)}</font><br/>"
            f"<font color='#5b6b80'>Role: {_safe_text(str(layer.get('decision_role') or '').replace('_', ' '))}; "
            f"reliability: {_safe_text(layer.get('reliability', 'none'))}; "
            f"arbiter: {'used' if layer.get('used_by_arbiter') else 'context only'}.</font>"
        )
        data.append(
            [
                Paragraph(_safe_text(layer.get("name", "")), styles["table_bold"]),
                Paragraph(_safe_text(str(layer.get("conclusion", "")).replace("_", " ")), styles["table"]),
                Paragraph(_percent_or_na(layer.get("ai_signal")), styles["table"]),
                Paragraph(_percent_or_na(layer.get("manipulation_signal")), styles["table"]),
                Paragraph(detail, styles["table"]),
            ]
        )
    table = Table(data, colWidths=[1.16 * inch, 1.25 * inch, 0.48 * inch, 0.54 * inch, 3.02 * inch], repeatRows=1, splitByRow=True)
    commands = list(_base_table_style(header=True).getCommands())
    for row_index, layer in enumerate(layers, start=1):
        conclusion = str(layer.get("conclusion", ""))
        color = TEAL_LIGHT if conclusion == "supports_real_or_camera_origin" else RED_LIGHT if conclusion == "supports_ai_generated" else AMBER_LIGHT if "manipulation" in conclusion else colors.white
        commands.append(("BACKGROUND", (0, row_index), (1, row_index), color))
    table.setStyle(TableStyle(commands))
    return table


def _numbered_lines(lines: list[str], styles: dict[str, ParagraphStyle]) -> Table:
    data = []
    for index, line in enumerate(lines[:10], start=1):
        data.append([Paragraph(f"{index:02d}", styles["table_bold"]), Paragraph(_safe_text(line), styles["body"])])
    if not data:
        data.append([Paragraph("01", styles["table_bold"]), Paragraph("No decision trace was recorded.", styles["body"])])
    table = Table(data, colWidths=[0.42 * inch, 6.03 * inch])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TEXTCOLOR", (0, 0), (0, -1), TEAL), ("LINEBELOW", (0, 0), (-1, -2), 0.35, LINE), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return table


def _region_map_table(regional_map: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    tiles = regional_map.get("tiles") or []
    by_position = {(int(tile.get("row", 0)), int(tile.get("col", 0))): tile for tile in tiles}
    rows = []
    for row in range(1, 5):
        cells = []
        for col in range(1, 5):
            tile = by_position.get((row, col), {})
            score = float(tile.get("severity") or 0)
            band = str(tile.get("severity_band") or "low")
            cells.append(Paragraph(f"R{row} C{col}<br/><font size='12'>{score:.0%}</font><br/>{_safe_text(band)}", styles["tile"]))
        rows.append(cells)
    table = Table(rows, colWidths=[1.61 * inch] * 4, rowHeights=[0.86 * inch] * 4)
    commands = [("GRID", (0, 0), (-1, -1), 0.7, colors.white), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]
    for row in range(1, 5):
        for col in range(1, 5):
            band = str(by_position.get((row, col), {}).get("severity_band") or "low")
            color = RED_LIGHT if band == "high" else AMBER_LIGHT if band == "medium" else TEAL_LIGHT
            commands.append(("BACKGROUND", (col - 1, row - 1), (col - 1, row - 1), color))
    table.setStyle(TableStyle(commands))
    return table


def _technical_summary(appendix: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    hashes = appendix.get("hashes") or {}
    reproducibility = appendix.get("reproducibility") or {}
    rows = [
        ("Schema / runtime", f"{appendix.get('schema_version', '0.2')} / {appendix.get('runtime_ms', 'not available')} ms"),
        ("Pipeline", reproducibility.get("pipeline", "not available")),
        ("Primary detector", reproducibility.get("primary_detector", "not available")),
        ("SHA-256", hashes.get("sha256", "not available")),
        ("Average / difference hash", f"{hashes.get('average_hash', 'n/a')} / {hashes.get('difference_hash', 'n/a')}"),
        ("Training policy", reproducibility.get("model_training", "No custom model was trained by this application.")),
    ]
    return _two_column_table(rows, styles)


def _detector_table(detectors: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(text, styles["table_header"]) for text in ("Detector", "Status", "Stance", "AI score", "Weight", "Evidence")]]
    for detector in detectors:
        evidence = " ".join((detector.get("evidence") or [])[:2])
        data.append(
            [
                Paragraph(_safe_text(detector.get("name", "")), styles["table_bold"]),
                Paragraph(_safe_text(detector.get("status", "")), styles["table"]),
                Paragraph(_safe_text(str(detector.get("label", "")).replace("_", " ")), styles["table"]),
                Paragraph(_percent_or_na(detector.get("ai_probability")), styles["table"]),
                Paragraph(f"{float(detector.get('weight') or 0):.2f}", styles["table"]),
                Paragraph(_safe_text(evidence), styles["table"]),
            ]
        )
    table = Table(data, colWidths=[1.37 * inch, 0.58 * inch, 1.05 * inch, 0.55 * inch, 0.45 * inch, 2.45 * inch], repeatRows=1, splitByRow=True)
    table.setStyle(_base_table_style(header=True))
    return table


def _metadata_table(metadata: dict[str, Any], c2pa: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("Format and dimensions", f"{metadata.get('format', 'unknown')} - {metadata.get('width', '?')} x {metadata.get('height', '?')}"),
        ("EXIF / XMP", f"EXIF: {'present' if metadata.get('has_exif') else 'not found'}; XMP: {'present' if metadata.get('xmp_present') else 'not found'}"),
        ("Generative markers", ", ".join(metadata.get("generative_markers") or []) or "none found"),
        ("Editing markers", ", ".join(metadata.get("editing_markers") or []) or "none found"),
        ("C2PA", f"{c2pa.get('status', 'unavailable')} - {c2pa.get('claim') or 'no readable claim'}"),
        ("Software values", "; ".join(metadata.get("software_values") or []) or "none found"),
    ]
    return _two_column_table(rows, styles)


def _two_column_table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(_safe_text(label), styles["table_bold"]), Paragraph(_safe_text(value), styles["table"])] for label, value in rows]
    table = Table(data, colWidths=[1.55 * inch, 4.90 * inch], splitByRow=True)
    table.setStyle(_base_table_style(first_column=True))
    return table


def _base_table_style(*, header: bool = False, first_column: bool = False) -> TableStyle:
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.extend([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)])
    if first_column:
        commands.append(("BACKGROUND", (0, 0), (0, -1), PAPER))
    return TableStyle(commands)


def _line_paragraph(lines: list[str], style: ParagraphStyle) -> Paragraph:
    if not lines:
        return Paragraph("Not available.", style)
    return Paragraph("<br/>".join(_safe_text(line) for line in lines), style)


def _bullet_lines(lines: list[str], styles: dict[str, ParagraphStyle], prefix: str = "") -> list[Any]:
    items: list[Any] = []
    for line in lines:
        items.append(Paragraph(f"- {_safe_text(prefix + str(line))}", styles["body"]))
        items.append(Spacer(1, 0.025 * inch))
    return items or [Paragraph("- No item recorded.", styles["body"])]


def _percent_or_na(value: Any) -> str:
    return f"{float(value):.0%}" if isinstance(value, (int, float)) else "not available"


def _safe_text(value: Any) -> str:
    return escape(str(value), quote=False)
