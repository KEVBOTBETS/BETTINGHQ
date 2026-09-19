"""Prepare the public GitHub Pages artifact.

The dashboard is intentionally a single large HTML file. Keeping these small UI
presentation changes here makes them easy to audit without rewriting the whole
file through automation. The model/data remain untouched.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "site"
DST = ROOT / "_public_site"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"public-site patch target missing: {label}")
    return text.replace(old, new, 1)


if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)

index = DST / "index.html"
html = index.read_text(encoding="utf-8")

# Match the MLB/NCAAF vocabulary: the primary action surface is Best Bets.
html = replace_once(
    html,
    '["best","What to bet",',
    '["best","Best Bets",',
    "Best Bets tab label",
)
html = replace_once(
    html,
    '<div><h2>What to bet</h2><p>No wager is forced.',
    '<div><h2>Best Bets</h2><p>No wager is forced.',
    "empty Best Bets heading",
)

# Put wagers that can actually be placed first. Within that group preserve the
# model's tier hierarchy, then use edge as the tie-breaker. A high-edge HOLD
# should never visually outrank an available BEST BET simply because it is
# further from kickoff.
html = replace_once(
    html,
    'const sorted = cands.slice().sort((a,b)=>(b.edge||0)-(a.edge||0));',
    'const tierRank = {"BEST BET":0,"GOOD":1,"LEAN":2,"PASS":3};\n'
    '  const sorted = cands.slice().sort((a,b)=>\n'
    '    (Number(a.held)-Number(b.held)) ||\n'
    '    ((tierRank[a.tier]??9)-(tierRank[b.tier]??9)) ||\n'
    '    ((b.edge||0)-(a.edge||0)));',
    "Best Bets ordering",
)
html = replace_once(
    html,
    '<div class="plays-head"><h2>${bettable} bettable now · ${esc(week&&week.label||"selected slate")}</h2>',
    '<div class="plays-head"><h2>Best Bets · ${bettable} bettable now · ${esc(week&&week.label||"selected slate")}</h2>',
    "Best Bets panel heading",
)

# Add an explicit state label to the summary list so a held look-ahead cannot be
# mistaken for a wager the staking plan says to place now.
html = replace_once(
    html,
    '<span class="play-meta">${esc(c.matchup)} · ${esc(fmtDate(c.game_date))}</span>',
    '<span class="play-meta">${esc(c.matchup)} · ${esc(fmtDate(c.game_date))} · ${c.held?"HOLD":"BETTABLE"}</span>',
    "Best Bets state label",
)

index.write_text(html, encoding="utf-8")

# Model-only performance is public; actual wagers remain browser-local.

print(f"Prepared {DST} with NFL Best Bets presentation patches")
