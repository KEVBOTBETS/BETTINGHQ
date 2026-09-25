# WNBA Edge Lab — model review

The August 2026 audit found that the prior version was mechanically correct but
too thin for the WNBA market. It could publish seven positions from a four-game
slate, gave most mature-season matchups the same confidence, treated a star and
a fringe inactive player too similarly, and priced totals with an 11-point
error assumption that the season data did not support.

## What changed

1. **Walk-forward calibration.** Every historical replay is trained only on
   games completed before that matchup. The latest 119-game check sets the
   margin/total bias and residual uncertainty used for pricing.
2. **Honest total variance.** The 2026 walk-forward total residual is roughly
   18 points, not 11. Wider calibrated variance materially reduces false total
   edges and Kelly stakes.
3. **Pace and efficiency checks.** Box-score shot volume, offensive and
   defensive efficiency, eFG%, three-point rate, free-throw rate, rebounding and
   assist rate now support the scoring projection. They receive a controlled
   weight because the simpler scoring baseline remains slightly more stable
   out of sample.
4. **WNBA schedule load.** Back-to-backs, three-in-four and four-in-six spots,
   rest and recent travel distance are included with capped adjustments.
5. **Role-aware player availability.** ESPN team leaders receive larger impact
   values; uncertainty scales with role. Coach's-decision and “not injury
   related” listings are shown but do not create a fake injury penalty.
6. **Independent prior.** ESPN's matchup predictor receives a small capped
   weight when available. It cannot override the local projection or the
   market.
7. **Variable confidence.** Sample size, box-score coverage, model/market
   disagreement, player uncertainty and three-point volatility now affect the
   game-specific confidence and variance.
8. **Stricter portfolio.** One position per game, three plays per slate, two
   Best Bets maximum, quarter Kelly, a 20% daily bankroll cap and a 2% at-price
   execution buffer.

## Current walk-forward diagnostics

The generated `site/data/calibration.json` file publishes the sample size,
bias, MAE, RMSE and residual sigma used by the live board. These figures update
automatically as completed games are added. They are model score-error
diagnostics, not a claim of betting profit.

## Preserved safeguards

- power-method two-way de-vigging;
- separate model edge, probability-point gap and offered-price expected value;
- current real price required before any market can qualify;
- compressed edges and a market anchor;
- no forced plays, demo data or invented -110 prices;
- manual My Ledger entries only;
- a separate shadow book for every priced model call;
- started games, stale future positions and incomplete two-way markets cannot
  become wagers.

The test suite covers price conversion, de-vigging, opponent-defence
sensitivity, projection reconciliation, market pricing, portfolio limits,
administrative absence filtering, leader-weighted injuries, duplicate
prevention and result grading.
