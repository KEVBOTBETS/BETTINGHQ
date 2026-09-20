# Props Edge — NFL only

Props Edge is the NFL player-prop board inside KEVBOTBETS. It covers touchdowns,
passing, rushing, receiving, kicking and defensive markets, and it has four tabs:

- **Parlay lab** — parlays built to a payout target (+1,000 / +5,000 / +10,000 /
  +30,000 / +50,000) for the full slate, for one day, or as a same-game parlay.
  Every ticket shows the model's own win chance, the 1-in-N hit rate, what $10
  returns, and the expected value at that price. Same-game tickets show the
  correlation multiplier that was applied.
- **Cheat sheets** — one market at a time, ranked by model probability, with the
  stat behind each number. It exports as a KEVBOT card image.
- **Prop board** — every leg the model will use, searchable, with its projection,
  recent form and price.
- **My ledger** — singles and parlays saved in that browser, with stake, result,
  bankroll and CSV export.

## Where the lines and prices come from

**Lines (the numbers), keyless.** ESPN publishes the DraftKings prop board on its
own public feed — player, market and the posted number — for every NFL game. Props
Edge reads it on every refresh, with no key and no scraping, and scores those exact
numbers. That means the board shows the line that will be on your bet slip instead
of one the model made up.

**Prices (the odds).** ESPN's feed does not include them. So each leg's price is the
model's own probability with a normal two-way hold applied, labelled **EST**
everywhere it appears. Three ways to get real prices:

1. Paste them (below) — no account, no key.
2. Odds-API.io, when its GitHub Actions secret is configured.
3. The Odds API, when its secret is configured. Only the six core prop markets are
   requested, only for games inside the kickoff window, because that provider charges
   one credit per market per game and the free tier is 500 a month. The credits left
   on the key are published in `meta.json` and shown on the page.

ESPN box scores also supply the player history the model projects from; that part
never needed a key either.

### Getting real prices in without a key

Use **Paste odds** on the page. Copy lines from any sportsbook or odds screen —
DraftKings, FanDuel, BetMGM, bet365, Caesars, theScore Bet, Pinnacle, OddsJam,
BettingPros, Action Network, Covers, VegasInsider, OddsShark, Props.cash — and
paste them one per line:

```
Josh Allen anytime touchdown +120
Tee Higgins over 58.5 receiving yards -115
Jahmyr Gibbs Over 4.5 Receptions +105
```

The page reads the player, market, side, line and price, and re-prices the board,
the cheat sheets and every parlay. If the book's line differs from the model's, the
leg is re-scored at the book's number instead of being ignored. Pasted prices stay
in that browser; nothing is uploaded. **Import CSV** does the same from a file.

These sites are never scraped by the pipeline. Their terms do not allow automated
extraction, so prices arrive either from a licensed odds API key or from this paste
box.

## Parlay rules

- One market per player per ticket, and no leg that contradicts another.
- Slate and day tickets take at most two legs from any one game; same-game
  tickets allow up to eight legs from that game.
- A leg needs at least two recent games of player history before the model will
  price it.
- Same-game legs get a correlation adjustment (quarterback with his own pass
  catcher, touchdown stacks), capped so a ticket can never claim a large edge
  from correlation alone.
- Bigger targets always mean a lower model chance. The card shows both so the
  trade is explicit; none of these tickets is a recommendation.

## Fast GitHub setup

1. Create a new public GitHub repository named `props-edge`.
2. Unzip this project and upload the files and folders inside it to the repository root.
3. Commit the upload to the `main` branch.
4. Open **Settings → Pages** and choose **GitHub Actions** as the source.
5. Open **Actions → Refresh Props Edge → Run workflow**.

The workflow refreshes automatically five times per day and redeploys the page. It can also be run at any time from GitHub Actions or through the dashboard's **Run GitHub update** link. The **Game date** selector lets you isolate today, tomorrow, or any other available scheduled day in the seven-day window.

## Add private odds-provider keys (optional)

