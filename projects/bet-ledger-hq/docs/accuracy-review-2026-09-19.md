# Accuracy review and Moneyling

Reviewed 2026-09-19. The shared ChatGPT conversation was not readable, so this
review uses the actual repositories and their stored prediction history.

## Confirmed MLB defect

At mlb-edge commit `14105541cffdeec4db69218fef21835d952fcc90`,
`pipeline/predict.py:record` overwrote pending game predictions on every build,
including after first pitch. `pipeline/grade.py:record_calls` did the same to
prices, tiers, lines and probabilities in the shadow betting history. Grading
later in the build then treated those snapshots as historical predictions.

The 360 graded game records reported 241 correct (66.94%). Only 25 retained a
last-update timestamp strictly before the saved start time: 13 correct (52%).
The remaining 335 graded records cannot establish pregame accuracy. All 341
ineligible records, including six pending records, remain in source history.
The clean matched-market sample contains 24 games: model 13 correct, market 14;
Brier 0.2473 versus 0.2467. This is too small to justify changing model weights.

The companion MLB repair freezes the latest pregame snapshot, rejects post-start
backfills and non-pregame states, and filters both reports and calibration by
verified snapshot time and season. It preserves the original source files and
actual user wagers. The current clean sample is below the 150-game calibration
minimum, so contaminated history no longer changes future forecasts.

These are data-integrity fixes. They do not prove a future increase in winner
accuracy, and the corrected historical rate is not comparable with the old one.

## Football review

The inspected NFL accuracy feed contains 16 graded game forecasts and 12 correct
winners; NCAAF has 88 and 62. These are different samples from the preferred
betting-pick records, which include spreads and totals. Neither sample warrants
new coefficients selected to improve the displayed percentage. Existing football
pregame game-history freezing and season scope remain in place.

## Moneyling

`#moneyling` uses the existing game forecasts, independently of betting tiers,
edge filters or suggested stakes. MLB uses the published final home probability;
NFL uses the game-detail probability conditional on no tie. College football uses
the published projected margin to choose the side, matching its symmetric winner
distribution. No confidence percentage is invented when the feed omits one.

Cards cover NFL regular/postseason, college football, and MLB regular/postseason.
Missing ratings, stale snapshots, failed feeds and started/unavailable games
cannot produce actionable predictions. Close calls remain explicitly undecided.
Toronto dates are used throughout. Selection IDs include sport and event ID, so
doubleheaders and similarly numbered cross-sport games remain distinct.

Selections persist locally, lock at start, and print as a winner card. They do
not create bets, submit a Proline entry, or write to the shared wager ledger.

## Source roles

The user requested statistics from TeamRankings/Sports Reference and retention
of ESPN (or a verified odds aggregator) for odds. ESPN/MLB feeds remain active.
The following public statistical pages were verified as research references:

- https://www.teamrankings.com/nfl/stat/points-per-game
- https://www.teamrankings.com/college-football/stat/points-per-game
- https://www.teamrankings.com/mlb/stat/runs-per-game

TeamRankings' terms restrict copying/storing its content without consent:
https://www.teamrankings.com/terms-of-service/ . No background importer or
redistributed statistics table was added. Sports Reference requests returned
access errors in this session; no restriction was bypassed. Moneyling links
these sites for statistics research without presenting them as active inputs.

OddsPortal and BetExplorer public homepages were readable, but a stable,
permitted NFL/NCAAF/MLB feed with explicit book, market, game, timestamp and
historical closing-line semantics was not verified. A generic list of scraper
libraries does not establish that contract. No odds source was silently replaced.

## Validation

- Moneyling pure-function tests cover winner-vs-value separation, missing inputs,
  duplicate games, Toronto dates, stale/future timestamps and start locks.
- Chromium tests cover 320px, 393px and desktop layouts, selection persistence,
  sport filters, source failures, no horizontal overflow, and no ledger writes.
- The existing Today browser suite and 38 adapter checks pass.
- The MLB companion repair passes its full synthetic pipeline and five targeted
  pregame-integrity regression tests.

The changes require merging the hub and MLB pull requests. Existing scheduled
builds then publish the tab and regenerate corrected accuracy reports.
