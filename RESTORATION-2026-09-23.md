# BETTINGHQ restoration — 23 September 2026

This repair keeps the new hub, Weekly football, Moneyline, parlay layout and all five card styles. It reconnects the complete WNBA and Ladder projects recovered from the 16 September source backup and restores the missing Props tools.

## Restored features

- WNBA and Ladder navigation, public deployment, refresh jobs and accuracy feeds.
- Props in Today, Top Picks, tickets, pick history, alerts and data health.
- A direct Accuracy entry in the hub; the long alerts section starts collapsed.
- Props Best Bets, held alternatives, every projection, the 10,000-run Matchup Lab, complete forecast history, downloads, model/source status and configurable staking.
- Props shared ledger and shared bankroll. Existing browser entries remain intact and require an explicit review before they join the shared ledger. New entries require actual accepted price, stake and sportsbook. No forecast creates a wager.

## Corrected calculations and history

All 26,506 recovered Props forecast records are retained with their original prediction, event, player, start and capture timestamp. Current-season reporting includes every saved pregame projection, whether priced, passed, held or unbet. Player-stat error and hypothetical returns at real offered prices are separate from actual wager profit.

New exact-line observations use real event IDs, freeze before kickoff, retain the first prediction across refreshes and dates, and cover every published leg rather than the first 400. One preferred side per player/market/event drives headline leg accuracy. The full side/line audit remains downloadable. The 17 legacy leg results without trustworthy pregame capture timestamps are preserved separately and excluded from verified accuracy. They are not added to the restored player projection totals.

Parlay scenarios no longer earn a claimed positive EV from model-generated prices. Fixed same-game correlation boosts are removed. Same-game win probabilities remain unavailable until a joint model is validated. Independent combinations show an independence estimate and require confirmation of the actual combined quote. This does not force more recommendations or inflate confidence.

Imported quotes require the exact event, player, market, side and line, a sportsbook and an observed timestamp. They expire and stop applying at kickoff. The old unscoped imports remain in browser storage but are not reused. CSV templates leave prices empty. A single calculation feeds the screen and share image; for example, three imported +200 legs yield +2600 and a $270 illustrative return on $10. Game dates use America/Toronto.

Expired, future-dated, unidentifiable or invalid sportsbook prices cannot enter new hypothetical-return records. Fresh PASS calls and all unpriced player projections are still tracked. Saved historical forecasts remain unchanged.

A real keyless refresh during repair retrieved 217 book quotes, 7,047 player projections and eight selectable Props options, with another fourteen held alternatives. These are a dated verification sample, not a promise of current availability. The options were LEAN because the qualified quotes were one-sided or the player/market disagreement required reduced confidence. Their labels were not raised merely to create GOOD/BEST picks. Full qualification reasons are displayed.

## Refresh and publication

The root workflow is authoritative. Full model refresh runs every three hours, with extra football runs on the existing schedule. Ticket and alert collection runs at :07 and :37 each hour from the repository's own published feeds. It preserves quote timestamps. Alerts use a four-hour delayed-collection threshold. Original nested workflows remain source references and are not activated separately in this monorepo.

Models refresh in an isolated copy. Generated output is copied back only after the model completes successfully, so a failed refresh cannot replace the published board with partially written data.

Public staging empties financial ledger outputs. Ladder retains its source history in the recovery but does not inject those bets into visitors' browsers. Browser-local history belongs to its original web origin; reconnect the existing Sheet or import a reviewed backup when using a new account/domain.

## Validation and limits

Run `python tools/verify.py` for all offline model, grading, shared-ledger, simulator, routing and publication checks. `python tools/verify.py --browser` also runs the existing browser suites, including the updated Props import/ledger regression flow. The accompanying validation report records what was actually run.

All 44 offline release checks passed, including the restored Props interface in a DOM test, all six models, grading, frozen history, shared ledger, and public-site staging. The local preview could not be opened by this session's cloud browser, so no visual browser pass is claimed.

Publication was attempted after the user attached the new GitHub account. GitHub is listed as installed, but account and repository checks currently fail with an unavailable-tool error; command-line Git also has no authenticated publishing credentials. No repaired code has been pushed or deployed by this session. The package contains the complete source, patch and verification results for upload through KEVBOTBETS/BETTINGHQ once authenticated publishing is available.

Software fixes do not establish an out-of-sample betting advantage. MLB/NFL accuracy safeguards already present in the new repository are retained, as are Weekly football's adjustable research filters.
