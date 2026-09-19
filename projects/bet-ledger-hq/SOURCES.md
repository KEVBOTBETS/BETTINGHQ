# Odds sources and remaining constraints

Reviewed 2026-09-14. An accessible webpage is not a permission grant or a guarantee of a stable, current odds feed.

2026-09-19 follow-up: keep ESPN for existing odds/schedules. TeamRankings and
Sports Reference are statistics research references, not replacement odds feeds.
Verified NFL/CFB points-per-game and MLB runs-per-game pages are linked from
Moneyline. TeamRankings' copying/storage restrictions mean no background
importer was added (https://www.teamrankings.com/terms-of-service/). Reference
site requests could not be verified here. OddsPortal/BetExplorer homepages alone
do not establish a usable historical or closing-odds API. Details and model
findings: [accuracy review](docs/accuracy-review-2026-09-19.md).

- Existing MLB/NFL/NCAAF pipelines already consume public ESPN data without user API keys. Keep provenance and timestamps, reject missing/unverified prices, cache conservatively and respect failures/rate limits. No in-play latency guarantee.
- NFL Props uses keyless ESPN player statistics and current rosters. Key-based sportsbook requests are disabled at the user's explicit request. Existing GitHub secret values are not read by the build. The Today dashboard adds no keys, tokens, third-party paid services or sportsbook integrations. A reliable authorized no-key replacement for the complete prop-price feed has not been verified.
- Apify's listed Sports Data Scraper explicitly uses an Apify token in its integration examples; using a wrapper does not remove authentication or possible cost: https://apify.com/sian.agency/sports-data-scraper
- SportSRC's documented V1 routes cover schedules, streams, results and standings. No suitable structured sportsbook prop-price endpoint was documented: https://sportsrc.org/
- Football-Data provides soccer data. It is not a replacement for the current MLB/NFL/NCAAF and NFL player-prop feeds: https://football-data.co.uk/data.php
- VegasInsider's terms restrict redistribution/public display without permission. No scraper or redistribution integration was added: https://www.vegasinsider.com/terms-of-use/
- Flashscore expressly restricts automated requests and scraping without consent: https://www.flashscore.com/terms-of-use/
- Covers restricts redistribution and public display without prior permission: https://www.covers.com/terms
- Oddschecker and OddsPortal are not integrated merely because a proposed list calls them scrapeable. A suitable allowed endpoint, exact markets/books, timestamp semantics and live response contract must be verified before adding one. No bot-block bypasses, hidden credentials, residential proxies or paid scraper services.
- Octoparse and WebHarvy are tools, not independently licensed sportsbook odds feeds.

## Safe implementation boundaries

Manual ledger entry stays manual. Today is a read-only overview; confirm the currently offered price and stake in the original board. Published odds age, model/data generation and sheet synchronization are separate clocks.

The Today accuracy cards do not claim profitability from winner accuracy. MLB market comparisons use the same matched sample. NFL/NCAAF use the current-season accuracy feeds. Props reports player-stat error; Ladder remains market-based screening.

Cross-board exposure is grouped only when sport, Toronto event date and team names match. Ambiguous rows/parlays remain in total exposure and are identified as unmatched. This is not complete correlation measurement.

## Still requiring separate work

- Complete no-key NFL prop-price coverage remains unverified; keyed providers are disabled, so Props remains projection-only until a usable keyless source is verified.
- New availability sources require verified access and current dated reports. Missing NCAAF reports remain explicitly flagged.
- Closing spread/total values require backward-compatible end-to-end ledger schema and deployed Apps Script support before full line-aware CLV can be claimed.
- Same-game parlay estimates now explicitly suppress an uncalibrated all-win probability. New model inputs and calibrated joint parlay probability estimates still require forward validation and suitable data. Do not invent coefficients or raise stakes because a small initial sample looks good.
