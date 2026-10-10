"""Build the GitHub profile README panels from live GitHub data.

GitHub strips CSS and JavaScript from READMEs, so every panel is a static,
self-contained SVG (no scripts, no external fonts or images). This script:

  1. fetches public data for USER and caches it in data/github.json,
  2. draws the panels into assets/,
  3. rewrites the generated regions of README.md (featured repositories,
     pinned projects and the full repository index).

    python scripts/build_assets.py            # fetch + build
    python scripts/build_assets.py --offline  # rebuild from data/github.json

Where each number comes from (all public, no secrets needed):
  repositories, languages .... GitHub REST API  /users/{user}, /repos/.../languages
  commits .................... GitHub Search API  /search/commits?q=author:{user}
  contribution calendar ...... github.com/users/{user}/contributions
If a source is unavailable the previous cached value is kept, so a failed
fetch never blanks a panel. .github/workflows/refresh.yml runs this daily.

Panels are 400px (two-up), 268px (three-up), 196px (four-up) or 160px
(five-up) wide so they sit side by side on desktop and wrap on mobile.
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

# ── Design tokens ────────────────────────────────────────────────────────────
BG, BG2, CARD, LINE = "#080D18", "#0D1728", "#0B1322", "#1D2B45"
CYAN, BLUE, RED, PURPLE = "#35DDF2", "#4D9FFF", "#FF4B55", "#A78BFA"
GREEN, YELLOW = "#48D597", "#F5C451"
INK, MUTED, DIM = "#F2F5FC", "#A7B5CD", "#6B7A96"

DISP = "Sora,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
BODY = "Inter,'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

LANG_COLORS = {
    "TypeScript": "#4D9FFF", "JavaScript": "#F5C451", "Python": "#5B8DEF",
    "Dart": "#2DD4BF", "CSS": "#A78BFA", "HTML": "#FF7A59", "PLpgSQL": "#7FB2E5",
    "Jupyter Notebook": "#F59E42", "Shell": "#48D597", "Kotlin": "#C084FC",
    "Swift": "#FF6B57", "C++": "#F472B6", "Ruby": "#EF4444", "Dockerfile": "#64A6C8",
}
# Notebook files are mostly embedded output, so their byte counts would swamp
# the real code. They are left out of language statistics.
EXCLUDED_LANGS = {"Jupyter Notebook"}
MAP_LEVELS = ["#121C30", "#14506A", "#1A84A6", "#27B4D3", "#35DDF2"]

# ── Curated content (edit here) ──────────────────────────────────────────────
PROFILE = dict(
    name="Shivam Upadhyay",
    title="SOFTWARE DEVELOPER",
    interests="AI · COMPUTER VISION · FULL-STACK · NETWORKS",
    card=[
        ("ROLE", "Network Operations · Microland"),
        ("EDUCATION", "B.Tech CSE · MIT-WPU, Pune"),
        ("BASED IN", "Bangalore, India"),
        ("BUILDS", "AI · Computer Vision · Full-Stack"),
        ("OPEN TO", "AI, vision and full-stack roles"),
    ],
)

# GitHub repo descriptions are empty, so each repo gets a short note here,
# written from that repo's own README and code. Repos missing from this table
# still appear in the index, using their GitHub description.
REPO_NOTES = {
    "AI": dict(title="FinPilot", accent=CYAN,
               blurb="AI personal-finance co-pilot grounded in a real transaction ledger. "
                     "Balances and alerts are deterministic code; the LLM only explains them.",
               stack=["Next.js", "FastAPI", "Supabase", "LangGraph"]),
    "App": dict(title="Communeo", accent=GREEN,
                blurb="Community platform for students, developers and founders: networking, "
                      "project collaboration, events and AI-assisted matching.",
                stack=["Flutter", "Dart", "Supabase"]),
    "Final-Exam": dict(title="SecureAIExam", accent=RED,
                       blurb="Secure exam-paper platform with role-based logins, sealed papers, "
                             "a hash-chained audit trail and QR scan-in at exam centers.",
                       stack=["React Native", "Node.js", "FastAPI", "Supabase"]),
    "AI_Agent": dict(title="AURA", accent=PURPLE,
                     blurb="Multi-agent personal AI platform: a coordinator routes requests to "
                           "travel, finance, research and calendar agents.",
                     stack=["React", "TypeScript", "Express", "FastAPI", "Supabase"]),
    "Portfolio": dict(title="Portfolio", blurb="Pokédex-inspired developer portfolio built with Next.js and GSAP"),
    "Secure-RAG": dict(title="Secure RAG", blurb="Document Q&A with semantic chunking, ChromaDB and a LangGraph retry loop"),
    "Path-finder": dict(title="PathFinder", blurb="Assistive navigation for visually impaired users using YOLO and MiDaS depth"),
    "Tennis-Analysis": dict(title="Tennis Analysis", blurb="Player, ball and court tracking from match video with YOLO and CNNs"),
    "Tarun-Birthday": dict(blurb="Animated birthday celebration site built with React and Vite"),
    "OneCart": dict(title="OneCART", blurb="MERN e-commerce store with live chat, voice and video"),
    "StockMarket": dict(blurb="Warehouse and stock management app with a FastAPI backend"),
    "ecom": dict(blurb="MERN e-commerce app built while following a course"),
    "Agent": dict(blurb="Earlier iteration of FinPilot"),
    "New-Exam": dict(blurb="Earlier iteration of SecureAIExam"),
}
FEATURED = ["AI", "App", "Final-Exam", "AI_Agent"]
PINNED = ["Tennis-Analysis", "Path-finder", "Secure-RAG", "Portfolio"]

# Technologies that appear in the repositories above or on the résumé.
STACK = [
    dict(slug="web", name="Web Development", tag="ELECTRIC", color=YELLOW,
         items=["JavaScript", "TypeScript", "React", "Next.js", "Node.js", "Express", "Tailwind CSS"]),
    dict(slug="backend", name="Backend & AI Agents", tag="FIRE", color="#FF8A4C",
         items=["Python", "FastAPI", "LangGraph", "LangChain"]),
    dict(slug="vision", name="AI & Computer Vision", tag="PSYCHIC", color=PURPLE,
         items=["YOLO", "OpenCV", "MiDaS", "CNNs", "LLMs & RAG"]),
    dict(slug="data", name="Databases", tag="WATER", color=BLUE,
         items=["Supabase", "PostgreSQL", "MongoDB", "MySQL", "ChromaDB"]),
    dict(slug="mobile", name="Mobile Development", tag="GRASS", color=GREEN,
         items=["Flutter", "Dart", "React Native", "Expo"]),
    dict(slug="infra", name="Tools & Infrastructure", tag="STEEL", color="#9FB0CC",
         items=["Git", "Docker", "Linux", "AWS", "Networking"]),
]

JOURNEY = [  # oldest first
    dict(slug="1", period="2021 — 2025", role="B.Tech, Computer Science",
         org="MIT World Peace University, Pune",
         text="Computer Science and Engineering. Graduated with an 8.61 CGPA."),
    dict(slug="2", period="JUL 2024 — JAN 2025", role="Software Intern",
         org="M3 Technology",
         text="Built SQL validation and reporting tooling for reporting pipelines."),
    dict(slug="3", period="JAN 2026 — PRESENT", role="Network Operations",
         org="Microland", now=True,
         text="Network infrastructure and operations, plus cloud and system administration."),
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
    dict(slug="email", label="Email", color=RED),
    dict(slug="linkedin", label="LinkedIn", color=BLUE),
    dict(slug="portfolio", label="Portfolio", color=CYAN),
    dict(slug="github", label="GitHub", color=PURPLE),
    dict(slug="resume", label="Résumé", color=GREEN),
]


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
    for cell, text_ in re.findall(r'<tool-tip[^>]*for="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"\s*(\d+)", text_)
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
    """Repositories with notes and a stable entry number (by creation date)."""
    repos = [r for r in data["repos"] if not r["fork"] and r["name"] != USER]
    repos.sort(key=lambda r: r["created_at"])
    out = {}
    for i, r in enumerate(repos, 1):
        note = REPO_NOTES.get(r["name"], {})
        code = {k: v for k, v in data["languages"].get(r["name"], {}).items() if k not in EXCLUDED_LANGS}
        if code:  # primary language by code size, ignoring excluded ones
            r = dict(r, language=max(code, key=code.get))
        out[r["name"]] = dict(
            r, no=f"{i:03d}", note=note, pushed=date.fromisoformat(r["pushed_at"][:10]),
            title=note.get("title") or r["name"],
            blurb=note.get("blurb") or r["description"] or "No description yet",
            slug=re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-"))
    return out


def language_share(data):
    totals = {}
    for langs in data["languages"].values():
        for lang, size in langs.items():
            if lang in EXCLUDED_LANGS:
                continue
            totals[lang] = totals.get(lang, 0) + size
    whole = sum(totals.values()) or 1
    return sorted(((k, v / whole) for k, v in totals.items()), key=lambda x: -x[1])


# ── Drawing helpers ──────────────────────────────────────────────────────────
def svg(w, h, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>{body}</svg>\n'
    )


def text(x, y, s, size, fill=INK, font=BODY, weight=400, anchor="start", spacing=0):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}"{ls}>{escape(str(s))}</text>'
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


def card(w, h, uid, accent=CYAN, rx=16):
    """Dark card: navy gradient, hairline border, accent glow and top edge."""
    return (
        f'<defs><linearGradient id="{uid}bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG2}"/>'
        f'<stop offset="1" stop-color="{CARD}"/></linearGradient>'
        f'<radialGradient id="{uid}gl" cx="0%" cy="0%" r="90%"><stop offset="0" stop-color="{accent}" stop-opacity=".16"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="{uid}ed" x1="0" x2="1"><stop offset="0" stop-color="{accent}"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="url(#{uid}bg)"/>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="url(#{uid}gl)"/>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="none" stroke="{accent}" stroke-opacity=".28"/>'
        f'<path d="M{rx} 1H{w * .55:.0f}" stroke="url(#{uid}ed)" stroke-width="2" stroke-linecap="round"/>'
    )


def ball(cx, cy, r, color, uid):
    """Poké Ball accent: coloured top, pearl bottom, dark band."""
    hi, lo = shade(color, .3), shade(color, -.35)
    return (
        f'<defs><linearGradient id="{uid}t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{hi}"/>'
        f'<stop offset=".5" stop-color="{color}"/><stop offset="1" stop-color="{lo}"/></linearGradient>'
        f'<linearGradient id="{uid}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F2F5FC"/>'
        f'<stop offset="1" stop-color="#A9B6D0"/></linearGradient>'
        f'<clipPath id="{uid}o"><circle r="{r}"/></clipPath></defs>'
        f'<g transform="translate({cx} {cy})"><g clip-path="url(#{uid}o)">'
        f'<rect x="{-r}" y="{-r}" width="{2 * r}" height="{r}" fill="url(#{uid}t)"/>'
        f'<rect x="{-r}" y="0" width="{2 * r}" height="{r}" fill="url(#{uid}b)"/>'
        f'<ellipse cx="{-r * .34:.1f}" cy="{-r * .5:.1f}" rx="{r * .32:.1f}" ry="{r * .18:.1f}" fill="#fff" opacity=".4"/>'
        f'<rect x="{-r}" y="{-r * .12:.1f}" width="{2 * r}" height="{r * .24:.1f}" fill="#070B14"/></g>'
        f'<circle r="{r * .3:.1f}" fill="#070B14"/><circle r="{r * .2:.1f}" fill="#F2F5FC"/></g>'
    )


def chips(x, y, labels, max_w, color=CYAN, size=9.5, row_h=23):
    """Mono pill chips that wrap inside max_w. Returns (svg, height used)."""
    out, cx, cy = [], x, y
    for label in labels:
        w = mono_w(label, size) + 16
        if cx + w > x + max_w and cx > x:
            cx, cy = x, cy + row_h
        out.append(
            f'<rect x="{cx:.1f}" y="{cy}" width="{w:.1f}" height="18" rx="9" fill="{color}" fill-opacity=".1" '
            f'stroke="{color}" stroke-opacity=".45"/>'
            + text(f"{cx + w / 2:.1f}", cy + 12.5, label, size, INK, MONO, 500, "middle")
        )
        cx += w + 6
    return "".join(out), cy - y + 18


def write(name, content):
    (OUT / name).write_text(content, encoding="utf-8", newline="\n")


# ── Panels ───────────────────────────────────────────────────────────────────
def banner():
    """Original night-sky scene: Poké Ball moon, ridgelines, trainer and companion."""
    w, h = 840, 280
    rnd = random.Random(7)
    stars = "".join(
        f'<circle cx="{rnd.randint(6, w - 6)}" cy="{rnd.randint(6, 170)}" r="{rnd.choice([.5, .7, .9, 1.2])}" '
        f'fill="{rnd.choice(["#fff", "#fff", "#BFEFFF", "#D9CCFF"])}" opacity="{rnd.choice([.3, .5, .7, .9])}"/>'
        for _ in range(120)
    )
    pixels = "".join(  # pixel-style sparkles
        f'<path d="M{x} {y - 4}v8M{x - 4} {y}h8" stroke="{c}" stroke-width="1.6" opacity=".8"/>'
        for x, y, c in ((442, 54, CYAN), (540, 118, PURPLE), (792, 150, CYAN), (392, 132, "#fff"))
    )
    lights = "".join(
        f'<rect x="{x}" y="{y}" width="2" height="2" fill="{c}" opacity="{o}"/>'
        for x, y, c, o in ((rnd.randint(300, 830), rnd.randint(196, 212), rnd.choice([YELLOW, CYAN, "#fff"]), rnd.choice([.5, .7, .9]))
                           for _ in range(46))
    )
    trainer = (
        '<g transform="translate(598 219)" fill="#03060D">'
        '<rect x="-9" y="-27" width="7" height="28" rx="2"/><rect x="2" y="-27" width="7" height="28" rx="2"/>'
        '<rect x="-11" y="-53" width="22" height="29" rx="6"/><rect x="-18" y="-51" width="9" height="19" rx="3.5"/>'
        '<rect x="10" y="-50" width="5" height="22" rx="2.5"/>'
        '<circle cy="-61" r="8"/><path d="M-9 -63a9 9 0 0 1 18 0Z"/><rect x="4" y="-65" width="11" height="3" rx="1.5"/>'
        "</g>"
        '<g transform="translate(634 217)" fill="#03060D">'  # companion: an original creature
        '<ellipse cy="-9" rx="11" ry="9.5"/><circle cx="4" cy="-21" r="8"/>'
        '<path d="M-2 -26l3-13 6 10Z"/><path d="M7 -28l6-10 1 13Z"/>'
        '<path d="M-10 -7q-13-3-9-16 3 6 9 7" stroke="#03060D" stroke-width="4" stroke-linecap="round" fill="none"/>'
        "</g>"
    )
    body = (
        f'<defs><clipPath id="bnc"><rect width="{w}" height="{h}" rx="18"/></clipPath>'
        f'<linearGradient id="bnsky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050912"/>'
        f'<stop offset=".5" stop-color="#0B1630"/><stop offset=".82" stop-color="#1B2356"/><stop offset="1" stop-color="#27306B"/></linearGradient>'
        f'<radialGradient id="bnglow" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{CYAN}" stop-opacity=".34"/>'
        f'<stop offset=".5" stop-color="{PURPLE}" stop-opacity=".16"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="bnhalo" cx="50%" cy="50%" r="50%"><stop offset=".3" stop-color="#CFE3FF" stop-opacity=".26"/>'
        f'<stop offset="1" stop-color="#CFE3FF" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="bnmoon" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F4F8FF"/><stop offset="1" stop-color="#A9BDE8"/></linearGradient>'
        f'<linearGradient id="bnscrim" x1="0" x2="1"><stop offset="0" stop-color="#050912" stop-opacity=".88"/>'
        f'<stop offset=".5" stop-color="#050912" stop-opacity=".35"/><stop offset=".75" stop-color="#050912" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="bnmc"><circle cx="704" cy="84" r="42"/></clipPath></defs>'
        f'<g clip-path="url(#bnc)">'
        f'<rect width="{w}" height="{h}" fill="url(#bnsky)"/>{stars}{pixels}'
        f'<ellipse cx="640" cy="222" rx="330" ry="110" fill="url(#bnglow)"/>'
        # Poké Ball moon
        f'<circle cx="704" cy="84" r="78" fill="url(#bnhalo)"/>'
        f'<circle cx="704" cy="84" r="42" fill="url(#bnmoon)"/>'
        f'<g clip-path="url(#bnmc)"><rect x="660" y="42" width="88" height="42" fill="{RED}" opacity=".5"/>'
        f'<rect x="660" y="80" width="88" height="8" fill="#1B2550"/></g>'
        f'<circle cx="704" cy="84" r="12" fill="#1B2550"/><circle cx="704" cy="84" r="7.5" fill="#EEF3FF"/>'
        # ridgelines, far to near
        f'<path d="M0 196L70 150 128 182 206 122 282 176 350 140 430 190 512 146 588 186 664 150 742 192 800 166 840 184V280H0Z" fill="#18245A" opacity=".85"/>'
        f'<path d="M0 216L92 178 168 206 250 164 330 204 420 176 500 210 590 182 690 212 770 190 840 208V280H0Z" fill="#101A40"/>'
        f"{lights}"
        f'<path d="M0 240Q160 216 330 234T600 218Q720 208 840 228V280H0Z" fill="#070C1C"/>'
        f'<path d="M0 262Q200 246 420 258T840 250V280H0Z" fill="#04070F"/>'
        f"{trainer}"
        f'<rect width="{w}" height="{h}" fill="url(#bnscrim)"/>'
        + text(48, 92, PROFILE["title"], 12, CYAN, MONO, 600, spacing=4.5)
        + text(46, 136, PROFILE["name"].upper(), 41, "#fff", DISP, 800, spacing=.5)
        + f'<rect x="48" y="152" width="56" height="3" rx="1.5" fill="{RED}"/><rect x="108" y="152" width="20" height="3" rx="1.5" fill="{CYAN}"/>'
        + text(48, 180, PROFILE["interests"], 11, MUTED, MONO, 500, spacing=1.8)
        + f'</g><rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="18" fill="none" stroke="{CYAN}" stroke-opacity=".25"/>'
    )
    write("profile-banner.svg", svg(w, h, body, f"{PROFILE['name']} — software developer. A night sky with a Poké Ball moon above mountain ridgelines, where a trainer and a small companion look out over distant lights."))


def info_card(name, uid, heading, accent, rows, title):
    w, h = 400, 76 + len(rows) * 30
    body = card(w, h, uid, accent) + ball(34, 36, 11, accent, uid + "b") + text(54, 40, heading, 10.5, accent, MONO, 600, spacing=2.4)
    for i, (k, v) in enumerate(rows):
        y = 78 + i * 30
        if i:
            body += f'<path d="M24 {y - 19}H376" stroke="{LINE}"/>'
        body += text(24, y, k, 8.5, DIM, MONO, 500, spacing=1.4) + text(128, y, v, 12.5, INK, BODY, 500)
    write(name, svg(w, h, body, title + ": " + "; ".join(f"{k.title()} — {v}" for k, v in rows)))


def profile_cards(data, repos, langs):
    info_card("profile-card.svg", "pc", "TRAINER CARD", CYAN, PROFILE["card"], "Profile")
    joined = datetime.fromisoformat(data["user"]["created_at"].replace("Z", "+00:00"))
    latest = max(repos.values(), key=lambda r: r["pushed"])
    rows = [
        ("HANDLE", f"@{USER}"),
        ("REPOSITORIES", f"{data['user']['public_repos']} public"),
        ("TOP LANGUAGES", " · ".join(l for l, _ in langs[:3])),
        ("MEMBER SINCE", joined.strftime("%B %Y")),
        ("LATEST PUSH", f"{latest['name']} · {latest['pushed'].strftime('%d %b %Y')}"),
    ]
    info_card("github-card.svg", "gc", "GITHUB ID", PURPLE, rows, "GitHub")


def divider():
    w, h = 840, 28
    body = (
        f'<defs><linearGradient id="dl" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{CYAN}"/></linearGradient>'
        f'<linearGradient id="dr" x1="0" x2="1"><stop offset="0" stop-color="{PURPLE}"/>'
        f'<stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x="60" y="13" width="336" height="2" rx="1" fill="url(#dl)"/>'
        f'<rect x="444" y="13" width="336" height="2" rx="1" fill="url(#dr)"/>'
        + ball(420, 14, 10, RED, "dv")
    )
    write("pokeball-divider.svg", svg(w, h, body, "Section divider"))


def stat_tiles(data, langs):
    """Four tiles of real numbers; anything that is zero is skipped."""
    stars = sum(r["stargazers_count"] for r in data["repos"])
    candidates = [
        (data["user"]["public_repos"], "PUBLIC REPOSITORIES", CYAN),
        (data["contributions"]["total"], "CONTRIBUTIONS · 1 YR", GREEN),
        (data["commits"], "COMMITS", PURPLE),
        (stars, "STARS EARNED", YELLOW),
        (data["prs"], "PULL REQUESTS", BLUE),
        (data["user"]["followers"], "FOLLOWERS", RED),
        (sum(1 for _, p in langs if p >= .01), "LANGUAGES", BLUE),
    ]
    tiles = [c for c in candidates if c[0]][:4]
    w, h = 196, 92
    for i, (value, label, color) in enumerate(tiles):
        body = (
            card(w, h, f"st{i}", color, rx=14)
            + f'<rect x="18" y="22" width="3" height="50" rx="1.5" fill="{color}"/>'
            + text(34, 52, f"{value:,}", 31, "#fff", DISP, 800, spacing=-.5)
            + text(34, 72, label, 8.5, MUTED, MONO, 500, spacing=1.2)
        )
        write(f"stat-{i + 1}.svg", svg(w, h, body, f"{value:,} {label.title()}"))
    return [f"{v:,} {l.lower()}" for v, l, _ in tiles]


def activity_map(data):
    """The real contribution calendar from github.com."""
    days = data["contributions"]["days"]
    total = data["contributions"]["total"]
    first = date.fromisoformat(days[0]["date"])
    start = first - timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday
    w, h, x0, y0, step, cell = 840, 248, 50, 78, 14.6, 11.5
    cells, months, seen = "", "", None
    for d in days:
        dt = date.fromisoformat(d["date"])
        col, row = (dt - start).days // 7, (dt.weekday() + 1) % 7
        x, y = x0 + col * step, y0 + row * step
        cells += f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2.5" fill="{MAP_LEVELS[d["level"]]}"/>'
        if dt.month != seen and dt.day <= 7 and col < 52:
            months += text(f"{x:.1f}", y0 - 10, dt.strftime("%b").upper(), 8.5, DIM, MONO, 500, spacing=1)
            seen = dt.month
    weekdays = "".join(
        text(x0 - 9, y0 + r * step + 9, n, 8, DIM, MONO, 500, "end")
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
        facts.append(("LATEST", date.fromisoformat(active[-1]["date"]).strftime("%d %b %Y").upper()))
    fx, fact_svg = 28, ""
    for k, v in facts:
        fact_svg += text(fx, 208, k, 8, DIM, MONO, 500, spacing=1.4) + text(fx, 225, v, 11.5, INK, MONO, 700, spacing=.4)
        fx += max(mono_w(k, 8) + len(k) * 1.4, mono_w(v, 11.5)) + 30
    legend = text(676, 220, "LESS", 8, DIM, MONO, 500, "end", 1) + "".join(
        f'<rect x="{684 + i * 15}" y="210" width="11.5" height="11.5" rx="2.5" fill="{c}"/>' for i, c in enumerate(MAP_LEVELS)
    ) + text(764, 220, "MORE", 8, DIM, MONO, 500, spacing=1)
    body = (
        card(w, h, "am", CYAN)
        + ball(36, 36, 11, RED, "amb")
        + text(56, 40, "CONTRIBUTION MAP · LAST 12 MONTHS", 10.5, CYAN, MONO, 600, spacing=2)
        + text(w - 28, 40, f"{total:,} CONTRIBUTIONS", 12, "#fff", MONO, 700, "end", 1)
        + months + weekdays + cells
        + f'<path d="M28 190H{w - 28}" stroke="{LINE}"/>'
        + fact_svg + legend
    )
    summary = ", ".join(f"{k.lower()} {v.lower()}" for k, v in facts)
    write("activity-map.svg", svg(w, h, body, f"Contribution map: {total} contributions in the last 12 months; {summary}."))


def language_panel(langs):
    w, h = 400, 196
    top = langs[:6]
    scale = sum(p for _, p in top) or 1
    x, bar = 24.0, ""
    for lang, p in top:
        bw = 352 * p / scale
        bar += f'<rect x="{x:.1f}" y="62" width="{max(bw - 2, 1):.1f}" height="12" rx="3" fill="{lang_color(lang)}"/>'
        x += bw
    legend = ""
    for i, (lang, p) in enumerate(top):
        lx, ly = 24 + (i % 2) * 182, 106 + (i // 2) * 28
        legend += (
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{lang_color(lang)}"/>'
            + text(lx + 18, ly, lang, 12, INK, BODY, 500)
            + text(lx + 164, ly, f"{p * 100:.1f}%", 11, MUTED, MONO, 500, "end")
        )
    body = (
        card(w, h, "lg", BLUE)
        + text(24, 38, "MOST USED LANGUAGES", 10.5, BLUE, MONO, 600, spacing=2.2)
        + text(376, 38, "BY CODE SIZE", 8.5, DIM, MONO, 500, "end", 1.4)
        + bar + legend
    )
    summary = ", ".join(f"{l} {p * 100:.1f}%" for l, p in top)
    write("languages.svg", svg(w, h, body, f"Most used languages by code size: {summary}"))


def recent_panel(repos):
    w, h = 400, 196
    latest = sorted(repos.values(), key=lambda r: r["pushed"], reverse=True)[:4]
    rows = ""
    for i, r in enumerate(latest):
        y = 72 + i * 33
        if i:
            rows += f'<path d="M24 {y - 21}H376" stroke="{LINE}"/>'
        rows += (
            text(24, y, f"#{r['no']}", 9.5, DIM, MONO, 500, spacing=1)
            + text(64, y, r["name"], 13, "#fff", DISP, 600)
            + f'<circle cx="212" cy="{y - 4}" r="4.5" fill="{lang_color(r["language"])}"/>'
            + text(222, y, r["language"] or "—", 10.5, MUTED, BODY)
            + text(376, y, r["pushed"].strftime("%d %b").upper(), 10, GREEN, MONO, 500, "end", .6)
        )
    body = (
        card(w, h, "rc", GREEN)
        + text(24, 38, "RECENT ACTIVITY", 10.5, GREEN, MONO, 600, spacing=2.2)
        + text(376, 38, "LATEST PUSHES", 8.5, DIM, MONO, 500, "end", 1.4)
        + rows
    )
    summary = "; ".join(f"{r['name']} ({r['pushed'].strftime('%d %b %Y')})" for r in latest)
    write("recent.svg", svg(w, h, body, f"Most recently pushed repositories: {summary}"))


def repo_alt(r):
    stack = r["note"].get("stack")
    tail = f" Built with {', '.join(stack)}." if stack else ""
    return f"{r['title']} ({USER}/{r['name']}) — {r['blurb']}{tail}"


def featured_cards(repos):
    w, h = 400, 214
    for name in FEATURED:
        r = repos.get(name)
        if not r:
            continue
        note, uid = r["note"], "f" + r["no"]
        accent = note.get("accent", CYAN)
        desc = "".join(text(24, 102 + k * 17, ln, 12, MUTED, BODY)
                       for k, ln in enumerate(textwrap.wrap(r["blurb"], 56)[:3]))
        chip_svg, _ = chips(24, 150, note.get("stack", []), 352, accent)
        body = (
            card(w, h, uid, accent)
            + ball(34, 36, 11, accent, uid + "b")
            + text(54, 40, f"ENTRY #{r['no']}", 9.5, accent, MONO, 600, spacing=2)
            + text(376, 40, f"{USER}/{r['name']}", 9.5, DIM, MONO, 500, "end", .4)
            + text(24, 78, r["title"], 22, "#fff", DISP, 800)
            + desc + chip_svg
            + f'<path d="M24 180H376" stroke="{LINE}"/>'
            + f'<circle cx="29" cy="194" r="4.5" fill="{lang_color(r["language"])}"/>'
            + text(40, 198, r["language"] or "—", 10.5, INK, BODY, 500)
            + text(376, 198, "OPEN REPOSITORY ↗", 9, accent, MONO, 600, "end", 1.2)
        )
        write(f"project-{r['slug']}.svg", svg(w, h, body, repo_alt(r)))


def stack_cards():
    w = 268
    h = 76 + max(chips(22, 76, s["items"], 226, size=10, row_h=24)[1] for s in STACK) + 20
    for s in STACK:
        c = s["color"]
        chip_svg, _ = chips(22, 76, s["items"], 226, c, size=10, row_h=24)
        body = (
            card(w, h, s["slug"], c)
            + ball(36, 38, 13, c, s["slug"] + "b")
            + text(60, 35, s["name"], 14, "#fff", DISP, 700)
            + text(60, 51, f"{s['tag']} TYPE", 8, c, MONO, 600, spacing=1.8)
            + chip_svg
        )
        write(f"stack-{s['slug']}.svg", svg(w, h, body, f"{s['name']}: {', '.join(s['items'])}"))


def route_cards():
    w, h = 268, 178
    for i, j in enumerate(JOURNEY):
        now = j.get("now")
        c = GREEN if now else CYAN
        desc = "".join(text(22, 124 + k * 16, ln, 11.5, MUTED, BODY)
                       for k, ln in enumerate(textwrap.wrap(j["text"], 38)[:3]))
        first, last = i == 0, i == len(JOURNEY) - 1
        body = (
            card(w, h, "rt" + j["slug"], c)
            + f'<path d="M{30 if first else 0} 36H{w if not last else 30}" stroke="{LINE}" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'
            + ball(30, 36, 9, RED if now else c, "rtb" + j["slug"])
            + text(246, 40, j["period"], 9.5, c, MONO, 600, "end", 1.2)
            + (text(246, 56, "CURRENT", 8, GREEN, MONO, 600, "end", 1.6) if now else "")
            + text(22, 80, j["role"], 16, "#fff", DISP, 700)
            + text(22, 100, j["org"], 12, INK, BODY, 500)
            + desc
        )
        write(f"route-{j['slug']}.svg", svg(w, h, body, f"{j['period']}: {j['role']}, {j['org']}. {j['text']}"))


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
        title = "".join(text(98, 144 + k * 15, ln, 11.5, INK, DISP, 600, "middle")
                        for k, ln in enumerate(textwrap.wrap(b["title"], 24)))
        body = (
            card(w, h, uid, YELLOW, rx=14)
            + f'<defs><linearGradient id="{uid}m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFF0B8"/>'
            f'<stop offset=".45" stop-color="{YELLOW}"/><stop offset="1" stop-color="#B9741F"/></linearGradient></defs>'
            f'{shape} fill="url(#{uid}m)" stroke="#FFF0B8" stroke-opacity=".7" stroke-width="1.2" stroke-linejoin="round"/>'
            + glyph
            + text(98, 126, b["kind"], 8.5, YELLOW, MONO, 600, "middle", 2)
            + title
            + text(98, h - 12, b["sub"], 8.5, MUTED, MONO, 400, "middle")
        )
        write(f"badge-{b['slug']}.svg", svg(w, h, body, f"{b['kind'].title()}: {b['title']} — {b['sub']}"))


def link_buttons():
    w, h = 160, 52
    for l in LINKS:
        c = l["color"]
        body = (
            card(w, h, "ln" + l["slug"], c, rx=12)
            + ball(26, 26, 9, c, "lnb" + l["slug"])
            + text(46, 31, l["label"], 14, "#fff", DISP, 700)
            + text(w - 16, 31, "↗", 14, c, BODY, 400, "end")
        )
        write(f"link-{l['slug']}.svg", svg(w, h, body, l["label"]))


# ── README generated regions ─────────────────────────────────────────────────
def featured_html(repos):
    out = ['<p align="center">']
    for name in FEATURED:
        r = repos.get(name)
        if r:
            out.append(f'  <a href="{r["html_url"]}"><img src="assets/project-{r["slug"]}.svg" width="400" '
                       f'alt="{escape(repo_alt(r), quote=True)}"></a>')
    out.append("</p>")
    demos = [f'<a href="{repos[n]["homepage"]}">{escape(repos[n]["title"])} live demo</a>'
             for n in FEATURED if n in repos and repos[n]["homepage"]]
    if demos:
        out.append(f'<p align="center"><sub>{" · ".join(demos)}</sub></p>')
    return "\n".join(out)


def pinned_md(repos):
    lines = []
    for name in PINNED:
        r = repos.get(name)
        if r:
            demo = f' · [live]({r["homepage"]})' if r["homepage"] else ""
            lines.append(f'- **[{r["title"]}]({r["html_url"]})** — {r["blurb"]}. `{r["language"] or "—"}`{demo}')
    return "\n".join(lines)


def index_md(repos):
    rows = ["| No. | Repository | About | Language | Updated |", "|:--|:--|:--|:--|:--|"]
    for r in sorted(repos.values(), key=lambda r: r["pushed"], reverse=True):
        about = r["blurb"] if r["title"] == r["name"] else f'**{r["title"]}** — {r["blurb"]}'
        rows.append(f'| {r["no"]} | [{r["name"]}]({r["html_url"]}) | {about} | {r["language"] or "—"} | {r["pushed"].strftime("%b %Y")} |')
    return "\n".join(rows)


def update_readme(regions):
    doc = README.read_text(encoding="utf-8")
    for key, content in regions.items():
        start, end = f"<!-- {key}:START (generated by scripts/build_assets.py) -->", f"<!-- {key}:END -->"
        if start not in doc or end not in doc:
            print(f"  ! README markers for {key} not found")
            continue
        head, rest = doc.split(start, 1)
        doc = f"{head}{start}\n{content}\n{end}{rest.split(end, 1)[1]}"
    README.write_text(doc, encoding="utf-8", newline="\n")


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
    banner()
    profile_cards(data, repos, langs)
    divider()
    tiles = stat_tiles(data, langs)
    activity_map(data)
    language_panel(langs)
    recent_panel(repos)
    featured_cards(repos)
    stack_cards()
    route_cards()
    badge_medals()
    link_buttons()
    update_readme({"FEATURED": featured_html(repos), "PINNED": pinned_md(repos), "INDEX": index_md(repos)})
    print(f"{len(repos)} repositories · {', '.join(tiles)}")
    print(f"wrote {len(list(OUT.glob('*.svg')))} panels to {OUT}")


if __name__ == "__main__":
    main()
