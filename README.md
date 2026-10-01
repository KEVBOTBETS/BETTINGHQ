# KEVBOTBETS · The Matchday Network

One repository contains the recovered hub, Moneyline, NFL, college football,
MLB, NHL, WNBA, Props and Ladder projects. Start with **START-HERE.md**. The initial page opens Weekly
football; the existing sport dashboards and shared ledger remain available.

## Broadcast edition

[Open the hub](https://kevbotbets.github.io/BETTINGHQ/bet-ledger-hq/#today) ·
[Sports Desk](https://kevbotbets.github.io/BETTINGHQ/bet-ledger-hq/#desk) ·
[Performance Center](https://kevbotbets.github.io/BETTINGHQ/bet-ledger-hq/#accuracy)

The whole site shares a sports broadcast identity with local fonts, league
colors, field/court/rink artwork and responsive data panels. The Sports Desk
covers NFL, NCAAF, MLB, NHL, NBA, NCAAB and WNBA scores, standings and headlines.
NBA/NCAAB are research views; automated picks remain closed pending validation.

The Performance Center grades original pregame snapshots with calibration
charts, confidence intervals, probability scores, paired market comparisons
and a downloadable audit. It excludes unresolved teams and post-start captures.
See [the methodology and league extension contract](projects/bet-ledger-hq/docs/broadcast-performance.md).

## What changed

- **NHL Ice Lab** adds visual matchup cards, scoring probability maps, goalie status, team comparisons, PP/PK, standings, injury/news reports, explicit wager entry and frozen forecast accuracy. NHL is included in Moneyline tickets, qualified Daily Picks, ticket archives/results, pick changes, goalie alerts and the shared ledger. Keyless refresh runs twice hourly; see `projects/nhl-edge-lab/README.md` for qualification rules and model limits.

- New **Weekly football** view shows a rolling seven-day NFL/CFB slate, winner
  forecasts and up to one priced candidate per market per game.
- **Research leans** default to a 0.5% minimum adjusted model return. This is
  lower than NFL's 1.5% and CFB's 2.5% LEAN thresholds and changes display only.
  It does not increase model confidence, change saved tiers, suggest a stake,
  or create a wager. The control can be adjusted on the page.
- Weekly volume/correlation exclusions may be reviewed as research alternatives.
  Missing prices, negative EV, stale quotes, hard stops, held bets and started
  games cannot be promoted by this control. Multiple markets on one game are
  alternatives, not independent recommended wagers.
- Moneyline retains winner-only cards and browser-saved selections.
- MLB accuracy/calibration excludes snapshots changed after first pitch.
- NFL calibration now uses raw pre-calibration snapshots, one canonical side
  per event/market, and a distinct-game minimum. Its symmetric correction keeps
  opposing-side probabilities complementary. Legacy rows remain in history
  but cannot silently become calibration training data.
- One tested refresh/deploy workflow replaces the separate repository schedules.
  Internal links are relative and do not depend on the former account name.

## Recovered scope

All eight complete source projects are included: `bet-ledger-hq`, `nfl-edge-lab`,
`ncaaf-edge-lab`, `mlb-edge`, `nhl-edge-lab`, `wnba-edge-lab`, `props-edge`, and `ladderbet`.
Their saved forecast history is preserved. See **RESTORATION-2026-09-23.md** for
the repaired quote, parlay, accuracy and shared-ledger behavior.

Personal browser-local wagers, passwords, tokens and Google Sheet contents are
not contained in a GitHub source backup. Reconnect the existing Sheet from the
Ledger tab. The public build always empties any financial ledger output.

## Local commands

Python 3.12 and Node 22 are used by the included workflow.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
npm --prefix projects/bet-ledger-hq ci --ignore-scripts
cd projects/bet-ledger-hq
npx playwright install chromium
cd ../..
python tools/verify.py --browser
python tools/build_site.py
python -m http.server 8000 --directory _site
```

Open `http://localhost:8000/`. Serving files is required; opening HTML directly
from Finder will not load the feeds correctly.

For current data, run `python tools/refresh.py --sport all` while online.
`--sport football` refreshes NFL, CFB and Props. Individual `mlb`, `nhl`, `wnba`,
`props`, and `ladder` refreshes are supported; `archive` collects tickets/alerts
from saved model feeds without repeating upstream requests.
Recovered feed timestamps are preserved until an actual successful refresh.
Old snapshots may therefore show **stale**, with actionable suggestions withheld.

## Source and performance limits

ESPN remains the football schedule/odds source; MLB retains its existing public
MLB/ESPN data pipeline. Reference-site links are research aids, not model inputs.
No unverified OddsPortal, BetExplorer, TeamRankings or Sports Reference scraper
is installed. Single-book odds and incomplete availability reports remain labeled.

See **ACCURACY-REVIEW.md** for measured results and limits. This release repairs
software and reporting; improved future accuracy or profit has not been established.

The original per-project workflows are retained inside `projects/` for reference.
GitHub executes only the root `.github/workflows/release.yml` in this repository.

## Matchday presentation

The hub and every league share `projects/bet-ledger-hq/sports-theme.css`:
athletic display typography, league colours, field/rink/court artwork, scoreboard
statistics and consistent ticket controls. Fonts are served locally with their
OFL licences in `assets/sports/`. The existing light-theme controls, reduced-motion
preference and print layouts remain supported.

`tools/sports_theme.py` attaches the presentation during the portable site build,
including generated NFL and Ladder pages, so scheduled model refreshes preserve
the design. Models, qualification rules and personal ledger storage are separate
from this layer. Use `tools/build_site.py` to preview the complete themed repo.
