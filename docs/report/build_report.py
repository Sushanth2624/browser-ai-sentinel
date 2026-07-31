#!/usr/bin/env python3
"""Builds the Browser AI Sentinel capstone final report as a .docx, matching the RACE/REVA
format confirmed against capstone 1's own mentor-reviewed, submitted report (read-only
reference — nothing from that repo is copied or modified; only the format specs were extracted:
A4 page, 1in margins, Times New Roman throughout, Normal 12pt/1.5 spacing, Heading 1 14pt bold,
Heading 2/3 12pt bold, Caption 12pt bold).

This is a fresh, standalone generator — same mechanism as capstone 1's build script (chapter/
figure/table auto-numbering via small counters), no code shared between the two repos.

Staged build (see /root/.claude/plans — this file grows chapter by chapter across sessions):
  Stage 1 (done): infrastructure + full skeleton + front matter.
  Stage 2+: chapter content, filled in incrementally — search "STAGE" markers below.

Run: .venv/bin/python build_report.py
"""
from __future__ import annotations

import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor

TIMES = "Times New Roman"
OUT_PATH = "Browser_AI_Sentinel_Final_Report_Sushanth_Sridhar.docx"

# ---------------------------------------------------------------------------
# Document + style setup
# ---------------------------------------------------------------------------

doc = Document()


def setup_page():
    section = doc.sections[0]
    section.page_width = Inches(8.268)   # A4
    section.page_height = Inches(11.693)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)


def setup_styles():
    normal = doc.styles["Normal"]
    normal.font.name = TIMES
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(8)

    h1 = doc.styles["Heading 1"]
    h1.font.name = TIMES
    h1.font.size = Pt(14)
    h1.font.bold = True
    h1.font.color.rgb = RGBColor(0, 0, 0)
    h1.paragraph_format.line_spacing = 1.5
    h1.paragraph_format.space_before = Pt(0)
    h1.paragraph_format.space_after = Pt(14)

    h2 = doc.styles["Heading 2"]
    h2.font.name = TIMES
    h2.font.size = Pt(12)
    h2.font.bold = True
    h2.font.color.rgb = RGBColor(0, 0, 0)
    h2.paragraph_format.line_spacing = 1.5
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(8)

    # "Heading 3 Custom" in the reference doc — python-docx can't rename Heading 3 cleanly
    # across all Word versions, so add a genuinely custom style instead.
    if "Heading 3 Custom" not in [s.name for s in doc.styles]:
        from docx.enum.style import WD_STYLE_TYPE
        h3 = doc.styles.add_style("Heading 3 Custom", WD_STYLE_TYPE.PARAGRAPH)
        h3.base_style = doc.styles["Heading 3"]
    else:
        h3 = doc.styles["Heading 3 Custom"]
    h3.font.name = TIMES
    h3.font.size = Pt(12)
    h3.font.bold = True
    h3.font.color.rgb = RGBColor(0, 0, 0)
    h3.paragraph_format.space_before = Pt(8)
    h3.paragraph_format.space_after = Pt(6)

    if "Caption" not in [s.name for s in doc.styles]:
        from docx.enum.style import WD_STYLE_TYPE
        cap = doc.styles.add_style("Caption", WD_STYLE_TYPE.PARAGRAPH)
    else:
        cap = doc.styles["Caption"]
    cap.font.name = TIMES
    cap.font.size = Pt(12)
    cap.font.bold = True
    cap.paragraph_format.line_spacing = 1.0
    cap.paragraph_format.space_before = Pt(4)
    cap.paragraph_format.space_after = Pt(10)


setup_page()
setup_styles()

# ---------------------------------------------------------------------------
# Chapter / figure / table numbering state
# ---------------------------------------------------------------------------

_state = {"chapter": 0, "fig": 0, "table": 0, "sub": 0, "subsub": 0}
_figures_list: list[tuple[str, str]] = []
_tables_list: list[tuple[str, str]] = []


def set_chapter(n: int):
    _state["chapter"] = n
    _state["fig"] = 0
    _state["table"] = 0
    _state["sub"] = 0
    _state["subsub"] = 0


def next_fig() -> str:
    _state["fig"] += 1
    return f"{_state['chapter']}.{_state['fig']}"


