# Broadcast edition and forecast evidence

The shared theme is applied during staging, including generated NFL and Ladder pages. The hub includes a seven-league Sports Desk and dedicated NBA/NCAAB research routes. Existing ticket, ledger and qualification engines remain in place.

Sports Desk reads ESPN's public scoreboard, news and standings endpoints without keys. It labels retrieval time, separates each endpoint's failures, and falls back to timestamped published game snapshots where available. A failed request is never presented as proof that no games exist. NBA/NCAAB are research-only until a model is validated. External research links are not model inputs or claims of unrestricted reuse; MoneyPuck's published usage terms still apply.

## Performance Center

`tools/performance.py` builds `data/performance.json` from public game forecast history. The source logs remain unchanged. Each accepted row requires an event ID, resolved teams, a timezone-aware pregame capture, a valid home-win probability and verified non-tied final scores. Only one record per league/event is accepted. MLB requires its last stored update to predate first pitch; an older first-seen timestamp cannot rescue a postgame overwrite.

The page provides season/window/version filters, Brier score, log loss, winner-call accuracy with Wilson intervals, calibration buckets, a CSV audit and paired market comparisons. All probabilities have the same target: a home win. Exactly 50% forecasts are scored for probability error but omitted from winner-call accuracy. Metrics are recomputed over the selected sample. Props and Ladder use different targets and remain separate. Source collection timestamps and exclusion counts are public.

Market Brier comparisons require probabilities for the same games. Spreads are not converted into synthetic historical moneyline probabilities. NHL and WNBA now freeze fresh same-book, two-sided no-vig probabilities when they are available at the first game forecast. Later prices cannot be added to an older snapshot. Margin and total error comparisons also use matched games. Positive historical skill is descriptive, not proof of profitability or independent model skill; some models already blend market inputs.

WNBA bracket placeholders (TBD/TBA/Unknown teams) no longer generate new projections or frozen forecasts. Older placeholder records remain in the audit but are excluded from performance summaries.

## Adding a league

1. Add its research configuration in `sports-desk-core.js` and its capabilities in `sports.json`.
2. Implement independent schedule/team identities, score status, timezone-aware start/capture timestamps and explicit source health. Keep missing odds and lineups missing.
3. Freeze forecasts before play; verify outcomes independently; add an adapter to `tools/performance.py`. Use a sport-appropriate outcome target (a three-way sport cannot silently use the binary scorer).
4. Validate chronologically, by model version, against the market on identical games. Keep research available while ticket qualification remains disabled.
5. Enable Today/Moneyline/archives only after adding eligibility, freshness, settlement and regression checks appropriate to that sport. A registry flag alone must not create a priced pick.

No claim of market-leading accuracy is made. More data sources or a visual redesign are not evidence of better predictive performance.
