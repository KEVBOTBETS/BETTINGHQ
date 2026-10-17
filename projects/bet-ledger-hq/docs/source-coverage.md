# Keyless source coverage repair — October 17, 2026

- Pin both release jobs to Ubuntu 24.04 to keep the tested runner stable during the ubuntu-latest migration.
- Capture the MLB retry fixture output. The intentional first failure remains asserted, but no longer emits a misleading real Actions warning. Production retry warnings remain enabled.
- NHL full-game public-price fallback now checks missing markets, not just empty games. Read Covers, then VegasInsider, then ScoresAndOdds until the next-48-hour games have paired ML, puck-line and total coverage. Preserve bookmaker, both sides, exact teams/kickoff, observation time, source URL and per-source results. Never use regulation 1X2 as an OT-inclusive moneyline.
- Reject hidden Covers rows, support explicit month/day kickoffs, retain source timestamps, and replace stale duplicate book contracts only with newer paired observations. Failed sources never renew prices.
- NHL and WNBA coverage separates the next 24 hours from later unposted games. A distant unposted market becomes an explanatory note; missing current prices, stale prices and optional source failures stay visible. NHL Sources shows market counts and attempted fallback results.
- College football reads current dated Covers injury reports when ESPN has no report for a team. Match exact full team names; preserve abbreviated player names and date-only precision; reject reports older than 72 hours, future dates and stale pages. Reports remain partial, do not establish starters, and do not add scoring coefficients. The existing QB review flag applies to a recent QB listing.

OddsPortal/Flashscore comparison or three-way summary numbers are not imported without an exact named-book two-way contract. Historical odds archives and Hockey Reference statistics are not substituted for live prices. Existing goalie confirmation and wager qualification rules remain in force.
