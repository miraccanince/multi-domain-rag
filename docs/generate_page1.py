"""
Page 1: Workflow Design — Visual Workflow Diagram (v2 - Flowchart style)
AI-Powered Lead Management & Qualification Workflow for Cleeng
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

OUTPUT = "/Users/mirac/Desktop/RAGDocumentationAssistant/docs/page1_workflow.pdf"

# Colors
BLUE = HexColor("#2563EB")
BLUE_LIGHT = HexColor("#EFF6FF")
PURPLE = HexColor("#7C3AED")
PURPLE_LIGHT = HexColor("#F5F3FF")
YELLOW = HexColor("#D97706")
YELLOW_LIGHT = HexColor("#FFFBEB")
GREEN = HexColor("#059669")
GREEN_LIGHT = HexColor("#ECFDF5")
DARK = HexColor("#1E293B")
GRAY = HexColor("#64748B")
LIGHT_BG = HexColor("#F8FAFC")
ARROW_COLOR = HexColor("#94A3B8")

W, H = A4  # 595.27 x 841.89
CX = W / 2


# ─── Drawing primitives ───

def rrect(c, x, y, w, h, r, fill, stroke=None, sw=1.2):
    c.saveState()
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw)
    else:
        c.setStrokeColor(fill)
        c.setLineWidth(0)
    p = c.beginPath()
    p.roundRect(x, y, w, h, r)
    p.close()
    c.drawPath(p, fill=1, stroke=1 if stroke else 0)
    c.restoreState()


def arrow_down(c, x, y1, y2, color=ARROW_COLOR):
    """Vertical arrow from y1 down to y2."""
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.4)
    c.line(x, y1, x, y2 + 5)
    p = c.beginPath()
    p.moveTo(x - 3.5, y2 + 5)
    p.lineTo(x, y2)
    p.lineTo(x + 3.5, y2 + 5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def arrow_right(c, x1, x2, y, color=ARROW_COLOR):
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.4)
    c.line(x1, y, x2 - 5, y)
    p = c.beginPath()
    p.moveTo(x2 - 5, y - 3.5)
    p.lineTo(x2, y)
    p.lineTo(x2 - 5, y + 3.5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def arrow_left(c, x1, x2, y, color=ARROW_COLOR):
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.4)
    c.line(x1, y, x2 + 5, y)
    p = c.beginPath()
    p.moveTo(x2 + 5, y - 3.5)
    p.lineTo(x2, y)
    p.lineTo(x2 + 5, y + 3.5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def diamond(c, cx, cy, w, h, fill, stroke):
    c.saveState()
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1.5)
    p = c.beginPath()
    p.moveTo(cx, cy + h / 2)
    p.lineTo(cx + w / 2, cy)
    p.lineTo(cx, cy - h / 2)
    p.lineTo(cx - w / 2, cy)
    p.close()
    c.drawPath(p, fill=1, stroke=1)
    c.restoreState()


def badge(c, x, cy, text, bg, fg):
    c.saveState()
    tw = c.stringWidth(text, "Helvetica-Bold", 5.5) + 8
    bh = 10
    rrect(c, x, cy - bh / 2, tw, bh, 3, bg)
    c.setFillColor(fg)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(x + 4, cy - 2, text)
    c.restoreState()
    return tw


def flowbox(c, x, y, w, h, title, bullets, box_color, badge_text):
    """Compact flowchart box with badge + title + bullets."""
    bg = {BLUE: BLUE_LIGHT, PURPLE: PURPLE_LIGHT,
          YELLOW: YELLOW_LIGHT, GREEN: GREEN_LIGHT}[box_color]

    rrect(c, x, y, w, h, 6, bg, box_color, 1.3)

    # Left color bar
    c.saveState()
    c.setFillColor(box_color)
    p = c.beginPath()
    p.roundRect(x, y, 4, h, 2)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

    # Badge
    badge_labels = {
        BLUE: ("AUTOMATION", white),
        PURPLE: ("AI-POWERED", white),
        YELLOW: ("HUMAN REVIEW", white),
        GREEN: ("ACTION", white),
    }
    btxt, bfg = badge_labels[box_color]
    badge(c, x + 10, y + h - 10, btxt, box_color, bfg)

    # Title
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 10, y + h - 24, title)

    # Bullets
    c.setFont("Helvetica", 6.5)
    c.setFillColor(GRAY)
    for i, b in enumerate(bullets):
        c.drawString(x + 13, y + h - 35 - i * 9.5, f"• {b}")


def create_page1():
    c = canvas.Canvas(OUTPUT, pagesize=A4)

    # ── HEADER ──
    rrect(c, 0, H - 50, W, 50, 0, DARK)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(20, H - 32, "AI-Powered Lead Management & Qualification Workflow")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94A3B8"))
    c.drawString(20, H - 44, "Cleeng — Demand Generation Workflow Automation")
    c.drawRightString(W - 20, H - 32, "Mirac Can Ince")
    c.drawRightString(W - 20, H - 44, "February 2026")

    # ── LEGEND ──
    ly = H - 64
    items = [
        (BLUE, "Traditional Automation"),
        (PURPLE, "AI-Powered"),
        (YELLOW, "Human-in-the-Loop"),
        (GREEN, "Actions / Outputs"),
    ]
    lx = 20
    for color, label in items:
        rrect(c, lx, ly - 3, 8, 8, 2, color)
        c.setFillColor(DARK)
        c.setFont("Helvetica", 6.5)
        c.drawString(lx + 11, ly - 1, label)
        lx += c.stringWidth(label, "Helvetica", 6.5) + 22

    # ── TRIGGER SOURCES (horizontal row) ──
    ty = H - 102
    sources = ["Webinar Signup", "LinkedIn Ads", "Demo Request", "Content Download"]
    sw = 100
    gap = 12
    total = len(sources) * sw + (len(sources) - 1) * gap
    sx_start = CX - total / 2

    for i, src in enumerate(sources):
        sx = sx_start + i * (sw + gap)
        rrect(c, sx, ty, sw, 22, 5, white, BLUE, 1)
        c.setFillColor(BLUE)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(sx + sw / 2, ty + 7, src)

    # Trigger label above
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(CX, ty + 30, "TRIGGER: New Lead Entry")

    # Merge lines from sources to center arrow
    merge_y = ty - 2
    for i in range(4):
        sx = sx_start + i * (sw + gap) + sw / 2
        c.saveState()
        c.setStrokeColor(ARROW_COLOR)
        c.setLineWidth(0.8)
        c.line(sx, ty, sx, merge_y)
        c.restoreState()
    # Horizontal merge line
    c.saveState()
    c.setStrokeColor(ARROW_COLOR)
    c.setLineWidth(0.8)
    c.line(sx_start + sw / 2, merge_y, sx_start + 3 * (sw + gap) + sw / 2, merge_y)
    c.restoreState()
    arrow_down(c, CX, merge_y, merge_y - 14)

    # ── STEP 1: Data Normalization ──
    s1_w = 440
    s1_h = 50
    s1_x = CX - s1_w / 2
    s1_y = merge_y - 14 - s1_h
    flowbox(c, s1_x, s1_y, s1_w, s1_h, "Data Normalization, Deduplication & Validation",
            ["Standardize fields → unified schema  |  Email MX record + domain validation",
             "Deduplicate: email exact match + company fuzzy match (Levenshtein ≤ 2)"],
            BLUE, "AUTOMATION")

    arrow_down(c, CX, s1_y, s1_y - 12)

    # ── STEP 2: AI Research ──
    s2_h = 58
    s2_y = s1_y - 12 - s2_h
    flowbox(c, s1_x, s2_y, s1_w, s2_h, "AI Research & Enrichment Agent (RAG-based)",
            ["Company intel: industry, size, funding, tech stack (via APIs + knowledge base)",
             "Intent signals: website visits, content engagement, competitor research",
             "Output → Structured JSON: company_profile, intent_signals, confidence_score"],
            PURPLE, "AI-POWERED")

    arrow_down(c, CX, s2_y, s2_y - 12)

    # ── STEP 3: AI Scoring ──
    s3_h = 50
    s3_y = s2_y - 12 - s3_h
    flowbox(c, s1_x, s3_y, s1_w, s3_h, "AI Lead Scoring Engine (0–100)",
            ["ICP Fit (0–40): industry, size, region, tech  |  Intent (0–35): web, content, demo signals",
             "Behavioral (0–25): email, webinar, pricing page  →  Score + Confidence output"],
            PURPLE, "AI-POWERED")

    arrow_down(c, CX, s3_y, s3_y - 14)

    # ── DECISION DIAMOND ──
    d_cy = s3_y - 14 - 20
    diamond(c, CX, d_cy, 180, 36, PURPLE_LIGHT, PURPLE)
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(CX, d_cy + 4, "Score ≥ 80 AND")
    c.drawCentredString(CX, d_cy - 6, "Confidence ≥ 0.75?")

    # ── BRANCH ARROWS ──
    left_x = CX - 140     # center of left branch
    right_x = CX + 140    # center of right branch
    branch_bw = 200        # branch box width

    # Left arrow from diamond
    c.saveState()
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.4)
    c.line(CX - 90, d_cy, left_x, d_cy)
    c.restoreState()
    arrow_down(c, left_x, d_cy, d_cy - 18, GREEN)

    # YES label
    rrect(c, left_x - 28, d_cy + 10, 56, 13, 4, HexColor("#DCFCE7"), GREEN)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(left_x, d_cy + 14, "YES — Hot Lead")

    # Right arrow from diamond
    c.saveState()
    c.setStrokeColor(YELLOW)
    c.setLineWidth(1.4)
    c.line(CX + 90, d_cy, right_x, d_cy)
    c.restoreState()
    arrow_down(c, right_x, d_cy, d_cy - 18, YELLOW)

    # NO label
    rrect(c, right_x - 28, d_cy + 10, 56, 13, 4, YELLOW_LIGHT, YELLOW)
    c.setFillColor(YELLOW)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(right_x, d_cy + 14, "NO — Nurture")

    # ── LEFT BRANCH: HOT LEAD ──
    lb_x = left_x - branch_bw / 2
    b_top = d_cy - 18

    # AI Outreach
    o_h = 46
    o_y = b_top - o_h
    flowbox(c, lb_x, o_y, branch_bw, o_h, "Personalized Outreach Generation",
            ["Email draft + LinkedIn message",
             "Company-specific value prop + social proof"],
            PURPLE, "AI-POWERED")

    arrow_down(c, left_x, o_y, o_y - 8)

    # Sales Review
    sr_h = 36
    sr_y = o_y - 8 - sr_h
    flowbox(c, lb_x, sr_y, branch_bw, sr_h, "Sales Rep Review & Edit",
            ["Review AI draft → personalize → approve & send"],
            YELLOW, "HUMAN REVIEW")

    arrow_down(c, left_x, sr_y, sr_y - 8)

    # Route to Rep
    rr_h = 36
    rr_y = sr_y - 8 - rr_h
    flowbox(c, lb_x, rr_y, branch_bw, rr_h, "Route to Sales Rep",
            ["Territory + industry expertise + capacity balancing"],
            GREEN, "ACTION")

    # ── RIGHT BRANCH: NURTURE ──
    rb_x = right_x - branch_bw / 2

    # Nurture
    n_h = 46
    n_y = b_top - n_h
    flowbox(c, rb_x, n_y, branch_bw, n_h, "Automated Nurture Workflow",
            ["Warm (60-79) / Cool (40-59) / Cold (<40)",
             "Drip email sequences + re-engagement monitor"],
            BLUE, "AUTOMATION")

    arrow_down(c, right_x, n_y, n_y - 8)

    # Low confidence human review
    lc_h = 36
    lc_y = n_y - 8 - lc_h
    flowbox(c, rb_x, lc_y, branch_bw, lc_h, "Low-Confidence Review Queue",
            ["Analyst reviews if confidence < 0.75"],
            YELLOW, "HUMAN REVIEW")

    # Re-score loop (dashed arrow back to scoring)
    loop_x = rb_x + branch_bw + 6
    c.saveState()
    c.setStrokeColor(PURPLE)
    c.setDash(3, 2)
    c.setLineWidth(1)
    c.line(right_x, lc_y, right_x, lc_y - 8)
    c.line(right_x, lc_y - 8, loop_x, lc_y - 8)
    c.line(loop_x, lc_y - 8, loop_x, s3_y + s3_h / 2)
    c.line(loop_x, s3_y + s3_h / 2, s1_x + s1_w + 2, s3_y + s3_h / 2)
    c.restoreState()
    # Loop label
    c.setFillColor(PURPLE)
    c.setFont("Helvetica-Oblique", 5.5)
    c.drawCentredString(loop_x + 2, lc_y - 8 + 40, "Re-score")

    # ── Converge arrows to FINAL ACTIONS ──
    final_y = rr_y - 16
    fa_w = 460
    fa_x = CX - fa_w / 2
    fa_h = 36

    # Arrow from left branch
    arrow_down(c, left_x, rr_y, final_y + fa_h)

    # Arrow from right branch to final
    c.saveState()
    c.setStrokeColor(ARROW_COLOR)
    c.setLineWidth(1)
    c.line(right_x, lc_y, right_x, final_y + fa_h + 6)
    # Horizontal connect to final box
    c.line(right_x, final_y + fa_h + 6, CX + fa_w / 2 - 10, final_y + fa_h + 6)
    c.restoreState()

    # ── FINAL ACTIONS BOX ──
    rrect(c, fa_x, final_y, fa_w, fa_h, 6, GREEN_LIGHT, GREEN, 1.3)

    # Left color bar
    c.saveState()
    c.setFillColor(GREEN)
    pp = c.beginPath()
    pp.roundRect(fa_x, final_y, 4, fa_h, 2)
    pp.close()
    c.drawPath(pp, fill=1, stroke=0)
    c.restoreState()

    badge(c, fa_x + 10, final_y + fa_h - 10, "FINAL ACTIONS", GREEN, white)

    # 4 columns
    cols = [
        ("Update CRM", "HubSpot/Salesforce sync"),
        ("Log Scoring Data", "Analytics & tracking"),
        ("Slack Notification", "#sales-leads alert"),
        ("Schedule Follow-ups", "Multi-channel cadence"),
    ]
    col_w = fa_w / 4
    for i, (title, sub) in enumerate(cols):
        cx_col = fa_x + 10 + i * col_w
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(cx_col, final_y + fa_h - 24, title)
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 6)
        c.drawString(cx_col, final_y + fa_h - 33, sub)

    # ── FOOTER ──
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 6)
    c.drawCentredString(CX, 14, "Page 1 of 3 — Workflow Design | AI-Powered Lead Management for Cleeng")

    c.save()
    print(f"Page 1 saved: {OUTPUT}")


if __name__ == "__main__":
    create_page1()
