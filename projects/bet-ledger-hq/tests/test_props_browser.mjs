/* Props Edge: parlay lab, cheat sheet, board, ledger and the card studio.
   The model files are stubbed so the page is checked, not today's real slate. */
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';

const SITE = path.resolve(process.cwd(), '../../_site');
const TYPES = {'.js': 'text/javascript; charset=utf-8', '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml'};
const server = createServer(async (request, response) => {
  let pathname = decodeURIComponent(new URL(request.url, 'http://local').pathname);
  if (pathname.endsWith('/')) pathname += 'index.html';
  const file = path.resolve(SITE, '.' + pathname);
  if (!file.startsWith(SITE)) return response.writeHead(403).end();
  try {
    response.setHeader('Content-Type', TYPES[path.extname(file)] || 'application/octet-stream');
    response.end(await readFile(file));
  } catch (_) { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = 'http://127.0.0.1:' + server.address().port;

const start = '2026-12-20T18:00:00Z';
const leg = (player, market, side, line, price, probability, matchup) => ({
  id: `${player}-${market}-${side}-${line}`.toLowerCase().replace(/\s+/g, '_'),
  sport: 'NFL', event_id: matchup, matchup, start_time: start, player, team: matchup.split(' ')[0],
  market, side, line, pick: `${player} ${side} ${line ?? ''} ${market.toLowerCase()}`.trim(),
  price_american: price, price_decimal: price > 0 ? 1 + price / 100 : 1 + 100 / Math.abs(price),
  price_source: 'model', book: 'Model estimate', model_prob: probability, samples: 6,
  projection: 60, recent: [55, 62, 71], confidence: 0.6, group: market === 'Anytime touchdown' ? 'touchdown' : 'receiving',
  reason: `${player} reason line for ${market}.`,
});
const legs = [
  leg('Alpha Player', 'Anytime touchdown', 'yes', null, 150, 0.44, 'BUF @ HOU'),
  leg('Bravo Player', 'Receiving yards', 'over', 58.5, -120, 0.55, 'BUF @ HOU'),
  leg('Charlie Player', 'Receptions', 'over', 4.5, 110, 0.48, 'DAL @ NYG'),
  leg('Delta Player', 'Anytime touchdown', 'yes', null, 260, 0.3, 'DAL @ NYG'),
];
const ticket = (id, scope, label, target, rows) => {
  const decimal = rows.reduce((total, row) => total * row.price_decimal, 1);
  return {
    id, scope, label, target, legs: rows, leg_count: rows.length,
    price_decimal: decimal, price_american: Math.round((decimal - 1) * 100),
    payout_on_10: 10 * decimal, model_prob: 0.12, independent_prob: 0.1, correlation_applied: 1.2,
    fair_american: 700, expected_value_on_10: 1.2, one_in: 8, estimated_prices: true, off_target: false,
    games: [...new Set(rows.map(row => row.matchup))], start_time: start,
  };
};
const parlays = {
  generated_at: start, targets: [1000, 5000, 10000, 30000, 50000],
  counts: {slate: 2, day: 0, game: 1}, estimated_prices: true,
  tickets: [
    ticket('slate-1000-a', 'slate', 'Full slate', 1000, [legs[0], legs[2], legs[3]]),
    ticket('slate-5000-a', 'slate', 'Full slate', 5000, [legs[0], legs[2], legs[3], legs[1]]),
    ticket('game-1000-a', 'game', 'BUF @ HOU', 1000, [legs[0], legs[1]]),
  ],
};
const meta = {
  generated_at: start, counts: {legs: legs.length, parlays: parlays.tickets.length, book_priced_legs: 0, projections: 40},
  estimated_prices: true, source_by_sport: {NFL: {source: 'ESPN public statistics', projections: 40, errors: []}},
};

const browser = await chromium.launch({headless: true});
try {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({viewport: {width, height: 900}, serviceWorkers: 'block'});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://**/*', route => route.abort());
    await page.route('**/data/legs.json*', route => route.fulfill({contentType: 'application/json', body: JSON.stringify(legs)}));
    await page.route('**/data/parlays.json*', route => route.fulfill({contentType: 'application/json', body: JSON.stringify(parlays)}));
    await page.route('**/data/meta.json*', route => route.fulfill({contentType: 'application/json', body: JSON.stringify(meta)}));
    await page.goto(origin + '/props-edge/');

    await page.locator('.ticket').first().waitFor();
    assert.equal(await page.locator('.ticket').count(), 1, 'the first target shows its tickets');
    assert.match(await page.locator('#price-banner').textContent(), /model estimate/i, 'estimated prices are disclosed');
    assert.equal(await page.locator('.est').first().textContent(), 'EST PRICE');

    await page.locator('.target[data-target="5000"]').click();
    assert.match(await page.locator('.ticket .ticket-top').first().textContent(), /target \+5,000/i);
    await page.locator('.target[data-target="30000"]').click();
    assert.match(await page.locator('#parlays .empty').textContent(), /No parlay reached/i, 'an empty target explains itself');

    await page.locator('[data-scope="game"]').click();
    await page.locator('.target[data-target="1000"]').click();
    assert.equal(await page.locator('.ticket').count(), 1, 'same-game scope has its own tickets');
    assert.match(await page.locator('.corr').first().textContent(), /CORRELATION/);

    // Pasted odds replace the estimates, re-score a different line and re-price the ticket.
    await page.locator('[data-tab="parlays"]').click();
    await page.locator('[data-scope="slate"]').click();
    const beforePrice = await page.locator('.ticket .price').first().textContent();
    await page.locator('#paste-lines').click();
    await page.locator('#paste-box').fill('Alpha Player anytime touchdown +240\nBravo Player over 49.5 receiving yards -105\nnonsense row');
    await page.locator('#paste-apply').click();
    assert.match(await page.locator('#paste-status').textContent(), /Read 2 lines, 1 matched/);
    await page.locator('#paste-close').click();
    assert.notEqual(await page.locator('.ticket .price').first().textContent(), beforePrice, 'a pasted price changes the ticket');
    assert.match(await page.locator('.ticket-top small').first().textContent(), /WITH YOUR LINES/);
    const estTags = await page.locator('.ticket').first().locator('.est').count();
    const legCount = await page.locator('.ticket').first().locator('.legs li').count();
    assert.ok(estTags < legCount, 'the pasted leg drops its estimate tag while the rest keep theirs');
    assert.equal(await page.locator('.ticket').first().locator('.legs li', {hasText: 'Alpha Player'}).locator('.est').count(), 0);
    await page.locator('[data-tab="board"]').click();
    assert.match(await page.locator('.board-row', {hasText: 'Bravo'}).first().textContent(), /49\.5/, 'the board follows the pasted line');
    await page.locator('[data-tab="parlays"]').click();
    await page.locator('#paste-lines').click();
    await page.locator('#paste-clear').click();
    await page.locator('#paste-close').click();

    await page.locator('[data-tab="sheet"]').click();
    await page.locator('.sheet-row').first().waitFor();
    assert.equal(await page.locator('.sheet-row').count(), 2, 'touchdown sheet lists only touchdown legs');
    assert.equal((await page.locator('.sheet-prob').first().textContent()).trim(), '44%');
    await page.locator('#sheet-markets .chip', {hasText: 'Receiving yards'}).click();
    assert.equal(await page.locator('.sheet-row').count(), 1);

    await page.locator('[data-tab="board"]').click();
    assert.equal(await page.locator('.board-row').count(), legs.length);
    await page.locator('#board-search').fill('charlie');
    assert.equal(await page.locator('.board-row').count(), 1, 'search filters the board');
    await page.locator('.board-row button').click();

    await page.locator('[data-tab="ledger"]').click();
    assert.equal(await page.locator('.ledger-row').count(), 1, 'a single lands in the ledger');
    await page.locator('.ledger-row select[data-field="result"]').selectOption('Win');
    await page.locator('.ledger-row input[data-field="stake"]').fill('20');
    await page.locator('.ledger-row input[data-field="stake"]').blur();
    assert.match(await page.locator('#ledger-kpis').textContent(), /\$/, 'the ledger reports profit');

    await page.reload();
    await page.locator('.ledger-row').first().waitFor();
    assert.equal(await page.locator('.ledger-row').count(), 1, 'the ledger survives a reload, on the tab it was left on');
    await page.locator('.ledger-row button[data-field="remove"]').click();

    if (width === 1440) {
      await page.locator('[data-tab="parlays"]').click();
      await page.locator('.ticket [data-action="card"]').first().click();
      await page.locator('#card-canvas').waitFor();
      await page.waitForFunction(() => document.querySelector('#card-status').textContent.includes('leg'));
      const size = await page.evaluate(() => [document.querySelector('#card-canvas').width, document.querySelector('#card-canvas').height]);
      assert.equal(size[0], 1080, 'the parlay card renders at card width');
      assert.ok(size[1] >= 1350, 'the parlay card renders at card height');
      await page.locator('#card-close').click();
    }

    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no sideways scroll at ' + width);
    assert.deepEqual(errors, []);
    await context.close();
  }
  console.log('Props browser: parlay targets, same-game scope, cheat sheet, board, ledger and card studio passed');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
