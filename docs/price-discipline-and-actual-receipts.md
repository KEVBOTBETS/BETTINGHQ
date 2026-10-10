# Price discipline and confirmed actual bets

The existing layout and sidebar are retained. This release implements the first recommended group: minimum acceptable odds, conservative probability sensitivity, and accepted-receipt reconciliation. It does not establish profitability or implement the other seven proposed research upgrades.

## Policy

`value-core.js` is the shared calculation. For a published conditional win probability q, push probability u, and decimal price d, raw EV is `(1-u)*(q*d-1)`. The stress probability is `max(0,q-0.03)`. An additional execution policy requires stress EV at least 0.02 per unit staked. The minimum decimal price is `(1 + 0.02/(1-u))/stress_probability`, converted to integer American odds rounded toward a better price. These 3 percentage-point and 2% defaults are conservative sensitivity settings, not empirically estimated confidence bounds and not evidence of an edge.

NFL, NCAAF and NHL publish non-push conditional probabilities; props publish unconditional win probabilities and a separate non-push probability. The policy validates that pair before calculating. Other push-bearing formats require an explicit conditional probability. Unknown probabilities, invalid/unverified/model prices, unknown book identities, stale/future quotes, stale publication, held/filtered picks, unknown kickoff and started games cannot pass. Quotes use a four-hour maximum; publication a six-hour maximum. Existing tighter source limits still apply.

The portable build adds `value_policy` and retains `source_tier` to current NFL, NCAAF, NFL prop, NHL and WNBA board rows (and prop legs). Failed rows become PASS with zero suggested stakes and a stated reason. Existing PASS rows are never promoted. Published headline counts are recalculated after the gate, with original counts retained separately. Original repository forecast archives and historical grades are untouched. Research parlays remain unvalidated. MLB/Ladder retain their existing source policy; no new stress qualification claim is made for them.

Minimum odds and sensitivity details appear in NFL/NCAAF cards, NFL Props Best Bets, weekly football, the three night pages and Today. Today and night views recheck annotated rows at runtime. NFL/NCAAF actual-price dialogs recheck the stress policy and return PASS for a changed line rather than treating the old minimum odds as transferable. Recording a bet remains possible without an endorsement.

## Confirmed receipts

Ledger HQ adds a collapsible reconciliation table within the current ledger. An existing ledger entry is not assumed to have been accepted. Confirm its sportsbook, integer American odds, exact line, stake, accepted time and actual result. The first confirmation stores a reference snapshot with its capture time and provenance; it is explicitly not represented as the original publication. Later edits preserve that reference. New NFL/NCAAF native entries also retain their board probability, push basis and model version when available.

Receipts are private settings in the existing connected Sheet (`kevbot_execution_v1_<encoded id>`), with an observed history record. No public financial file or API key is required, and canonical wagers are not overwritten. Actual totals count only confirmed receipts and their explicitly entered sportsbook results. Pending receipts contribute exposure, pushes contribute settled turnover with zero P/L, and voids are excluded from turnover. The older board-ledger totals remain separately labeled as including unconfirmed entries. Different lines are marked as non-comparable; no EV is transferred.

Download confirmed receipts CSV to retain accepted prices, original reference prices, times, stakes and results. Existing missing-row recovery backups do not include these supplemental settings; the connected Sheet and the receipt CSV are the current receipt record. The UI shows the newest 100 filtered rows for reconciliation; summary and export cover all matching rows.

## Validation

`test_value_execution.mjs` covers threshold rounding across favorite/underdog odds, push normalization, stale/missing/future fields, unchanged research tiers, runtime gates, immutable first references, receipt validation, actual results and ROI denominators. `test_value_execution_browser.mjs` exercises confirmation, reload, invalid input retention, actual P/L, unchanged underlying rows and night-page quote gating at desktop and phone widths. These run with the complete portable release checks.
