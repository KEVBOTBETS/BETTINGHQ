# Ten keyless research upgrades

All diagnostics are public model research. They neither place wagers nor change qualification thresholds, production model weights, or the user's ledger.

1. **Football odds fallback:** `tools/football_public_odds.py` reads public Covers full-game tables before NFL/NCAAF pricing. Both teams and kickoff (within one minute) must match. Each market needs both real opposite prices at one book, a recent page timestamp and a known pregame event. A replacement retains all currently priced markets and adds coverage, or replaces a stale bundle. Books and quote timestamps are never spliced. Offline builds make no requests.
2. **Source agreement:** compare fresh exact contracts with observations no more than 90 minutes apart. A three-percentage-point implied-price gap is a review signal, not proof of a bad quote. Two displays of the same sportsbook remain one book. Different distributors do not establish independent upstream sources.
3. **Favourite/underdog results:** classify from original saved American odds. Missing prices are a separate group, not an inferred favourite.
4. **Odds bands:** -200 or shorter, -101 to -199, even money, +101 to +199, +200 or longer, and unpriced. Returns require original prices and settled calls; accuracy and returns have different denominators.
5. **Recommended/research comparison:** immutable capture-time recommendation status. Older unknown labels are not guessed. Cohort mix can differ; this is descriptive rather than a causal filter test.
6. **Drift review:** one recorded model version; 10 recent game dates versus 10 earlier dates, at least 30 verified calls per window. A flag requires a Brier-error increase of at least 0.02 and a positive date-bootstrap interval. Whole dates are retained, so a large Saturday is never split across comparison windows. Repeated monitoring is exploratory, not an automatic promotion/demotion test.
7. **College efficiency challenger:** keyless `espn_cfb_pbp` public Parquet assets from SportsDataverse. Match saved official game identity, both teams, completed status and final scores. Exclude future/incomplete games, kneels and no-plays. Reuse chronological opponent-adjusted EPA/success/explosive/pace features; NCAAF has separate conservative residual floors and version. Corrected-history replay is exploratory; future immutable captures provide the forward test. No production promotion.
8. **Team bias:** actual minus projected margin from each team's perspective. Display sample counts, average miss and mean absolute error. Fewer than eight games is marked small sample; two teams from one game are not independent tests.
9. **Leg-removal preview:** NCAAF game tickets and the shared NFL/Model Lab ticket audit. Preview each subset without changing a ticket or saved slip. Price products require fresh observed singles at one book. Same-game subsets have no inferred joint probability. Different-game independence and recorded push assumptions are explicit.
10. **Weekly review:** Toronto Monday–Sunday boundaries and verified result-observation times. Plain-language results, pending calls, comparison limits, drift review flags and latest collection notes. Downloadable site-wide text; no email or external messages.

Additional availability snapshots preserve first observations and genuine state changes before kickoff. Expected depth-chart starters never become confirmed by being saved. Outcome groups are associations, not estimated causal injury values.

## Where to read it

Performance and Moneyline Results contain a compact weekly check-in. The expandable review offers odds groups, recommendation cohorts, drift, team bias, availability context, source checks and college research. Model Lab retains the detailed forecast comparison. No new sidebar destination is added.

## Verification

`tests/test_ten_upgrades.py`, `tests/test_parlay_removals.mjs`, and `tests/test_ten_upgrades_browser.mjs` cover exact quote matching, time and price gates, cohort denominators, immutable captures, Toronto boundaries, date-clustered monitoring, final-score matching, mobile layouts, exports, reload failure retention and read-only ticket subsets. Existing sport, research and browser regression suites remain release gates.