def next_table() -> str:
    _state["table"] += 1
    return f"{_state['chapter']}.{_state['table']}"


# ---------------------------------------------------------------------------
# Paragraph-level helpers
# ---------------------------------------------------------------------------

def para(text="", bold=False, italic=False, align=None, size=None, space_after=None, style=None):
    p = doc.add_paragraph(style=style)
    run = p.add_run(text)
    run.font.name = TIMES
    if size:
        run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if align:
        p.alignment = align
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def placeholder(text: str):
    """Marks genuinely-unknown information plainly, rather than leaving it silently blank —
    same pattern the reference report used ([Designation], [Year], etc.)."""
    return para(text, italic=True)


def page_break():
    doc.add_page_break()


def chapter_heading(text: str, number: int):
    set_chapter(number)
    page_break()
    p = doc.add_paragraph(style="Heading 1")
    run = p.add_run(f"Chapter {number}: {text}")
    run.font.name = TIMES
    run.font.size = Pt(14)
    run.bold = True
    return p


def front_heading(text: str):
    """Front-matter section heading (Abstract, Acknowledgment, ...) — Heading 1 style, no
    chapter numbering."""
    page_break()
    p = doc.add_paragraph(style="Heading 1")
    run = p.add_run(text)
    run.font.name = TIMES
    run.font.size = Pt(14)
    run.bold = True
    return p


def subheading(text: str):
    _state["sub"] += 1
    _state["subsub"] = 0
    label = f"{_state['chapter']}.{_state['sub']}"
    p = doc.add_paragraph(style="Heading 2")
    run = p.add_run(f"{label} {text}")
    run.font.name = TIMES
    run.font.size = Pt(12)
    run.bold = True
    return p


def subsubheading(text: str):
    _state["subsub"] += 1
    label = f"{_state['chapter']}.{_state['sub']}.{_state['subsub']}"
    p = doc.add_paragraph(style="Heading 3 Custom")
    run = p.add_run(f"{label} {text}")
    run.font.name = TIMES
    run.font.size = Pt(12)
    run.bold = True
    return p


def figure(path: str, caption_text: str, width: float = 6.0):
    label = next_fig()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(path, width=Inches(width))
    cap = doc.add_paragraph(style="Caption")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.add_run(f"Fig {label}: {caption_text}")
    _figures_list.append((label, caption_text))
    return label


def table(headers: list[str], rows: list[list[str]], caption_text: str, widths=None):
    label = next_table()
    cap = doc.add_paragraph(style="Caption")
    cap.add_run(f"Table {label}: {caption_text}")
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = ""
        r = hdr_cells[i].paragraphs[0].add_run(h)
        r.font.name = TIMES
        r.font.size = Pt(11)
        r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(val))
            r.font.name = TIMES
            r.font.size = Pt(11)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    para("", size=1)  # small breathing room after the table
    _tables_list.append((label, caption_text))
    return label


