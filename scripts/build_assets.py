"""Build the Trainer Command Center profile from live GitHub data.

GitHub strips CSS and JavaScript from READMEs, so every panel is a
self-contained SVG. This script:

  1. fetches the profile, repositories, languages, commit/PR/issue totals and
     the contribution calendar for USER (cached in data/github.json),
  2. draws the panels into assets/,
  3. rewrites the repository index between the REPOS markers in README.md.

    python scripts/build_assets.py            # fetch + build
    python scripts/build_assets.py --offline  # rebuild from data/github.json

.github/workflows/refresh.yml runs it daily. Panels are 400px (two-up),
268px (three-up) or 196px (four-up) wide so they sit side by side on desktop
and wrap to one column on mobile.
"""

from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
import json
import os
import random
import re
import sys
import textwrap
import urllib.request

USER = "dynagi"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
CACHE = ROOT / "data" / "github.json"
README = ROOT / "README.md"

# ── Design tokens (shared with the portfolio) ────────────────────────────────
VOID, ABYSS, SOLID, LINE = "#07080f", "#0b0d18", "#141828", "#23283b"
RED, RED_HI, RED_LO = "#ee2b1f", "#ff5a4d", "#a60d06"
HOLO, HOLO_SOFT, GOLD = "#45e6d4", "#7bf3e6", "#f5c451"
INK, MUTED, MUTED_2 = "#eef1fa", "#8b91a7", "#5c627a"

DISP = "Sora,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
BODY = "Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572a5",
    "Dart": "#00b4ab", "CSS": "#8a63d2", "HTML": "#e34c26", "PLpgSQL": "#5b8fc7",
    "Jupyter Notebook": "#da5b0b", "Shell": "#89e051", "Kotlin": "#a97bff",
    "Swift": "#f05138", "C++": "#f34b7d", "Ruby": "#cc342d", "Dockerfile": "#5d8aa8",
}
MAP_LEVELS = ["#151a2a", "#17524f", "#1f8a80", "#2fc0b0", "#45e6d4"]

# ── Curated content ──────────────────────────────────────────────────────────
PROFILE = dict(
    name="Shivam Upadhyay",
    tagline="SOFTWARE DEVELOPER · AI · VISION · WEB",
    klass="SOFTWARE DEVELOPER",
    region="BANGALORE, INDIA",
    focus="FinPilot · Communeo",
)

# GitHub repo descriptions are empty, so each repo gets a short note here.
# tier: "rare" (featured), "lab" (experiments), "archive"; otherwise repos
# pushed in the last ACTIVE_DAYS are "active" and the rest "archive".
# Repos missing from this table still appear, using their GitHub description.
ACTIVE_DAYS = 90
REPO_NOTES = {
    "AI": dict(title="FinPilot", blurb="AI personal-finance agent over a real ledger",
               type="AI · FINTECH", tier="rare", sprite="chart",
               stack=["Next.js", "FastAPI", "Supabase", "LangGraph"],
               why="Deterministic finance, LLM only for language: balances and alerts are exact "
                   "code, and the agent can only call read-only tools on your own data."),
    "Final-Exam": dict(title="SecureAIExam", blurb="Leak-resistant exam paper platform",
                       type="SECURITY · FULL-STACK", tier="rare", sprite="shield",
                       stack=["React Native", "Node.js", "FastAPI", "Supabase"],
                       why="Follows every question paper from sealing to the exam hall, with a "
                           "hash-chained audit trail and QR scan-in at each center."),
    "App": dict(title="Communeo", blurb="Community app for students, devs & founders",
                type="MOBILE · COMMUNITY", tier="rare", sprite="network",
                stack=["Flutter", "Dart", "Supabase"],
                why="One app for networking, hackathon team formation, jobs, mentorship and "
                    "events, with AI-assisted matching."),
    "Portfolio": dict(title="Pokédex Portfolio", blurb="Pokémon-inspired developer portfolio",
                      type="WEB"),
    "AI_Agent": dict(title="AURA", blurb="Web client for a multi-agent AI assistant",
                     type="AI · WEB"),
    "Secure-RAG": dict(title="Secure RAG", blurb="Document Q&A with semantic chunking and a LangGraph retry loop",
                       type="AI · LLM", tier="lab"),
    "Path-finder": dict(title="PathFinder", blurb="Assistive navigation from object detection and depth",
                        type="COMPUTER VISION", tier="lab"),
    "Tennis-Analysis": dict(title="Tennis Analysis", blurb="Player, ball and court tracking from match video",
                            type="COMPUTER VISION", tier="lab"),
    "Tarun-Birthday": dict(title="Birthday Reveal", blurb="Animated birthday celebration site",
                           type="SIDE QUEST", tier="lab"),
    "OneCart": dict(title="OneCART", blurb="MERN e-commerce with live chat, voice and video",
                    type="FULL-STACK"),
    "StockMarket": dict(blurb="Warehouse and stock management app", type="FULL-STACK"),
    "ecom": dict(blurb="MERN e-commerce built while following a course", type="LEARNING BUILD"),
    "Agent": dict(title="FinPilot · early build", blurb="First iteration of the finance agent",
                  type="AI · FINTECH", tier="archive"),
    "New-Exam": dict(title="SecureAIExam · early build", blurb="Earlier iteration of the exam platform",
                     type="SECURITY", tier="archive"),
}

