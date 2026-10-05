# Football and NHL props review — October 5, 2026

## NFL week and selection repair

The default week was selected from the first non-PASS betting candidate, including held look-ahead candidates. On October 5 that selected Week 6, despite ESPN identifying the active slate as Week 4 and supplying Falcons–Saints prices for tonight. The active calendar interval now takes precedence, independently of betting qualification. Week 5 remains navigable. Quiet weeks list their games and projected spreads, and link to the manual selection board. Historical weeks show archived pregame margins where available rather than retrospectively creating picks.

The new **All football spreads** tab lists every scheduled NFL/NCAAF game in a user-selected date range. It compares the home model spread with the posted home spread, shows the cover lean and model rating, and allows either team to be selected. The exact chosen-team line, American price and book must be entered. Missing quotes do not create fake -110 prices. Started, canceled and postponed games cannot be selected. Selections remain manual plans; exported JSON and PNG tickets do not place bets or create ledger stakes.

Both pipelines now publish display projections beyond their qualification horizon for future matchups with known ratings. Distant games carry a note about missing availability/weather inputs. Unrated matchups are still shown with unavailable projections. Display expansion does not alter candidate pricing, tier thresholds, bankroll sizing or frozen prediction history.

## Model review

The published October 5 feed contains **63 completed regular-season NFL games and 390 college games**. Current-season results already update both models. NFL uses 32 current ESPN FPI team ratings plus an independent win-total/prior-results component. NCAAF uses 138 current FPI teams and current results; its prior-season result input is disabled.

The NFL published frozen-game evaluation contains 63 graded games: margin MAE 9.34 versus market 9.48 on 62 paired games; total MAE 11.28 versus market 11.10 on 63. NCAAF has 292 graded game forecasts, but only 61 paired quoted spread comparisons: margin MAE 10.48 versus market 10.44. Its selected ATS sample is 28/59 (47.5%; 95% interval 35.3–60.0%). These are mixed historical model cohorts, not proof that the newest version beats a bookmaker. NFL's anchored-version betting cohort has zero settled picks in this feed. No weights or qualification thresholds were loosened merely to generate bets.

Tonight's ATS candidate is ATL +1.5 at -112: raw estimated EV -1.42%, adjusted expected return -2.51%. NO -1.5 also has negative estimated EV. Those PASS decisions remain visible and manually selectable. A model spread prediction does not imply a positive-value bet.

## Ticket repair

Daily, game and prop tickets share a variable-height renderer with one full-width row per leg. Long names and prop contracts wrap instead of being cut off; odds and status occupy a separate column. Legacy artwork styles route through the same readable layout. The winner-only Moneyline card rendering is unchanged. Desktop and mobile browser checks verify all 24 legs in each of the five ticket styles, full text and canvas bounds. All 50 standard offline release checks pass; the new spread-contract and browser regression checks also pass.

## NHL props

The existing collector only reads Covers' NHL prop index. Its current HTML advertises individual game odds links and contains **zero prop cards**. A directly advertised game-market fragment returned an empty odds section during inspection; no verified book contracts were available to import. This is not evidence that books have no NHL markets.

Official NHL roster requests also used ESPN/display codes such as TB, SJ and NJ, which returned 404s. They now map to TBL, SJS and NJD, with corresponding Montreal/Los Angeles/Winnipeg/Vegas/Nashville/Utah aliases. A five-game minimum also hid legitimate two-game current-season player statistics; descriptive history now accepts one or more games and labels small samples explicitly. The corrected collection returned **1,850 history rows** for 47 upcoming games; 20 teams had available roster responses in that collection.

The feed now preserves history-season/sample warnings, reports roster/statistics/offer coverage, exposes only actually advertised Covers game links, and explains zero observed offers. Manual sportsbook line entry remains available alongside the restored statistics. MoneyPuck's downloadable stats are useful research inputs, but are not sportsbook prop lines. No keys, credentials, proxy rotation or access-control bypass were introduced. NHL model probabilities remain unavailable until a separate sport-specific prop model has been validated.
