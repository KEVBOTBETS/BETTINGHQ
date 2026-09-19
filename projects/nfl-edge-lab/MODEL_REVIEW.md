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
