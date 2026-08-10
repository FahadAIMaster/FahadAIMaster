#!/usr/bin/env python3
"""Generate stats.svg, streak.svg, langs.svg, year.svg from GitHub's GraphQL API.
Standard library only - urllib, json, datetime. No third-party dependencies.

Determinism (both required, per the setup guide):
  1. Window pinned to whole UTC days (from=today-364d 00:00:00Z, to=today 23:59:59Z)
     - otherwise two runs minutes apart bucket days into different weeks.
  2. privacy: PUBLIC filter on repositories - the workflow's GITHUB_TOKEN only sees
     public repos; a personal token would see private ones too and disagree on numbers.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["GITHUB_TOKEN"]
LOGIN = os.environ["GH_LOGIN"]
API_URL = "https://api.github.com/graphql"

# Same ramp as the portrait pipeline - shared visual language.
RAMP = " .`:-=+*cs#%@"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        name
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-generator",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_contributions():
    now = datetime.now(timezone.utc)
    to = now.replace(hour=23, minute=59, second=59, microsecond=0)
    frm = (now - timedelta(days=364)).replace(hour=0, minute=0, second=0, microsecond=0)
    data = gql(QUERY, {
        "login": LOGIN,
        "from": frm.isoformat().replace("+00:00", "Z"),
        "to": to.isoformat().replace("+00:00", "Z"),
    })
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]


def flatten_days(user):
    days = []
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    return days


def compute_streaks(days):
    counts = [c for _, c in days]
    dates = [d for d, _ in days]
    longest = cur = 0
    longest_range = cur_range = (None, None)
    start_idx = None
    for i, c in enumerate(counts):
        if c > 0:
            if start_idx is None:
                start_idx = i
            cur = i - start_idx + 1
            cur_range = (dates[start_idx], dates[i])
            if cur > longest:
                longest = cur
                longest_range = cur_range
        else:
            start_idx = None
            cur = 0
    # Current streak: walk back from the most recent day.
    current = 0
    current_range = (None, None)
    end_idx = len(counts) - 1
    # Allow today to be 0 (day not over yet) without breaking the streak.
    if counts and counts[-1] == 0:
        end_idx -= 1
    i = end_idx
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    if current:
        current_range = (dates[max(i + 1, 0)], dates[end_idx])
    return current, current_range, longest, longest_range


def compute_languages(user):
    totals = {}
    colors = {}
    repo_counts = {}
    for repo in user["repositories"]["nodes"]:
        seen_in_repo = set()
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#888"
            if name not in seen_in_repo:
                repo_counts[name] = repo_counts.get(name, 0) + 1
                seen_in_repo.add(name)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    total_bytes = sum(totals.values()) or 1
    return [
        {"name": n, "pct": totals[n] / total_bytes * 100, "repos": repo_counts.get(n, 0), "color": colors[n]}
        for n, _ in ranked
    ]


def svg_wrap(width, height, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  text {{ font-family: 'JetBrains Mono', monospace; fill: #c9d1d9; }}
  .dim {{ fill: #6e7681; }}
  .accent {{ fill: #58a6ff; }}
</style>
<rect width="{width}" height="{height}" fill="#0d1117"/>
{body}
</svg>'''


def render_stats_svg(total, weekly_counts):
    # Column chart, not a line - daily contributions are sparse/discrete, a line
    # through 0,0,11,0,0,10 implies values that never existed.
    bars = []
    max_v = max(weekly_counts) or 1
    bar_w = 6
    gap = 2
    x = 20
    base_y = 90
    for v in weekly_counts[-52:]:
        h = int((v / max_v) * 60)
        bars.append(f'<rect x="{x}" y="{base_y - h}" width="{bar_w}" height="{h}" fill="#58a6ff" opacity="0.85"/>')
        x += bar_w + gap
    body = f'''
<text x="20" y="30" font-size="22" class="accent">{total}</text>
<text x="20" y="48" font-size="11" class="dim">contributions, last 12 months</text>
{"".join(bars)}
<line x1="20" y1="{base_y}" x2="{x}" y2="{base_y}" stroke="#30363d" stroke-width="1"/>
'''
    return svg_wrap(max(x + 20, 380), 110, body)


def render_streak_svg(current, current_range, longest, longest_range):
    def fmt(rng):
        if rng[0] is None:
            return "—"
        return f"{rng[0]} → {rng[1]}"
    body = f'''
<text x="20" y="30" font-size="20" class="accent">{current} day{"s" if current != 1 else ""}</text>
<text x="20" y="48" font-size="11" class="dim">current streak · {fmt(current_range)}</text>
<text x="20" y="78" font-size="20">{longest} day{"s" if longest != 1 else ""}</text>
<text x="20" y="96" font-size="11" class="dim">longest streak · {fmt(longest_range)}</text>
'''
    return svg_wrap(380, 115, body)


def render_langs_svg(langs):
    rows = []
    y = 30
    for lang in langs:
        bar_w = int(lang["pct"] * 2.4)
        rows.append(f'''
<text x="20" y="{y}" font-size="12">{lang["name"]}</text>
<rect x="120" y="{y-10}" width="{bar_w}" height="10" fill="{lang["color"]}"/>
<text x="{120+bar_w+8}" y="{y}" font-size="11" class="dim">{lang["pct"]:.1f}% · {lang["repos"]} repo{"s" if lang["repos"] != 1 else ""}</text>''')
        y += 26
    return svg_wrap(400, y + 10, "".join(rows))


def render_year_svg(days):
    # One character per day using the portrait's own ramp - shared visual language.
    cols = []
    x, y = 20, 20
    for i, (_, count) in enumerate(days[-365:]):
        level = min(len(RAMP) - 1, int(count))
        ch = RAMP[level] if count > 0 else "."
        cols.append(f'<text x="{x}" y="{y}" font-size="9" class="dim">{ch}</text>')
        x += 8
        if (i + 1) % 53 == 0:
            x = 20
            y += 11
    return svg_wrap(460, y + 15, "".join(cols))


def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    user = fetch_contributions()
    days = flatten_days(user)
    total = user["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    # Weekly sparkline: sum each 7-day bucket.
    weekly = []
    for i in range(0, len(days), 7):
        weekly.append(sum(c for _, c in days[i:i + 7]))

    current, current_range, longest, longest_range = compute_streaks(days)
    langs = compute_languages(user)

    write("stats.svg", render_stats_svg(total, weekly))
    write("streak.svg", render_streak_svg(current, current_range, longest, longest_range))
    write("langs.svg", render_langs_svg(langs))
    write("year.svg", render_year_svg(days))

    print(f"Generated: total={total}, current_streak={current}, longest_streak={longest}, top_lang={langs[0]['name'] if langs else 'n/a'}")


if __name__ == "__main__":
    main()
