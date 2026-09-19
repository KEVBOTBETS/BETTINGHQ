# KEVBOTBETS portable recovery

One repository contains the recovered hub, Moneyling, NFL, college football,
and MLB projects. Start with **START-HERE.md**. The initial page opens Weekly
football; the existing sport dashboards and shared ledger remain available.

## What changed

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
- Moneyling retains winner-only cards and browser-saved selections.
- MLB accuracy/calibration excludes snapshots changed after first pitch.
- NFL calibration now uses raw pre-calibration snapshots, one canonical side
  per event/market, and a distinct-game minimum. Its symmetric correction keeps
  opposing-side probabilities complementary. Legacy rows remain in history
  but cannot silently become calibration training data.
- One tested refresh/deploy workflow replaces the separate repository schedules.
  Internal links are relative and do not depend on the former account name.

## Recovered scope

Complete local source copies exist for `bet-ledger-hq`, `nfl-edge-lab`,
`ncaaf-edge-lab`, and `mlb-edge`. Their saved model history is included.
Full WNBA, Props, and Ladder projects were not available locally when the account
became inaccessible. Their navigation/feed entries are disabled in this release.
Historical tickets and partial shared-ledger integration folders are preserved;
those fragments are not substitutes for the missing complete projects.

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
`--sport football` refreshes NFL and CFB; `--sport mlb` refreshes MLB.
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
