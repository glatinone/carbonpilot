# Build the CarbonPilot submission deck (PPTX) in the Ledger design system.
# Reads submission/scripts/content.json. Run with the tools venv python.
import json
import re
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONTENT = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
OUT = ROOT / "CarbonPilot_submission_deck.pptx"

# ---- Ledger tokens ----------------------------------------------------------
PAPER = RGBColor(0xFB, 0xFA, 0xF7)
BAND = RGBColor(0xF6, 0xF5, 0xF1)
INK = RGBColor(0x14, 0x15, 0x0F)
SOFT = RGBColor(0x33, 0x33, 0x2E)
MUTED = RGBColor(0x6D, 0x6D, 0x63)
FAINT = RGBColor(0x9A, 0x9A, 0x8E)
RULE = RGBColor(0xE2, 0xE0, 0xD8)
STRONG = RGBColor(0xC9, 0xC6, 0xBA)
SAVE = RGBColor(0x1C, 0x4B, 0x36)
ALERT = RGBColor(0x9C, 0x5A, 0x12)

SERIF = "Source Serif 4"
SANS = "Inter"
MONO = "IBM Plex Mono"

SW, SH = Inches(13.333), Inches(7.5)
MX = Inches(0.9)          # side margin
CW = Inches(13.333 - 1.8) # content width

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]


def slide_new():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER
    return s


def _track(run, spc):
    run.font._rPr.set("spc", str(spc))


