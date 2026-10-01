# Keyless refresh and model development

## Refresh reliability

Pushes, pull requests and manual releases run every browser check. Scheduled
refreshes may reuse an **exact** successful code fingerprint certificate; they
still run all non-browser release checks and the post-refresh data checks.
Source, configuration, tests, assets, workflow and dependency changes invalidate
the certificate. Changing public model JSON does not. No prefix cache restores
are permitted; a cache miss runs the full suite. A newly broken release cannot
certify itself. This avoids a data-dependent layout issue halting every refresh
of previously validated code. Browser regressions remain blocking on releases.

NHL/other partial source and odds coverage now produces a review warning even
when publication is fresh. Public ticket health separates freshness from
coverage. Missing odds never become invented selections. The production workflow
explicitly leaves both optional commercial odds-provider keys empty.

## Chronological comparisons

The Performance Center includes an entire-season experimental report for each
modeled league. It deliberately does not inherit the display's window/version
filters. Training and comparison cohorts never mix leagues or baseline versions.

The fixed symmetric-slope challenger chooses from 0.5, 0.75, 1.0, 1.25 using
log loss on at least 40 earlier results. A training result must have a recorded
grading/verification time strictly before the test forecast capture. Merely
starting earlier is insufficient. Missing times are excluded, not inferred.
This is an exploratory historical replay, not a claimed prospectively deployed
calibrator or a reconstruction of historical team inputs.

Reports include paired Brier/log loss, five fixed calibration buckets and a
day-clustered approximate 95% interval of loss differences. Current-model and
market comparisons use explicitly labelled cohorts. Manual review candidacy
requires 100 tests, 100 market pairs, 28 distinct dates in each comparison, and
negative upper interval limits for both loss measures against both comparators.
These thresholds are screening rules, not proof or a betting guarantee. Repeated
inspection and model selection introduce bias; promotion requires a new untouched
prospective holdout. **Automatic promotion is always disabled.** Detailed replay
predictions, training counts and last training-result times are included in
`bet-ledger-hq/data/performance.json`.

## NHL context challenger

`nhl-context-shadow-1.0` runs alongside `nhl-poisson-1.0`; the production board,
Daily Picks, Moneyline and tickets continue to use the original model and gates.
The matchup lab displays its research probability and per-component adjustments.

Public NHL team/goalie season summaries supply shots, special teams and goalie
saves/shots. Goalie matching requires an exact normalized unique name and an
explicit confirmed starter; schedule-only fallback does not invent confirmation.
Current statistics expire after 6 hours, prior-season inputs after 7 days.
Unavailable, ambiguous, stale or future-dated inputs produce zero adjustment and
a visible missing-component reason. All inputs used are available at capture.

Hypotheses are intentionally bounded and not described as trained coefficients:

- Shots: 0.025 goals per shot above/below 30, shrunk by games/(games+20), capped
  at 0.2 goals. Prior-season team feature weight is halved.
- Special teams: combined PP/PK deviation from 20%/80%, coefficient 0.75,
  similarly shrunk and capped at 0.2 goals.
- Goalies: saves/shots with a 1,000-shot 90.5% prior; prior-year evidence half
  weighted. Adjustment relative to the team's goal-rate save proxy uses weight
  0.35 and is capped at 0.3 goals. Empty-net effects limit this proxy.
- OT/SO: team wins minus regulation wins against overtime losses, Beta(10,10)
  shrinkage, half-weighted prior season; head-to-head tie-break capped 35–65%.
  It is not a playoff-specific overtime model and cannot drive tickets yet.

The challenger and provenance are deep-copied only when a **new original pregame
record** is captured. Existing history is never backfilled with today's features.
Grading keeps the original result-observation timestamp unless the score changes.
Expect an initial evidence-collection period, especially when public odds or
confirmed goalie information is absent. No accuracy improvement is claimed until
the paired prospective results support it.