def code(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(10)
    return p


def bullet(text: str, style="List Bullet"):
    p = doc.add_paragraph(text, style=style)
    for r in p.runs:
        r.font.name = TIMES
        r.font.size = Pt(12)
    return p


# ---------------------------------------------------------------------------
# Fields: page numbers, TOC
# ---------------------------------------------------------------------------

def _field(paragraph, instr_text):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instr_text
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(fld_end)
    return run


def setup_footer():
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _field(p, "PAGE")


def add_toc_field():
    p = doc.add_paragraph()
    _field(p, 'TOC \\o "1-3" \\h \\z \\u')
    note = para('Right-click here and choose "Update Field" (or press F9) to generate the '
                'Table of Contents with page numbers.', italic=True, size=10)
    return p


setup_footer()

# ---------------------------------------------------------------------------
# STAGE 1 — Front matter
# ---------------------------------------------------------------------------

PROJECT_TITLE = ("Client-Side Detection of Indirect Prompt Injection and Unauthorized Data "
                  "Exfiltration in Browser-to-AI Interactions Using Multi-Indicator Content "
                  "Analysis")

# --- Cover page ---
para("A Project Report on", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
p = para(PROJECT_TITLE, bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
para("Submitted in partial fulfilment for award of degree of", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Master of Technology", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
para("In Cybersecurity", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
para("Submitted by", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Sushanth Sridhar", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
para("SRN: R24TF007  |  Batch: CS14", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
para("Under the Guidance of", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Sandeep", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
placeholder("[Designation]")
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
para("", space_after=18)
para("REVA Academy for Corporate Excellence", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
para("REVA University", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
para("Rukmini Knowledge Park, Kattigenahalli,", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
para("Yelahanka, Bangalore – 560064", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
para("July 2026", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

# --- Candidate's Declaration ---
front_heading("Candidate’s Declaration")
para(
    f"I, Sushanth Sridhar, hereby declare that I have completed the project work towards "
    f"Master of Technology in Cybersecurity at REVA University on the topic entitled "
    f"“{PROJECT_TITLE}” under the supervision of Sandeep, [Designation]. This report "
    f"embodies the original work done by me in partial fulfilment of the requirements for the "
    f"award of the degree for the academic year [Year]."
)
para("Place: Bengaluru                         Name of the Student: Sushanth Sridhar")
para("Date:                                        Signature of Student")

# --- Acknowledgment of Project Ownership and Usage Rights ---
front_heading("Acknowledgment of Project Ownership and Usage Rights")
para(
    "I, Sushanth Sridhar, a student enrolled in the Master of Technology in Cybersecurity "
    "Program and Batch CS14 at RACE, hereby acknowledge that any project, including but not "
    "limited to software, hardware, research, or other intellectual property created by me "
    "during my academic tenure at RACE, is the property of RACE, REVA University."
)
para(
    "I understand and agree that RACE has the exclusive rights to use, reproduce, modify, or "
    "distribute the aforementioned projects for academic, research, and further development "
    "purposes. This includes the right to monetize, commercialize, or otherwise exploit the "
    "projects as deemed fit by RACE."
)
para(
    "I acknowledge that I have no objection to RACE, REVA University, using, reproducing, or "
    "further developing the projects for the benefit of the institution and its academic "
    "community. I further affirm that any commercial or research activities related to the "
    "projects conducted by RACE shall not require additional consent or approval from me."
)
para(
    "This acknowledgment is made willingly and without any reservations. I am grateful for the "
    "education and opportunities provided by RACE, and I recognize the importance of "
    "contributing to the academic and research goals of the institution."
)
para("Place: Bengaluru                         Name of the Student: Sushanth Sridhar")
para("Date:                                        Signature of Student")

# --- Certificate ---
front_heading("Certificate")
para(
    f"This is to certify that the project work entitled “{PROJECT_TITLE}” has been "
    f"carried out by Sushanth Sridhar with SRN R24TF007, who is a bonafide student of REVA "
    f"University, submitting the second-year project report in fulfilment for the award of "
    f"Master of Technology in Cybersecurity during the academic year [Year]. The project report "
    f"has been tested for plagiarism and has passed the plagiarism test with a similarity score "
    f"of less than 15%. The project report has been approved as it satisfies the academic "
    f"requirements in respect of the project work prescribed for the said degree."
)
para("Signature of the Guide                              Signature of the Director")
para("Sandeep                    [Name of the Director]")
para("Guide                                             Director")

p = doc.add_paragraph(style="Heading 2")
r = p.add_run("External Viva")
r.font.name = TIMES
r.font.size = Pt(12)
r.bold = True
para("Names of the Examiners")
placeholder("[Name]  [Designation]  [Signature]")
placeholder("[Name]  [Designation]  [Signature]")
para("Place: Bengaluru")
para("Date:")

# --- Acknowledgment ---
front_heading("Acknowledgment")
para(
    "I would like to express my sincere gratitude to my project guide, Sandeep, for the "
    "continuous guidance, technical feedback, and encouragement provided throughout this "
    "capstone project. I am also thankful to the faculty and program office of REVA Academy for "
    "Corporate Excellence (RACE) for their support during the course of this MTech in "
    "Cybersecurity program, batch CS14."
)
para(
    "I extend my gratitude to my classmates and peers for their valuable discussions and "
    "feedback during the development and evaluation of this project. I am also thankful to my "
    "family and friends for their patience and encouragement throughout this journey."
)
para(
    "I gratefully acknowledge the support provided by the Hon’ble Chancellor, Dr. P Shayma "
    "Raju, Hon’ble Vice Chancellor, Dr. Sanjay Chitnis, and Registrar, Dr. M. Dhanamjaya, "
    "REVA University, whose vision for research-driven, industry-relevant postgraduate education "
    "made this capstone project possible."
)
para("Place: Bengaluru")
para("Date:")

# --- Similarity Index Report ---
front_heading("Similarity Index Report")
para(
    f"This is to certify that this project report titled “{PROJECT_TITLE}” was "
    f"scanned for similarity detection. The process and outcome are given below. The plagiarism "
    f"report is attached in the appendix."
)
bullet("Software Used: Turnitin")
placeholder("Date of Report Generation: [to be filled after running Turnitin]")
placeholder("Similarity Index in %: [to be filled — must be < 15%]")
placeholder("Total word count: [auto-filled by Word once final]")
para("Name of the Guide: Sandeep")
para("Place: Bengaluru                         Name of the Student: Sushanth Sridhar")
para("Date:                                        Signature of Student")
para("Verified by:")
para("Signature")
placeholder("[Verifying officer name and title to be added]")

# --- Lists ---
front_heading("List of Abbreviations")
_ABBR = [
    ("DOM", "Document Object Model"),
    ("TLS", "Transport Layer Security"),
    ("SNI", "Server Name Indication"),
    ("JA3 / JA4", "TLS client fingerprinting methods (Salesforce JA3; FoxIO JA4)"),
    ("MV3", "Chrome Extension Manifest Version 3"),
    ("CDP", "Chrome DevTools Protocol"),
    ("DLP", "Data Loss Prevention"),
    ("PII", "Personally Identifiable Information"),
    ("EDR", "Endpoint Detection and Response"),
    ("MITRE ATLAS", "Adversarial Threat Landscape for Artificial-Intelligence Systems"),
    ("OWASP", "Open Worldwide Application Security Project"),
    ("F1", "Harmonic mean of precision and recall"),
    ("TP / FP / TN / FN", "True Positive / False Positive / True Negative / False Negative"),
]
abbr_table = doc.add_table(rows=1, cols=2)
abbr_table.style = "Table Grid"
abbr_table.rows[0].cells[0].text = "Abbreviation"
abbr_table.rows[0].cells[1].text = "Expansion"
for abbr, expansion in _ABBR:
    row = abbr_table.add_row()
    row.cells[0].text = abbr
    row.cells[1].text = expansion

front_heading("List of Figures")
placeholder("[Populated at final assembly, Stage 6 — see Fig labels generated throughout the report]")

front_heading("List of Tables")
placeholder("[Populated at final assembly, Stage 6 — see Table labels generated throughout the report]")

# --- Abstract ---
front_heading("Abstract")
placeholder("(Not to exceed 1 page)")
para(
    "AI-powered browser agents (ChatGPT Atlas, Perplexity Comet, Claude in Chrome) now read and "
    "act on arbitrary web content on a user's behalf, and the open web has begun filling with "
    "content specifically crafted to hijack that behaviour — indirect prompt injection "
    "hidden in off-screen CSS, HTML comments, and metadata that a human never sees but an agent's "
    "context window does. Independent testing found ChatGPT Atlas blocked only 5.8% and "
    "Perplexity Comet only 7% of such pages, against 47–53% for conventional phishing "
    "defences in ordinary browsers, and Google recorded a 32% rise in malicious indirect-"
    "injection content between November 2025 and February 2026. Existing defences are vendor-"
    "side and reactive; a proactive, client-side sentinel that inspects page content before an "
    "agent ever reads it is largely unexplored."
)
para(
    "This project builds and evaluates such a sentinel as a standalone system: a Chrome "
    "extension that scans the live DOM of any page for six independent indicators of hidden "
    "instructions (off-screen positioning, zero-width Unicode, suspicious HTML comments, hidden "
    "alt/ARIA text, JSON-LD metadata, and visible imperative language) and combines them with a "
    "noisy-OR multi-indicator score; a Go agent bridging the extension to a local Python scoring "
    "service and a Postgres store via Chrome's native messaging API; a real Zeek/Suricata network "
    "sensor performing JA3/JA4 TLS fingerprinting to identify known AI platforms and cluster "
    "unlisted “shadow AI” services; and an outbound data-loss-prevention gate that "
    "intercepts and classifies fetch/XHR bodies to known AI domains before they are sent, holding "
    "flagged content for user approval."
)
para(
    "The system was evaluated end to end — not simulated — against a 70-page labelled "
    "synthetic dataset (30 benign, 10 deliberately weak “hard-negative” pages, 30 "
    "injected) visited by a 4-container test fleet, each container its own OS user and hostname, "
    "running the real extension, agent, and scoring pipeline. The multi-indicator detector (C) "
    "achieved F1 0.979 (precision 0.983, recall 0.975), against F1 0.911 for a visibility-only "
    "baseline (B) and F1 0.784 for a keyword-only baseline (A) — mirroring the same C > B > A "
    "pattern from the author's prior capstone on network-based C2 detection. The result that most "
    "directly supports the multi-indicator design: on the hard-negative pages, the keyword-only "
    "baseline false-positived on 32 of 40 visits and the visibility-only baseline on 20 of 40, "
    "against 2 of 40 for the multi-indicator detector."
)
para(
    "Building the system end to end surfaced nine real, documented defects and their fixes "
    "spanning every layer — a Chrome install-path assumption that silently broke content-"
    "script injection, a native-messaging registration gap, a TLS client-fingerprint (JA3) "
    "instability caused by Chrome's GREASE mechanism that silently defeated the shadow-AI "
    "clustering rule until re-keyed to JA4, and others — each caught by checking real output "
    "against expectation rather than trusting a clean-looking log, and each recorded with root "
    "cause and fix rather than smoothed over in the final narrative. The shadow-AI clustering "
    "rule was also confirmed to have genuine practical limits: once corrected, the same "
    "fingerprint that caught the two seeded “unknown AI” test domains also pulled in "
    "sixteen unrelated domains from the browser's own background traffic, demonstrating directly "
    "why the technique is a human triage signal rather than an automated verdict."
)
para(
    "The findings support the conclusion that combining independent, cheaply-computed content "
    "indicators client-side detects indirect prompt injection substantially more reliably than "
    "any single indicator alone, while remaining fully inspectable — every flagged page "
    "shows exactly which indicators fired — and that this client-side vantage point is "
    "structurally unavailable to network-only or vendor-side defences."
)
para(
    "Keywords: Prompt Injection, Indirect Prompt Injection, Browser AI Agents, Data Loss "
    "Prevention, Shadow AI, TLS Fingerprinting, JA3, JA4, MITRE ATLAS, Multi-Indicator Detection, "
    "Chrome Extension Security"
)

# --- Table of Contents ---
front_heading("Table of Contents")
add_toc_field()

# ---------------------------------------------------------------------------
# STAGE 1 — Chapter skeleton (headings only; content filled in later stages)
# ---------------------------------------------------------------------------

STAGE_PENDING = "[Content pending — see build plan for staging]"

chapter_heading("Introduction", 1)
subheading("The Shift From a Network Perimeter to an Agentic Browser Perimeter")
para(STAGE_PENDING, italic=True)
subheading("Scope and Organization of This Report")
para(STAGE_PENDING, italic=True)

chapter_heading("Literature Review", 2)
subheading("Indirect Prompt Injection Against AI Browser Agents")
para(STAGE_PENDING, italic=True)
subheading("Existing Detection and Red-Team Tooling")
para(STAGE_PENDING, italic=True)
subheading("Shadow AI Discovery and Enterprise DLP for AI Tools")
para(STAGE_PENDING, italic=True)
subheading("TLS Client Fingerprinting (JA3/JA4)")
para(STAGE_PENDING, italic=True)
subheading("MITRE ATLAS and OWASP LLM Top 10")
para(STAGE_PENDING, italic=True)
subheading("Consolidated Gap and This Project's Contribution")
para(STAGE_PENDING, italic=True)

chapter_heading("Problem Statement", 3)
para(STAGE_PENDING, italic=True)

chapter_heading("Objectives of the Study", 4)
para(STAGE_PENDING, italic=True)

chapter_heading("Project Methodology", 5)
subheading("Phased Build-and-Verify Methodology")
para(STAGE_PENDING, italic=True)
subheading("Evaluation (A/B/C Comparison) Methodology")
para(STAGE_PENDING, italic=True)
subheading("Problems Encountered and How They Were Resolved")
para(STAGE_PENDING, italic=True)

chapter_heading("Resource Requirement Specification", 6)
subheading("Hardware Requirements")
para(STAGE_PENDING, italic=True)
subheading("Software Requirements")
para(STAGE_PENDING, italic=True)
subheading("Data Requirements")
para(STAGE_PENDING, italic=True)

chapter_heading("Software Design", 7)
subheading("System Architecture")
para(STAGE_PENDING, italic=True)
subheading("Data Flow: Browser Event to Stored Verdict")
para(STAGE_PENDING, italic=True)
subheading("Module Design")
para(STAGE_PENDING, italic=True)

chapter_heading("Implementation", 8)
subheading("Objective 1 — Multi-Indicator Prompt-Injection Detection")
para(STAGE_PENDING, italic=True)
subheading("Objective 2 — AI-Platform and Shadow-AI Discovery")
para(STAGE_PENDING, italic=True)
subheading("Objective 3 — Outbound DLP / Exfiltration Gate")
para(STAGE_PENDING, italic=True)
subheading("Objective 4 — Multi-Endpoint Test Fleet and Dashboard")
para(STAGE_PENDING, italic=True)

chapter_heading("Testing and Validation", 9)
subheading("Build and Type Verification")
para(STAGE_PENDING, italic=True)
subheading("Functional Test Cases (Mapped to Objectives)")
para(STAGE_PENDING, italic=True)
subheading("Headline Results (Configuration A vs B vs C)")
para(STAGE_PENDING, italic=True)

chapter_heading("Analysis and Results", 10)
subheading("Headline Comparison")
para(STAGE_PENDING, italic=True)
subheading("Why Every Single Indicator Falls Short")
para(STAGE_PENDING, italic=True)
subheading("The Shadow-AI Clustering Finding")
para(STAGE_PENDING, italic=True)
subheading("Fleet-Wide Endpoint Attribution")
para(STAGE_PENDING, italic=True)
subheading("Summary of Findings")
para(STAGE_PENDING, italic=True)

chapter_heading("Conclusions and Future Scope", 11)
subheading("Limitations")
para(STAGE_PENDING, italic=True)
subheading("Future Scope")
para(STAGE_PENDING, italic=True)

# --- Bibliography ---
front_heading("Bibliography")
para(STAGE_PENDING, italic=True)

# --- Appendix ---
front_heading("Appendix")
p = doc.add_paragraph(style="Heading 2")
r = p.add_run("Plagiarism Report")
r.font.name, r.font.size, r.bold = TIMES, Pt(12), True
placeholder("[To be attached after Turnitin scan]")

p = doc.add_paragraph(style="Heading 2")
r = p.add_run("Paper Publications in a Journal/Conference Presented/White Paper")
r.font.name, r.font.size, r.bold = TIMES, Pt(12), True
placeholder("[None at time of submission]")

p = doc.add_paragraph(style="Heading 2")
r = p.add_run("Certificate for the Conference Presentation")
r.font.name, r.font.size, r.bold = TIMES, Pt(12), True
placeholder("[Not applicable]")

p = doc.add_paragraph(style="Heading 2")
r = p.add_run("Github Link")
r.font.name, r.font.size, r.bold = TIMES, Pt(12), True
para("https://github.com/Sushanth2624/browser-ai-sentinel")

p = doc.add_paragraph(style="Heading 2")
r = p.add_run("Additional Reproduction Notes")
r.font.name, r.font.size, r.bold = TIMES, Pt(12), True
para(STAGE_PENDING, italic=True)

# ---------------------------------------------------------------------------
doc.save(OUT_PATH)
print(f"Saved {OUT_PATH} ({datetime.datetime.now().isoformat(timespec='seconds')})")
