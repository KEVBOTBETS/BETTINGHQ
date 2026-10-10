# Keyless prop price recovery

Covers is the primary public price source. Normalize Unicode minus signs and
recognize sportsbook labels containing “Odds”, while preserving card boundaries,
unknown-book boundaries and unique scheduled-player matching.

DraftKings Network's public props table is a fallback, requested only when Covers
has no prices. Initially it accepts exact anytime touchdown scorer contracts,
matching full player name, both teams and displayed Eastern kickoff date/time
against the frozen schedule. Milestone markets such as “2+ TDs” and “50+ yards”
are rejected. The public table is a regional reference: its prices remain research
until confirmed at the user's sportsbook. Unavailable or restricted pages are
reported without an access workaround or repeated request.

`state/price_quotes.json` stores the last quote snapshot. A failed source may retain
its prior offers, with the original price, line and observation timestamp. A
successful source replaces its prior snapshot, including removing offers no longer
present. Retained and reference offers cannot qualify automatically. Four-hour-old
offers leave the active quote feed; expired records survive during outages for up
to 72 hours or kickoff in `site/data/quote-history.json`. Future timestamps,
rescheduled events, missing/invalid prices and unmatched players are rejected.

Best Bets shows observation / retention / expiration counts. Sources & method
shows provider status and diagnostics, player-market coverage, qualified counts and
rejection categories. Counts are offers or projections, not unique wagers. Today
labels retained and reference comparison quotes without refreshing their timestamps.

Validation includes parser drift and unknown-book isolation, exact fallback event
matching, outage/recovery/expiry tests, no automatic qualification of cached or
reference prices, and desktop/mobile coverage checks. Live captured Covers offers
were checked against their sportsbook columns. The local runtime could not fetch
the DraftKings Network table; its fallback reports that condition explicitly, and
its parser is tested against the public table schema and published offer examples.
