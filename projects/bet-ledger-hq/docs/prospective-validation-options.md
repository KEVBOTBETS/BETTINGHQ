# Forward validation with every-game research options

The public release builds market controls from immutable `market-calibration-v2`
captures. Legacy captures remain in the research archive, outside the new controls.
V2 explicitly handles conditional spread probabilities and push mass; observed
prices must be under four hours old and forecast publications under six hours.
Retained, regional reference and estimated prices cannot enter this forward record.
Same-book, same-time opposite quotes provide a frozen de-vigged benchmark where
available. Missing historical benchmarks are never backfilled.

Each sport, market and baseline version has its own record. One player/market per
scheduled event votes once, regardless of alternate lines or books. Controls need
200 settled contracts, 100 distinct events and 28 game dates before acting.
Day-clustered bootstrap intervals identify sustained chosen-side overconfidence
above five percentage points, or model inferiority to the frozen market on both
Brier error and log loss. These exploratory controls pause public recommendations
and suggested stakes, without changing original forecasts or existing wager receipts.
An insufficient sample is explicitly unproven; it does not imply that an edge exists.
Calibrators fit only earlier verified outcomes and stay in shadow mode. Prospective
improvement against both baseline and market produces a review candidate, not an
automatic model promotion or profit claim.

Performance displays the controls; its league/version selection applies, while its
time window does not truncate this forward control record. Audit JSON is downloadable.

All Football Spreads keeps every scheduled NFL and NCAAF game visible and manually
selectable before kickoff. A research cover direction is shown where inputs permit;
missing spread/price inputs require the user's actual book numbers. AVOID, BAD and
paused recommendations do not lock manual selections. A failed refresh retains the known schedule in the current session, marks forecasts stale and asks for current book confirmation. No side or price is invented
to satisfy a betting quota, and saved plans do not place wagers.

Longshot research adds +500 to +1,000, +5,000, +10,000, +30,000 and +50,000 targets.
A +500 same-game scenario may use two legs; higher targets retain existing minimums.
When the same same-game legs appear in a slate search, the game scope takes priority
rather than duplicating the ticket. Targets are search goals, not offered combined
prices. Actual estimated odds and off-target warnings remain visible. Paused markets
remain available for moonshot research; core tickets omit paused-market legs.
No ticket is padded or assigned a positive EV to meet a target. Unsupported games
and insufficient combinations stay visibly unavailable.
