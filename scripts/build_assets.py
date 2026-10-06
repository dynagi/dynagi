"""Generate the SVG panels used by README.md.

GitHub strips CSS and JavaScript from READMEs, so every Pokedex panel is a
self-contained SVG drawn with the portfolio's design tokens. Edit the data
below, then run:

    python scripts/build_assets.py

Panels are 400px (two-up), 268px (three-up) or 196px (four-up) wide so they sit
side by side on desktop and wrap to a single column on mobile.
"""

from html import escape
from pathlib import Path
import random
import textwrap

OUT = Path(__file__).resolve().parent.parent / "assets"

# ── Design tokens (mirrors the portfolio's :root) ────────────────────────────
VOID, ABYSS, SOLID, LINE = "#07080f", "#0b0d18", "#141828", "#23283b"
RED, RED_HI, RED_LO = "#ee2b1f", "#ff5a4d", "#a60d06"
HOLO, HOLO_SOFT, GOLD = "#45e6d4", "#7bf3e6", "#f5c451"
INK, MUTED, MUTED_2 = "#eef1fa", "#8b91a7", "#5c627a"

DISP = "Sora,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
BODY = "Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ── Content (facts match the portfolio) ──────────────────────────────────────
PROJECTS = [
    dict(id="001", slug="pathfinder", name="PathFinder", sprite="vision",
         ball=("#5aa9ff", "#2f6bdb", "#1f4aa0"), rare=True,
         subtitle="AI Assistive System · Visually Impaired",
         category="Computer Vision", period="Feb 2025 — May 2025",
         types=["YOLO", "MiDaS", "KCF", "Python", "OpenCV"]),
    dict(id="002", slug="tennis-analysis", name="Tennis Analysis", sprite="tennis",
         ball=("#7ee06a", "#35b54a", "#1f7d33"), rare=True,
         subtitle="Match Analytics with Computer Vision",
         category="Computer Vision", period="Jan 2025 — Apr 2025",
         types=["YOLOv8", "CNN", "OpenCV", "Python"]),
    dict(id="003", slug="heart-risk-measure", name="Heart Risk Measure", sprite="heart",
         ball=("#c98bff", "#8a3ff0", "#5e1fb0"), rare=False,
         subtitle="ML Heart-Disease Prediction",
         category="Machine Learning", period="Jan 2024 — Feb 2024",
         types=["Python", "scikit-learn", "Pandas", "ML"]),
    dict(id="004", slug="onecart", name="OneCART", sprite="cart",
         ball=("#ffd25a", "#f0a32f", "#b9741f"), rare=False,
         subtitle="Real-time MERN E-commerce",
         category="Full-Stack", period="Mar 2023 — May 2023",
         types=["React", "Node.js", "Express", "MongoDB", "ZEGOCLOUD"]),
    dict(id="005", slug="secure-exam", name="Secure Exam", sprite="shield",
         ball=("#ff7a6a", "#e0332f", "#8f1613"), rare=True,
         subtitle="Exam Platform with Center Custody & Live Alerts",
         category="Full-Stack · Security", period="2025",
         types=["React", "Node.js", "MongoDB", "Claude API", "Socket.io", "QR Codes"]),
    dict(id="006", slug="secure-rag", name="Secure RAG", sprite="rag",
         ball=("#8bd6c6", "#2fb39f", "#146e64"), rare=False,
         subtitle="Semantic RAG Pipeline over ChromaDB",
         category="AI / LLM", period="2025",
         types=["LangGraph", "ChromaDB", "LangChain", "Streamlit", "Python"]),
]

# Skill levels (1-5) are the same self-ratings shown on the portfolio.
SKILLS = [
    dict(slug="psychic", type="PSYCHIC TYPE", name="AI & Machine Learning", color="#34e7d8",
         items=[("Python", 5), ("OpenCV", 5), ("YOLO", 4), ("TensorFlow", 4),
                ("PyTorch", 4), ("CNN", 4), ("LLMs / RAG", 3)]),
    dict(slug="electric", type="ELECTRIC TYPE", name="Web Development", color="#ff5ad0",
         items=[("React", 4), ("Next.js", 4), ("Node.js", 4), ("Express.js", 4),
                ("MongoDB", 4), ("Tailwind CSS", 4), ("TypeScript", 3)]),
    dict(slug="steel", type="STEEL TYPE", name="Tools & Platforms", color="#ffb43e",
         items=[("Git", 4), ("Docker", 3), ("Linux", 4), ("AWS", 3),
                ("Firebase", 3), ("VS Code", 5), ("MySQL", 4)]),
]

