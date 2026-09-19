# KEVBOTBETS — one page for every board

Open **https://chillychilly14.github.io/bet-ledger-hq/** and use the navigation
for Today, Ledger, Moneyline, MLB, NFL, NCAAF, Props and Ladder. The selected board opens inside
the workspace, without a new browser tab. On phones the navigation stays at
the bottom; on desktop it sits on the left.

Each board is loaded on its first visit and retained while switching, so its
filters, simulator inputs and scroll position stay intact. Links such as
`#mlb`, `#nfl` and `#props` open a particular board, and browser Back/Forward
works between selections. Reload board affects only the selected board.

## Moneyline: pick the winners

Open **Moneyline** (`#moneyline`) for NFL, college football and MLB winner-only
cards. Filter by Toronto game date and sport, choose either team, or fill the
card with the predicted winners. Selections save in this browser and lock when
the game starts; Print card prints the selected winners. No wager or stake is
created. This is a separate winner view of the existing forecasts, independent
of the value-bet tiers. Unavailable or stale forecasts cannot suggest picks.

Run `npm run test:moneyline` for adapter and browser checks. See
[the accuracy review](docs/accuracy-review-2026-09-19.md) for the confirmed MLB
tracking defect, its companion fix, source roles and validation limits.

The five sports repositories retain their own scheduled data workflows.
The original Ledger HQ remains at `ledger.html` and uses the same browser
storage and shared Google Sheet. See [SETUP-SYNC.md](SETUP-SYNC.md) to enable
cross-device syncing. No token or Google Sheet credentials belong in this repo.

GitHub Pages should serve `main` from `/ (root)`. Add the hub to your phone's
home screen for one KEVBOTBETS shortcut. An internet connection is required to
load boards; this hub does not promise offline caching.

## Ledger HQ

Every bet from every board, in one place — and the shared ledger the five boards
sync through.

