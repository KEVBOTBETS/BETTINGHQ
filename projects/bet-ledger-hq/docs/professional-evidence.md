# Prices and evidence

The existing navigation and board layout remain. No new API credentials are required.

- Today cards expand to compare the latest observed offers for the same source,
  event, start time, market, player, side and selection line. Quotes without a
  source timestamp, older than four hours, in the future, or after kickoff are
  excluded. Coverage is limited to public offers actually collected. Props now
  preserve eligible offers before portfolio deduplication. Book-specific model
  probabilities are not transferred to another book. Users confirm settlement
  rules and availability at the sportsbook.
- Changes to review includes price-limit crossings for saved published picks.
  The unchanged contract must cross its saved minimum American price. A new
  quote baseline suppresses repeats. Missing feeds do not report recovery.
  These scheduled in-app alerts are not push notifications or live-market alerts.
- Refresh keeps `data/tickets/pregame-prices.json`: the last observed pregame
  price per exact contract and book, for up to 90 days / 50,000 contracts. Gaps
  are preserved; no closing timestamp is invented. Current quotes are separately
  published in `quotes.json`. These public records contain no personal receipts.
- Ledger closing-price tracking requires a confirmed receipt, same accepted
  book and selection line, explicit settlement-rule confirmation, and a quote
  after acceptance but strictly before kickoff. Unknown kickoff requires manual
  confirmation. Changed receipt terms invalidate the comparison. Legacy closing
  fields remain stored but are not treated as verified receipt comparisons.
  Movement is accepted decimal price / observed decimal price - 1, separate
  from no-vig CLV. Minutes before kickoff show observation coverage.
- Ledger and Performance Center show private actual evidence by sport / market.
  Only confirmed receipts count. Pending exposure and void counts are separate;
  settled stake includes pushes and excludes voids. Forecast scoring remains
  in the existing frozen-prediction sections and does not imply actual returns.
  ROI intervals use 1,000 deterministic bootstrap samples of whole game dates,
  after 100 settled receipts and 28 distinct dates. Those are review thresholds,
  not proof of accuracy or profitability; dates can remain mutually dependent.

Validation: exact-contract / stale quote / crossing tests, pregame retention,
receipt mismatch rejection, actual-only scoring and clustered uncertainty;
desktop and mobile integration checks plus the existing release suite.
The release review also repairs Weekly Game Props tab restoration when cached
feeds finish before the deferred panel script. Its reload test delays that script
to verify saved ticket visibility deterministically.
