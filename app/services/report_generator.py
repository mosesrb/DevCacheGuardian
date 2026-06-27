"""
ReportGenerator (v7) — exportable audit reports in HTML, Markdown, and PDF.

HTML   — self-contained single file, all styles inline, no external deps
Markdown — GitHub-flavoured markdown, suitable for team wikis / issue trackers
PDF    — generated from HTML via PySide6 QPrinter / QTextDocument (no weasyprint)
"""
from __future__ import annotations

import html as _html
from datetime import datetime
from pathlib import Path
from typing import List

from app.models import CacheItem, RiskLevel
from app.utils import fmt_bytes


_RISK_COLOR = {
    RiskLevel.SAFE:   ("#052e16", "#4ade80"),
    RiskLevel.REVIEW: ("#1c0a00", "#fbbf24"),
    RiskLevel.DANGER: ("#1c0404", "#f87171"),
}
_ECO_COLOR = {
    "Python": "#3b82f6", "Node.js": "#22c55e", "AI/ML": "#f59e0b",
    "Docker": "#0ea5e9", "System": "#6b7280", "Build Systems": "#a78bfa",
}


# ── shared data prep ──────────────────────────────────────────────────────────

def _prep(items, health, growth_deltas, cleanup_stats, scan_duration):
    now    = datetime.now().strftime("%B %d, %Y at %H:%M")
    total  = sum(i.size_bytes for i in items)
    safe   = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.SAFE)
    review = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.REVIEW)
    danger = sum(1 for i in items if i.risk_level == RiskLevel.DANGER)
    score  = health.get("score", 0)
    grade  = health.get("grade", "?")
    bd     = health.get("breakdown", {})
    sorted_items = sorted(items, key=lambda x: -x.size_bytes)
    growers = sorted(
        [d for d in growth_deltas if (d.get("delta_bytes") or 0) > 1024*1024],
        key=lambda x: -(x.get("delta_bytes") or 0)
    )[:15]
    return dict(
        now=now, total=total, safe=safe, review=review, danger=danger,
        score=score, grade=grade, bd=bd, sorted_items=sorted_items,
        growers=growers, cleanup_stats=cleanup_stats, scan_duration=scan_duration,
    )


# ── HTML ─────────────────────────────────────────────────────────────────────