TIERS = [
    ("active", "⚡ ACTIVE BUILDS", "Pushed to in the last 90 days."),
    ("lab", "◈ EXPERIMENT LAB", "AI, computer-vision and side experiments."),
    ("archive", "ARCHIVED ENTRIES", "Older builds and earlier iterations."),
]

# Only technologies that appear in the repositories above or on the résumé.
TYPES = [
    dict(slug="electric", type="ELECTRIC", name="Web", color="#f5d35c",
         items=["TypeScript", "JavaScript", "React", "Next.js", "Node.js", "Express", "Tailwind CSS"]),
    dict(slug="fire", type="FIRE", name="Backend & Agents", color="#ff7a45",
         items=["Python", "FastAPI", "LangGraph", "LangChain", "Streamlit"]),
    dict(slug="psychic", type="PSYCHIC", name="AI & Vision", color="#e0609b",
         items=["YOLO", "OpenCV", "MiDaS", "CNNs", "LLMs / RAG"]),
    dict(slug="water", type="WATER", name="Data", color="#4aa8ff",
         items=["Supabase", "PostgreSQL", "MongoDB", "ChromaDB", "MySQL"]),
    dict(slug="grass", type="GRASS", name="Mobile", color="#57e08a",
         items=["Flutter", "Dart", "React Native", "Expo"]),
    dict(slug="steel", type="STEEL", name="Tools & Infra", color="#9aa1b8",
         items=["Git", "Docker", "Linux", "AWS", "Networking"]),
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

SPRITES = {  # 120x120 line icons for the scanner screen
    "shield": '<path d="M60 12l34 13v29c0 25-15 42-34 50-19-8-34-25-34-50V25Z"/><circle cx="60" cy="55" r="8"/><path d="M60 63v13" opacity=".7"/>',
    "chart": '<path d="M16 102h88" opacity=".6"/><path d="M22 84l24-26 18 13 30-38"/><circle cx="94" cy="33" r="6"/><path d="M22 102V88M46 102V70M64 102V80" opacity=".5"/>',
    "network": '<circle cx="60" cy="28" r="13"/><circle cx="26" cy="90" r="13"/><circle cx="94" cy="90" r="13"/><path d="M53 39L33 79M67 39l20 40M39 90h42" opacity=".6"/>',
    "repo": '<path d="M30 14h60v92H38a8 8 0 0 1 0-16h52"/><path d="M30 98V22a8 8 0 0 1 8-8" /><path d="M48 34h26M48 50h26" opacity=".6"/>',
}


# ── GitHub data ──────────────────────────────────────────────────────────────
def _get(url, accept="application/vnd.github+json"):
    headers = {"User-Agent": f"{USER}-profile-build", "Accept": accept}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return r.read().decode("utf-8")


def _api(path):
    return json.loads(_get(f"https://api.github.com/{path}"))


def _contributions():
    """Read the public contribution calendar (no token needed)."""
    page = _get(f"https://github.com/users/{USER}/contributions", accept="text/html")
    counts = {}
    for cell, text in re.findall(r'<tool-tip[^>]*for="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"\s*(\d+)", text)
        counts[cell] = int(m.group(1)) if m else 0
    days = []
    for tag in re.findall(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', page):
        d = re.search(r'data-date="([\d-]+)"', tag)
        cid = re.search(r'id="([^"]+)"', tag)
        lvl = re.search(r'data-level="(\d)"', tag)
        if d and cid and lvl:
            days.append(dict(date=d.group(1), level=int(lvl.group(1)), count=counts.get(cid.group(1), 0)))
    if not days:
        raise RuntimeError("contribution calendar not found")
    days.sort(key=lambda x: x["date"])
    total = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", page)
    return dict(days=days, total=int(total.group(1).replace(",", "")) if total else sum(x["count"] for x in days))


def fetch(previous):
    """Fetch everything; any piece that fails keeps its cached value."""
    data = dict(previous)

    def step(key, fn):
        try:
            data[key] = fn()
        except Exception as exc:  # network / rate limit: keep the cached value
            if key not in data:
                raise
            print(f"  ! {key}: {exc} (kept cached value)")

    step("user", lambda: {k: v for k, v in _api(f"users/{USER}").items()
                          if k in ("login", "name", "public_repos", "followers", "following", "created_at")})
    step("repos", lambda: [
        {k: r[k] for k in ("name", "description", "language", "stargazers_count", "forks_count",
                           "fork", "archived", "html_url", "homepage", "created_at", "pushed_at")}
        for r in _api(f"users/{USER}/repos?per_page=100&type=owner")])
    step("languages", lambda: {r["name"]: _api(f"repos/{USER}/{r['name']}/languages")
                               for r in data["repos"] if not r["fork"] and r["name"] != USER})
    step("commits", lambda: _api(f"search/commits?q=author:{USER}&per_page=1")["total_count"])
    step("prs", lambda: _api(f"search/issues?q=author:{USER}+type:pr&per_page=1")["total_count"])
    step("issues", lambda: _api(f"search/issues?q=author:{USER}+type:issue&per_page=1")["total_count"])
    step("contributions", _contributions)
    data["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return data


def repo_view(data):
    """Repositories with notes, tier and a stable Pokedex number (by creation date)."""
    today = date.fromisoformat(data["fetched_at"])
    repos = [r for r in data["repos"] if not r["fork"] and r["name"] != USER]
    repos.sort(key=lambda r: r["created_at"])
    out = []
    for i, r in enumerate(repos, 1):
        note = REPO_NOTES.get(r["name"], {})
        pushed = date.fromisoformat(r["pushed_at"][:10])
        tier = note.get("tier") or ("archive" if r["archived"] or (today - pushed).days > ACTIVE_DAYS else "active")
        out.append(dict(r, no=f"{i:03d}", note=note, tier=tier, pushed=pushed,
                        blurb=note.get("blurb") or r["description"] or "No description yet",
                        slug=re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")))
    return out


def language_share(data):
    totals = {}
    for langs in data["languages"].values():
        for lang, size in langs.items():
            totals[lang] = totals.get(lang, 0) + size
    whole = sum(totals.values()) or 1
    return sorted(((k, v / whole) for k, v in totals.items()), key=lambda x: -x[1])


# ── Drawing helpers ──────────────────────────────────────────────────────────
MOTION_GUARD = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
DEVICE_CSS = (
    ".led{animation:l 2.4s ease-in-out infinite}.l2{animation-delay:.4s}.l3{animation-delay:.8s}@keyframes l{50%{opacity:.35}}"
)


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
        f'fill="{fill}" text-anchor="{anchor}"{ls}{extra}>{escape(str(s))}</text>'
    )


def mono_w(s, size):
    return len(s) * size * 0.62


def shade(color, amount):
    """Lighten (amount > 0) or darken (amount < 0) a #rrggbb colour."""
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    target = 255 if amount > 0 else 0
    return "#" + "".join(f"{round(c + (target - c) * abs(amount)):02x}" for c in rgb)


def lang_color(lang):
    return LANG_COLORS.get(lang, MUTED)


def panel(w, h, uid, rx=20, nebula=True, grid=False):
    """Dark surface: abyss fill, hairline border, optional red + holo nebula."""
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


def ball(cx, cy, r, colors, uid, cls="", shadow=True):
    """Capsule: glossy coloured top, pearl bottom, dark band."""
    hi, mid, lo = colors
    c = f' class="{cls}"' if cls else ""
    sh = f'<ellipse cy="{r * 1.14:.1f}" rx="{r * .72:.1f}" ry="{r * .1:.1f}" fill="#000" opacity=".45"/>' if shadow else ""
    return (
        f'<defs><linearGradient id="{uid}t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{hi}"/>'
        f'<stop offset=".45" stop-color="{mid}"/><stop offset="1" stop-color="{lo}"/></linearGradient>'
        f'<linearGradient id="{uid}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef1f8"/>'
        f'<stop offset=".58" stop-color="#cfd5e6"/><stop offset="1" stop-color="#aab1c8"/></linearGradient>'
        f'<radialGradient id="{uid}k" cx="38%" cy="32%" r="70%"><stop offset="0" stop-color="#ffffff"/>'
        f'<stop offset=".55" stop-color="#d4d9e8"/><stop offset="1" stop-color="#8c93ab"/></radialGradient>'
        f'<clipPath id="{uid}o"><circle r="{r}"/></clipPath></defs>'
        f'<g transform="translate({cx} {cy})"><g{c}>{sh}'
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


def device(w, h, uid, label, screen_h):
    """Red Pokedex shell with lens, LEDs and a dark scanner screen."""
    return (
        f'<defs><linearGradient id="{uid}dv" x1="0" y1="0" x2=".5" y2="1"><stop offset="0" stop-color="#e0241b"/>'
        f'<stop offset="1" stop-color="#a8120c"/></linearGradient>'
        f'<linearGradient id="{uid}sc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a1f1c"/>'
        f'<stop offset="1" stop-color="#06100f"/></linearGradient>'
        f'<radialGradient id="{uid}ln" cx="36%" cy="32%" r="75%"><stop offset="0" stop-color="#bfe9ff"/>'
        f'<stop offset=".55" stop-color="#3aa0e6"/><stop offset="1" stop-color="#155a9c"/></radialGradient></defs>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="22" fill="url(#{uid}dv)" stroke="#ff6a5e"/>'
        f'<path d="M22 1.5H{w - 22}" stroke="#fff" stroke-opacity=".3" stroke-linecap="round"/>'
        f'<circle cx="34" cy="26" r="13" fill="url(#{uid}ln)" stroke="#f2f4fa" stroke-width="2.5"/>'
        f'<circle cx="62" cy="19" r="4.5" fill="#ff5a52" class="led"/>'
        f'<circle cx="77" cy="19" r="4.5" fill="#ffd84d" class="led l2"/>'
        f'<circle cx="92" cy="19" r="4.5" fill="#57e08a" class="led l3"/>'
        + text(w - 20, 30, label, 10, "#ffe9c2", MONO, 700, "end", 2.2)
        + f'<rect x="14" y="48" width="{w - 28}" height="{screen_h}" rx="13" fill="url(#{uid}sc)" stroke="#0b0c12" stroke-width="3"/>'
    )


def write(name, content):
    (OUT / name).write_text(content, encoding="utf-8")


def month_year(d):
    return d.strftime("%b %Y")


# ── Panels ───────────────────────────────────────────────────────────────────
def hero_trainer(data):
    w, h = 400, 300
    rnd = random.Random(24)
    stars = "".join(
        f'<circle cx="{rnd.randint(8, w - 8)}" cy="{rnd.randint(8, h - 8)}" r="{rnd.choice([.6, .8, 1.1])}" '
        f'fill="#fff" opacity="{rnd.choice([.25, .4, .6])}"{" class=\"tw\"" if i % 4 == 0 else ""}/>'
        for i in range(46)
    )
    body = (
        panel(w, h, "he", grid=True) + stars
        + f'<circle cx="200" cy="84" r="68" fill="{HOLO}" opacity=".07" class="glow"/>'
        + ball(200, 84, 48, (RED_HI, RED, RED_LO), "heb", "float")
        + text(200, 168, "TRAINER COMMAND CENTER", 10, HOLO, MONO, 500, "middle", 3)
        + text(200, 204, PROFILE["name"].upper(), 29, "#fff", DISP, 800, "middle", .6)
        + text(200, 227, PROFILE["tagline"], 9.5, MUTED, MONO, 500, "middle", 1.5)
        + f'<path d="M60 246H340" stroke="{LINE}"/>'
        + text(200, 268, "CURRENT FOCUS", 8.5, MUTED_2, MONO, 500, "middle", 2.2)
        + text(200, 285, PROFILE["focus"], 12.5, INK, DISP, 600, "middle")
    )
    css = (
        ".float{animation:f 5s ease-in-out infinite}@keyframes f{50%{transform:translateY(-6px)}}"
        ".tw{animation:t 3.2s ease-in-out infinite}@keyframes t{50%{opacity:.05}}"
        ".glow{animation:g 5s ease-in-out infinite}@keyframes g{50%{opacity:.14}}"
    )
    write("hero-trainer.svg", svg(w, h, body, f"Trainer Command Center — {PROFILE['name']}. {PROFILE['tagline'].title()}. Current focus: {PROFILE['focus']}.", css))


def trainer_id(data, langs):
    w, h = 400, 300
    joined = datetime.fromisoformat(data["user"]["created_at"].replace("Z", "+00:00"))
    fields = [
        ("HANDLE", f"@{USER}"),
        ("CLASS", PROFILE["klass"]),
        ("REGION", PROFILE["region"]),
        ("TYPES", " · ".join(l.upper() for l, _ in langs[:3])),
        ("REPOS", f"{data['user']['public_repos']} PUBLIC"),
        ("SINCE", joined.strftime("%b %Y").upper()),
    ]
    step = 29
    rows = "".join(
        f'<path d="M40 {93 + i * step}H360" stroke="{HOLO}" stroke-opacity=".1"/>'
        + text(40, 82 + i * step, k, 9.5, "#5fa89d", MONO, 500, spacing=1.8)
        + text(118, 82 + i * step, v, 11.5, "#dffaf3", MONO, 500, spacing=.3)
        for i, (k, v) in enumerate(fields)
    )
    y = 82 + len(fields) * step
    body = (
        device(w, h, "ti", "TRAINER ID", 238)
        + f'<defs><clipPath id="tic"><rect x="14" y="48" width="372" height="238" rx="13"/></clipPath></defs>'
        + rows
        + text(40, y, "STATUS", 9.5, "#5fa89d", MONO, 500, spacing=1.8)
        + f'<circle cx="123" cy="{y - 4}" r="4" fill="#57e08a" class="led"/>'
        + text(135, y, "OPEN TO TEAM-UPS", 11.5, "#9affe6", MONO, 700, spacing=.3)
        + f'<g clip-path="url(#tic)"><rect x="14" y="46" width="372" height="2" fill="{HOLO}" opacity=".3" class="scan"/></g>'
    )
    css = DEVICE_CSS + ".scan{animation:s 5s linear infinite}@keyframes s{to{transform:translateY(240px)}}"
    label = "; ".join(f"{k.title()}: {v}" for k, v in fields)
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
        + ball(420, 14, 11, (RED_HI, RED, RED_LO), "dv", shadow=False)
    )
    write("divider.svg", svg(w, h, body, "Section divider"))


def stat_tiles(data, langs):
    """Four tiles of real numbers; anything that is zero is skipped."""
    stars = sum(r["stargazers_count"] for r in data["repos"])
    candidates = [
        (data["user"]["public_repos"], "REPOSITORIES", RED_HI),
        (data["contributions"]["total"], "CONTRIBUTIONS · 1 YR", HOLO),
        (data["commits"], "COMMITS", GOLD),
        (stars, "STARS EARNED", GOLD),
        (data["prs"], "PULL REQUESTS", HOLO),
        (data["user"]["followers"], "FOLLOWERS", RED_HI),
        (data["issues"], "ISSUES OPENED", INK),
        (len(langs), "LANGUAGES", INK),
    ]
    tiles = [c for c in candidates if c[0]][:4]
    w, h = 196, 92
    for i, (value, label, color) in enumerate(tiles):
        body = (
            panel(w, h, f"st{i}", rx=16, nebula=False)
            + f'<rect x="18" y="20" width="3" height="52" rx="1.5" fill="{color}"/>'
            + text(34, 52, f"{value:,}", 32, "#fff", DISP, 800, spacing=-.5)
            + text(34, 72, label, 9, MUTED, MONO, 500, spacing=1.4)
        )
        write(f"stat-{i + 1}.svg", svg(w, h, body, f"{value:,} {label.title()}"))
    return [f"{v:,} {l.lower()}" for v, l, _ in tiles]


def activity_map(data):
    """The real contribution calendar, drawn on the scanner screen."""
    days = data["contributions"]["days"]
    total = data["contributions"]["total"]
    first = date.fromisoformat(days[0]["date"])
    start = first - timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday
    w, h, x0, y0, step, cell = 840, 276, 50, 106, 14.6, 11.5
    cells, months, seen = "", "", None
    for d in days:
        dt = date.fromisoformat(d["date"])
        col, row = (dt - start).days // 7, (dt.weekday() + 1) % 7
        x, y = x0 + col * step, y0 + row * step
        cells += f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2.5" fill="{MAP_LEVELS[d["level"]]}"/>'
        if dt.month != seen and dt.day <= 7 and col < 52:
            months += text(f"{x:.1f}", y0 - 10, dt.strftime("%b").upper(), 8.5, "#5fa89d", MONO, 500, spacing=1)
            seen = dt.month
    weekdays = "".join(
        text(x0 - 9, y0 + r * step + 9, n, 8, "#5fa89d", MONO, 500, "end")
        for r, n in ((1, "MON"), (3, "WED"), (5, "FRI"))
    )
    active = [d for d in days if d["count"]]
    best = max(days, key=lambda d: d["count"])
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    facts = [("ACTIVE DAYS", str(len(active))), ("LONGEST STREAK", f"{longest} DAYS")]
    if best["count"]:
        facts.append(("BEST DAY", f"{best['count']} · {date.fromisoformat(best['date']).strftime('%d %b').upper()}"))
    if active:
        facts.append(("LAST SEEN", date.fromisoformat(active[-1]["date"]).strftime("%d %b %Y").upper()))
    fx, fact_svg = 34, ""
    for k, v in facts:
        fact_svg += text(fx, 236, k, 8, "#5fa89d", MONO, 500, spacing=1.4) + text(fx, 252, v, 11.5, "#dffaf3", MONO, 700, spacing=.4)
        fx += max(mono_w(k, 8) + len(k) * 1.4, mono_w(v, 11.5)) + 30
    legend = text(672, 248, "LESS", 8, "#5fa89d", MONO, 500, "end", 1) + "".join(
        f'<rect x="{680 + i * 15}" y="238" width="11.5" height="11.5" rx="2.5" fill="{c}"/>' for i, c in enumerate(MAP_LEVELS)
    ) + text(760, 248, "MORE", 8, "#5fa89d", MONO, 500, spacing=1)
    body = (
        device(w, h, "am", "TRAINER ACTIVITY", 214)
        + text(34, 74, "CONTRIBUTION MAP · LAST 12 MONTHS", 9.5, HOLO, MONO, 500, spacing=2)
        + text(w - 34, 75, f"{total:,} CONTRIBUTIONS", 12, "#fff", MONO, 700, "end", 1)
        + months + weekdays + cells
        + f'<path d="M34 220H{w - 34}" stroke="{HOLO}" stroke-opacity=".12"/>'
        + fact_svg + legend
    )
    summary = ", ".join(f"{k.lower()} {v.lower()}" for k, v in facts)
    write("activity-map.svg", svg(w, h, body, f"Contribution map: {total} contributions in the last 12 months; {summary}.", DEVICE_CSS))


def language_panel(langs):
    w, h = 400, 196
    top = langs[:6]
    scale = sum(p for _, p in top) or 1
    x, bar = 24.0, ""
    for i, (lang, p) in enumerate(top):
        bw = 352 * p / scale
        bar += f'<rect x="{x:.1f}" y="60" width="{max(bw - 2, 1):.1f}" height="12" rx="3" fill="{lang_color(lang)}"/>'
        x += bw
    legend = ""
    for i, (lang, p) in enumerate(top):
        lx, ly = 24 + (i % 2) * 180, 104 + (i // 2) * 28
        legend += (
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{lang_color(lang)}"/>'
            + text(lx + 18, ly, lang, 12, INK, BODY, 500)
            + text(lx + 160, ly, f"{p * 100:.1f}%", 11, MUTED, MONO, 500, "end")
        )
    body = (
        panel(w, h, "lg", nebula=False)
        + text(24, 34, "MOST USED TYPES", 10, HOLO, MONO, 500, spacing=2.4)
        + text(376, 34, "BY CODE SIZE", 8.5, MUTED_2, MONO, 500, "end", 1.4)
        + bar + legend
    )
    summary = ", ".join(f"{l} {p * 100:.1f}%" for l, p in top)
    write("languages.svg", svg(w, h, body, f"Most used languages by code size: {summary}"))


def recent_panel(repos):
    w, h = 400, 196
    latest = sorted(repos, key=lambda r: r["pushed"], reverse=True)[:4]
    rows = ""
    for i, r in enumerate(latest):
        y = 68 + i * 33
        lang = r["language"] or "—"
        rows += (
            f'<path d="M24 {y + 12}H376" stroke="{LINE}"/>' * (i < 3)
            + text(24, y, f"#{r['no']}", 9.5, MUTED_2, MONO, 500, spacing=1)
            + text(64, y, r["name"], 13, "#fff", DISP, 600)
            + f'<circle cx="222" cy="{y - 4}" r="4.5" fill="{lang_color(r["language"])}"/>'
            + text(232, y, lang, 10.5, MUTED, BODY)
            + text(376, y, r["pushed"].strftime("%d %b").upper(), 10, HOLO, MONO, 500, "end", .6)
        )
    body = (
        panel(w, h, "rc", nebula=False)
        + text(24, 34, "LAST SEEN IN", 10, HOLO, MONO, 500, spacing=2.4)
        + text(376, 34, "LATEST PUSHES", 8.5, MUTED_2, MONO, 500, "end", 1.4)
        + rows
    )
    summary = "; ".join(f"{r['name']} ({r['pushed'].strftime('%d %b %Y')})" for r in latest)
    write("recent.svg", svg(w, h, body, f"Most recently pushed repositories: {summary}"))


def repo_cards(repos):
    """One Pokedex entry per repository, using live GitHub fields."""
    w, h = 400, 160
    for r in (r for r in repos if r["tier"] != "rare"):
        note, uid = r["note"], "r" + r["no"]
        base = lang_color(r["language"])
        colors = (shade(base, .35), base, shade(base, -.4))
        heading = note.get("title")
        y = 56
        head_svg = text(120, 50, r["name"], 20, "#fff", DISP, 700)
        if heading and heading.lower().replace(" ", "") != r["name"].lower().replace("-", "").replace("_", ""):
            head_svg += text(120, 68, heading, 11.5, HOLO_SOFT, DISP, 600)
            y = 74
        blurb = "".join(text(120, y + 15 + k * 15, ln, 11.5, MUTED, BODY)
                        for k, ln in enumerate(textwrap.wrap(r["blurb"], 42)[:2]))
        meta = [r["language"] or "No language"]
        if r["stargazers_count"]:
            meta.append(f"★ {r['stargazers_count']}")
        if r["forks_count"]:
            meta.append(f"⑂ {r['forks_count']}")
        tw = mono_w(note.get("type", ""), 8.5) + len(note.get("type", "")) * .8 + 18
        type_pill = (
            f'<rect x="{376 - tw:.1f}" y="16" width="{tw:.1f}" height="18" rx="9" fill="none" stroke="{HOLO}" stroke-opacity=".4"/>'
            + text(f"{376 - tw / 2:.1f}", 28.5, note["type"], 8.5, HOLO, MONO, 500, "middle", .8)
        ) if note.get("type") else ""
        body = (
            panel(w, h, uid)
            + f'<circle cx="60" cy="74" r="46" fill="{base}" opacity=".09"/>'
            + ball(60, 74, 34, colors, uid + "b", "wob")
            + text(120, 29, f"#{r['no']}", 10, MUTED, MONO, 500, spacing=2)
            + type_pill + head_svg + blurb
            + f'<path d="M120 126H376" stroke="{LINE}"/>'
            + f'<circle cx="125" cy="140" r="4.5" fill="{base}"/>'
            + text(136, 144, "  ·  ".join(meta), 10.5, INK, BODY, 500)
            + text(376, 144, f"UPDATED {month_year(r['pushed']).upper()}", 8.5, MUTED_2, MONO, 500, "end", .8)
        )
        css = ".wob{animation:w 6s ease-in-out infinite}@keyframes w{0%,84%,100%{transform:rotate(0)}88%{transform:rotate(-9deg)}92%{transform:rotate(7deg)}96%{transform:rotate(-3deg)}}"
        write(f"repo-{r['slug']}.svg", svg(w, h, body, repo_alt(r), css))


def repo_alt(r):
    bits = [f"#{r['no']} {r['name']}"]
    if r["note"].get("title"):
        bits.append(r["note"]["title"])
    bits.append(r["blurb"])
    bits.append(f"{r['language'] or 'No language'}, updated {month_year(r['pushed'])}")
    return " — ".join(bits)


def rare_devices(repos):
    """Featured repositories on the large scanner."""
    w, h = 600, 246
    for r in (r for r in repos if r["tier"] == "rare"):
        note, uid = r["note"], "d" + r["no"]
        y = 126
        sub = ""
        for line in textwrap.wrap(r["blurb"].upper(), 38):
            sub += text(214, y, line, 10.5, HOLO, MONO, 500, spacing=.6)
            y += 15
        chip_svg, _ = chips(214, y + 8, note.get("stack", []), 350)
        body = (
            device(w, h, uid, "★ RARE ENCOUNTER", 162)
            + f'<defs><radialGradient id="{uid}vi" cx="50%" cy="0%" r="110%"><stop offset="0" stop-color="#0d2a26"/>'
            f'<stop offset="1" stop-color="#061312"/></radialGradient>'
            f'<clipPath id="{uid}vc"><rect x="30" y="64" width="160" height="130" rx="10"/></clipPath></defs>'
            f'<rect x="30" y="64" width="160" height="130" rx="10" fill="url(#{uid}vi)" stroke="{HOLO}" stroke-opacity=".25"/>'
            f'<g transform="translate(64 82) scale(.77)" fill="none" stroke="{HOLO_SOFT}" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round">{SPRITES[note.get("sprite", "repo")]}</g>'
            f'<g clip-path="url(#{uid}vc)"><rect x="30" y="60" width="160" height="2" fill="{HOLO}" opacity=".7" class="scan"/></g>'
            + text(40, 80, f"#{r['no']}", 9.5, HOLO, MONO, 500, spacing=1.6)
            + text(214, 84, f"{USER}/{r['name']}", 10, "#5fa89d", MONO, 500, spacing=.6)
            + text(w - 30, 84, (r["language"] or "").upper(), 9.5, MUTED, MONO, 500, "end", 1)
            + text(214, 110, note.get("title", r["name"]), 25, "#fff", DISP, 800)
            + sub + chip_svg
            + f'<rect x="20" y="218" width="20" height="20" rx="5" fill="#0f1016"/>'
            f'<path d="M30 221v14M23 228h14" stroke="#2b2e3a" stroke-width="3.5" stroke-linecap="round"/>'
            + "".join(f'<rect x="{54 + i * 8}" y="225" width="4" height="6" rx="1" fill="#7a0f0a"/>' for i in range(58))
            + f'<circle cx="{w - 58}" cy="228" r="10" fill="#23b48f"/>' + text(w - 58, 231.5, "A", 9, "#fff", MONO, 700, "middle")
            + f'<circle cx="{w - 30}" cy="228" r="10" fill="#e0991f"/>' + text(w - 30, 231.5, "B", 9, "#fff", MONO, 700, "middle")
        )
        css = DEVICE_CSS + ".scan{animation:s 3.6s linear infinite}@keyframes s{to{transform:translateY(134px)}}"
        write(f"rare-{r['slug']}.svg", svg(w, h, body, f"Rare encounter — {repo_alt(r)}", css))


def type_panels():
    w = 268
    h = 108 + max(chips(22, 108, t["items"], 226, size=10, row_h=24)[1] for t in TYPES) + 22
    for t in TYPES:
        c = t["color"]
        chip_svg, _ = chips(22, 108, t["items"], 226, size=10, fill=INK, stroke=c, row_h=24)
        tw = mono_w(t["type"], 9) + len(t["type"]) * 1.6 + 22
        body = (
            panel(w, h, t["slug"], nebula=False)
            + f'<circle cx="46" cy="50" r="30" fill="{c}" opacity=".13"/>'
            + ball(46, 50, 21, (shade(c, .3), c, shade(c, -.35)), t["slug"] + "b")
            + f'<rect x="84" y="28" width="{tw:.1f}" height="19" rx="9.5" fill="{c}" fill-opacity=".14" stroke="{c}" stroke-opacity=".6"/>'
            + text(f"{84 + tw / 2:.1f}", 41, t["type"], 9, c, MONO, 700, "middle", 1.6)
            + text(84, 68, t["name"], 15, "#fff", DISP, 700)
            + f'<path d="M22 92H246" stroke="{LINE}"/>'
            + chip_svg
        )
        write(f"type-{t['slug']}.svg", svg(w, h, body, f"{t['type'].title()} type · {t['name']}: {', '.join(t['items'])}"))


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


# ── README repository index ──────────────────────────────────────────────────
def card_html(r):
    return (f'  <a href="{r["html_url"]}"><img src="assets/repo-{r["slug"]}.svg" width="400" '
            f'alt="{escape(repo_alt(r), quote=True)}"></a>')


def repo_index(repos):
    out = []
    for r in sorted((r for r in repos if r["tier"] == "rare"), key=lambda r: r["pushed"], reverse=True):
        note = r["note"]
        links = f'<a href="{r["html_url"]}"><b>[ OPEN REPOSITORY ]</b></a>'
        if r["homepage"]:
            links += f' &nbsp; <a href="{r["homepage"]}"><b>[ LIVE DEMO ]</b></a>'
        out += [
            '<p align="center">',
            f'  <a href="{r["html_url"]}"><img src="assets/rare-{r["slug"]}.svg" width="600" '
            f'alt="{escape("Rare encounter — " + repo_alt(r), quote=True)}"></a>',
            "</p>",
            '<p align="center">',
            f'  {escape(note.get("why", r["blurb"]))}<br>',
            f"  {links}",
            "</p>",
            "",
        ]
    for key, label, hint in TIERS:
        group = sorted((r for r in repos if r["tier"] == key), key=lambda r: r["pushed"], reverse=True)
        if not group:
            continue
        cards = ['<p align="center">'] + [card_html(r) for r in group] + ["</p>"]
        live = [f'<a href="{r["homepage"]}">{escape(r["name"])} ↗</a>' for r in group if r["homepage"]]
        if live:
            cards.append(f'<p align="center"><sub>LIVE: {" · ".join(live)}</sub></p>')
        if key == "archive":
            out += ["<details>", f"<summary><b>{label}</b> — {len(group)} entries. {hint}</summary>", "<br>", ""] + cards + ["", "</details>", ""]
        else:
            out += [f'<p align="center"><code>{label}</code><br><sub>{hint}</sub></p>'] + cards + [""]
    return "\n".join(out).rstrip()


def update_readme(repos):
    start, end = "<!-- REPOS:START (generated by scripts/build_assets.py) -->", "<!-- REPOS:END -->"
    doc = README.read_text(encoding="utf-8")
    if start not in doc or end not in doc:
        print("  ! README markers not found; repository index not updated")
        return
    head, rest = doc.split(start, 1)
    tail = rest.split(end, 1)[1]
    README.write_text(f"{head}{start}\n{repo_index(repos)}\n{end}{tail}", encoding="utf-8", newline="\n")


def main():
    offline = "--offline" in sys.argv
    cached = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    data = cached if offline else fetch(cached)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    repos, langs = repo_view(data), language_share(data)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    hero_trainer(data)
    trainer_id(data, langs)
    divider()
    tiles = stat_tiles(data, langs)
    activity_map(data)
    language_panel(langs)
    recent_panel(repos)
    repo_cards(repos)
    rare_devices(repos)
    type_panels()
    route_cards()
    badge_medals()
    link_buttons()
    update_readme(repos)
    print(f"{len(repos)} repositories · {', '.join(tiles)}")
    print(f"wrote {len(list(OUT.glob('*.svg')))} panels to {OUT}")


if __name__ == "__main__":
    main()
