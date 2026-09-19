# Accuracy and weekly selection review

Reviewed against recovered files saved on September 19, 2026. These are small
historical samples, not fresh live results or an out-of-sample evaluation of the
new release. Existing frozen records are preserved.

| Model | Winner calls | Spread directions | Total directions |
|---|---:|---:|---:|
| NFL | 12 / 16 (75.0%) | 4 / 7 (57.1%) | 7 / 15 (46.7%) |
| College football | 62 / 88 (70.5%) | 22 / 48 (45.8%) | 22 / 45 (48.9%) |
| MLB, valid pregame snapshots | 13 / 25 (52.0%) | — | See the corrected MLB report |

These are game prediction statistics, not personal wager returns. Winner hit
rate can be high simply by picking favorites, whose prices are more expensive.
Spread/total direction counts exclude pushes and games with no usable comparison.

## What the saved evidence supports

- NFL mean margin error was 11.70 points versus 11.63 for the market on the
  same 16 games. College margin error was 10.40 versus 10.32 on the 50 matched
  games. These samples do not establish an advantage over the market.
- In MLB, 335 graded snapshots had been updated after first pitch. The old
  241/360 headline (66.9%) was not a trustworthy pregame result. Removing those
  observations leaves 13/25, with 341 total excluded records including pending
  rows. Those records remain in the raw history instead of being erased.
- On the 24 clean MLB games with comparable market probabilities, the model
  selected 13 winners and the market selected 14. The new release does not
  claim to improve that record.

## Why the football board looked narrow

NFL's configured LEAN threshold is 1.5% adjusted expected return, with at most
one suggested bet per game and six plays per week. The recovered board contains
38 market rows removed as correlated alternatives and 22 removed by weekly
volume limits across its full lookahead window. Six NFL moneyline plays were
qualified in the September 19–22 window. These are rows, not independent games.

College's configured LEAN threshold is 2.5%, with a ten-play weekly cap. Ten
plays were qualified in the same window. Missing QB/player availability and
single-book prices cap otherwise stronger candidates at LEAN. Lowering an edge
threshold cannot supply that missing evidence.

The new Weekly football view therefore offers **research leans at 0.5% adjusted
return by default**, separate from qualified betting tiers. The user can change
that display minimum. It reveals positive-return estimates and volume-limited
alternatives without rewriting historical tiers or overriding data/price hard
stops. The threshold is a presentation choice, not a backtested optimum.

## NFL calibration repair

The prior calibration fit could count both sides of each market toward its
sample minimum and refit using already corrected probabilities. Its shared
intercept could also break the requirement that complementary outcomes sum to
one. New snapshots retain the uncalibrated probability. Training now requires
verified pregame timestamps, one canonical side per event/market, at least 400
event/market observations and at least 100 distinct games. A symmetric slope
correction preserves complementary probabilities. Legacy records are excluded
from training when their raw-input provenance cannot be established.

Calibration was already disabled in the recovered live settings for lack of
samples. This fixes a latent reliability issue; it is not evidence that the
next week's winner forecasts will be better.

## How to judge the next versions

Keep first-published predictions, actual quote timestamps, final scores and
version identifiers. Evaluate new predictions chronologically. Compare model
and market on exactly the same games, report sample counts, Brier/log loss and
calibration where probabilities exist, and track price/line movement separately
from winner hit rate. Treat repeated markets within one game as correlated.
Do not optimize thresholds on the same short sample used to report improvement.

The recovered snapshots do not contain a full multi-book closing-odds history.
No claim about closing-line value or profitable weekly bet volume is made.
