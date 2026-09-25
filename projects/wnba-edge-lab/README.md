# WNBA Edge Lab

An automatic WNBA model and dashboard built to follow the same operating model
as MLB Edge Desk. It fetches the schedule, results, team performance, injury
reports and available DraftKings prices from ESPN's public feeds, then rebuilds
the board without asking the user for data or an API key.

There is no uploaded slate, spreadsheet input, sample board, demo mode or
fabricated fallback. If a live refresh fails, the last successfully fetched
real-data cache remains visible and is labeled. If no real cache exists, the
dashboard shows an honest no-data state.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m pipeline.build
cd site && python -m http.server 8000
```

Open <http://localhost:8000>. `python -m pipeline.build --offline` rebuilds from
the last real cache only; it never synthesizes games or prices.

## Automatic operation

The GitHub Actions workflow refreshes several times daily and on every push to
`main`. Each run:

- refreshes the season schedule, final scores, current markets and injuries;
- builds pace/efficiency, shooting, rebounding, venue, travel and schedule-load profiles;
- weights reported absences by player role and ignores administrative non-injury listings;
- walk-forward calibrates bias and score uncertainty without using future results;
- selects no more than one position per game and three per slate;
- freezes every priced model call in a separate accuracy shadow book;
- republishes the static dashboard to GitHub Pages.

Qualified plays are recommendations only. They are **not** written to My
Ledger automatically. Review the current sportsbook price, click **Add to My
Ledger** only after you place the wager, and edit the stake to the amount you
actually accepted. The browser locks that confirmed entry and grades it from
the final ESPN score. JSON and CSV export keep a portable backup.

The dashboard includes Best Bets, Full Board, Schedule, a 10,000-run scenario
simulator, My Ledger, Accuracy, Model and Data Sources views. One selected date
drives every relevant view.

## Risk rules

- C$200 starting model bankroll and quarter-Kelly sizing;
- C$5 minimum, C$60 hard maximum, 10% per-bet limit and 20% daily exposure cap;
- 1.8% Lean, 3.2% Good and 4.5% Best Bet compressed model-edge thresholds;
- 75% minimum confidence, with stricter Best Bet gates;
- at least 2% positive value at the offered price after edge compression;
- no more than three plays, two Best Bets and one position from any game;
- no selection while a high-impact player has a materially unresolved status;
- no-vig two-way market comparison for qualification, with actual offered-price
  break-even and realized value kept separate;
- moneyline, spread and total pricing only when real two-sided quotes exist;
- started games and unpriced markets are never selected.

See [`MODEL_REVIEW.md`](MODEL_REVIEW.md) for the calculation audit. Model output
is informational, not betting advice or a guarantee.

## Publication reliability (September 2026)

- Scheduled source refreshes run at 04:17, 08:17, 12:17, 16:17, 20:17 and 23:17
  UTC, reducing the previous overnight gap. GitHub schedules can still be delayed.
- An open, visible page checks for a new publication every five minutes and on
  return after at least a minute away. This checks published files, not sportsbooks.
- Background updates retain the selected date and tab, defer while editing a
  stake, using the simulator/history, or importing a ledger, and retain existing
  data if the download fails or spans two different publication versions.
- Status badges show publication age, source warnings and stale/cached data.
  Quote-age/start-time eligibility rules are unchanged and still checked at Add.
- Confidence is distinct from win probability. Missing injury listings do not
  prove a healthy lineup; check team news. Accuracy totals include AVOID/legacy
  calls and remain separate from the manual wager ledger.
- The existing quarter-Kelly calculation, C$5 stake floor, C$200 model reference,
  all thresholds, daily limits, projections, simulations and grading are unchanged.
  The stake floor can raise the displayed stake above its quarter-Kelly amount.

Additional presentation/refresh regression checks:

```bash
node tests/test_feed.mjs
node tests/test_refresh.mjs
```