Any key previously pasted into chat, source code, or another public location must be revoked and replaced at the provider before use.

For each replacement key:

1. In the new repository, open **Settings → Secrets and variables → Actions**.
2. Choose **New repository secret**.
3. Create `ODDS_API_IO_KEY` for Odds-API.io.
4. Create `THE_ODDS_API_KEY` for The Odds API.
5. Paste each replacement value only into its matching secret and save it.
6. Run **Actions → Refresh Props Edge → Run workflow**.

Do not put a key in an Actions variable, `.env` file, JSON file, JavaScript, HTML, issue, commit message, or workflow text. The workflow reads the two repository secrets only during the private data-build step. It publishes player, market, price, model, and source fields—not credentials or provider request URLs. Provider errors are sanitized before they reach public JSON.

The `.gitignore` excludes `.env` files. The automated tests also reject long secret-shaped hexadecimal tokens before each refresh.

## Run without any API keys

No setup is required. The workflow automatically uses ESPN's public schedules and recent box scores. When enough recent player samples and an upcoming matchup exist, the site displays projection cards. ESPN does not publish sportsbook prop odds, so it cannot calculate price-based expected value by itself.

This mode may legitimately show no rows during an offseason, before schedules are posted, or before players have enough recent games.

## Import current sportsbook lines

On the dashboard, choose **Download CSV template**, enter current lines, then choose **Import sportsbook lines**. Required columns are:

```csv
sport,player,market,line,over_odds,under_odds,yes_odds,no_odds,book,matchup
NFL,Player Name,Receiving yards,64.5,-110,-110,,,DraftKings,Away @ Home
NFL,Player Name,Anytime touchdown,,,,+150,,DraftKings,Away @ Home
```

The CSV is read only by that browser tab and is not uploaded, committed, or retained after the page closes. Player and market names must match a displayed ESPN projection.

## Bet ledger

- Choose **Add to ledger** on any Best, Good, or Lean card.
- Change the stake and set the result to Pending, Win, Loss, Push, or Void.
- Win/loss profit is calculated from the saved American price and stake.
- Add closing odds to calculate CLV, and keep injury, role, or line-movement notes with the bet.
- The dashboard calculates open exposure, available bankroll, settled P/L, and ROI.
- Choose **Export ledger CSV** to download the complete ledger.
- Ledger entries use browser storage and persist on that browser and device. They are not uploaded to GitHub and do not automatically sync to another phone or computer.

## Data and model rules

- DraftKings is the target book for automatically priced plays. FanDuel is the second primary comparison book so the free Odds-API.io account stays within its two-book maximum.
- Generic odds-provider labels are normalized into real prop markets, including the full NFL group above, MLB batter and pitcher props, and WNBA points, rebounds, assists, threes, and combination props.
- Consensus probabilities use complete two-sided prices from at least two books and remove the two-way market margin before comparison.
- If DraftKings has a current price but fewer than two consensus books are available, the model can conservatively compare that price with the matching ESPN player projection. These cards are explicitly labeled `DraftKings price vs ESPN projection`.
- Model probabilities are shrunk toward 50% to reduce overconfidence.
- A positive expected value and at least a 2% model edge are required for a Lean; 4% is Good and 6% is Best.
- Prices outside -250 to +500 are rejected, except NFL anytime-touchdown prices may extend to +750 because that market naturally contains longer odds; the conservative touchdown model and $50 stake cap still apply.
- ESPN projections use up to eight recent player games, weight recent games more heavily, and show the sample count and confidence.
- Action Network and OddsShark are not scraped because automated extraction is prohibited or blocked. Sportsbook sites can also be geo-, age-, and bot-gated, so they are not a reliable unattended GitHub Actions feed.

This is an informational model, not a promise of profit. Verify the player, market, line, price, and availability at the sportsbook before betting, and use legal age and responsible-gambling limits.

## Local checks

```bash
python -m unittest tests.test_offline -v
python -m pipeline.build
python -m http.server 8000 --directory site
```

Then open `http://localhost:8000`.
