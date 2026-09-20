/* NFL Props Edge. Parlay lab, cheat sheets, board and a browser-local ledger.
   Every number shown comes from the published model files; nothing is invented here. */
(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const LEDGER_KEY = 'kevbot-props-ledger-v2';
  const BANK_KEY = 'kevbot-props-bank-v2';
  const IMPORT_KEY = 'kevbot-props-imported-lines-v1';
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const odds = (value) => (value == null || !Number.isFinite(Number(value)) ? '—' : (Number(value) > 0 ? '+' : '') + Math.round(Number(value)));
  const pct = (value) => (value == null ? '—' : Math.round(Number(value) * 100) + '%');
  const money = (value) => (value == null || !Number.isFinite(Number(value)) ? '—' : (Number(value) < 0 ? '-$' : '$') + Math.abs(Number(value)).toFixed(2));
  const clock = (value) => {
    const time = Date.parse(value);
    if (!Number.isFinite(time)) return '';
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Toronto', weekday: 'short', hour: 'numeric', minute: '2-digit' }).format(time);
  };
  const dayLabel = (value) => {
    const time = Date.parse(value + 'T12:00:00Z');
    return Number.isFinite(time) ? new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Toronto', weekday: 'long', month: 'short', day: 'numeric' }).format(time) : value;
  };
  const decimalOf = (american) => (american >= 0 ? 1 + american / 100 : 1 + 100 / Math.abs(american));
  const americanOf = (decimal) => (decimal >= 2 ? Math.round((decimal - 1) * 100) : -Math.round(100 / (decimal - 1)));
  const norm = (value) => String(value ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '');

  const state = { meta: null, legs: [], parlays: { tickets: [] }, imported: {}, scope: 'slate', target: null, sheetMarket: 'Anytime touchdown', ledger: [], bank: { bankroll: 500, maxBet: 50 } };

  /* ---------- storage ---------- */
  const readStore = (key, fallback) => { try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch (_) { return fallback; } };
  const writeStore = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { return false; } };

  /* ---------- imported book lines ---------- */
  const importKey = (leg) => `${norm(leg.player)}|${norm(leg.market)}|${leg.side}|${leg.line ?? ''}`;
  function pricedLeg(leg) {
    const found = state.imported[importKey(leg)];
    if (!found) return leg;
    return { ...leg, price_american: found.price, price_decimal: decimalOf(found.price), price_source: 'book', book: found.book || 'Imported line', imported: true };
  }
  function ticketPrice(ticket) {
    const legs = ticket.legs.map(pricedLeg);
    const decimal = legs.reduce((total, leg) => total * Number(leg.price_decimal), 1);
    const changed = legs.some((leg) => leg.imported);
    return { legs, decimal, american: americanOf(decimal), changed };
  }

  /* ---------- loading ---------- */
  async function load() {
    const stamp = Date.now();
    const get = (file) => fetch(`data/${file}?v=${stamp}`, { cache: 'no-store' }).then((response) => {
      if (!response.ok) throw new Error(`${file} unavailable`);
      return response.json();
    });
    const [meta, legs, parlays] = await Promise.all([get('meta.json'), get('legs.json').catch(() => []), get('parlays.json').catch(() => ({ tickets: [] }))]);
    state.meta = meta; state.legs = Array.isArray(legs) ? legs : []; state.parlays = parlays || { tickets: [] };
  }

  function freshness() {
    const meta = state.meta || {};
    const when = meta.generated_at ? new Date(meta.generated_at) : null;
    const age = when ? (Date.now() - when.getTime()) / 3600000 : null;
    const source = (meta.source_by_sport && meta.source_by_sport.NFL && meta.source_by_sport.NFL.source) || 'unknown source';
    $('#freshness').textContent = when
      ? `${state.legs.length} legs · ${(state.parlays.tickets || []).length} parlays · built ${clock(meta.generated_at)} (${age < 1 ? 'under an hour' : Math.round(age) + 'h'} old) · ${source}`
      : 'Model files could not be read.';
    $('#sources').textContent = `Source: ${source}. Prices marked EST are the model's own estimate, not a live sportsbook price.`;
    const banner = $('#price-banner');
    const estimated = meta.estimated_prices !== false && !(meta.counts && meta.counts.book_priced_legs);
    const imported = Object.keys(state.imported).length;
    if (estimated) {
      banner.hidden = false;
      banner.innerHTML = `No sportsbook feed is configured, so every price below is a <b>model estimate</b> with a normal hold applied. ${imported ? `${imported} imported line${imported === 1 ? '' : 's'} are in use.` : 'Use <b>Import book lines</b> to paste today’s real prices, or add an odds-provider key to the repository secrets.'}`;
    } else banner.hidden = true;
  }

  /* ---------- parlay lab ---------- */
  function targets() {
    const list = (state.parlays.targets || [1000, 5000, 10000, 30000, 50000]);
    if (state.target == null) state.target = list[0];
    $('#targets').innerHTML = list.map((target) => {
      const count = (state.parlays.tickets || []).filter((ticket) => ticket.target === target && ticket.scope === state.scope).length;
      return `<button class="target" role="radio" data-target="${target}" aria-checked="${state.target === target}"><b>+${target.toLocaleString('en-CA')}</b><small>${count} TICKET${count === 1 ? '' : 'S'}</small></button>`;
    }).join('');
  }

  function parlayFilters() {
    const tickets = (state.parlays.tickets || []).filter((ticket) => ticket.scope === state.scope);
    const games = [...new Set(tickets.flatMap((ticket) => ticket.games))].sort();
    const days = [...new Set(tickets.map((ticket) => String(ticket.start_time || '').slice(0, 10)).filter(Boolean))].sort();
    const keep = (select, options, all) => {
      const previous = select.value;
      select.innerHTML = `<option value="all">${all}</option>` + options.map(([value, label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join('');
      select.value = options.some(([value]) => value === previous) ? previous : 'all';
    };
    keep($('#parlay-game'), games.map((game) => [game, game]), 'Every game');
    keep($('#parlay-day'), days.map((day) => [day, dayLabel(day)]), 'Every day');
  }

  function legRow(leg) {
    const chance = Number(leg.model_prob);
    const tone = chance >= 0.6 ? '' : chance >= 0.35 ? ' mid' : ' low';
    const market = leg.market === 'Anytime touchdown' ? 'Anytime touchdown scorer' : `${leg.side === 'over' ? 'Over' : leg.side === 'under' ? 'Under' : leg.side} ${leg.line ?? ''} ${leg.market.toLowerCase()}`;
    return `<li><span class="pip"></span><div class="leg-main"><b>${esc(leg.player)}</b><span class="market">${esc(market)}</span>
      <span class="meta">${esc(leg.matchup)} · ${esc(clock(leg.start_time))} · ${esc(leg.book)}${leg.imported ? ' · imported' : ''}</span>
      ${leg.reason ? `<p class="why">${esc(leg.reason)}</p>` : ''}</div>
      <div class="leg-right"><span class="leg-odds">${odds(leg.price_american)}</span><span class="hit${tone}">${pct(leg.model_prob)} model</span>${leg.price_source === 'model' ? '<span class="est">EST PRICE</span>' : ''}</div></li>`;
  }

  function ticketCard(ticket) {
    const { legs, decimal, american, changed } = ticketPrice(ticket);
    const probability = Number(ticket.model_prob);
    const payout = 10 * decimal;
    const ev = probability * payout - 10;
    const correlation = Number(ticket.correlation_applied || 1);
    return `<article class="ticket" data-id="${esc(ticket.id)}">
      <div class="ticket-top">
        <div><h3>${ticket.leg_count} leg parlay</h3><span class="scope">${esc(ticket.scope === 'game' ? ticket.label : ticket.scope === 'day' ? dayLabel(ticket.label) : 'Full slate')} · target +${ticket.target.toLocaleString('en-CA')}</span></div>
        <div><span class="price">${odds(american)}</span><small>${changed ? 'WITH YOUR LINES' : 'MODEL BOARD'}</small></div>
      </div>
      <div class="ticket-stats">
        <div><b>${pct(probability)}</b><span>Model chance</span></div>
        <div><b>1 in ${ticket.one_in ?? '—'}</b><span>Hit rate</span></div>
        <div><b>${money(payout)}</b><span>Pays on $10</span></div>
        <div><b>${money(ev)}</b><span>Model EV</span></div>
      </div>
      <ul class="legs">${legs.map(legRow).join('')}</ul>
      <div class="ticket-actions">
        <button class="primary" data-action="ledger">Add to ledger</button>
        <button data-action="copy">Copy legs</button>
        <button data-action="card">Make card</button>
        ${correlation > 1.02 ? `<span class="corr">SAME-GAME CORRELATION ×${correlation.toFixed(2)}</span>` : ''}
      </div>
    </article>`;
  }

  function renderParlays() {
    targets(); parlayFilters();
    const game = $('#parlay-game').value, day = $('#parlay-day').value;
    const tickets = (state.parlays.tickets || []).filter((ticket) =>
      ticket.scope === state.scope && ticket.target === state.target
      && (game === 'all' || ticket.games.includes(game))
      && (day === 'all' || String(ticket.start_time || '').slice(0, 10) === day));
    $('#parlay-count').textContent = `${tickets.length} ticket${tickets.length === 1 ? '' : 's'} at this target`;
    $('#parlays').innerHTML = tickets.length
      ? tickets.map(ticketCard).join('')
      : `<div class="empty">No parlay reached +${Number(state.target).toLocaleString('en-CA')} for this filter.<br>Try another target or scope. Parlays need enough legs with a recent player sample, so an empty board usually means the slate has not been built yet.</div>`;
  }

  /* ---------- cheat sheets ---------- */
  function sheetMarkets() {
    const counts = state.legs.reduce((map, leg) => { map[leg.market] = (map[leg.market] || 0) + 1; return map; }, {});
    const markets = ['Anytime touchdown', 'Passing yards', 'Pass attempts', 'Pass completions', 'Rushing yards', 'Rush attempts', 'Receiving yards', 'Receptions', 'Targets', 'Kicking points', 'Tackles + assists']
      .filter((market) => counts[market]);
    if (!markets.includes(state.sheetMarket)) state.sheetMarket = markets[0] || 'Anytime touchdown';
    $('#sheet-markets').innerHTML = markets.map((market) => `<button class="chip" role="radio" data-market="${esc(market)}" aria-checked="${market === state.sheetMarket}">${esc(market)}</button>`).join('');
  }

  function sheetRows() {
    return state.legs
      .filter((leg) => leg.market === state.sheetMarket && leg.side !== 'under')
      .map(pricedLeg)
      .sort((a, b) => b.model_prob - a.model_prob)
      .slice(0, 24);
  }

  function renderSheet() {
    sheetMarkets();
    const rows = sheetRows();
    $('#sheet-title').textContent = state.sheetMarket === 'Anytime touchdown' ? 'Anytime touchdown cheat sheet' : `${state.sheetMarket} cheat sheet`;
    $('#sheet-count').textContent = `${rows.length} player${rows.length === 1 ? '' : 's'} · model probability, best first`;
    $('#sheet').innerHTML = rows.length ? rows.map((leg, index) => `<article class="sheet-row">
      <span class="rank">${String(index + 1).padStart(2, '0')}</span>
      <div><h3>${esc(leg.player)}<span>${esc(leg.team)}</span></h3>
        <p class="match">${esc(leg.matchup)} · ${esc(clock(leg.start_time))}</p>
        <p class="why">${esc(leg.reason)}</p></div>
      <div class="sheet-odds"><b>${odds(leg.price_american)}</b><span>${leg.price_source === 'model' ? 'EST ODDS' : 'ODDS'}</span></div>
      <div class="sheet-prob">${pct(leg.model_prob)}</div>
    </article>`).join('') : '<div class="empty">No legs in this market yet.</div>';
  }

  /* ---------- board ---------- */
  function boardFilters() {
    const groups = [...new Set(state.legs.map((leg) => leg.group))].sort();
    const games = [...new Set(state.legs.map((leg) => leg.matchup))].sort();
    const fill = (select, values, all) => {
      const previous = select.value;
      select.innerHTML = `<option value="all">${all}</option>` + values.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join('');
      select.value = values.includes(previous) ? previous : 'all';
    };
    fill($('#board-group'), groups, 'All markets');
    fill($('#board-game'), games, 'Every game');
  }

  function renderBoard() {
    boardFilters();
    const group = $('#board-group').value, game = $('#board-game').value, search = norm($('#board-search').value);
    const rows = state.legs.map(pricedLeg).filter((leg) =>
      (group === 'all' || leg.group === group)
      && (game === 'all' || leg.matchup === game)
      && (!search || norm(leg.player + leg.market).includes(search)))
      .sort((a, b) => b.model_prob - a.model_prob).slice(0, 300);
    $('#board').innerHTML = rows.length ? rows.map((leg) => `<article class="board-row">
      <div><b>${esc(leg.pick)}</b><div class="meta">${esc(leg.matchup)} · ${esc(clock(leg.start_time))} · ${esc(leg.book)} · ${leg.samples || 0} game sample</div><div class="why">${esc(leg.reason)}</div></div>
      <div class="num">${odds(leg.price_american)}<small>${leg.price_source === 'model' ? 'EST' : 'PRICE'}</small></div>
      <div class="num" style="color:var(--teal)">${pct(leg.model_prob)}<small>MODEL</small></div>
      <div><button data-action="single" data-id="${esc(leg.id)}">Add</button></div>
    </article>`).join('') : '<div class="empty">No legs match this filter.</div>';
  }

  /* ---------- ledger ---------- */
  function loadLedger() {
    state.ledger = readStore(LEDGER_KEY, []);
    state.bank = { ...state.bank, ...readStore(BANK_KEY, {}) };
    $('#bankroll').value = state.bank.bankroll;
    $('#max-bet').value = state.bank.maxBet;
  }
  const saveLedger = () => writeStore(LEDGER_KEY, state.ledger);

  function addEntry(entry) {
    state.ledger.unshift({ id: 'bet-' + Math.random().toString(36).slice(2, 10), added_at: new Date().toISOString(), stake: Math.min(Number(state.bank.maxBet) || 10, 10), result: 'Pending', note: '', ...entry });
    saveLedger(); renderLedger();
  }

  function profit(entry) {
    const stake = Number(entry.stake) || 0, price = Number(entry.price_american) || 0;
    if (entry.result === 'Win') return price > 0 ? stake * price / 100 : stake * 100 / Math.abs(price);
    if (entry.result === 'Loss') return -stake;
    return 0;
  }

  function renderLedger() {
    const settled = state.ledger.filter((entry) => ['Win', 'Loss', 'Push', 'Void'].includes(entry.result));
    const pending = state.ledger.filter((entry) => entry.result === 'Pending');
    const pl = settled.reduce((total, entry) => total + profit(entry), 0);
    const staked = settled.reduce((total, entry) => total + (Number(entry.stake) || 0), 0);
    const exposure = pending.reduce((total, entry) => total + (Number(entry.stake) || 0), 0);
    const wins = settled.filter((entry) => entry.result === 'Win').length;
    $('#ledger-kpis').innerHTML = [
      [state.ledger.length, 'Bets'], [pending.length, 'Pending'], [`${wins}-${settled.filter((e) => e.result === 'Loss').length}`, 'Record'],
      [money(exposure), 'Open exposure'], [money(Number(state.bank.bankroll) - exposure + pl), 'Available'], [money(pl), 'Profit / loss'],
      [staked ? Math.round((pl / staked) * 100) + '%' : '—', 'ROI'],
    ].map(([value, label]) => `<div class="kpi"><b class="${label === 'Profit / loss' && pl ? (pl > 0 ? 'won' : 'lost') : ''}">${esc(value)}</b><span>${esc(label)}</span></div>`).join('');
    $('#ledger').innerHTML = state.ledger.length ? state.ledger.map((entry) => `<article class="ledger-row" data-id="${esc(entry.id)}">
      <header><b>${esc(entry.title)}</b><span class="${entry.result === 'Win' ? 'won' : entry.result === 'Loss' ? 'lost' : 'muted'}">${odds(entry.price_american)} · ${esc(entry.result)} · ${money(profit(entry))}</span></header>
      ${entry.legs && entry.legs.length > 1 ? `<ul class="ledger-legs">${entry.legs.map((leg) => `<li>${esc(leg)}</li>`).join('')}</ul>` : ''}
      <div class="ledger-controls">
        <label>Stake <input type="number" min="0" step="1" value="${Number(entry.stake) || 0}" data-field="stake"></label>
        <label>Result <select data-field="result">${['Pending', 'Win', 'Loss', 'Push', 'Void'].map((value) => `<option ${value === entry.result ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
        <label>Note <input type="text" value="${esc(entry.note || '')}" data-field="note" placeholder="injury, line move…"></label>
        <button data-field="remove" class="ghost">Remove</button>
      </div>
    </article>`).join('') : '<div class="empty">No bets saved. Add a parlay from the Parlay lab or a single from the board.</div>';
  }

  function exportLedger() {
    const header = ['added_at', 'title', 'legs', 'price_american', 'stake', 'result', 'profit', 'note'];
    const rows = state.ledger.map((entry) => [entry.added_at, entry.title, (entry.legs || []).join(' | '), entry.price_american, entry.stake, entry.result, profit(entry).toFixed(2), entry.note || '']);
    const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob); link.download = 'kevbot-props-ledger.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 4000);
  }

  /* ---------- CSV import of real book lines ---------- */
  function parseCsv(text) {
    const lines = text.trim().split(/\r?\n/);
    if (!lines.length) return {};
    const header = lines[0].split(',').map((cell) => norm(cell));
    const index = (name) => header.indexOf(norm(name));
    const columns = { player: index('player'), market: index('market'), line: index('line'), over: index('over_odds'), under: index('under_odds'), yes: index('yes_odds'), book: index('book') };
    const found = {};
    for (const row of lines.slice(1)) {
      const cells = row.split(',').map((cell) => cell.trim().replace(/^"|"$/g, ''));
      const player = cells[columns.player], market = cells[columns.market];
      if (!player || !market) continue;
      const line = cells[columns.line] === '' ? null : Number(cells[columns.line]);
      const book = columns.book >= 0 ? cells[columns.book] : 'Imported';
      const add = (side, raw) => {
        const price = Number(raw);
        if (!raw || !Number.isFinite(price) || price === 0) return;
        found[`${norm(player)}|${norm(market)}|${side}|${side === 'yes' ? '' : (line ?? '')}`] = { price: Math.round(price), book };
      };
      add('over', cells[columns.over]); add('under', cells[columns.under]); add('yes', cells[columns.yes]);
    }
    return found;
  }

  function downloadTemplate() {
    const rows = sheetRows().slice(0, 12).map((leg) => [leg.player, leg.market, leg.line ?? '', leg.side === 'yes' ? '' : leg.price_american, '', leg.side === 'yes' ? leg.price_american : '', 'DraftKings', leg.matchup]);
    const csv = [['player', 'market', 'line', 'over_odds', 'under_odds', 'yes_odds', 'book', 'matchup'], ...rows]
      .map((row) => row.join(',')).join('\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    link.download = 'kevbot-props-lines-template.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 4000);
  }

  /* ---------- share card ---------- */
  const SWATCH = { gridiron: 'linear-gradient(135deg,#ffd772,#8a5a12 55%,#111)', ballpark: 'linear-gradient(135deg,#f6ecd6 50%,#0c1a2e 50%)', scoreboard: 'radial-gradient(circle,#ffb000 30%,#050608 32%)', northern: 'linear-gradient(90deg,#c8102e 28%,#fff 28% 72%,#c8102e 72%)', slip: 'repeating-linear-gradient(0deg,#fff 0 4px,#ddd 4px 6px)' };
  let cardStyle = 'gridiron', cardPayload = null, drawing = 0;
  try { const saved = localStorage.getItem('kevbot-props-card-style'); if (saved) cardStyle = saved; } catch (_) {}

  function cardTicket(payload) {
    return {
      day: (payload.day || new Date().toISOString()).slice(0, 10),
      id: payload.id,
      published_at: new Date().toISOString(),
      picks: payload.picks,
    };
  }

  async function drawCard() {
    if (!window.MoneylineCard || !cardPayload) return;
    const token = ++drawing;
    $('#card-status').textContent = 'Drawing…';
    $$('.style-option').forEach((button) => button.setAttribute('aria-checked', String(button.dataset.style === cardStyle)));
    window.MoneylineCard.base = '../bet-ledger-hq/';
    try {
      await window.MoneylineCard.drawTicket($('#card-canvas'), cardTicket(cardPayload), { style: cardStyle, outcomeKey: (row) => row.pick, override: cardPayload.override });
      if (token === drawing) $('#card-status').textContent = `${cardPayload.picks.length} leg${cardPayload.picks.length === 1 ? '' : 's'} · ${cardPayload.override.subtitle}`;
    } catch (_) { if (token === drawing) $('#card-status').textContent = 'Could not draw this card. Try another style.'; }
  }

  function openCard(payload) {
    cardPayload = payload;
    if (!window.MoneylineCard) { alert('The card studio could not load on this page.'); return; }
    $('#card-styles').innerHTML = Object.entries(window.MoneylineCard.styles).map(([key, value]) =>
      `<button type="button" role="radio" class="style-option" data-style="${key}" aria-checked="false"><i style="background:${SWATCH[key]}"></i><span><b>${esc(value.name)}</b><small>${esc(value.note)}</small></span></button>`).join('');
    const dialog = $('#card-dialog');
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
    drawCard();
  }

  function parlayCardPayload(ticket) {
    const { legs, american } = ticketPrice(ticket);
    return {
      id: ticket.id,
      day: String(ticket.start_time || '').slice(0, 10),
      override: {
        title: 'PARLAY', titleCase: 'Parlay', subtitle: `${ticket.leg_count} LEG · ${odds(american)}`,
        stubKicker: `${ticket.leg_count} LEG PARLAY · ${odds(american)}`, ribbon: 'TRUE NORTH PARLAY',
        slipTitle: `${ticket.leg_count} LEG PARLAY ${odds(american)}`, stamp: 'LOCKED IN',
        stats: [['LEGS', String(ticket.leg_count)], ['PRICE', odds(american)], ['MODEL', pct(ticket.model_prob)], ['PAYS $10', money(10 * ticket.price_decimal)]],
        slipLines: [['PARLAY PRICE', odds(american)], ['MODEL CHANCE', pct(ticket.model_prob)], ['PAYS ON $10', money(10 * ticket.price_decimal)]],
      },
      picks: legs.map((leg) => ({
        key: 'props', sport: 'NFL', pick: leg.market === 'Anytime touchdown' ? `${leg.player} anytime TD` : `${leg.player} ${leg.side} ${leg.line ?? ''}`,
        event: leg.matchup, start: leg.start_time, price: leg.price_american, tier: leg.market.toUpperCase(),
        probability: leg.model_prob, book: leg.book, source: 'NFL',
      })),
    };
  }

  function sheetCardPayload() {
    const rows = sheetRows().slice(0, 8);
    return {
      id: 'sheet-' + norm(state.sheetMarket),
      day: new Date().toISOString().slice(0, 10),
      override: {
        title: 'CHEAT SHEET', titleCase: 'Cheat Sheet', subtitle: state.sheetMarket.toUpperCase(),
        stubKicker: `${state.sheetMarket.toUpperCase()} · MODEL BOARD`, ribbon: 'TRUE NORTH CHEAT SHEET',
        slipTitle: `${state.sheetMarket.toUpperCase()} CHEAT SHEET`, stamp: 'MODEL',
        stats: [['PLAYS', String(rows.length)], ['TOP MODEL', pct(rows[0] && rows[0].model_prob)], ['MARKET', state.sheetMarket.split(' ')[0].toUpperCase()], ['SOURCE', rows.some((row) => row.price_source === 'book') ? 'BOOK' : 'EST']],
        slipLines: [['MARKET', state.sheetMarket], ['PLAYS', String(rows.length)], ['TOP MODEL CHANCE', pct(rows[0] && rows[0].model_prob)]],
      },
      picks: rows.map((leg) => ({
        key: 'props', sport: 'NFL', pick: `${leg.player} ${leg.market === 'Anytime touchdown' ? 'anytime TD' : (leg.side + ' ' + (leg.line ?? ''))}`,
        event: leg.matchup, start: leg.start_time, price: leg.price_american, tier: pct(leg.model_prob) + ' MODEL',
        probability: leg.model_prob, book: leg.book, source: 'NFL',
      })),
    };
  }

  /* ---------- events ---------- */
  function showTab(name) {
    $$('.tab').forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.tab === name)));
    $$('.panel').forEach((panel) => { panel.hidden = panel.id !== `tab-${name}`; });
    if (name === 'sheet') renderSheet();
    if (name === 'board') renderBoard();
    if (name === 'ledger') renderLedger();
    if (name === 'parlays') renderParlays();
    try { history.replaceState(null, '', '#' + name); } catch (_) {}
  }

  function wire() {
    $$('.tab').forEach((tab) => tab.addEventListener('click', () => showTab(tab.dataset.tab)));
    $('.scope-picker').addEventListener('click', (event) => {
      const button = event.target.closest('[data-scope]'); if (!button) return;
      state.scope = button.dataset.scope;
      $$('[data-scope]').forEach((chip) => chip.setAttribute('aria-checked', String(chip.dataset.scope === state.scope)));
      renderParlays();
    });
    $('#targets').addEventListener('click', (event) => {
      const button = event.target.closest('[data-target]'); if (!button) return;
      state.target = Number(button.dataset.target); renderParlays();
    });
    $('#parlay-game').addEventListener('change', renderParlays);
    $('#parlay-day').addEventListener('change', renderParlays);
    $('#sheet-markets').addEventListener('click', (event) => {
      const button = event.target.closest('[data-market]'); if (!button) return;
      state.sheetMarket = button.dataset.market; renderSheet();
    });
    $('#sheet-card').addEventListener('click', () => openCard(sheetCardPayload()));
    ['#board-group', '#board-game'].forEach((selector) => $(selector).addEventListener('change', renderBoard));
    $('#board-search').addEventListener('input', renderBoard);
    $('#board').addEventListener('click', (event) => {
      const button = event.target.closest('[data-action=single]'); if (!button) return;
      const leg = pricedLeg(state.legs.find((row) => row.id === button.dataset.id) || {});
      if (!leg.id) return;
      addEntry({ title: leg.pick, price_american: leg.price_american, legs: [leg.pick], model_prob: leg.model_prob, kind: 'single' });
      button.textContent = 'Added ✓'; setTimeout(() => { button.textContent = 'Add'; }, 1500);
    });
    $('#parlays').addEventListener('click', async (event) => {
      const button = event.target.closest('[data-action]'); if (!button) return;
      const id = button.closest('.ticket').dataset.id;
      const ticket = (state.parlays.tickets || []).find((row) => row.id === id); if (!ticket) return;
      const { legs, american } = ticketPrice(ticket);
      const text = legs.map((leg) => `${leg.player} — ${leg.market === 'Anytime touchdown' ? 'anytime TD' : `${leg.side} ${leg.line ?? ''} ${leg.market.toLowerCase()}`} (${odds(leg.price_american)}${leg.price_source === 'model' ? ' est' : ''}) · ${leg.matchup}`);
      if (button.dataset.action === 'copy') {
        const payload = `KEVBOT ${ticket.leg_count}-leg parlay ${odds(american)} · model ${pct(ticket.model_prob)}\n` + text.map((row, index) => `${index + 1}. ${row}`).join('\n');
        try { await navigator.clipboard.writeText(payload); button.textContent = 'Copied ✓'; }
        catch (_) { button.textContent = 'Copy failed'; }
        setTimeout(() => { button.textContent = 'Copy legs'; }, 1600);
      }
      if (button.dataset.action === 'ledger') {
        addEntry({ title: `${ticket.leg_count}-leg parlay · ${ticket.scope === 'game' ? ticket.label : ticket.scope}`, price_american: american, legs: text, model_prob: ticket.model_prob, kind: 'parlay' });
        button.textContent = 'Added ✓'; setTimeout(() => { button.textContent = 'Add to ledger'; }, 1600);
      }
      if (button.dataset.action === 'card') openCard(parlayCardPayload(ticket));
    });
    $('#ledger').addEventListener('change', (event) => {
      const field = event.target.dataset.field; if (!field) return;
      const id = event.target.closest('.ledger-row').dataset.id;
      const entry = state.ledger.find((row) => row.id === id); if (!entry) return;
      entry[field] = field === 'stake' ? Number(event.target.value) : event.target.value;
      saveLedger(); renderLedger();
    });
    $('#ledger').addEventListener('click', (event) => {
      if (event.target.dataset.field !== 'remove') return;
      const id = event.target.closest('.ledger-row').dataset.id;
      state.ledger = state.ledger.filter((row) => row.id !== id); saveLedger(); renderLedger();
    });
    ['#bankroll', '#max-bet'].forEach((selector) => $(selector).addEventListener('change', () => {
      state.bank = { bankroll: Number($('#bankroll').value) || 0, maxBet: Number($('#max-bet').value) || 0 };
      writeStore(BANK_KEY, state.bank); renderLedger();
    }));
    $('#export-ledger').addEventListener('click', exportLedger);
    $('#template').addEventListener('click', downloadTemplate);
    $('#import-lines').addEventListener('click', () => $('#csv-input').click());
    $('#csv-input').addEventListener('change', async (event) => {
      const file = event.target.files && event.target.files[0]; if (!file) return;
      const found = parseCsv(await file.text());
      state.imported = { ...state.imported, ...found };
      writeStore(IMPORT_KEY, state.imported);
      event.target.value = '';
      freshness(); renderParlays(); renderSheet(); renderBoard();
    });
    $('#card-styles').addEventListener('click', (event) => {
      const button = event.target.closest('[data-style]'); if (!button) return;
      cardStyle = button.dataset.style;
      try { localStorage.setItem('kevbot-props-card-style', cardStyle); } catch (_) {}
      drawCard();
    });
    $('#card-close').addEventListener('click', () => $('#card-dialog').close && $('#card-dialog').close());
    $('#card-download').addEventListener('click', () => {
      $('#card-canvas').toBlob((blob) => {
        if (!blob) return;
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob); link.download = `kevbot-props-${cardStyle}.png`; link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 4000);
      }, 'image/png');
    });
    $('#card-share').addEventListener('click', () => {
      $('#card-canvas').toBlob(async (blob) => {
        try { await navigator.share({ files: [new File([blob], 'kevbot-props.png', { type: 'image/png' })], title: 'KEVBOT props' }); } catch (_) {}
      }, 'image/png');
    });
    window.addEventListener('message', (event) => { if (event.origin === location.origin && event.data && event.data.type === 'kevbotbets:activate') refresh(); });
    window.addEventListener('online', refresh);
  }

  async function refresh() {
    try {
      await load();
      freshness();
      const tab = (location.hash || '#parlays').slice(1);
      showTab(['parlays', 'sheet', 'board', 'ledger'].includes(tab) ? tab : 'parlays');
    } catch (error) {
      $('#freshness').textContent = 'The model files could not be loaded. The last build may still be running.';
      $('#parlays').innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    }
  }

  state.imported = readStore(IMPORT_KEY, {});
  loadLedger(); wire(); refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 600000);
})();
