# Thursday, Sunday and Monday night football

The existing hub layout and sidebar remain in place, with three new routes:

- `#thursday-night`
- `#sunday-night`
- `#monday-night`

Each uses `night-football.html?night=...`, with independent retained frame state, and includes matchups, team news, original book lines/odds, production-qualified bets, player props and published research parlays.

The actual NFL schedule determines selection in `America/Toronto`; UTC dates do not identify the night. Evening kickoffs start at 18:00 Eastern. Afternoon games are excluded, and multiple Monday evening games stay together. The current night remains available after kickoff and into the following morning. A dropdown supports other published dates, and manual selection survives refreshes.

NFL and props feeds load independently and transactionally. Failed or malformed updates retain the last good snapshot and cannot qualify new bets. Production tiers, source publication freshness, individual quote freshness, holds and verification are checked separately. Betting locks at kickoff; forecast and final-game review remain visible. Page refresh checks published files and does not claim to collect live book prices.

Parlays appear only when **every original leg** belongs to selected games. Mixed-night tickets are excluded without trimming or relabeling. Combined sportsbook prices, ticket EV and same-game probability are not invented. Estimated individual-leg price products remain labeled research.

`tools/night_news.py` obtains public ESPN team-news feeds without a key for relevant games in the next fourteen days. Original story publication and receipt times are retained. Each team failure preserves its last good data and timestamp. The football/props/all collection workflow publishes the cache alongside newsletters. News does not change model coefficients or confirm a starter/injury status.

Regression tests cover Toronto midnight and DST, evening selection, doubleheaders, quote/forecast freshness, exact parlay scope, failed and malformed updates, date persistence, kickoff locks and sidebar navigation on desktop and mobile.