TRAINER_ID = [
    ("HANDLE", "@dynagi"),
    ("CLASS", "AI & CV ENGINEER"),
    ("REGION", "BANGALORE, IN"),
    ("SPECIALTY", "VISION · LLMs · FULL-STACK"),
    ("BASE", "MICROLAND · NETWORK ENG."),
    ("TRAINED AT", "MIT-WPU · B.TECH CSE"),
]

JOURNEY = [  # oldest first
    dict(slug="1", period="2021 — 2025", role="B.Tech, Computer Science",
         org="MIT World Peace University, Pune",
         text="Starter route. Graduated with an 8.61 CGPA; foundations in "
              "DSA, databases, operating systems, networks and ML."),
    dict(slug="2", period="JUL 2024 — JAN 2025", role="Software Intern",
         org="M3 Technology",
         text="First gym. Wrote SQL validation and reporting tooling that "
              "made reporting pipelines faster and more accurate."),
    dict(slug="3", period="JAN 2026 — PRESENT", role="Network Engineer",
         org="Microland", now=True,
         text="Current route. Levelling up in IT infrastructure, cloud and "
              "system administration."),
]

STATS = [
    ("6", "FIELD ENTRIES", RED_HI),
    ("2", "PUBLICATIONS", GOLD),
    ("2", "CERTIFICATIONS", HOLO),
    ("8.61", "CGPA · B.TECH CSE", INK),
]

BADGES = [
    dict(slug="paper-heart", kind="PUBLICATION", glyph="paper",
         title="ML Models for Heart Disease Prediction", sub="Research paper · Aug 2024"),
    dict(slug="paper-tennis", kind="PUBLICATION", glyph="paper",
         title="Tennis Analytics with ML & Computer Vision", sub="Research paper · Jun 2025"),
    dict(slug="oci-ai", kind="CERTIFICATION", glyph="check",
         title="OCI 2025 — AI Foundations Associate", sub="Oracle Cloud · Aug 2025"),
    dict(slug="oci-ds", kind="CERTIFICATION", glyph="check",
         title="OCI 2025 — Data Science Professional", sub="Oracle Cloud · Sep 2025"),
]

LINKS = [
    dict(slug="email", tag="TRANSMIT", label="Email", primary=True),
    dict(slug="linkedin", tag="CONNECT", label="LinkedIn"),
    dict(slug="portfolio", tag="LINK", label="Portfolio"),
    dict(slug="resume", tag="RECORD", label="Résumé"),
]

SPRITES = {  # line icons from the portfolio's Pokedex entries (120x120 box)
    "vision": '<path d="M10 60c14-26 86-26 100 0-14 26-86 26-100 0Z"/><circle cx="60" cy="60" r="16"/><circle cx="60" cy="60" r="4.5" fill="#7bf3e6"/><path d="M60 16v-8M60 112v-8M16 60H8M112 60h-8" opacity=".55"/>',
    "tennis": '<circle cx="64" cy="58" r="24"/><path d="M46 41c12 7 22 18 36 38"/><path d="M14 92c20-7 40-3 60 12M26 22c8 12 11 21 28 28" opacity=".5"/>',
    "heart": '<path d="M60 98C28 74 16 58 16 42a21 21 0 0 1 44-8 21 21 0 0 1 44 8c0 16-12 32-44 56Z"/><path d="M26 58h14l6-13 9 24 7-17 5 6h16" stroke="#ffffff"/>',
    "cart": '<path d="M16 24h14l11 50h46l11-34H38"/><circle cx="52" cy="94" r="7"/><circle cx="86" cy="94" r="7"/>',
    "shield": '<path d="M60 12l34 13v29c0 25-15 42-34 50-19-8-34-25-34-50V25Z"/><circle cx="60" cy="55" r="8"/><path d="M60 63v13" opacity=".7"/>',
    "rag": '<path d="M32 12h38l18 18v78H32Z"/><path d="M70 12v18h18" opacity=".6"/><circle cx="56" cy="66" r="15"/><path d="M67 77l15 15"/>',
}

# ── Drawing helpers ──────────────────────────────────────────────────────────
MOTION_GUARD = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def svg(w, h, body, title, css=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>'
        f"<style>{css}{MOTION_GUARD}</style>{body}</svg>\n"
    )


