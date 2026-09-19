# WNBA and Top Picks rollout

## Included

- WNBA navigation, qualified-feed adapter, health warnings and exposure grouping.
- NBA, NHL and NCAAB are inactive entries in `sports.json`. They do not produce picks or empty broken frames. Activating a future board requires a real feed, adapter tests and a navigation entry.
- Classic, baseball, hockey and football ticket styles using original KEVBOT artwork, with no third-party team branding.
- Current ticket previews freeze their picks when opened. Style changes do not change those picks. The latest 30 generated tickets are kept on that browser. Storage failures are visible.
- A scheduled public archive runs at minutes 7 and 37 each hour (GitHub schedules can be delayed). Tickets are append-only by content ID. Results and quote observations are separate files.
- Official MLB/ESPN final-score grading, selected supported NFL prop statistics, correction history and pending-review treatment for unsupported/ambiguous results. Book-specific voids are never inferred from a postponed game or missing player statistics.
- Hypothetical one-unit ticket performance, grouped by source, market, tier and model version. Repeated publication of the same selection does not multiply its record. The first published line and price are used for performance. Different snapshot lines are graded independently for images.
- Cross-sport tier rotation replaces raw cross-model edge comparisons. Probability-error sample counts are reported; genuinely calibrated cross-model ranking needs more forward results and is not claimed here.
- Same-book, last-observed pregame quote tracking. Line advantage and same-line implied-price difference are separate. These observations are closing proxies, not guaranteed closing prices.
- Manual closing-quote details and shared observed-change history in existing sheet settings. No Apps Script schema change or redeployment is needed. Settings-only writes are covered by the actual server's in-memory integration tests.
- Failed fetches retain the last successful publication information but cannot qualify new bets. The monitor shows failures and last-success timestamps.

## Boundaries

No credentials or personal ledger data enter the public archive. No recommendations automatically become real wagers. Actual bankroll returns remain separate from hypothetical ticket results. The WNBA adapter syncs only its manually confirmed wagers.

The HQ history is an observation log, not a complete server audit: its first read establishes a baseline, and intermediate changes while HQ is closed can be missed. Full server-side audit/undo requires a separately deployed Apps Script upgrade.

Locally created tickets are device-local, not automatically published to GitHub. Their picks can be exported from Tickets & results. The scheduled public archive is available across devices. Local picks only receive a result overlay when that exact selection and line are present in the public result set.

WNBA's shared bankroll is displayed without altering its prediction model or server-calculated suggested stakes. The UI labels the model's reference bankroll separately; confirm the actual amount when manually adding a wager.

## Verification

Run `node tests/test_today.mjs`, `node tests/test_tickets.mjs`, `node tests/test_betsync.mjs`, `node tests/test_server.mjs` and `npm run test:browser`. WNBA adds `node tests/test_sync.mjs` to its existing deployment tests. `tests/render-tickets.mjs` is optional offline artwork QA using the Codex runtime canvas package.
