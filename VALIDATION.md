# Release validation

The release passed **33 check commands** in `tools/verify.py --browser`. The
machine-readable outcomes are included in the download's `validation` folder.

- NFL: 131 Python tests, including calibration complement, sample independence,
  timestamp and raw-input checks.
- College football: its offline calculation suite and 35 accuracy, schedule,
  context and privacy tests.
- MLB: full synthetic pipeline, pregame-freeze regression tests, configuration,
  build runner and browser-engine simulation replay.
- All three sports: existing ledger and shared-sync tests. They use fixtures;
  no real wager or Google Sheet was written.
- Hub: existing sync, ticket, alerts, history and Today tests, plus Moneyling
  and weekly research-view tests.
- Chromium browser checks: Moneyling at 320/393/1440 pixels; weekly football at
  393/1440, including a nested repository URL, lower research threshold,
  qualified-only behavior, stale/failed feeds and page-width checks.
- Portable site checks: eight board targets resolve, only the recovered sports
  are active, no executable page depends on the former account hostname, and
  public financial ledger files are empty.

NFL and college ESPN scoreboard endpoints, and the MLB public schedule endpoint,
also returned HTTP 200 during an upstream smoke check. This checks endpoint
availability only; it is not a complete live model rebuild or verification of
every upstream odds/injury field. Results are included in `UPSTREAM-CHECK.json`.

The checked package pins Python dependency versions and the hub's npm lockfile.
Workflow YAML and release-script syntax were checked locally. Source files were
scanned for common embedded token/private-key patterns; no matches were found.

**Not verified:** a deployment under a new GitHub account, its account permissions,
Google Sheet reconnection, Safari/WebKit, or future betting accuracy. The included
workflow performs fresh model builds and gates publication on successful checks.
Browser screenshots in the validation folder use deterministic fixtures, not
live picks.
