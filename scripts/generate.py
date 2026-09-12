#!/usr/bin/env python3
"""Regenerate every card on the profile README from live data.

Run by .github/workflows/profile-cards.yml once a day. The dithered portrait is
not recomputed - it is lifted out of the existing dark.svg / light.svg, so the
only thing that changes run to run is the live numbers.

Anything that cannot be fetched falls back to the value already on disk, so a
flaky API never blanks the profile.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "ashokvarma1188")
LEET = os.environ.get("LEETCODE_USER", "ashokvarma5247")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

W, H = 1180, 610
CYCLE = 5.0   # intro runs once over this many seconds, then freezes
PX, PY, PW, PH = 36, 84, 400, 492
IX0, IX1 = 476, 1144
ROW_Y0, ROW_DY = 124, 25.4
FS = 13.5
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

THEMES = {
    "dark": dict(
        bg="#070B16", panel="#0A101F", panel2="#0C1426", bar="#0B1222",
        hair="rgba(255,255,255,0.10)", frame="rgba(34,211,238,0.35)",
        label="#93B4FF", value="#DCE3F5", dim="#475569", muted="#94A3B8",
        cyan="#22D3EE", chip_bg="#6D28D9", chip_fg="#EDE9FE", live="#34D399",
        leader="rgba(148,163,184,0.40)", scan="#22D3EE",
        card="#0C1426", stroke="rgba(34,211,238,0.30)", tile="#DCE3F5",
        sub="#64748B", track="rgba(148,163,184,0.20)",
        g1="#60A5FA", g2="#A78BFA", g3="#22D3EE"),
    "light": dict(
        bg="#FFFFFF", panel="#F7F9FC", panel2="#EEF2F8", bar="#E8EDF5",
        hair="rgba(15,23,42,0.10)", frame="rgba(8,145,178,0.45)",
        label="#1D4ED8", value="#0F172A", dim="#94A3B8", muted="#475569",
        cyan="#0891B2", chip_bg="#DDD6FE", chip_fg="#4C1D95", live="#059669",
        leader="rgba(71,85,105,0.35)", scan="#0891B2",
        card="#FFFFFF", stroke="rgba(8,145,178,0.35)", tile="#0F172A",
        sub="#94A3B8", track="rgba(71,85,105,0.18)",
        g1="#2563EB", g2="#7C3AED", g3="#0891B2"),
}
LANG_COLORS = {"JavaScript": "#F1E05A", "HTML": "#E34C26", "CSS": "#563D7C",
               "Java": "#B07219", "Python": "#3572A5", "C++": "#F34B7D",
               "TypeScript": "#3178C6", "Dart": "#00B4AB", "C": "#555555"}

PROMPT = "ashokvarma5247@gmail.com - % ./profile.sh --live"
CHIP = "ashokvarma5247@gmail.com"


# ---------------------------------------------------------------- fetching
def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def post_json(url, payload, headers=None):
    data = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def github_stats():
    hdr = {"Accept": "application/vnd.github+json",
           "User-Agent": "profile-card-generator"}
    if TOKEN:
        hdr["Authorization"] = "Bearer " + TOKEN
    user = get_json("https://api.github.com/users/" + USER, hdr)
    repos, page = [], 1
    while page <= 5:
        batch = get_json(
            "https://api.github.com/users/%s/repos?per_page=100&page=%d" % (USER, page), hdr)
        if not batch:
            break
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r.get("fork")]
    langs = {}
    for r in own:
        if r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:4]
    by_name = {r["name"].lower(): r for r in repos}
    return dict(
        public_repos=user.get("public_repos", 0),
        followers=user.get("followers", 0),
        original=len(own),
        stars=sum(r.get("stargazers_count", 0) for r in own),
        langs=top,
        repos=by_name,
    )


def leetcode_solved():
    q = ("query($u:String!){matchedUser(username:$u){"
         "submitStatsGlobal{acSubmissionNum{difficulty count}}}}")
    d = post_json("https://leetcode.com/graphql",
                  {"query": q, "variables": {"u": LEET}},
                  {"Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0"})
    nums = d["data"]["matchedUser"]["submitStatsGlobal"]["acSubmissionNum"]
    for n in nums:
        if n["difficulty"] == "All":
            return n["count"]
    return sum(n["count"] for n in nums)


# ---------------------------------------------------------------- helpers
def kt(*times):
    return ";".join("%.5f" % (t / CYCLE) for t in times)


def hold(t_start, dur=0.45):
    return ('<animate attributeName="opacity" values="0;0;1;1" keyTimes="%s" '
            'dur="%ss" repeatCount="1" fill="freeze"/>'
            % (kt(0, t_start, t_start + dur, CYCLE), CYCLE))


def accent(t, ident="accent"):
    return ('<linearGradient id="%s" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="%s"><animate attributeName="stop-color" '
            'values="%s;%s;%s;%s" dur="9s" repeatCount="indefinite"/></stop>'
            '<stop offset="0.5" stop-color="%s"><animate attributeName="stop-color" '
            'values="%s;%s;%s;%s" dur="9s" repeatCount="indefinite"/></stop>'
            '<stop offset="1" stop-color="%s"><animate attributeName="stop-color" '
            'values="%s;%s;%s;%s" dur="9s" repeatCount="indefinite"/></stop>'
            '</linearGradient>'
            % (ident, t["g1"], t["g1"], t["g2"], t["g3"], t["g1"],
               t["g2"], t["g2"], t["g3"], t["g1"], t["g2"],
               t["g3"], t["g3"], t["g1"], t["g2"], t["g3"]))


def wrap(text, per_line, max_lines=3):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= per_line:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


def portrait_of(path):
    """Lift the already-dithered portrait out of the SVG we generated before."""
    s = open(path, encoding="utf-8").read()
    m = re.search(r'href="data:image/png;base64,([^"]+)"', s)
    if not m:
        raise SystemExit("no portrait found in " + path)
    return m.group(1)


# ---------------------------------------------------------------- banner
def banner(theme, png, solved):
    t = THEMES[theme]
    rows = [
        ("Subject", "Ashok Varma"),
        ("Role", "Full-Stack Developer"),
        ("Origin", "Andhra Pradesh, India"),
        ("Education", "B.Tech CSE · VIT-AP University"),
        ("Status", "Building + Learning + Shipping"),
        ("ToolChain", "VS Code, Git, Postman, Figma"),
        (None, None),
        ("Core.Lang", "JavaScript, Java"),
        ("Core.Frontend", "React, HTML5, CSS3"),
        ("Core.Backend", "Node.js, Express.js"),
        ("Core.Database", "MongoDB, MySQL"),
        ("Core.Infra", "Git, GitHub, Vercel"),
        (None, None),
        ("- Contact", None),
        ("Grid.Mail", "ashokvarma5247@gmail.com"),
        ("Grid.LeetCode", "%s · %d solved" % (LEET, solved)),
        ("Grid.LinkedIn", "ashok-varma-287a03299"),
        ("Grid.GitHub", "@" + USER),
    ]
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %d %d" font-family="%s" role="img" '
         'aria-label="Ashok Varma - full-stack developer profile card">'
         % (W, H, W, H, FONT)]
    s.append("<defs>" + accent(t))
    s.append('<linearGradient id="panelGrad" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
             '</linearGradient>' % (t["panel"], t["panel2"]))
    s.append('<linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="%s" stop-opacity="0"/>'
             '<stop offset="0.5" stop-color="%s" stop-opacity="0.55"/>'
             '<stop offset="1" stop-color="%s" stop-opacity="0"/></linearGradient>'
             % (t["scan"], t["scan"], t["scan"]))
    s.append('<filter id="glow3" x="-60%" y="-60%" width="220%" height="220%">'
             '<feGaussianBlur stdDeviation="3"/></filter>')
    s.append('<filter id="glow6" x="-60%" y="-60%" width="220%" height="220%">'
             '<feGaussianBlur stdDeviation="6"/></filter>')
    s.append('<clipPath id="winClip"><rect x="2" y="2" width="%d" height="%d" rx="18"/></clipPath>'
             % (W - 4, H - 4))
    s.append('<clipPath id="portClip"><rect x="%d" y="%d" width="%d" height="%d" rx="10"/></clipPath>'
             % (PX, PY, PW, PH))
    s.append('<clipPath id="wipe"><rect x="%d" y="%d" width="%d" height="%d">'
             '<animate attributeName="height" values="0;0;%d;%d" keyTimes="%s" '
             'dur="%ss" repeatCount="1" fill="freeze"/></rect></clipPath>'
             % (PX, PY, PW, PH, PH, PH, kt(0, 0.2, 0.6, CYCLE), CYCLE))
    s.append("</defs>")

    s.append('<rect x="2" y="2" width="%d" height="%d" rx="18" fill="%s"/>' % (W - 4, H - 4, t["bg"]))
    s.append('<g clip-path="url(#winClip)">')
    s.append('<rect x="2" y="2" width="%d" height="%d" fill="url(#panelGrad)"/>' % (W - 4, H - 4))
    s.append('<rect x="2" y="2" width="%d" height="46" fill="%s"/>' % (W - 4, t["bar"]))
    s.append('<line x1="2" y1="48" x2="%d" y2="48" stroke="%s"/>' % (W - 2, t["hair"]))
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        s.append('<circle cx="%d" cy="25" r="5.5" fill="%s"/>' % (30 + i * 20, c))
    s.append('<text x="%s" y="29" text-anchor="middle" font-size="12" fill="%s">%s</text>'
             % (W / 2, t["muted"], escape(PROMPT)))
    s.append('<text x="38" y="74" font-size="10" letter-spacing="3" fill="%s">VISUAL.MAP</text>' % t["dim"])
    s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="none" stroke="%s" '
             'stroke-width="2" opacity="0.45" filter="url(#glow3)"/>' % (PX, PY, PW, PH, t["cyan"]))
    s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>'
             % (PX, PY, PW, PH, t["panel"], t["frame"]))
    s.append('<g clip-path="url(#portClip)"><g clip-path="url(#wipe)">'
             '<image x="%d" y="%d" width="%d" height="%d" image-rendering="pixelated" '
             'preserveAspectRatio="none" href="data:image/png;base64,%s"/></g>'
             % (PX, PY, PW, PH, png))
    s.append('<rect x="%d" y="%d" width="%d" height="46" fill="url(#scanGrad)" opacity="0">'
             '<animate attributeName="opacity" values="0;0;0.9;0.9;0;0" keyTimes="%s" dur="%ss" '
             'repeatCount="1" fill="freeze"/><animate attributeName="y" values="%d;%d;%d;%d" '
             'keyTimes="%s" dur="%ss" repeatCount="1" fill="freeze"/></rect></g>'
             % (PX, PY, PW, kt(0, 0.16, 0.22, 0.55, 0.62, CYCLE), CYCLE,
                PY, PY, PY + PH - 46, PY + PH - 46, kt(0, 0.2, 0.6, CYCLE), CYCLE))
    for cx, cy, dx, dy in ((PX, PY, 1, 1), (PX + PW, PY, -1, 1),
                           (PX, PY + PH, 1, -1), (PX + PW, PY + PH, -1, -1)):
        s.append('<path d="M%d,%d L%d,%d L%d,%d" fill="none" stroke="%s" stroke-width="2" opacity="0.8"/>'
                 % (cx + dx * 2, cy + dy * 18, cx + dx * 2, cy + dy * 2,
                    cx + dx * 18, cy + dy * 2, t["cyan"]))

    s.append('<text x="%d" y="74" font-size="10" letter-spacing="3" fill="%s">SYSTEM.INFO</text>'
             % (IX0, t["cyan"]))
    s.append('<circle cx="%d" cy="70" r="3.5" fill="%s"><animate attributeName="opacity" '
             'values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/></circle>' % (IX1 - 46, t["live"]))
    s.append('<circle cx="%d" cy="70" r="3.5" fill="%s" filter="url(#glow6)">'
             '<animate attributeName="r" values="3.5;9;3.5" dur="1.6s" repeatCount="indefinite"/>'
             '<animate attributeName="opacity" values="0.7;0;0.7" dur="1.6s" repeatCount="indefinite"/>'
             '</circle>' % (IX1 - 46, t["live"]))
    s.append('<text x="%d" y="74" text-anchor="end" font-size="10" letter-spacing="2" fill="%s">LIVE</text>'
             % (IX1, t["live"]))
    s.append('<g opacity="1">%s<rect x="%d" y="%d" width="%d" height="24" rx="6" fill="%s"/>'
             '<text x="%d" y="%d" font-size="12.5" fill="%s">%s</text></g>'
             % (hold(0.55, 0.1), IX0, ROW_Y0 - 36, int(len(CHIP) * 7.6 + 22), t["chip_bg"],
                IX0 + 11, ROW_Y0 - 19, t["chip_fg"], escape(CHIP)))

    for i, (label, value) in enumerate(rows):
        if label is None:
            continue
        y = ROW_Y0 + i * ROW_DY
        start = 0.7 + i * 0.1
        cid = "row%d" % i
        s.append('<clipPath id="%s"><rect x="%d" y="%s" width="%d" height="20">'
                 '<animate attributeName="width" values="0;0;%d;%d" keyTimes="%s" dur="%ss" '
                 'repeatCount="1" fill="freeze"/></rect></clipPath>'
                 % (cid, IX0, y - 14, IX1 - IX0, IX1 - IX0, IX1 - IX0,
                    kt(0, start, start + 0.12, CYCLE), CYCLE))
        s.append('<g clip-path="url(#%s)">' % cid)
        if value is None:
            s.append('<text x="%d" y="%s" font-size="%s" fill="%s" letter-spacing="1">%s</text>'
                     % (IX0, y, FS, t["dim"], escape(label)))
        else:
            lw, vw = len(label) * FS * 0.605, len(value) * FS * 0.605
            s.append('<text x="%d" y="%s" font-size="%s" fill="%s">%s</text>'
                     % (IX0, y, FS, t["label"], escape(label)))
            s.append('<text x="%d" y="%s" font-size="%s" fill="%s" text-anchor="end">%s</text>'
                     % (IX1, y, FS, t["value"], escape(value)))
            g0, g1 = IX0 + lw + 8, IX1 - vw - 8
            if g1 - g0 > 16:
                s.append('<line x1="%.1f" y1="%s" x2="%.1f" y2="%s" stroke="%s" stroke-width="1" '
                         'stroke-dasharray="1.5 4.5"/>' % (g0, y - 4, g1, y - 4, t["leader"]))
        s.append("</g>")

    last = ROW_Y0 + (len(rows) - 1) * ROW_DY
    s.append('<g opacity="1">%s<text x="%d" y="%s" font-size="12" fill="%s">'
             '▸ more about me &amp; my projects below in this README ⬇</text>'
             '<rect x="%d" y="%s" width="8" height="15" fill="%s">'
             '<animate attributeName="opacity" values="1;1;0;0;1" dur="1.1s" repeatCount="indefinite"/>'
             '</rect></g>' % (hold(2.6, 0.1), IX0, last + 40, t["dim"], IX0 + 372, last + 29, t["cyan"]))
    s.append('<rect x="2" y="%d" width="%d" height="4" fill="url(#accent)" opacity="0.85"/></g>' % (H - 6, W - 4))
    s.append('<rect x="2" y="2" width="%d" height="%d" rx="18" fill="none" stroke="url(#accent)" '
             'stroke-width="2" opacity="0.65"/></svg>' % (W - 4, H - 4))
    return "".join(s)


# ---------------------------------------------------------------- cards
def head(h, label):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'font-family="%s" role="img" aria-label="%s">' % (W, h, W, h, FONT, escape(label)))


REPO_GLYPH = ('<path transform="translate(28,34) scale(1.15)" fill="%s" d="M2 2.5A2.5 2.5 0 '
              '014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 '
              '010-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 '
              '012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8z"/>')
STAR_GLYPH = ('<path transform="translate(%d,149) scale(0.95)" fill="%s" d="M8 .25a.75.75 0 '
              '01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 '
              '01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 '
              '01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"/>')

FEATURED = [
    ("Smartnest", "Full-stack real estate platform - owners list directly, "
                  "buyers contact owners. No broker, no commission."),
    ("youtube-focus-extension", "Browser extension that keeps YouTube "
                               "distraction-free so it stays a study tool."),
]


def projects_card(theme, repos):
    t = THEMES[theme]
    h, gap = 196, 24
    cw = (W - gap) // 2
    s = [head(h, "Featured projects"), "<defs>" + accent(t, "acc") + "</defs>"]
    s.append('<rect width="%d" height="%d" fill="%s" rx="12"/>' % (W, h, t["bg"] if theme == "light" else t["panel"]))
    for i, (name, desc) in enumerate(FEATURED):
        r = repos.get(name.lower(), {})
        lang = r.get("language") or "JavaScript"
        stars = r.get("stargazers_count", 0)
        s.append('<g transform="translate(%d,0)">' % (i * (cw + gap)))
        s.append('<rect x="1" y="1" width="%d" height="%d" rx="12" fill="%s" stroke="%s"/>'
                 % (cw - 2, h - 2, t["card"], t["stroke"]))
        s.append('<rect x="1" y="1" width="%d" height="4" fill="url(#acc)"/>' % (cw - 2))
        s.append(REPO_GLYPH % t["cyan"])
        s.append('<text x="54" y="46" font-size="17" font-weight="700" fill="%s">%s</text>'
                 % (t["cyan"], escape(name)))
        for j, line in enumerate(wrap(desc, 62)):
            s.append('<text x="28" y="%d" font-size="13" fill="%s">%s</text>'
                     % (86 + j * 22, t["muted"], escape(line)))
        fy = h - 34
        s.append('<circle cx="34" cy="%d" r="6" fill="%s"/>' % (fy - 4, LANG_COLORS.get(lang, t["label"])))
        s.append('<text x="48" y="%d" font-size="13" fill="%s">%s</text>' % (fy, t["value"], escape(lang)))
        bx = 48 + len(lang) * 8 + 26
        s.append(STAR_GLYPH % (bx, t["sub"]))
        s.append('<text x="%d" y="%d" font-size="13" fill="%s">%d</text>' % (bx + 22, fy, t["sub"], stars))
        s.append("</g>")
    s.append("</svg>")
    return "".join(s)


def stats_card(theme, st):
    t = THEMES[theme]
    h = 196
    tiles = [("Public repos", st["public_repos"]), ("Original repos", st["original"]),
             ("Total stars", st["stars"]), ("Followers", st["followers"])]
    s = [head(h, "GitHub statistics"), "<defs>" + accent(t, "acc") + "</defs>"]
    s.append('<rect width="%d" height="%d" fill="%s" rx="12"/>' % (W, h, t["bg"] if theme == "light" else t["panel"]))
    s.append('<rect x="1" y="1" width="%d" height="%d" rx="12" fill="%s" stroke="%s"/>'
             % (W - 2, h - 2, t["card"], t["stroke"]))
    s.append('<rect x="1" y="1" width="%d" height="4" fill="url(#acc)"/>' % (W - 2))
    s.append('<text x="30" y="40" font-size="10" letter-spacing="3" fill="%s">REPOSITORY.STATS</text>' % t["cyan"])
    for i, (lab, val) in enumerate(tiles):
        x = 30 + i * 128
        s.append('<text x="%d" y="84" font-size="30" font-weight="700" fill="%s">%s</text>' % (x, t["tile"], val))
        s.append('<text x="%d" y="106" font-size="11" fill="%s">%s</text>' % (x, t["sub"], lab))
    s.append('<line x1="30" y1="132" x2="530" y2="132" stroke="%s"/>' % t["track"])
    s.append('<text x="30" y="160" font-size="12" fill="%s">Building with the MERN stack '
             '· open to internships</text>' % t["muted"])

    lx, lw = 600, 550
    langs = st["langs"] or [("JavaScript", 1)]
    total = sum(n for _, n in langs) or 1
    s.append('<text x="%d" y="40" font-size="10" letter-spacing="3" fill="%s">TOP.LANGUAGES</text>'
             % (lx, t["cyan"]))
    s.append('<clipPath id="barclip"><rect x="%d" y="56" width="%d" height="12" rx="6"/></clipPath>'
             % (lx, lw))
    s.append('<g clip-path="url(#barclip)">')
    off = 0.0
    for name, n in langs:
        seg = lw * n / total
        s.append('<rect x="%.1f" y="56" width="%.1f" height="12" fill="%s"/>'
                 % (lx + off, seg + 0.6, LANG_COLORS.get(name, t["label"])))
        off += seg
    s.append("</g>")
    for i, (name, n) in enumerate(langs):
        cx = lx + (i % 2) * 280
        cy = 104 + (i // 2) * 30
        s.append('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (cx + 6, cy - 5, LANG_COLORS.get(name, t["label"])))
        s.append('<text x="%d" y="%d" font-size="13" fill="%s">%s</text>' % (cx + 20, cy, t["tile"], escape(name)))
        s.append('<text x="%d" y="%d" font-size="13" text-anchor="end" fill="%s">%.1f%%</text>'
                 % (cx + 240, cy, t["sub"], 100.0 * n / total))
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- main
def previous_solved():
    try:
        s = open("dark.svg", encoding="utf-8").read()
        m = re.search(r"(\d+) solved", s)
        return int(m.group(1)) if m else 0
    except OSError:
        return 0


def main():
    try:
        st = github_stats()
    except Exception as e:                      # keep the old card rather than blanking it
        print("github stats failed: %s - keeping existing cards" % e, file=sys.stderr)
        st = None
    try:
        solved = leetcode_solved()
    except Exception as e:
        solved = previous_solved()
        print("leetcode failed: %s - reusing %d" % (e, solved), file=sys.stderr)

    pngs = {"dark": portrait_of("dark.svg"), "light": portrait_of("light.svg")}
    for theme in ("dark", "light"):
        suffix = "" if theme == "dark" else "-light"
        name = "dark.svg" if theme == "dark" else "light.svg"
        open(name, "w", encoding="utf-8").write(banner(theme, pngs[theme], solved))
        if st:
            open("stats%s.svg" % suffix, "w", encoding="utf-8").write(stats_card(theme, st))
            open("projects%s.svg" % suffix, "w", encoding="utf-8").write(projects_card(theme, st["repos"]))
    print("solved=%s stats=%s" % (solved, "ok" if st else "skipped"))


if __name__ == "__main__":
    main()
