# NHL Ice Lab

Keyless NHL dashboard integrated into KEVBOTBETS: the HQ NHL tab, Moneyline winner selections/card studio, Daily Picks/Top Picks tickets, forward-only ticket archive and grading, pick/price changes, injuries, shared ledger/exposure and game-forecast accuracy.

## Run

From this directory: `python -m pipeline.build` (Python 3.12+, standard library only).
From the repository root: `python tools/refresh.py --sport nhl` stages the site and updates the shared ticket archive. The existing release workflow refreshes NHL at minutes 7 and 37 each hour, subject to GitHub queue delays, plus all-model runs. No personal API keys or sportsbook credentials are used by this project.

## Data

ESPN public NHL JSON: rolling 14-day results/8-day schedule, same-book two-sided ML/puck-line/total prices, goalie statuses, current/prior season standings, team statistics, injuries and news. Independent NHL public schedules and results provide a fallback when ESPN is unavailable. Named CA/US partners in that feed supply paired American moneyline prices; missing puck lines, totals and goalie confirmations are never invented. NHL standings and season team summaries provide goal rates, shots, faceoffs, league rankings and PP/PK. Stable game IDs preserve existing tickets when feeds switch. Source status, timestamps, sample season and missing fields remain visible. Public snapshots do not guarantee a currently available Ontario sportsbook price. MoneyPuck/Natural Stat Trick/Data Punk are linked as research resources, not presented as ingested model inputs.

Failure of both current schedule feeds, or complete team-statistics failure, aborts publication. ESPN-only failures publish the independent NHL fallback with visible source status; unconfirmed goalies hold automated picks while unpriced winner forecasts remain available on Moneyline. The repository's transactional refresh retains the last successful files with their original timestamps. Optional failures are shown individually. Historic source caches retain their original observation times. Browser/server eligibility checks reject stale quotes and started games. Source caches contain public season stats only.

## Forecast and qualification

The uncalibrated baseline blends current team GF/GA rates with 20 games of prior-season strength, regressed 45% toward 3.05 goals. Home ice adds/subtracts 0.12 goals unless neutral; back-to-back teams receive a small documented adjustment. Independent Poisson regulation goals become a final-score distribution with an equal OT/SO tie-break and a deciding goal. These projections are not shot-based xG. Goalie talent, player injuries, empty-net effects and playoff OT dynamics are not independently fitted; they are limitations, not hidden calibrated features.

Moneyline winner cards use the unpriced model forecast. Priced recommendations use 25% model probability and 75% same-book no-vig market probability; integer lines handle push mass explicitly. At least 3% expected return qualifies a lean, 5% good and 8% best, provided both goalies are confirmed, the game is regular season/playoffs and within 24 hours, stats are usable, and both prices were observed within 90 minutes. Raw model/market disagreement above 15 percentage points or expected return above 15% is held for review. At most one qualified market per game flows to daily picks. No thresholds imply validated profitability.

Every first pregame game forecast freezes before puck drop and is later graded from finals, even without a wager. Preseason/exhibitions never enter model accuracy or automated recommendations. NHL moneylines include overtime/shootouts; market settlement assumes standard full-game terms. Personal wagers are entered explicitly with actual stake/odds/book, remain local or in the user's configured shared Sheet, and are never committed with public model data.

## Checks

`python -m unittest discover -s tests`; hub `tests/test_nhl.mjs` checks cross-league adapters, ticket grading, puck-line orientation and shared sync. `tests/test_nhl_browser.mjs` checks desktop/mobile rendering, NHL moneyline selection/card export, filters, stale-feed behavior and explicit local ledger entry. These checks are included in `tools/verify.py`.


### NHL desk and keyless price recovery

Visible full-game Covers tables provide a first independent book-price fallback;
VegasInsider provides a second. Matches require exact home/away identity and
scheduled start, complete two-sided prices at one named book, and compatible
puck lines/totals. Covers publication timestamps stay attached to quotes. Opening
and consensus columns never become named-book offers. A failed read never renews
old prices. The board shows the best fresh price on each side; each candidate
retains its own opposite same-book price for no-vig calculation.

Every future game has a manual research entry for moneyline, puck line or total,
even without public odds. Exact user prices and lines are required. Research
entries remain separate from qualified recommendations, and started games lock.
The shared ledger still settles against official final scores.

NHL Props adds participation-conditional anytime scorer estimates from current
and prior official club goal counts. Gamma-Poisson shrinkage uses 12 baseline
games and at most 30 prior club games, a bounded matchup adjustment and a cap on
team player goal rates. Goalies and players without five historical games are
excluded. Regulation/OT scoring is modeled; shootout goals are excluded. This
model has not been prospectively calibrated. Transfers, line deployment and
injuries require review. Model fair odds are never sportsbook quotes.

Two-, three- and four-to-six-leg scorer research combinations use distinct games
on the same Eastern calendar day. Products assume independence and are not
calibrated joint probabilities. Same-game scorer tickets remain manual research
without a claimed joint chance. Saveable tickets require observed book offers;
manual anytime offers use a binary Yes contract with no made-up numeric line.