The boards ([mlb-edge](https://github.com/chillychilly14/mlb-edge),
[ncaaf-edge-lab](https://github.com/chillychilly14/ncaaf-edge-lab),
[nfl-edge-lab](https://github.com/chillychilly14/nfl-edge-lab),
[props-edge](https://github.com/chillychilly14/props-edge),
[ladderbet](https://github.com/chillychilly14/ladderbet)) each keep their bets in
the browser, as they always have. This repository holds the two things that let
those copies agree with each other:

- **`apps-script/Code.gs`** — the Google Apps Script behind one Google Sheet.
  It is the only server involved, it is free, and the sheet is yours to read and
  edit by hand.
- **`betsync.js`** — the client the boards load. It works out what changed on
  this device, sends it, takes back what changed elsewhere, and resolves the
  disagreements. It is byte-identical in all five boards.

And the page itself:

- **`ledger.html` + `hq.js`** — the cross-sport dashboard. Combined bankroll and
  its curve, ROI by board, tier and market, open bets you can settle from your
  phone, moneyline price-change comparison, and a CSV export. Spread/total closing-line value needs additional schema support.

**Setup: [SETUP-SYNC.md](SETUP-SYNC.md)** — written for someone who has never
opened Apps Script. About ten minutes, once.

## How the pieces fit

Each board keeps its own ledger in its own shape, because each sport needs a
different one — a run line is not a player prop is not a ladder rung. The sheet
stores a flat row per bet with the columns every sport shares, plus the board's
own record carried verbatim in `native_json`. So the sheet stays readable and
sortable, a cross-sport view is possible, and no board loses anything it depends
on by passing through.

The server stamps revisions and rejects an edit based on an older revision. A
device that has been offline cannot push a bet back to pending over a result
already saved. Undo creates a new revision and blocks stale writes from
restoring the values that were undone.

## One bankroll

All five boards size their stakes off one number: what you started with, plus
every settled result anywhere. Set it once, in any Sync panel or on this page.
A losing weekend on the props board shrinks the next MLB stake, which is the
point — five separate bankrolls that only exist on paper are five ways to be
more exposed than you think.

## Tests

```sh
node tests/test_betsync.mjs   # what gets sent, what wins a conflict, what the bankroll comes to
node tests/test_server.mjs    # the real Code.gs and the real client, two devices, one sheet
```

Both run offline with no browser: the sync layer is pure functions and the Apps
Script runs against an in-memory spreadsheet. Each board also has its own
`tests/test_sync.mjs` checking that its bets survive the round trip unchanged.

## Privacy

The web app URL and the token live in each browser's own storage and are never
committed here. "Anyone with the link" is how a Google Apps Script web app is
published; the token is what actually grants access. `resetToken` in the Apps
Script editor issues a new one if you ever need to.

## Today: daily review

The default route is now `#today`. It reads published board files without changing the sports models or automatically adding bets. Filter by Toronto date and sport; stale snapshots and zero-stake held rows are excluded. Missing quote times are explicitly marked for verification. The sheet is read through the existing configured sync client, never through a public credential file.

Accuracy uses each board's frozen prediction feed, never the legacy NFL mixed-season export. Exposure groups recognizable same-game positions across boards; unrecognized bets still count toward total exposure. It is a warning system, not a joint probability estimate or automatic stake limit. Parlay exposure and inconsistent names can require manual review.

`node tests/test_today.mjs` checks adapters, stale prices, season scope, and cross-board grouping. `npm install && npx playwright install chromium && npm run test:browser` checks the dashboard at 320px, 393px and desktop width with deterministic public-feed fixtures and an unconfigured ledger. No live bets or sheet records are written by these tests.

See [SOURCES.md](SOURCES.md) for the no-key provider review and remaining constraints.

## Alerts, installation, and ticket backups

Today shows in-app changes observed during the scheduled refresh (normally twice an hour; GitHub schedules can be delayed). MLB lineup/pitcher changes use the existing board. Dated ESPN injury reports cover MLB, NFL, WNBA, and NCAAF when available. First observations establish a baseline; a missing report never means healthy. Odds alerts compare archived qualifying picks with later same-book quotes. This is not an OS push-notification service or a real-time odds feed.

Install from the hub toolbar, or use Safari’s Add to Home Screen. Only static code/artwork is cached. Live feeds, scores, private ledger requests, and credentials are excluded from the service-worker cache. Saved local ticket originals remain usable offline; result verification and backup require a connection. App updates wait for the user to choose Reload.

Generated ticket originals back up to the existing private sheet connection and merge across devices. The latest 100 are retained; images are rendered from snapshots. A failed backup retains local copies and retries when the page reconnects. Backups are scoped to the connection so changing accounts does not upload the previous connection’s tickets. Public daily archives remain separate.

## Server history and guarded undo

Deploy the updated [Apps Script](apps-script/Code.gs) using the [one-time upgrade page](server-upgrade.html). Update the existing deployment version; keep the same URL/token. The hub detects the server’s capabilities and keeps the earlier observed-history view until deployment.

The server appends prepared/applied receipts and chunked before/after payloads for API wager/settings changes. Unconfirmed writes cannot be undone. Undo checks both the revision and current values under a script lock, preserves native board data, and writes a new audit entry. Direct sheet edits, older history, and nonfinancial ticket backups are outside this audit. Tests use an in-memory spreadsheet and never alter a live ledger.

## Mobile navigation, pick history and ledger recovery

The hub has one red Top Picks button: in the desktop left panel and beside the
horizontal scrolling navigation on mobile. The former floating Today button is
removed. Mobile navigation stays in one row so the selected board keeps the screen.

Today → **What changed? Pick history** records changes to published qualified
picks from the first successful observation onward. It compares prices, lines,
books, tiers and rankings within each sport, retains up to 500 observations for
30 days, and pauses comparisons during source failures. It neither reconstructs
earlier changes nor changes any model's calculations or qualification rules.

Ledger → **Ledger backups & recovery** keeps up to 10 distinct successful ledger
snapshots in this browser, scoped to the connected sheet. Download JSON backups
to preserve them when changing browsers/devices or clearing browser storage.
Connection credentials and bankroll settings are excluded. Keep exported wager
history private. If browser storage is full/blocked, use Download current ledger.

Recovery previews the backup against a fresh sheet read. It restores at most 100
missing wager IDs per confirmation; existing rows, settlements, deletions and
bankroll settings are untouched. A second read and a server revision guard prevent
overwriting a concurrent change. Old servers can export/preview backups but require
the existing safe-undo server upgrade before restore becomes available. Re-import
larger backups to review the next batch. No wager is restored merely by uploading
or previewing a file.

Run `node tests/test_recovery_history.mjs` for the backup/history checks. Browser
tests include small-screen navigation height, the single ticket button, and a
backup → preview → cancel → confirmed restore cycle against a fake sheet only.
