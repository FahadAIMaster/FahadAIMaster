#!/usr/bin/env python3
"""Generate langs.svg, year.svg from GitHub's GraphQL API.
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


def render_langs_svg(langs):
    rows = []
    y = 34
    for lang in langs:
        bar_w = int(lang["pct"] * 2.8)
        rows.append(f'''
<text x="24" y="{y}" font-size="13">{lang["name"]}</text>
<rect x="140" y="{y-11}" width="{bar_w}" height="11" fill="{lang["color"]}"/>
<text x="{140+bar_w+10}" y="{y}" font-size="12" class="dim">{lang["pct"]:.1f}% · {lang["repos"]} repo{"s" if lang["repos"] != 1 else ""}</text>''')
        y += 30
    return svg_wrap(460, y + 12, "".join(rows))


def render_year_svg(days):
    # One character per day using the portrait's own ramp - shared visual language.
    cols = []
    x, y = 24, 24
    step = 9.8
    for i, (_, count) in enumerate(days[-365:]):
        level = min(len(RAMP) - 1, int(count))
        ch = RAMP[level] if count > 0 else "."
        cols.append(f'<text x="{x:.1f}" y="{y}" font-size="10" class="dim">{ch}</text>')
        x += step
        if (i + 1) % 53 == 0:
            x = 24
            y += 13
    return svg_wrap(560, y + 18, "".join(cols))


def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    user = fetch_contributions()
    days = flatten_days(user)
    langs = compute_languages(user)

    write("langs.svg", render_langs_svg(langs))
    write("year.svg", render_year_svg(days))

    print(f"Generated: top_lang={langs[0]['name'] if langs else 'n/a'}")


if __name__ == "__main__":
    main()