def text(x, y, s, size, fill=INK, font=BODY, weight=400, anchor="start", spacing=0, extra=""):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}"{ls}{extra}>{escape(s)}</text>'
    )


def mono_w(s, size):
    return len(s) * size * 0.62


def panel(w, h, uid, rx=20, nebula=True, grid=False):
    """Dark portfolio surface: void fill, hairline border, red + holo nebula."""
    out = [
        f'<defs><clipPath id="{uid}c"><rect width="{w}" height="{h}" rx="{rx}"/></clipPath>'
        f'<radialGradient id="{uid}r" cx="12%" cy="0%" r="75%"><stop offset="0" stop-color="{RED}" stop-opacity=".30"/>'
        f'<stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="{uid}h" cx="95%" cy="100%" r="75%"><stop offset="0" stop-color="{HOLO}" stop-opacity=".20"/>'
        f'<stop offset="1" stop-color="{HOLO}" stop-opacity="0"/></radialGradient>'
        f'<pattern id="{uid}g" width="28" height="28" patternUnits="userSpaceOnUse">'
        f'<path d="M28 0H0V28" fill="none" stroke="#ffffff" stroke-opacity=".045"/></pattern></defs>'
        f'<g clip-path="url(#{uid}c)"><rect width="{w}" height="{h}" fill="{ABYSS}"/>'
    ]
    if grid:
        out.append(f'<rect width="{w}" height="{h}" fill="url(#{uid}g)"/>')
    if nebula:
        out.append(f'<rect width="{w}" height="{h}" fill="url(#{uid}r)"/><rect width="{w}" height="{h}" fill="url(#{uid}h)"/>')
    out.append("</g>")
    out.append(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="none" stroke="{LINE}"/>')
    return "".join(out)


def ball(cx, cy, r, colors, uid, cls=""):
    """The portfolio's capsule: glossy coloured top, pearl bottom, dark band."""
    hi, mid, lo = colors
    c = f' class="{cls}"' if cls else ""
    return (
        f'<defs><linearGradient id="{uid}t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{hi}"/>'
        f'<stop offset=".45" stop-color="{mid}"/><stop offset="1" stop-color="{lo}"/></linearGradient>'
        f'<linearGradient id="{uid}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef1f8"/>'
        f'<stop offset=".58" stop-color="#cfd5e6"/><stop offset="1" stop-color="#aab1c8"/></linearGradient>'
        f'<radialGradient id="{uid}k" cx="38%" cy="32%" r="70%"><stop offset="0" stop-color="#ffffff"/>'
        f'<stop offset=".55" stop-color="#d4d9e8"/><stop offset="1" stop-color="#8c93ab"/></radialGradient>'
        f'<clipPath id="{uid}o"><circle r="{r}"/></clipPath></defs>'
        f'<g transform="translate({cx} {cy})"><g{c}>'
        f'<ellipse cy="{r * 1.14:.1f}" rx="{r * .72:.1f}" ry="{r * .1:.1f}" fill="#000" opacity=".45"/>'
        f'<g clip-path="url(#{uid}o)">'
        f'<rect x="{-r}" y="{-r}" width="{2 * r}" height="{r}" fill="url(#{uid}t)"/>'
        f'<rect x="{-r}" y="0" width="{2 * r}" height="{r}" fill="url(#{uid}b)"/>'
        f'<ellipse cx="{-r * .34:.1f}" cy="{-r * .52:.1f}" rx="{r * .34:.1f}" ry="{r * .2:.1f}" fill="#fff" opacity=".42" transform="rotate(-24 {-r * .34:.1f} {-r * .52:.1f})"/>'
        f'<rect x="{-r}" y="{-r * .13:.1f}" width="{2 * r}" height="{r * .26:.1f}" fill="#090a12"/>'
        f"</g>"
        f'<circle r="{r * .3:.1f}" fill="#090a12"/><circle r="{r * .235:.1f}" fill="#e7ebf5"/>'
        f'<circle r="{r * .16:.1f}" fill="url(#{uid}k)" stroke="#060710" stroke-width="{max(1, r * .03):.1f}"/>'
        f"</g></g>"
    )


def chips(x, y, labels, max_w, size=9.5, fill="#dffaf3", stroke=HOLO, row_h=22):
    """Mono pill chips that wrap inside max_w. Returns (svg, height used)."""
    out, cx, cy = [], x, y
    for label in labels:
        w = mono_w(label, size) + 16
        if cx + w > x + max_w and cx > x:
            cx, cy = x, cy + row_h
        out.append(
            f'<rect x="{cx:.1f}" y="{cy}" width="{w:.1f}" height="17" rx="8.5" fill="{stroke}" fill-opacity=".08" '
            f'stroke="{stroke}" stroke-opacity=".4"/>'
            + text(f"{cx + w / 2:.1f}", cy + 12, label, size, fill, MONO, 500, "middle")
        )
        cx += w + 6
    return "".join(out), cy - y + 17


def write(name, content):
    (OUT / name).write_text(content, encoding="utf-8")


# ── Panels ───────────────────────────────────────────────────────────────────
def hero_trainer():
    """Left hero panel: capsule, name and the three types from the type chart."""
    w, h = 400, 300
    rnd = random.Random(24)
    stars = "".join(
        f'<circle cx="{rnd.randint(8, w - 8)}" cy="{rnd.randint(8, h - 8)}" r="{rnd.choice([.6, .8, 1.1])}" '
        f'fill="#fff" opacity="{rnd.choice([.25, .4, .6])}"{" class=\"tw\"" if i % 4 == 0 else ""}/>'
        for i in range(46)
    )
    pills, x = "", 0
    widths = [mono_w(g["type"].split()[0], 9) + 9 * 1.4 + 22 for g in SKILLS]
    x = 200 - (sum(widths) + 8 * (len(widths) - 1)) / 2
    for g, pw in zip(SKILLS, widths):
        label = g["type"].split()[0]
        pills += (
            f'<rect x="{x:.1f}" y="254" width="{pw:.1f}" height="20" rx="10" fill="{g["color"]}" fill-opacity=".1" '
            f'stroke="{g["color"]}" stroke-opacity=".55"/>'
            + text(f"{x + pw / 2:.1f}", 267.5, label, 9, g["color"], MONO, 700, "middle", 1.4)
        )
        x += pw + 8
    body = (
        panel(w, h, "he", grid=True) + stars
        + f'<circle cx="200" cy="88" r="70" fill="{HOLO}" opacity=".07" class="glow"/>'
        + ball(200, 88, 50, (RED_HI, RED, RED_LO), "heb", "float")
        + text(200, 176, "TRAINER'S POKÉDEX · GITHUB EDITION", 9.5, HOLO, MONO, 500, "middle", 2.4)
        + text(200, 212, "SHIVAM UPADHYAY", 29, "#fff", DISP, 800, "middle", .6)
        + text(200, 236, "AI · COMPUTER VISION · FULL-STACK", 10.5, MUTED, MONO, 500, "middle", 1.8)
        + pills
    )
    css = (
        ".float{animation:f 5s ease-in-out infinite}@keyframes f{50%{transform:translateY(-6px)}}"
        ".tw{animation:t 3.2s ease-in-out infinite}@keyframes t{50%{opacity:.05}}"
        ".glow{animation:g 5s ease-in-out infinite}@keyframes g{50%{opacity:.14}}"
    )
    write("hero-trainer.svg", svg(w, h, body, "Trainer's Pokédex, GitHub edition — Shivam Upadhyay. AI, computer vision and full-stack.", css))


def trainer_id():
    """Right hero panel: a status readout on the Pokedex scanning screen."""
    w, h = 400, 300
    rows = "".join(
        f'<path d="M40 {96 + i * 31}H360" stroke="{HOLO}" stroke-opacity=".1"/>'
        + text(40, 85 + i * 31, k, 9.5, "#5fa89d", MONO, 500, spacing=1.8)
        + text(140, 85 + i * 31, v, 11.5, "#dffaf3", MONO, 500, spacing=.4)
        for i, (k, v) in enumerate(TRAINER_ID)
    )
    y = 85 + len(TRAINER_ID) * 31
    body = (
        f'<defs><linearGradient id="tidv" x1="0" y1="0" x2=".5" y2="1"><stop offset="0" stop-color="#e0241b"/>'
        f'<stop offset="1" stop-color="#a8120c"/></linearGradient>'
        f'<linearGradient id="tisc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a1f1c"/>'
        f'<stop offset="1" stop-color="#06100f"/></linearGradient>'
        f'<radialGradient id="tiln" cx="36%" cy="32%" r="75%"><stop offset="0" stop-color="#bfe9ff"/>'
        f'<stop offset=".55" stop-color="#3aa0e6"/><stop offset="1" stop-color="#155a9c"/></radialGradient>'
        f'<clipPath id="tic"><rect x="14" y="48" width="372" height="238" rx="13"/></clipPath></defs>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="22" fill="url(#tidv)" stroke="#ff6a5e"/>'
        f'<path d="M22 1.5H{w - 22}" stroke="#fff" stroke-opacity=".3" stroke-linecap="round"/>'
        f'<circle cx="34" cy="26" r="13" fill="url(#tiln)" stroke="#f2f4fa" stroke-width="2.5"/>'
        f'<circle cx="62" cy="19" r="4.5" fill="#ff5a52" class="led"/>'
        f'<circle cx="77" cy="19" r="4.5" fill="#ffd84d" class="led l2"/>'
        f'<circle cx="92" cy="19" r="4.5" fill="#57e08a" class="led l3"/>'
        + text(w - 20, 30, "TRAINER ID", 10, "#ffe9c2", MONO, 700, "end", 2.2)
        + f'<rect x="14" y="48" width="372" height="238" rx="13" fill="url(#tisc)" stroke="#0b0c12" stroke-width="3"/>'
        + rows
        + text(40, y, "STATUS", 9.5, "#5fa89d", MONO, 500, spacing=1.8)
        + f'<circle cx="145" cy="{y - 4}" r="4" fill="#57e08a" class="led"/>'
        + text(157, y, "OPEN TO TEAM-UPS", 11.5, "#9affe6", MONO, 700, spacing=.4)
        + f'<g clip-path="url(#tic)"><rect x="14" y="46" width="372" height="2" fill="{HOLO}" opacity=".35" class="scan"/></g>'
    )
    css = (
        ".led{animation:l 2.4s ease-in-out infinite}.l2{animation-delay:.4s}.l3{animation-delay:.8s}@keyframes l{50%{opacity:.35}}"
        ".scan{animation:s 5s linear infinite}@keyframes s{to{transform:translateY(240px)}}"
    )
    label = "; ".join(f"{k.title()}: {v}" for k, v in TRAINER_ID)
    write("trainer-id.svg", svg(w, h, body, f"Trainer ID — {label}; Status: open to team-ups", css))


def divider():
    w, h = 840, 28
    body = (
        f'<defs><linearGradient id="dl" x1="0" x2="1"><stop offset="0" stop-color="{RED}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{RED}"/></linearGradient>'
        f'<linearGradient id="dr" x1="0" x2="1"><stop offset="0" stop-color="{HOLO}"/>'
        f'<stop offset="1" stop-color="{HOLO}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x="60" y="13" width="336" height="2" rx="1" fill="url(#dl)"/>'
        f'<rect x="444" y="13" width="336" height="2" rx="1" fill="url(#dr)"/>'
        + ball(420, 14, 11, (RED_HI, RED, RED_LO), "dv").replace('<ellipse cy="12.5" rx="7.9" ry="1.1" fill="#000" opacity=".45"/>', "")
    )
    write("divider.svg", svg(w, h, body, "Section divider"))


def stat_tiles():
    w, h = 196, 92
    for i, (value, label, color) in enumerate(STATS):
        body = (
            panel(w, h, f"st{i}", rx=16, nebula=False)
            + f'<rect x="18" y="20" width="3" height="52" rx="1.5" fill="{color}"/>'
            + text(34, 52, value, 32, "#fff", DISP, 800, spacing=-.5)
            + text(34, 72, label, 9, MUTED, MONO, 500, spacing=1.6)
        )
        write(f"stat-{i + 1}.svg", svg(w, h, body, f"{value} {label.title()}"))


def holo_columns():
    w, row = 268, 33
    for g in SKILLS:
        c = g["color"]
        n = len(g["items"])
        h = 156 + n * row
        rows = ""
        for i, (name, level) in enumerate(g["items"]):
            y = 138 + i * row
            segs = "".join(
                f'<rect x="{168 + s * 15}" y="{y + 10}" width="11" height="6" rx="2" fill="{c}" '
                f'fill-opacity="{1 if s < level else .14}" stroke="{c}" stroke-opacity="{.9 if s < level else .3}" stroke-width=".8"/>'
                for s in range(5)
            )
            rows += (
                f'<g class="hc" style="animation-delay:{i * .12:.2f}s">'
                f'<rect x="20" y="{y}" width="228" height="26" rx="9" fill="{c}" fill-opacity=".07" stroke="{c}" stroke-opacity=".28"/>'
                + text(32, y + 17, name, 11.5, "#f4ffff", MONO, 500) + segs + "</g>"
            )
        tw = mono_w(g["type"], 8.5) + 8 * 1.6 + 20
        body = (
            panel(w, h, g["slug"], nebula=False)
            + f'<defs><linearGradient id="{g["slug"]}bm" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c}" stop-opacity=".5"/>'
            f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="M134 96L20 {h - 18}H248Z" fill="url(#{g["slug"]}bm)" opacity=".16" class="beam"/>'
            f'<rect x="{134 - tw / 2:.1f}" y="18" width="{tw:.1f}" height="18" rx="9" fill="{c}" fill-opacity=".12" stroke="{c}" stroke-opacity=".5"/>'
            + text(134, 30.5, g["type"], 8.5, c, MONO, 700, "middle", 1.6)
            + text(134, 58, g["name"], 14.5, "#fff", DISP, 700, "middle")
            + f'<circle cx="134" cy="96" r="28" fill="{c}" opacity=".14"/>'
            + ball(134, 96, 20, (c, c, c), g["slug"] + "b")
            + rows
        )
        css = (
            ".hc{animation:hc 6s ease-in-out infinite}@keyframes hc{0%,100%{opacity:1}6%{opacity:.55}12%{opacity:1}}"
            ".beam{animation:bm 4s ease-in-out infinite}@keyframes bm{50%{opacity:.28}}"
        )
        skills = ", ".join(f"{n} {l}/5" for n, l in g["items"])
        write(f"type-{g['slug']}.svg", svg(w, h, body, f"{g['type'].title()} · {g['name']}: {skills}", css))


def capsules():
    w, h = 400, 176
    for p in PROJECTS:
        uid = "c" + p["id"]
        sub = textwrap.wrap(p["subtitle"], 40)
        y = 72
        sub_svg = ""
        for line in sub:
            sub_svg += text(128, y, line, 11.5, MUTED, BODY)
            y += 15
        cw = mono_w(p["category"].upper(), 8.5) + len(p["category"]) * .8 + 18
        cat = (
            f'<rect x="128" y="{y - 4}" width="{cw:.1f}" height="18" rx="9" fill="none" stroke="{HOLO}" stroke-opacity=".4"/>'
            + text(137, y + 8.5, p["category"].upper(), 8.5, HOLO, MONO, 500, spacing=.8)
        )
        chip_svg, _ = chips(128, y + 22, p["types"], 256, size=9, fill="#cfd5e6", stroke="#8b91a7")
        body = (
            panel(w, h, uid)
            + f'<circle cx="66" cy="84" r="50" fill="{p["ball"][0]}" opacity=".08"/>'
            + ball(66, 84, 38, p["ball"], uid + "b", "wob")
            + text(128, 30, f"No. {p['id']}", 10, MUTED, MONO, 500, spacing=2)
            + (text(376, 30, "★ RARE", 9, GOLD, MONO, 700, "end", 1.5) if p["rare"] else "")
            + text(128, 54, p["name"], 21, "#fff", DISP, 700)
            + sub_svg + cat + chip_svg
            + text(66, 158, p["period"], 8.5, MUTED_2, MONO, 500, "middle", .4)
        )
        css = ".wob{animation:w 6s ease-in-out infinite}@keyframes w{0%,84%,100%{transform:rotate(0)}88%{transform:rotate(-9deg)}92%{transform:rotate(7deg)}96%{transform:rotate(-3deg)}}"
        write(f"entry-{p['id']}-{p['slug']}.svg",
              svg(w, h, body, f"No. {p['id']} {p['name']} — {p['subtitle']}. {p['category']}. {', '.join(p['types'])}.", css))


def devices():
    """Rare encounters: the red Pokedex device with its scanning screen."""
    w, h = 600, 246
    for p in (p for p in PROJECTS if p["rare"]):
        uid = "d" + p["id"]
        sub = textwrap.wrap(p["subtitle"].upper(), 36)
        y = 128
        sub_svg = ""
        for line in sub:
            sub_svg += text(214, y, line, 10.5, HOLO, MONO, 500, spacing=.6)
            y += 15
        chip_svg, _ = chips(214, y + 14, p["types"], 350, size=9.5)
        body = (
            f'<defs><linearGradient id="{uid}dv" x1="0" y1="0" x2=".5" y2="1"><stop offset="0" stop-color="#e0241b"/>'
            f'<stop offset="1" stop-color="#a8120c"/></linearGradient>'
            f'<linearGradient id="{uid}sc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a1f1c"/>'
            f'<stop offset="1" stop-color="#06100f"/></linearGradient>'
            f'<radialGradient id="{uid}vi" cx="50%" cy="0%" r="110%"><stop offset="0" stop-color="#0d2a26"/>'
            f'<stop offset="1" stop-color="#061312"/></radialGradient>'
            f'<radialGradient id="{uid}ln" cx="36%" cy="32%" r="75%"><stop offset="0" stop-color="#bfe9ff"/>'
            f'<stop offset=".55" stop-color="#3aa0e6"/><stop offset="1" stop-color="#155a9c"/></radialGradient>'
            f'<clipPath id="{uid}vc"><rect x="30" y="64" width="160" height="130" rx="10"/></clipPath></defs>'
            # device body
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="22" fill="url(#{uid}dv)" stroke="#ff6a5e"/>'
            f'<path d="M22 1.5H{w - 22}" stroke="#fff" stroke-opacity=".3" stroke-linecap="round"/>'
            # lights
            f'<circle cx="34" cy="27" r="14" fill="url(#{uid}ln)" stroke="#f2f4fa" stroke-width="2.5"/>'
            f'<circle cx="64" cy="20" r="5" fill="#ff5a52" class="led"/>'
            f'<circle cx="80" cy="20" r="5" fill="#ffd84d" class="led l2"/>'
            f'<circle cx="96" cy="20" r="5" fill="#57e08a" class="led l3"/>'
            + text(w - 20, 31, "★ RARE ENCOUNTER", 9.5, "#ffe9c2", MONO, 700, "end", 1.8)
            # screen
            + f'<rect x="14" y="48" width="{w - 28}" height="162" rx="13" fill="url(#{uid}sc)" stroke="#0b0c12" stroke-width="3"/>'
            f'<rect x="30" y="64" width="160" height="130" rx="10" fill="url(#{uid}vi)" stroke="{HOLO}" stroke-opacity=".25"/>'
            f'<g transform="translate(64 80) scale(.77)" fill="none" stroke="{HOLO_SOFT}" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round">{SPRITES[p["sprite"]]}</g>'
            f'<g clip-path="url(#{uid}vc)"><rect x="30" y="60" width="160" height="2" fill="{HOLO}" opacity=".7" class="scan"/></g>'
            + text(40, 80, f"No. {p['id']}", 9.5, HOLO, MONO, 500, spacing=1.6)
            + f'<circle cx="136" cy="184" r="2.5" fill="#9affe6" class="led"/>'
            + text(184, 187, "SCANNED", 8, "#9affe6", MONO, 500, "end", 1)
            + text(214, 104, p["name"], 26, "#fff", DISP, 800)
            + sub_svg + chip_svg
            + text(w - 30, 80, p["period"], 9, MUTED, MONO, 500, "end", .6)
            # controls
            + f'<rect x="20" y="218" width="20" height="20" rx="5" fill="#0f1016"/>'
            f'<path d="M30 221v14M23 228h14" stroke="#2b2e3a" stroke-width="3.5" stroke-linecap="round"/>'
            + "".join(f'<rect x="{54 + i * 8}" y="225" width="4" height="6" rx="1" fill="#7a0f0a"/>' for i in range(58))
            + f'<circle cx="{w - 58}" cy="228" r="10" fill="#23b48f"/>' + text(w - 58, 231.5, "A", 9, "#fff", MONO, 700, "middle")
            + f'<circle cx="{w - 30}" cy="228" r="10" fill="#e0991f"/>' + text(w - 30, 231.5, "B", 9, "#fff", MONO, 700, "middle")
        )
        css = (
            ".led{animation:l 2.4s ease-in-out infinite}.l2{animation-delay:.4s}.l3{animation-delay:.8s}@keyframes l{50%{opacity:.35}}"
            ".scan{animation:s 3.6s linear infinite}@keyframes s{to{transform:translateY(134px)}}"
        )
        write(f"rare-{p['id']}-{p['slug']}.svg",
              svg(w, h, body, f"Rare encounter No. {p['id']} — {p['name']}: {p['subtitle']}", css))


def route_cards():
    w, h = 268, 208
    for i, j in enumerate(JOURNEY):
        now = j.get("now")
        c = RED_HI if now else HOLO
        lines = textwrap.wrap(j["text"], 38)
        desc = "".join(text(22, 128 + k * 16, ln, 11.5, MUTED, BODY) for k, ln in enumerate(lines))
        first, last = i == 0, i == len(JOURNEY) - 1
        body = (
            panel(w, h, "rt" + j["slug"], nebula=False)
            + f'<path d="M{22 if first else 0} 36H{w if not last else 30}" stroke="{LINE}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'
            + f'<circle cx="30" cy="36" r="13" fill="{c}" opacity=".16"{" class=\"pulse\"" if now else ""}/>'
            + f'<circle cx="30" cy="36" r="6" fill="{ABYSS}" stroke="{c}" stroke-width="2.5"/>'
            + (f'<circle cx="30" cy="36" r="2.2" fill="{c}"/>' if now else "")
            + text(246, 40, j["period"], 9.5, c, MONO, 500, "end", 1.2)
            + text(22, 78, j["role"], 16.5, "#fff", DISP, 700)
            + text(22, 99, j["org"], 12, RED_HI if now else INK, BODY, 500)
            + desc
        )
        css = ".pulse{animation:p 2.2s ease-in-out infinite;transform-origin:30px 36px}@keyframes p{50%{transform:scale(1.5);opacity:.05}}"
        write(f"route-{j['slug']}.svg", svg(w, h, body, f"{j['period']}: {j['role']}, {j['org']}. {j['text']}", css))


def badge_medals():
    w, h = 196, 190
    for b in BADGES:
        uid = "b" + b["slug"].replace("-", "")
        if b["glyph"] == "paper":
            shape = '<path d="M98 26l36 21v42l-36 21-36-21V47Z"'
            glyph = '<path d="M86 52h16l9 9v24H86Z M102 52v9h9 M91 70h14 M91 77h14" fill="none" stroke="#3a2a05" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
        else:
            shape = '<path d="M98 26l26 9 12 25-12 34-26 16-26-16-12-34 12-25Z"'
            glyph = '<path d="M84 68l10 10 19-21" fill="none" stroke="#3a2a05" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
        lines = textwrap.wrap(b["title"], 24)
        title = "".join(text(98, 144 + k * 15, ln, 11.5, INK, DISP, 600, "middle") for k, ln in enumerate(lines))
        body = (
            panel(w, h, uid, rx=16, nebula=False)
            + f'<defs><linearGradient id="{uid}m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff0b8"/>'
            f'<stop offset=".45" stop-color="{GOLD}"/><stop offset="1" stop-color="#b9741f"/></linearGradient></defs>'
            f'<circle cx="98" cy="68" r="46" fill="{GOLD}" opacity=".08"/>'
            f'{shape} fill="url(#{uid}m)" stroke="#fff0b8" stroke-opacity=".7" stroke-width="1.2" stroke-linejoin="round" class="shine"/>'
            + glyph
            + text(98, 126, b["kind"], 8.5, GOLD, MONO, 500, "middle", 2)
            + title
            + text(98, h - 12, b["sub"], 8.5, MUTED, MONO, 400, "middle")
        )
        css = ".shine{animation:sh 5s ease-in-out infinite}@keyframes sh{50%{filter:brightness(1.18)}}"
        write(f"badge-{b['slug']}.svg", svg(w, h, body, f"{b['kind'].title()}: {b['title']} — {b['sub']}", css))


def link_buttons():
    w, h = 196, 58
    for l in LINKS:
        primary = l.get("primary")
        uid = "ln" + l["slug"]
        if primary:
            bg = (
                f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{RED_HI}"/>'
                f'<stop offset="1" stop-color="{RED}"/></linearGradient></defs>'
                f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="url(#{uid})" stroke="#ff6a5e"/>'
            )
        else:
            bg = panel(w, h, uid, rx=14, nebula=False)
        body = (
            bg
            + text(18, 24, f"[ {l['tag']} ]", 9, "#ffe1dd" if primary else HOLO, MONO, 500, spacing=1.6)
            + text(18, 44, l["label"], 15, "#fff", DISP, 700)
            + text(w - 18, 40, "↗", 16, "#fff" if primary else MUTED, BODY, 400, "end")
        )
        write(f"link-{l['slug']}.svg", svg(w, h, body, f"{l['tag'].title()} — {l['label']}"))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for build in (hero_trainer, trainer_id, divider, stat_tiles, holo_columns,
                  capsules, devices, route_cards, badge_medals, link_buttons):
        build()
    print(f"wrote {len(list(OUT.glob('*.svg')))} panels to {OUT}")
