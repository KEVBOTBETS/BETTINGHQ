# NFL Edge Lab — model review

Reviewed against the August 25, 2026 live build and the current MLB Edge Desk
interface.

## Calculation result

The pricing audit found and corrected one mismatch with MLB Edge: the NFL board
computed a no-vig market probability but tiered plays against the vig-included
break-even probability. It now qualifies on model return versus the complete
no-vig two-way market and keeps offered-price value separate for stake sizing.

The reviewed live run priced 33 upcoming games and all 198 available moneyline,
spread and total sides from real keyless prices. The 105-test offline suite
passed, including spread signs, NFL key numbers, tie pushes, de-vigging, market
anchoring, edge compression, confidence, injuries, weather, grading, CLV and
weekly limits.

The reviewed August 25 build shows seven preliminary regular-season edges, all
held with a C$0 suggested stake:

- preseason games are intentionally priced but never wagered;
- the first regular-season slate is still outside the configured eight-day bet
  window;
- the early Week 1 numbers remain visible for review without becoming wagers.

That is a timing and exposure decision, not a broken model. The board can flag
an edge before the betting window opens, but it cannot suggest a stake or expose
an Add to My Ledger control until the timing rule clears.

## Design changes

- Rebuilt the interface around the compact dark-first MLB Edge Desk palette,
  typography, cards, KPI strip and mobile behavior.
- Preserved every existing data view, simulator, market, ledger and health panel.
- Changed the wager ledger to MLB-style manual confirmation. Automatic tracking
  remains only in the separate model-accuracy shadow book.
- Renamed the user-facing PASS label to **AVOID**; the internal value remains
  `PASS`, so model logic and saved data are unchanged.

The original `nfl-edge` repository is untouched. This Lab is a separate upload.

## 2026-09-26 — underdog bias fix

Week 3 showed five BEST BETs, all big moneyline underdogs (+160 to +455), all
pinned at the 5.5% ceiling, with the projected score showing each one losing.
Four faults stacked up:

1. **Ratings squashed toward average.** The ridge penalty pulled every rating
   toward zero (lambda 14) while the preseason prior entered as a weak
   observation (~1.8). Spread of team strength was 1.1 pts vs 2.8 for the prior
   and 3.8 for FPI; KC–MIA came out a 3.6-point game the market had at 10.
   Ratings are now solved as deviations from the prior (real Bayesian shrinkage).
   Model-vs-market margin slope went from ~0.3 to 0.86.
2. **Pricing curve biased to underdogs.** At the market's own number the
   key-number curve gave a 7.5-pt favourite 44% to cover and a 10-pt favourite
   76% to win (market: 50% / ~83%). Every side is now priced as the market's
   fair number plus the model's *shift*, so a model that agrees with the market
   finds no edge anywhere. Moneylines de-vig with the power method
   (favourite-longshot bias).
3. **Totals squashed the same way** (slope 0.25) and total_sd was 10.2 vs a
   measured 13.8. Scoring ratings now use last season as a regressed prior;
   total_sd 13.5.
4. **Tier gates.** Probability-point floors per tier; BEST BET requires the model
   to favour the side (>=50%) and a price no longer than +150; board max price
   +300. Thresholds re-set to the honest edge range (old bars were set for
   40% raw edges and left GOOD in the top 1% and BEST unreachable). The
   "moved against us" rule now measures from the bet-window open, not the
   August opener, with a separate allowance for totals.

Tests: tests/test_market_anchoring.py. New calls are tagged tier_version
`2026-09-26-anchored` so the Accuracy tab can compare old vs new.
