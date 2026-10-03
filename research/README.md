# Model Lab

Five upgrades run beside production: an opponent-adjusted NFL play-efficiency challenger; unweighted lineup sensitivity scenarios and the existing NHL context challenger; exact-contract market auditing; recorded-workload NFL props with shared-game parlay draws; and immutable prospective model comparisons.

Nothing promotes a model, places a bet, pushes code or publishes a site. The new hub route is `#model-lab`. All inputs and outputs remain local until the user approves a release.

## Local commands

```bash
# Optional network import: public nflverse play data, no API key.
python -m tools.research.ingest

# Explicitly freeze new pregame forecasts/quotes and settle verified finals.
python -m tools.research.build --capture

# Offline rendering; does not mutate the prospective archive.
python tools/build_site.py
python -m unittest discover -s tests
cd projects/bet-ledger-hq
node tests/test_model_lab_browser.mjs
```

Serve `_site` with any local static HTTP server. Open `/bet-ledger-hq/#model-lab`. The source archive is `projects/bet-ledger-hq/data/research/history.json`. The portable report is generated in `_site/bet-ledger-hq/data/research/report.json`. Scheduled refreshes import inputs and explicitly capture new forecasts; plain site builds never fetch or backfill.

## What is measured

The efficiency model uses separate pass/rush EPA, success and explosive rates, pace and home field. Recent team profiles are shrunk toward conservative priors; defensive allowance adjusts offensive ratings for the opponents faced. Training labels require a verified completed schedule result. Neutral sites are recognized. Training features and residual forecasts exclude the evaluation date. A regularized regression predicts margin; a centered historical residual mixture and normal prior form a discrete outcome distribution. This is an experimental specification, not an accuracy claim.

Lineup scenarios vary the already-recorded injury adjustment around the existing forecast; they do not claim that adjustment is a full replacement value. No participation probability is assigned. Unknown goalie starters and missing verified replacement effects remain unknown. A scenario never applies a second injury haircut to production.

Market comparison requires event, player, market, line and settlement rules to match. ATS uses a canonical home line for both sides. Opposite quotes must share a book and exact observation timestamp before de-vigging. Future, post-start and more-than-12-hour-old quotes are rejected. Price history compares the same book and line. Last observed pregame prices are reported with their distance from kickoff and are not guaranteed closing prices. Expert picks are not betting-money data.

NFL prop volume uses recorded player opportunities and verified current-roster matching. Missing player games are not turned into zeros. Team passing/rushing counts vary with shared pace and game script. Multinomial allocations conserve opportunities with an explicit other-player bucket. Targeted pass volume is reduced for historical throwaways and untargeted attempts. Quarterback props require an identified expected starter; uncertain or backup roles abstain, and passing volume is conditional on the starter playing. Receptions are bounded by targets; receivers contribute to total passing yards. Historical workload shares do not confirm a starting role. Every probability is conditional on participation and is unvalidated.

Parlay masks preserve correlations within a game. Distinct games are simulated independently. Duplicate or contradictory markets are rejected, and manual tickets require one book. The interface supports 2–8 legs and shows the difference from independent multiplication. Core and Longshot are example sizes, not confidence tiers. No combined payout or ticket EV is invented; verified sportsbook pricing and push rules are required.

The first valid pregame forecast is frozen for each event/model/version. A later scrape cannot rewrite it. Results require completed scores and an observation timestamp after start. Brier, log loss, calibration, margin MAE, ATS and original quoted one-unit ROI use their respective eligible samples. Model comparisons require the same event and capture timestamp. Confidence intervals resample dates, with at least 100 paired events across 28 dates. An ensemble can fit grid weights only after 40 paired prospective results were available before its forecast. Every experiment stays in shadow mode; human review is required for release.

## Honest coverage limits

NFL play data is available without credentials. nflverse historical files may be corrected after games; retrospective replay is labeled exploratory and does not impersonate a vintage backtest. New prospective captures provide the usable test. Source files retain observation timestamps. Failed imports retain previously available season data and source metadata.

NCAAF EPA inputs and NHL ice-time opportunity histories have not been imported. Their new opportunity challengers abstain. Existing NCAAF/NHL forecasts, lineup observations, descriptive player history and exact-price research remain available. No NFL probability distribution or fabricated participation data is applied to those sports.

Before changing model definitions or comparison policy, bump `VERSION` and model versions. Preserve old captures. Do not mix versions into a claimed promotion result. There is no claimed accuracy improvement or guaranteed profitable model in this release.

Sources: [nflverse releases](https://github.com/nflverse/nflverse-data/releases/tag/pbp), [data availability and correction schedule](https://nflverse.nflverse.com/articles/nflverse_data_schedule.html), observed source snapshots from the existing ESPN/NHL/Covers pipelines.

The opportunity and current NFL prop probabilities also have a prospective archive, keyed by exact event/player/market/side/line/model/version. Multiple books count as one contract. Completed player opportunities must match an unambiguous recorded player; missing participation stays ungraded. Pushes are reported but excluded from no-push calibration. Their record is separate from the game-model record.
