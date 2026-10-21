# NBA Courtside

Keyless public NBA board, integrated with BettingHQ Today, Moneyline, performance and manual wager ledger.

Run `python -m pipeline.build` from this directory. ESPN public scoreboards, standings and statistics provide event identities/results; current named-book odds are paired per market. Covers, VegasInsider and ScoresAndOdds public pages supplement missing contracts with exact team and start matching. Source failures keep original observation times. Unpriced markets stay missing.

The separately versioned `nba-scoring-research-1.0` baseline blends current scoring/allowed rates with a 20-game previous regular-season prior, assumes two points of home court (zero on neutral courts), and uses normal margin/total standard deviations of 12/18 points. Integer lines account for pushes. These are disclosed research assumptions, not calibrated NBA parameters. Injuries, lineup changes, pace and rest are not currently model adjustments. All NBA candidates are held research rows with zero automatic stake. Existing sports models are unchanged.

First pregame game forecasts and priced calls freeze prospectively; finals settle the original snapshots. Predictions for already-started games are never reconstructed. Season leaders retain the season actually reported by ESPN, including previous-season reference data before new leaders qualify. Recent player rows are actual game box scores, not prop projections.

Only explicitly recorded wagers enter the private browser ledger and optional existing BetSync connection. Public refreshes never read or publish browser wagers. The 30-minute NBA/NHL job reuses bounded public source downloads through the Actions cache, not large recurring source-cache commits. Browser refresh checks publication every five minutes; this is not streaming odds.

Checks: `python -m unittest discover -s tests`; the shared NBA browser test covers mobile layouts, data tabs and receipt persistence.