def generate_html_report(items, health, growth_deltas, cleanup_stats,
                          scan_duration=0.0) -> str:
    d = _prep(items, health, growth_deltas, cleanup_stats, scan_duration)
    grade_color = {"A":"#4ade80","B":"#86efac","C":"#fbbf24","D":"#f97316","F":"#f87171"}.get(d['grade'],"#9ca3af")

    rows = "\n".join(_html_item_row(i) for i in d['sorted_items'])

    growth_section = ""
    if d['growers']:
        g_rows = "\n".join(_html_growth_row(g) for g in d['growers'])
        growth_section = f"""
        <h2>Cache Growth (since last scan)</h2>
        <table>
          <thead><tr><th>Cache</th><th>Ecosystem</th>
            <th>Previous</th><th>Current</th><th>Change</th></tr></thead>
          <tbody>{g_rows}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>DevCache Guardian — Audit Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,'Segoe UI',sans-serif;background:#0f1011;color:#c9cdd6;padding:32px;font-size:14px}}
h1{{font-size:24px;font-weight:700;color:#e2e8f0;margin-bottom:4px}}
h2{{font-size:16px;font-weight:600;color:#9ca3af;margin:32px 0 12px}}
.meta{{color:#374151;font-size:12px;margin-bottom:32px}}
.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:32px}}
.card{{background:#16181c;border:1px solid #1e2025;border-radius:8px;padding:14px 16px}}
.card-label{{font-size:10px;color:#4b5563;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
.card-value{{font-size:22px;font-weight:700}}
.score{{font-size:42px;font-weight:800;color:{grade_color}}}
table{{width:100%;border-collapse:collapse;margin-bottom:24px;background:#13151a;border-radius:8px;overflow:hidden}}
th{{background:#0d0e10;color:#4b5563;font-size:11px;text-transform:uppercase;letter-spacing:.4px;padding:10px 12px;text-align:left}}
td{{padding:10px 12px;border-bottom:1px solid #1a1d22;font-size:13px}}
tr:last-child td{{border-bottom:none}}
.badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600}}
code{{font-family:'Cascadia Code',Consolas,monospace;font-size:11px;color:#93c5fd;background:#0d1117;padding:2px 6px;border-radius:4px}}
.pos{{color:#f87171}}.neg{{color:#4ade80}}.zero{{color:#6b7280}}
footer{{margin-top:48px;color:#1f2937;font-size:11px;text-align:center}}
</style>
</head>
<body>
<h1>DevCache Guardian — Audit Report</h1>
<div class="meta">Generated {d['now']}{f"  ·  Scan took {d['scan_duration']:.1f}s" if d['scan_duration'] else ""}</div>
<div class="metrics">
  <div class="card">
    <div class="card-label">Health score</div>
    <div class="score">{d['score']}</div>
    <div style="color:{grade_color};font-size:14px;font-weight:600">Grade {d['grade']}</div>
  </div>
  <div class="card">
    <div class="card-label">Total found</div>
    <div class="card-value" style="color:#e2e8f0">{fmt_bytes(d['total'])}</div>
    <div style="color:#374151;font-size:11px">{len(items)} locations</div>
  </div>
  <div class="card">
    <div class="card-label">Safe to reclaim</div>
    <div class="card-value" style="color:#3b82f6">{fmt_bytes(d['safe'])}</div>
    <div style="color:#374151;font-size:11px">no project risk</div>
  </div>
  <div class="card">
    <div class="card-label">Needs review</div>
    <div class="card-value" style="color:#f59e0b">{fmt_bytes(d['review'])}</div>
    <div style="color:#374151;font-size:11px">re-downloadable</div>
  </div>
  <div class="card">
    <div class="card-label">All-time cleaned</div>
    <div class="card-value" style="color:#4ade80">{fmt_bytes(d['cleanup_stats'].get('total_bytes') or 0)}</div>
    <div style="color:#374151;font-size:11px">{d['cleanup_stats'].get('ops',0)} operations</div>
  </div>
</div>
<h2>All Cache Locations</h2>
<table>
  <thead><tr><th>Cache</th><th>Ecosystem</th><th>Size</th><th>Risk</th><th>Path</th><th>Command</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
{growth_section}
<footer>DevCache Guardian v3.0 — Developer Storage Intelligence Platform</footer>
</body></html>"""


def _html_item_row(item: CacheItem) -> str:
    bg, fg  = _RISK_COLOR.get(item.risk_level, ("#1a1d22", "#c9cdd6"))
    eco_c   = _ECO_COLOR.get(item.ecosystem, "#6b7280")
    label   = {RiskLevel.SAFE:"Safe",RiskLevel.REVIEW:"Review",RiskLevel.DANGER:"Danger"}[item.risk_level]
    cmd     = (f"<code>{_html.escape(item.cleanup_command.splitlines()[0])}</code>"
               if item.cleanup_command else "<span style='color:#374151'>—</span>")
    return (f"<tr>"
            f"<td><strong style='color:#e2e8f0'>{_html.escape(item.name)}</strong>"
            f"<br><span style='color:#374151;font-size:11px'>{_html.escape(item.description)}</span></td>"
            f"<td><span style='color:{eco_c};font-size:12px'>{_html.escape(item.ecosystem)}</span></td>"
            f"<td style='font-weight:600;color:#e2e8f0'>{item.size_label}</td>"
            f"<td><span class='badge' style='background:{bg};color:{fg};border:1px solid {fg}33'>{label}</span></td>"
            f"<td><code style='font-size:10px'>{_html.escape(item.path[:60])}{'…' if len(item.path)>60 else ''}</code></td>"
            f"<td>{cmd}</td></tr>")


def _html_growth_row(g: dict) -> str:
    delta = g.get("delta_bytes", 0) or 0
    eco_c = _ECO_COLOR.get(g.get("ecosystem",""), "#6b7280")
    ds    = fmt_bytes(abs(delta))
    if delta > 1024*100: css, sign = "pos", f"▲ +{ds}"
    elif delta < -1024*100: css, sign = "neg", f"▼ -{ds}"
    else: css, sign = "zero", "≈ unchanged"
    return (f"<tr>"
            f"<td><strong style='color:#e2e8f0'>{_html.escape(g.get('cache_name',''))}</strong></td>"
            f"<td><span style='color:{eco_c};font-size:12px'>{_html.escape(g.get('ecosystem',''))}</span></td>"
            f"<td style='color:#6b7280'>{fmt_bytes(g.get('prev_bytes',0) or 0)}</td>"
            f"<td style='color:#e2e8f0;font-weight:600'>{fmt_bytes(g.get('curr_bytes',0) or 0)}</td>"
            f"<td class='{css}' style='font-weight:600'>{sign}</td></tr>")