def txt(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, line_spacing=None,
        space_after=None, wrap=True, shrink=False):
    """runs: list of paragraphs; each paragraph = list of run dicts."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        if space_after is not None:
            p.space_after = Pt(space_after)
        for rd in para:
            r = p.add_run()
            r.text = rd.get("t", "")
            f = r.font
            f.name = rd.get("fam", SANS)
            f.size = Pt(rd.get("sz", 12))
            f.bold = rd.get("b", False)
            f.italic = rd.get("i", False)
            f.color.rgb = rd.get("c", INK)
            if rd.get("track"):
                _track(r, rd["track"])
    return box


def rule(slide, x, y, w, color=RULE, weight=1.0):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, Emu(int(weight * 12700)))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def kicker(slide, text, x, y, w=CW, color=FAINT, sz=10):
    return txt(slide, x, y, w, Inches(0.3),
               [[{"t": text.upper(), "fam": MONO, "sz": sz, "c": color, "track": 160}]])


def title(slide, text, y=Inches(0.78), sz=30, w=Inches(11.2)):
    return txt(slide, MX, y, w, Inches(1.1),
               [[{"t": text, "fam": SERIF, "sz": sz, "b": True, "c": INK}]],
               line_spacing=1.04)


def foot(slide, text, y=Inches(6.9)):
    rule(slide, MX, y, CW, RULE, 1.0)
    txt(slide, MX, y + Inches(0.08), CW, Inches(0.4),
        [[{"t": text, "fam": SANS, "sz": 9.5, "c": MUTED}]], line_spacing=1.2)


def chrome(slide, n, total):
    rule(slide, Emu(0), Emu(0), SW, INK, 2.5)
    txt(slide, MX, Inches(7.12), Inches(6), Inches(0.3),
        [[{"t": "CarbonPilot  ·  JAPAC AI Builder Cup 2026", "fam": MONO, "sz": 8,
           "c": FAINT, "track": 120}]])
    txt(slide, Inches(11.4), Inches(7.12), Inches(1.0), Inches(0.3),
        [[{"t": f"{n:02d} / {total:02d}", "fam": MONO, "sz": 8, "c": FAINT}]],
        align=PP_ALIGN.RIGHT)


def figure(slide, x, y, kick, value, unit, tone=None, vw=Inches(2.9), vsz=24):
    rule(slide, x, y, vw, INK, 2.0)
    kicker(slide, kick, x, y + Inches(0.14), vw, sz=8.5)
    c = {"save": SAVE, "alert": ALERT}.get(tone, INK)
    txt(slide, x, y + Inches(0.42), vw, Inches(0.5),
        [[{"t": value, "fam": MONO, "sz": vsz, "b": True, "c": c}]])
    txt(slide, x, y + Inches(0.98), vw, Inches(0.3),
        [[{"t": unit, "fam": MONO, "sz": 9.5, "c": MUTED}]])


def bullets(slide, items, x, y, w, num=True, sz=12.5, lead_sz=12.5):
    yy = y
    for i, it in enumerate(items):
        if isinstance(it, dict):
            lead, body = it["lead"], it["text"]
        else:
            lead, body = "", it
        rule(slide, x, yy, w, RULE, 1.0)
        runs = []
        if num:
            runs.append({"t": f"{i+1:02d}", "fam": MONO, "sz": 9, "c": FAINT})
            runs.append({"t": "   ", "fam": MONO, "sz": 9, "c": FAINT})
        if lead:
            runs.append({"t": lead + "  ", "fam": SANS, "sz": lead_sz, "b": True, "c": INK})
        if body:
            runs.append({"t": body, "fam": SANS, "sz": sz, "c": SOFT})
        txt(slide, x, yy + Inches(0.1), w, Inches(0.9), [runs], line_spacing=1.25)
        yy += Inches(0.62)
    return yy


def note(slide, text):
    ns = slide.notes_slide
    ns.notes_text_frame.text = text


def paragraph_from_md(md, base_sz=12.5):
    """Tiny markdown: **bold** and “smart quotes” only."""
    out = []
    for chunk in re.split(r"(\*\*.*?\*\*|\*.*?\*)", md):
        if not chunk:
            continue
        if chunk.startswith("**"):
            out.append({"t": chunk[2:-2], "fam": SANS, "sz": base_sz, "b": True, "c": INK})
        elif chunk.startswith("*") and chunk.endswith("*"):
            out.append({"t": chunk[1:-1], "fam": SANS, "sz": base_sz, "i": True, "c": SOFT})
        else:
            out.append({"t": chunk, "fam": SANS, "sz": base_sz, "c": SOFT})
    return out


def say(slide, text, x, y, w, sz=18):
    return txt(slide, x, y, w, Inches(1.6),
               [[{"t": text, "fam": SERIF, "sz": sz, "c": INK}]], line_spacing=1.28)


def loop(slide, steps, x, y, sz=15):
    runs = []
    for i, st in enumerate(steps):
        if i:
            runs.append({"t": "   →   ", "fam": MONO, "sz": sz, "c": STRONG})
        runs.append({"t": st, "fam": MONO, "sz": sz, "b": True, "c": INK})
    return txt(slide, x, y, Inches(10), Inches(0.4), [runs])


D = CONTENT["deck"]
TOTAL = len(D)

# ---------------------------------------------------------------- 1 · cover
d = D[0]
s = slide_new()
rule(s, Emu(0), Emu(0), SW, INK, 3.0)
kicker(s, d["kicker"], MX, Inches(1.05))
txt(s, MX, Inches(1.5), Inches(11), Inches(1.6),
    [[{"t": d["title"], "fam": SERIF, "sz": 64, "b": True, "c": INK}]])
txt(s, MX, Inches(2.75), Inches(9.0), Inches(1.4),
    [[{"t": d["lead"], "fam": SANS, "sz": 14.5, "c": SOFT}]], line_spacing=1.5)
rule(s, MX, Inches(4.35), CW, RULE, 1.0)
loop(s, d["loop"], MX, Inches(4.62), sz=16)
txt(s, MX, Inches(5.35), Inches(9), Inches(0.4),
    [[{"t": d["url"], "fam": MONO, "sz": 13, "c": MUTED}]])
foot(s, d["foot"], Inches(6.5))
note(s, d["notes"])
# ---------------------------------------------------------------- 2 · problem
d = D[1]
s = slide_new()
chrome(s, 2, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=31)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
bullets(s, d["bullets"], MX, Inches(2.35), Inches(6.9), sz=12.5)
xr = Inches(8.35)
kicker(s, "In the demo", xr, Inches(2.5))
figure(s, xr, Inches(2.85), d["figures"][0]["kicker"], d["figures"][0]["value"],
       d["figures"][0]["unit"])
figure(s, xr, Inches(4.35), d["figures"][1]["kicker"], d["figures"][1]["value"],
       d["figures"][1]["unit"])
say(s, d["say"], xr, Inches(5.7), Inches(4.0), sz=16.5)
foot(s, d["foot"])
note(s, d["notes"])
# ---------------------------------------------------------------- 3 · finding
d = D[2]
s = slide_new()
chrome(s, 3, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=29)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
fx = [MX, Inches(4.15), Inches(7.4), Inches(10.65)]
for i, f in enumerate(d["figures"]):
    figure(s, fx[i], Inches(2.45), f["kicker"], f["value"], f["unit"],
           tone=f.get("tone"), vw=Inches(2.6), vsz=26)
bullets(s, d["bullets"], MX, Inches(4.35), CW)
foot(s, d["foot"])
note(s, d["notes"])
# ---------------------------------------------------------------- 4 · solution
d = D[3]
s = slide_new()
chrome(s, 4, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=32)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
steps = d["steps"]
for i, st in enumerate(steps):
    col = i % 2
    row = i // 2
    x = MX + Inches(5.98) * col
    y = Inches(2.45) + Inches(2.05) * row
    rule(s, x, y, Inches(5.55), RULE, 1.0)
    txt(s, x, y + Inches(0.12), Inches(5.5), Inches(0.55),
        [[{"t": f"{i+1:02d}", "fam": MONO, "sz": 9, "c": FAINT}],
         [{"t": st["name"], "fam": SERIF, "sz": 19, "b": True, "c": INK}]])
    txt(s, x, y + Inches(0.82), Inches(5.3), Inches(1.0),
        [[{"t": st["text"], "fam": SANS, "sz": 11.5, "c": SOFT}]], line_spacing=1.35)
foot(s, d["foot"] if "foot" in d else "Six screens, one loop: each stage is its own engine and its own screen.")
note(s, d["notes"])
# ---------------------------------------------------------------- 5 · rule
d = D[4]
s = slide_new()
chrome(s, 5, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=31)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
xc = [MX, Inches(7.05)]
for i, (leadk, body) in enumerate([(d["left_lead"], d["left"]), (d["right_lead"], d["right"])]):
    x = xc[i]
    txt(s, x, Inches(2.45), Inches(5.5), Inches(0.5),
        [[{"t": leadk, "fam": SERIF, "sz": 17, "b": True, "c": INK}]])
    rule(s, x, Inches(3.05), Inches(5.4), INK, 2.0)
    txt(s, x, Inches(3.25), Inches(5.35), Inches(3.2),
        [[{"t": body, "fam": SANS, "sz": 13, "c": SOFT}]], line_spacing=1.5)
note(s, d["notes"])
# ---------------------------------------------------------------- 6 · demo
d = D[5]
s = slide_new()
chrome(s, 6, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=27)
txt(s, MX, Inches(2.0), Inches(10.5), Inches(0.4),
    [[{"t": d["lead"], "fam": SANS, "sz": 12.5, "c": MUTED}]])
fx = [MX, Inches(3.75), Inches(6.6), Inches(9.45)]
for i, f in enumerate(d["figures"]):
    figure(s, fx[i], Inches(2.55), f["kicker"], f["value"], f["unit"],
           tone=f.get("tone"), vw=Inches(2.9), vsz=23)
rows = d["table"]["rows"]
kicker(s, d["table"]["caption"], MX, Inches(4.15))
yy = Inches(4.45)
for i, (lab, val) in enumerate(rows):
    rule(s, MX, yy, Inches(6.1), RULE, 1.0)
    txt(s, MX, yy + Inches(0.1), Inches(5.4), Inches(0.4),
        [[{"t": lab, "fam": SANS, "sz": 12, "c": INK}]])
    txt(s, Inches(5.9), yy + Inches(0.1), Inches(1.1), Inches(0.4),
        [[{"t": val, "fam": MONO, "sz": 12, "b": True, "c": SAVE}]], align=PP_ALIGN.RIGHT)
    yy += Inches(0.5)
say(s, d["say"], Inches(7.6), Inches(4.3), Inches(4.8), sz=15)
foot(s, d["foot"])
note(s, d["notes"])
# ---------------------------------------------------------------- 7 · tech
d = D[6]
s = slide_new()
chrome(s, 7, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=27)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
xc = [MX, Inches(7.05)]
for i, items in enumerate([d["left"], d["right"]]):
    bullets(s, items, xc[i], Inches(2.4), Inches(5.4), num=False, sz=11.5)
foot(s, d["foot"] if "foot" in d else "Stated boundaries, not avoided ones — the honesty a judge should hear before the room asks.")
note(s, d["notes"])
# ---------------------------------------------------------------- 8 · verified
d = D[7]
s = slide_new()
chrome(s, 8, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=28)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
bullets(s, d["bullets"], MX, Inches(2.4), CW, sz=13)
foot(s, d["foot"])
note(s, d["notes"])
# ---------------------------------------------------------------- 9 · market
d = D[8]
s = slide_new()
chrome(s, 9, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=32)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
rows = d["table"]["rows"]
kicker(s, d["table"]["caption"], MX, Inches(2.35))
yy = Inches(2.65)
for i, (a, b) in enumerate(rows):
    rule(s, MX, yy, Inches(6.4), RULE, 1.0)
    last = i == len(rows) - 1
    txt(s, MX, yy + Inches(0.09), Inches(3.9), Inches(0.4),
        [[{"t": a, "fam": MONO if last else SANS, "sz": 11.5 if last else 12.5,
           "c": MUTED if last else INK, "b": last}]])
    txt(s, Inches(4.35), yy + Inches(0.09), Inches(3.0), Inches(0.4),
        [[{"t": b, "fam": MONO if last else SANS, "sz": 11.5 if last else 12.5,
           "c": SAVE if last else INK, "b": last}]])
    yy += Inches(0.52)
say(s, d["say"], Inches(7.7), Inches(2.55), Inches(4.7), sz=13.5)
rule(s, Inches(7.7), Inches(5.35), Inches(4.7), INK, 2.0)
txt(s, Inches(7.7), Inches(5.55), Inches(4.7), Inches(1.0),
    [[{"t": d["close"], "fam": SERIF, "sz": 18, "b": True, "c": INK}]], line_spacing=1.25)
foot(s, d["foot"])
note(s, d["notes"])
# ---------------------------------------------------------------- 10 · impact
d = D[9]
s = slide_new()
chrome(s, 10, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=31)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
bullets(s, d["bullets"], MX, Inches(2.4), Inches(7.0), sz=12.5)
xr = Inches(8.5)
fx = [xr, xr, xr]
fy = [Inches(2.55), Inches(4.15), Inches(5.75)]
for i, f in enumerate(d["figures"]):
    figure(s, fx[i], fy[i], f["kicker"], f["value"], f["unit"], vw=Inches(3.4), vsz=26)
note(s, d["notes"])
# ---------------------------------------------------------------- 11 · roadmap
d = D[10]
s = slide_new()
chrome(s, 11, TOTAL)
kicker(s, d["kicker"], MX, Inches(0.55))
title(s, d["title"], Inches(0.85), sz=32)
rule(s, MX, Inches(2.1), CW, RULE, 1.0)
bullets(s, d["bullets"], MX, Inches(2.4), CW, sz=12.5, lead_sz=13)
foot(s, d["foot"])
note(s, d["notes"])
# ---------------------------------------------------------------- 12 · closing
d = D[11]
s = slide_new()
rule(s, Emu(0), Emu(0), SW, INK, 3.0)
kicker(s, d["kicker"], MX, Inches(1.7))
txt(s, MX, Inches(2.15), Inches(11), Inches(1.2),
    [[{"t": d["title"], "fam": SERIF, "sz": 44, "b": True, "c": INK}]])
loop(s, d["loop"], MX, Inches(3.75), sz=16)
txt(s, MX, Inches(4.45), Inches(9), Inches(0.4),
    [[{"t": d["url"], "fam": MONO, "sz": 13, "c": MUTED}]])
txt(s, MX, Inches(5.0), Inches(9), Inches(0.9),
    [[{"t": d["say"], "fam": SANS, "sz": 13, "c": SOFT}]], line_spacing=1.4)
foot(s, d["foot"], Inches(6.5))
note(s, d["notes"])

prs.save(OUT)
print(f"Saved {OUT} with {TOTAL} slides")
