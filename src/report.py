"""
PDF report generator for battery analysis.

Generates a one-page A4 PDF report summarising a battery's assessment:
battery details, decision, reasons, recovered materials, recycling centre,
and CO2 savings.

Usage (from app.py):
    from report import generate_report
    pdf_bytes = generate_report(result)
"""

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)


def _fmt(value, decimals=2):
    """Format a number with thousands separators."""
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def generate_report(result: dict) -> bytes:
    """
    Build a PDF report from an analyse_battery() result dict.
    Returns the PDF as bytes.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Battery Report - {result.get('battery_id', 'Unknown')}",
        author="EV Battery Lifecycle Decision System",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=13,
                        textColor=colors.HexColor("#1F4E79"), spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=9,
                        textColor=colors.HexColor("#1F4E79"), spaceBefore=4,
                        spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=8,
                          leading=10)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=6,
                           textColor=colors.HexColor("#666666"), leading=8)

    story = []

    # ---------- Header ----------
    story.append(Paragraph("EV Battery Lifecycle Report", h1))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Battery ID: <b>{result.get('battery_id', '-')}</b>",
        small,
    ))
    story.append(Spacer(1, 2 * mm))

    # ---------- Battery details ----------
    story.append(Paragraph("Battery details", h2))
    details = [
        ["Battery type",    result.get("chemistry", "-")],
        ["Weight (kg)",     _fmt(result.get("weight_kg", 0), 1)],
        ["Capacity (kWh)",  _fmt(result.get("capacity_kwh", 0), 1)],
        ["Cycle count",     f"{result.get('cycle', 0):,}"],
        ["State of Health", f"{_fmt(result.get('soh', 0), 1)} %"],
        ["Remaining Useful Life", f"{result.get('rul', 0):,} cycles"],
    ]
    t = Table(details, colWidths=[55 * mm, 100 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.white, colors.HexColor("#F2F6FA")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    # ---------- Recommendation ----------
    story.append(Paragraph("Recommendation", h2))
    action = result.get("decision", "-")
    conf = result.get("confidence", 0)
    story.append(Paragraph(
        f"<b>Action:</b> {action} &nbsp;&nbsp;&nbsp; "
        f"<b>Confidence:</b> {conf*100:.0f}%",
        body,
    ))

    reasons = result.get("reasons", []) or []
    if reasons:
        story.append(Spacer(1, 1 * mm))
        story.append(Paragraph("<b>Reasoning:</b>", body))
        for r in reasons:
            story.append(Paragraph(f"&bull;&nbsp; {r}", body))

    story.append(Spacer(1, 2 * mm))

    # ---------- Materials + centres (only if recycling) ----------
    if result.get("materials"):
        story.append(Paragraph("Recoverable materials", h2))
        rows = [["Material", "Content (kg)", "Recovered (kg)", "Rate"]]
        for mat, data in result["materials"]["recoverable"].items():
            rows.append([
                mat,
                _fmt(data.get("content_kg", 0), 2),
                _fmt(data.get("recovered_kg", 0), 2),
                f"{data.get('rate', 0)*100:.0f}%",
            ])
        t = Table(rows, colWidths=[45 * mm, 40 * mm, 40 * mm, 25 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F2F6FA")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t)

        story.append(Spacer(1, 1 * mm))
        haz = result["materials"].get("hazardous", {}) or {}
        if haz:
            haz_txt = ", ".join(f"{k}: {_fmt(v,2)} kg" for k, v in haz.items())
            story.append(Paragraph(f"<b>Hazardous:</b> {haz_txt}", body))
        residual = result["materials"].get("residual_kg", 0)
        story.append(Paragraph(
            f"<b>Residual (slag / losses):</b> {_fmt(residual,2)} kg", body
        ))

        centres = result.get("centres", []) or []
        if centres:
            story.append(Paragraph("Recommended recycling centres", h2))
            rows = [["Centre", "Distance (km)", "Score"]]
            for c in centres:
                rows.append([
                    c.get("centre_name", "-"),
                    _fmt(c.get("distance_km", 0), 1),
                    _fmt(c.get("score", 0), 3),
                ])
            t = Table(rows, colWidths=[95 * mm, 35 * mm, 25 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#F2F6FA")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(t)
            story.append(Spacer(1, 1 * mm))
            top = centres[0]
            story.append(Paragraph(
                f"<b>Top pick:</b> {top.get('centre_name','-')} "
                f"({_fmt(top.get('distance_km',0),1)} km, "
                f"score {_fmt(top.get('score',0),3)})",
                body,
            ))

    # ---------- Environmental impact ----------
    carbon = result.get("carbon_avoided_kg", 0) or 0
    if carbon > 0:
        story.append(Paragraph("Environmental impact", h2))
        story.append(Paragraph(
            f"<b>CO2 avoided by recycling this battery:</b> {_fmt(carbon, 0)} kg",
            body,
        ))
        story.append(Paragraph(
            f"Equivalent to ~{carbon/0.25:,.0f} km of average car driving.",
            body,
        ))

        rows = [["Material", "Recovered (kg)", "CO2 factor (kg/kg)", "CO2 avoided (kg)"]]
        for row in result.get("carbon_breakdown", []) or []:
            rows.append([
                row.get("material", "-"),
                _fmt(row.get("recovered_kg", 0), 2),
                _fmt(row.get("co2_factor", 0), 1),
                _fmt(row.get("co2_avoided_kg", 0), 2),
            ])
        t = Table(rows, colWidths=[40 * mm, 40 * mm, 40 * mm, 35 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F2F6FA")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t)
        story.append(Spacer(1, 1 * mm))
        story.append(Paragraph(
            "Emission factors: Argonne GREET model (2023).", small
        ))

    # ---------- Method note ----------
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<b>Method:</b> RUL estimated via a physics-informed degradation curve "
        "(SoH -> remaining cycles). Decision rules based on SoH and RUL bands: "
        "CONTINUE_EV (SoH >= 80% and RUL >= 200), SECOND_LIFE (60-80% SoH, RUL >= 50), "
        "REPAIR (40-60% SoH), RECYCLE (< 40% SoH or RUL < 50). "
        "Materials modelled from chemistry and total battery mass; recovery rates "
        "reflect industry-standard pyro + hydro processes.",
        small,
    ))

    # ---------- Footer ----------
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "EV Battery Lifecycle &nbsp;|&nbsp; AI Decision Pipeline",
        small,
    ))

    doc.build(story)
    return buf.getvalue()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pipeline import analyse_battery

    sample = analyse_battery(
        battery_id="EVB-IN-000245",
        chemistry="LFP",
        capacity_kwh=45,
        weight_kg=320,
        cycle=1420, voltage=3.75, temperature=28,
        capacity=32, soh=30,
    )
    pdf = generate_report(sample)
    out = Path("sample_report.pdf")
    out.write_bytes(pdf)
    print(f"Wrote {out} ({len(pdf):,} bytes)")