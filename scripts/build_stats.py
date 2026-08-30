#!/usr/bin/env python3
"""Draw the two profile stat strips from live GitHub data.

Everything on the strip is a number the API can answer for, so the README never
claims more than the account actually holds. Rendering happens here instead of
through a third-party badge service: an SVG committed to the repository keeps
working when someone else's host is down, and nobody gets to see who reads the
profile.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

USER = "NspxMiguel"
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# Linguist colours. Here colour IS the information — it identifies one item in a
# list of many — which is the one case the design language allows beyond the
# single accent.
LANGUAGE_COLOURS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "Swift": "#F05138",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Rust": "#dea584",
    "Go": "#00ADD8",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "Ruby": "#701516",
    "Dart": "#00B4AB",
    "Lua": "#000080",
    "Vue": "#41b883",
    "Objective-C": "#438eff",
    "Makefile": "#427819",
    "Dockerfile": "#384d54",
    "Nix": "#7e7eff",
    "Metal": "#8f14e9",
}
FALLBACK_COLOUR = "#8a8a8e"

THEMES = {
    "dark": {
        "bg": "#000000",
        "ink": "#ffffff",
        "muted": "#9a9aa0",
        "accent": "#57d4e7",
        "rule": "rgba(255,255,255,0.10)",
        "track": "rgba(255,255,255,0.08)",
    },
    "light": {
        "bg": "#f4f6f5",
        "ink": "#17202a",
        "muted": "#596675",
        "accent": "#177b8c",
        "rule": "rgba(23,32,42,0.14)",
        "track": "rgba(23,32,42,0.10)",
    },
}

SANS = ("-apple-system, BlinkMacSystemFont, &apos;SF Pro Text&apos;, "
        "&apos;Segoe UI&apos;, Roboto, Helvetica, Arial, sans-serif")
MONO = ("ui-monospace, &apos;SF Mono&apos;, &apos;JetBrains Mono&apos;, "
        "Menlo, Consolas, monospace")


def gh(endpoint):
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"gh api {endpoint} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def contributions_last_year():
    """The same figure the contribution graph on the profile shows.

    Read over GraphQL because the REST API has no equivalent. A token without
    access to private activity simply reports the public part, which is the
    honest number to print anyway.
    """
    query = (
        '{ user(login: "%s") { contributionsCollection '
        "{ contributionCalendar { totalContributions } } } }" % USER
    )
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    payload = json.loads(result.stdout)
    return (payload["data"]["user"]["contributionsCollection"]
            ["contributionCalendar"]["totalContributions"])


def collect():
    repos = []
    page = 1
    while True:
        batch = gh(f"users/{USER}/repos?per_page=100&page={page}&type=owner")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    own = [r for r in repos if not r["fork"]]

    # Repository count per language, not bytes: bytes let one generated bundle
    # outweigh a year of work in another language.
    tally = {}
    for repo in own:
        language = repo.get("language")
        if language:
            tally[language] = tally.get(language, 0) + 1
    languages = sorted(tally.items(), key=lambda item: (-item[1], item[0]))[:4]

    pushes = [r["pushed_at"] for r in own if r.get("pushed_at")]
    last_push = max(pushes) if pushes else None
    if last_push:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(
            last_push.replace("Z", "+00:00")
        )
        days = delta.days
        recency = "today" if days == 0 else ("1 day" if days == 1 else f"{days} days")
    else:
        recency = "—"

    return {
        "repos": len(own),
        "contributions": contributions_last_year(),
        "languages": languages,
        "distinct_languages": len(tally),
        "recency": recency,
    }


def render(data, theme_name):
    t = THEMES[theme_name]
    width, height = 1280, 250

    columns = [
        (str(data["repos"]), "public repos"),
        (f"{data['contributions']:,}".replace(",", " ")
         if data["contributions"] is not None else "—", "contributions, 12 mo"),
        (str(data["distinct_languages"]), "languages"),
        (data["recency"], "last push"),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="{data["repos"]} public repositories, '
        f'{data["contributions"]} contributions in the last year, '
        f'{data["distinct_languages"]} languages, last push {data["recency"]}">',
        f'<rect width="{width}" height="{height}" fill="{t["bg"]}"/>',
    ]

    # Four numbers, evenly spaced, no frame around any of them. A row of
    # identical cards would give every figure the same weight and say nothing.
    x = 96
    step = 268
    for value, label in columns:
        parts.append(
            f'<text x="{x}" y="76" fill="{t["ink"]}" font-family="{MONO}" '
            f'font-size="46" font-weight="700" letter-spacing="-1.5">{value}</text>'
        )
        parts.append(
            f'<text x="{x + 2}" y="104" fill="{t["muted"]}" font-family="{MONO}" '
            f'font-size="12" font-weight="700" letter-spacing="1.4">{label.upper()}</text>'
        )
        x += step

    parts.append(
        f'<rect x="96" y="146" width="{width - 192}" height="1" fill="{t["rule"]}"/>'
    )

    total = sum(count for _, count in data["languages"]) or 1
    bar_x, bar_y, bar_w, bar_h = 96, 178, width - 192, 8
    parts.append(
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="4" fill="{t["track"]}"/>'
    )

    offset = 0.0
    for index, (language, count) in enumerate(data["languages"]):
        segment = bar_w * (count / total)
        last = index == len(data["languages"]) - 1
        # Every segment but the last leaves a 3px gap; the last one runs to the
        # end of the bar, so rounding never shows a sliver of empty track.
        drawn = bar_w - offset if last else max(segment - 3, 2)
        colour = LANGUAGE_COLOURS.get(language, FALLBACK_COLOUR)
        parts.append(
            f'<rect x="{bar_x + offset:.1f}" y="{bar_y}" '
            f'width="{drawn:.1f}" height="{bar_h}" rx="4" fill="{colour}"/>'
        )
        offset += segment

    legend_x = 96
    for language, count in data["languages"]:
        colour = LANGUAGE_COLOURS.get(language, FALLBACK_COLOUR)
        share = round(100 * count / total)
        parts.append(
            f'<circle cx="{legend_x + 5}" cy="216" r="5" fill="{colour}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 18}" y="221" fill="{t["muted"]}" '
            f'font-family="{SANS}" font-size="15">{language}</text>'
        )
        parts.append(
            f'<text x="{legend_x + 26 + 8.2 * len(language)}" y="221" '
            f'fill="{t["ink"]}" font-family="{MONO}" font-size="15" '
            f'font-weight="700">{share}%</text>'
        )
        legend_x += 60 + 8.2 * len(language) + 8 * len(str(share))

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    data = collect()
    for theme in THEMES:
        path = os.path.join(ASSETS, f"stats-{theme}.svg")
        with open(path, "w") as handle:
            handle.write(render(data, theme) + "\n")
        print(f"wrote {path}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    sys.exit(main())