# ── Markdown ──────────────────────────────────────────────────────────────────

def _md_escape(text: str) -> str:
    """Escape pipe characters and backticks to prevent Markdown table injection."""
    return str(text).replace("|", "\\|").replace("`", "\\`")


def generate_markdown_report(items, health, growth_deltas, cleanup_stats,
                              scan_duration=0.0) -> str:
    d = _prep(items, health, growth_deltas, cleanup_stats, scan_duration)
    lines = []
    lines.append(f"# DevCache Guardian — Audit Report")
    lines.append(f"")
    lines.append(f"Generated: **{d['now']}**" + (f"  ·  Scan duration: **{d['scan_duration']:.1f}s**" if d['scan_duration'] else ""))
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Health Score: {d['score']}/100 — Grade {d['grade']}")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total found | **{fmt_bytes(d['total'])}** across {len(items)} locations |")
    lines.append(f"| Safe to reclaim | **{fmt_bytes(d['safe'])}** |")
    lines.append(f"| Needs review | **{fmt_bytes(d['review'])}** |")
    lines.append(f"| Protected (env/projects) | **{d['danger']} items** |")
    lines.append(f"| All-time cleaned | **{fmt_bytes(d['cleanup_stats'].get('total_bytes') or 0)}** ({d['cleanup_stats'].get('ops',0)} operations) |")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## All Cache Locations")
    lines.append(f"")
    lines.append(f"| Cache | Ecosystem | Size | Risk | Cleanup command |")
    lines.append(f"|-------|-----------|------|------|-----------------|")
    for item in d['sorted_items']:
        label = {RiskLevel.SAFE:"✅ Safe",RiskLevel.REVIEW:"🟡 Review",RiskLevel.DANGER:"🔴 Danger"}[item.risk_level]
        cmd   = f"`{_md_escape(item.cleanup_command.splitlines()[0])}`" if item.cleanup_command else "—"
        lines.append(f"| {_md_escape(item.name)} | {_md_escape(item.ecosystem)} | **{item.size_label}** | {label} | {cmd} |")

    if d['growers']:
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"## Cache Growth (since last scan)")
        lines.append(f"")
        lines.append(f"| Cache | Ecosystem | Previous | Current | Change |")
        lines.append(f"|-------|-----------|----------|---------|--------|")
        for g in d['growers']:
            delta = g.get("delta_bytes", 0) or 0
            ds    = fmt_bytes(abs(delta))
            sign  = f"▲ +{ds}" if delta > 0 else (f"▼ -{ds}" if delta < 0 else "≈ unchanged")
            lines.append(
                f"| {_md_escape(g.get('cache_name',''))} | {_md_escape(g.get('ecosystem',''))} "
                f"| {fmt_bytes(g.get('prev_bytes',0) or 0)} "
                f"| {fmt_bytes(g.get('curr_bytes',0) or 0)} | **{sign}** |"
            )

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*DevCache Guardian v3.0 — Developer Storage Intelligence Platform*")
    return "\n".join(lines)


# ── PDF (via Qt) ──────────────────────────────────────────────────────────────

def generate_pdf_report(items, health, growth_deltas, cleanup_stats,
                         scan_duration=0.0, output_path: str = "") -> bool:
    """
    Generate a PDF by rendering the HTML report through Qt's print engine.
    Returns True on success, False on failure.
    No external dependencies (weasyprint, reportlab, etc.) needed.
    """
    try:
        from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtCore import QMarginsF
        from PySide6.QtWidgets import QApplication
        import sys

        html_content = generate_html_report(
            items, health, growth_deltas, cleanup_stats, scan_duration
        )

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(output_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageLayout(QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(15, 15, 15, 15),
        ))

        doc = QTextDocument()
        doc.setHtml(html_content)
        doc.print_(printer)
        return True

    except Exception as exc:
        from loguru import logger
        logger.error(f"PDF generation failed: {exc}")
        return False
