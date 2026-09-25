/* NFL Props Edge. Parlay lab, cheat sheets, board and a browser-local ledger.
   Every number shown comes from the published model files; nothing is invented here. */
(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const LEDGER_KEY = 'kevbot-props-ledger-v2';
  const BANK_KEY = 'kevbot-props-bank-v2';
  const IMPORT_KEY = 'kevbot-props-imported-lines-v2';
  const Q = window.PropsQuotes;
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

  const state = { meta: null, legs: [], parlays: { tickets: [] }, imported: {}, scope: 'slate', target: null, sheetMarket: 'Anytime touchdown', realLinesOnly: true, ledger: [], bank: { bankroll: 0, maxBet: 10 } };

  /* ---------- storage ---------- */
  const readStore = (key, fallback) => { try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch (_) { return fallback; } };
  const writeStore = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { alert('Browser storage is full or unavailable. This change could not be saved; export your ledger before closing.'); throw new Error('Storage unavailable'); } };

  /* ---------- imported book lines ---------- */
  const importKey = Q.key;
  const maxQuoteAge = () => Number(state.meta?.max_odds_age_hours || 12);
  const pricedLeg = leg => Q.apply(leg, state.imported, Date.now(), maxQuoteAge());
  const ticketPrice = ticket => Q.ticket(ticket, state.imported, Date.now(), maxQuoteAge());

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
    const quota = (meta.odds_feed && meta.odds_feed.quota) || {};
    const credits = quota['x-requests-remaining'];
    const window = (meta.odds_feed && meta.odds_feed.window && meta.odds_feed.window.NFL) || {};
    const lineSource = (meta.odds_feed && meta.odds_feed.line_source) || null;
    $('#sources').textContent = `Source: ${source}${lineSource ? ' · lines: ' + lineSource : ''}. Prices marked EST are the model's own estimate, not a live sportsbook price.`
      + (credits ? ` Odds key: ${credits} credits left.` : '')
      + (window.hours_to_kickoff != null ? ` Next kickoff in ${window.hours_to_kickoff}h${window.inside_window === false ? ' — paid odds are only pulled inside ' + window.window_hours + 'h of kickoff.' : '.'}` : '');
    const banner = $('#price-banner');
    const estimated = meta.estimated_prices !== false && !(meta.counts && meta.counts.book_priced_legs);
    const imported = state.legs.filter(leg => pricedLeg(leg).imported).length;
    const onBookLines = (meta.counts && meta.counts.legs_on_book_lines) || 0;
    if (estimated) {
      banner.hidden = false;
      banner.innerHTML = (onBookLines
        ? `<b>${onBookLines.toLocaleString('en-CA')} legs sit on the real DraftKings numbers</b>, pulled keyless from ESPN's public feed — that feed publishes the line but not the price, so each price below is a <b>model estimate</b> with a normal hold applied. `
        : 'No verified book prices are available in this build. Prices below are a <b>model estimate</b> with a normal hold applied. ')
        + (imported ? `${imported} of your own price${imported === 1 ? '' : 's'} are in use.` : 'Use <b>Paste odds</b> to drop your book\u2019s real prices on top.');
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
    const days = [...new Set(tickets.map((ticket) => Q.day(ticket.start_time)).filter(Boolean))].sort();
    const keep = (select, options, all) => {
      const previous = select.value;
      select.innerHTML = `<option value="all">${all}</option>` + options.map(([value, label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join('');
      select.value = options.some(([value]) => value === previous) ? previous : 'all';
    };
    keep($('#parlay-game'), games.map((game) => [game, game]), 'Every game');
    keep($('#parlay-day'), days.map((day) => [day, dayLabel(day)]), 'Every day');
  }

  /* Injury status and line movement, shown wherever a leg is. */
  function legTags(leg) {
    const tags = [];
    if (leg.status) tags.push(`<span class="tag">${esc(String(leg.status).toUpperCase())}</span>`);
    if (leg.open_line != null && leg.line != null && Math.abs(Number(leg.open_line) - Number(leg.line)) >= 0.05) {
      const up = Number(leg.line) > Number(leg.open_line);
      tags.push(`<span class="tag move">${up ? '↑' : '↓'} FROM ${Number(leg.open_line)}</span>`);
    }
    return tags.length ? ' ' + tags.join(' ') : '';
  }

  function legRow(leg) {
    const chance = Number(leg.model_prob);
    const tone = chance >= 0.6 ? '' : chance >= 0.35 ? ' mid' : ' low';
    const market = leg.market === 'Anytime touchdown' ? 'Anytime touchdown scorer' : `${leg.side === 'over' ? 'Over' : leg.side === 'under' ? 'Under' : leg.side} ${leg.line ?? ''} ${leg.market.toLowerCase()}`;
    return `<li><span class="pip"></span><div class="leg-main"><b>${esc(leg.player)}</b>${legTags(leg)}<span class="market">${esc(market)}</span>
      <span class="meta">${esc(leg.matchup)} · ${esc(clock(leg.start_time))} · ${esc(leg.book)}${leg.imported ? ' · your price' : ''}</span>
      ${leg.reason ? `<p class="why">${esc(leg.reason)}</p>` : ''}</div>
      <div class="leg-right"><span class="leg-odds">${odds(leg.price_american)}</span><span class="hit${tone}">${pct(leg.model_prob)} model</span>${leg.price_source === 'model' ? `<span class="est">EST PRICE${leg.line_source ? ' · REAL LINE' : ''}</span>` : ''}</div></li>`;
  }

  function ticketCard(ticket) {
    const { legs, decimal, american, changed, probability } = ticketPrice(ticket);
    const payout = 10 * decimal;
    const ev = null;
    const correlation = 1;
    const offBoard = legs.filter((leg) => !isReal(leg)).length;
    const placeable = `<p class="placeable warn">RESEARCH · ${legs.some(l=>l.price_source!=='book')?'ESTIMATED PRICES':'INDIVIDUAL LEG PRICES'} · Combined price needs confirmation.${ticketPrice(ticket).sameGame?' Same-game probability is unavailable.':''}${offBoard?' Some lines may not be offered.':''}</p>`;
    return `<article class="ticket" data-id="${esc(ticket.id)}">
      <div class="ticket-top">
        <div><h3>${ticket.leg_count} leg parlay</h3><span class="scope">${esc(ticket.scope === 'game' ? ticket.label : ticket.scope === 'day' ? dayLabel(ticket.label) : 'Full slate')} · target +${ticket.target.toLocaleString('en-CA')}</span></div>
        <div><span class="price">${odds(american)}</span><small>${changed ? 'WITH YOUR LINES' : 'MODEL BOARD'}</small></div>
      </div>
      ${placeable}
      <div class="ticket-stats">
        <div><b>${pct(probability)}</b><span>Model chance</span></div>
        <div><b>1 in ${probability > 0 ? Math.round(1 / probability) : '—'}</b><span>Estimated frequency</span></div>
        <div><b>${money(payout)}</b><span>Illustrative $10 return</span></div>
        <div><b>${money(ev)}</b><span>Model EV</span></div>
      </div>
      <ul class="legs">${legs.map(legRow).join('')}</ul>
      <div class="ticket-actions">
        <button class="primary" data-action="ledger">Log actual bet</button>
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
      && (day === 'all' || Q.day(ticket.start_time) === day));
    $('#parlay-count').textContent = `${tickets.length} ticket${tickets.length === 1 ? '' : 's'} at this target`
      + (state.parlays.book_lines_only ? ' · every leg is a line the book posts' : '');
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

  const realOnly = () => state.realLinesOnly;
  const isReal = (leg) => Boolean(leg.line_source) || leg.price_source === 'book' || leg.imported;

  function sheetRows() {
    return state.legs
      .filter((leg) => leg.market === state.sheetMarket && leg.side !== 'under')
      .filter((leg) => !realOnly() || isReal(leg))
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
        <p class="match">${esc(leg.matchup)} · ${esc(clock(leg.start_time))}${legTags(leg)}</p>
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
      (!realOnly() || isReal(leg))
      && (group === 'all' || leg.group === group)
      && (game === 'all' || leg.matchup === game)
      && (!search || norm(leg.player + leg.market).includes(search)))
      .sort((a, b) => b.model_prob - a.model_prob).slice(0, 300);
    $('#board').innerHTML = rows.length ? rows.map((leg) => `<article class="board-row">
      <div><b>${esc(leg.pick)}</b>${legTags(leg)}<div class="meta">${esc(leg.matchup)} · ${esc(clock(leg.start_time))} · ${esc(leg.line_source || leg.book)} · ${leg.samples || 0} game sample</div><div class="why">${esc(leg.reason)}</div></div>
      <div class="num">${odds(leg.price_american)}<small>${leg.price_source === 'model' ? 'EST' : 'PRICE'}</small></div>
      <div class="num" style="color:var(--teal)">${pct(leg.model_prob)}<small>MODEL</small></div>
      <div><button data-action="single" data-id="${esc(leg.id)}">Add</button></div>
    </article>`).join('') : '<div class="empty">No legs match this filter.</div>';
  }

  /* ---------- model record ---------- */
  function renderRecord() {
    const accuracy = (state.meta && state.meta.accuracy) || {};
    const settled = Number(accuracy.settled || 0);
    $('#record-kpis').innerHTML = [
      [accuracy.record || '—', 'Record'],
      [accuracy.hit_rate == null ? '—' : pct(accuracy.hit_rate), 'Hit rate'],
      [accuracy.average_predicted == null ? '—' : pct(accuracy.average_predicted), 'Model said'],
      [accuracy.brier == null ? '—' : Number(accuracy.brier).toFixed(3), 'Brier score'],
      [String(accuracy.legs || 0), 'Legs graded'],
    ].map(([value, label]) => `<div class="kpi"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join('');
    $('#record-cal').textContent = `${accuracy.total_logged || 0} exact-line observations frozen before kickoff; one preferred side per player/market in the headline record. ${accuracy.legacy_excluded || 0} old results without verified capture times are preserved separately and excluded. Calibration is diagnostic; no automatic fit is applied to these same results.`;
    const bucketRow = (bucket) => {
      const gap = Number(bucket.actual) - Number(bucket.predicted);
      return `<article class="board-row">
        <div><b>${Math.round(bucket.from * 100)}–${Math.round(Math.min(bucket.to, 1) * 100)}% legs</b>
          <div class="meta">${bucket.legs} graded · model said ${pct(bucket.predicted)}, they landed ${pct(bucket.actual)}</div>
          <div class="bar"><i style="width:${Math.max(2, Math.min(100, Number(bucket.actual) * 100))}%"></i></div></div>
        <div class="num">${pct(bucket.predicted)}<small>SAID</small></div>
        <div class="num" style="color:${Math.abs(gap) <= 0.05 ? 'var(--teal)' : gap > 0 ? 'var(--blue)' : '#ff8e8e'}">${pct(bucket.actual)}<small>ACTUAL</small></div>
      </article>`;
    };
    const buckets = accuracy.buckets || [];
    $('#record-buckets').innerHTML = buckets.length
      ? buckets.map(bucketRow).join('')
      : '<div class="empty">Nothing graded yet. Legs are graded from the box score after their game goes final, so the first numbers land the day after a slate.</div>';
    const markets = Object.entries(accuracy.by_market || {}).sort((a, b) => b[1].legs - a[1].legs);
    $('#record-markets').innerHTML = markets.length
      ? markets.map(([market, entry]) => `<article class="board-row">
          <div><b>${esc(market)}</b><div class="meta">${entry.legs} graded · model said ${pct(entry.predicted)}</div></div>
          <div class="num">${entry.wins}-${entry.legs - entry.wins}<small>RECORD</small></div>
          <div class="num" style="color:var(--teal)">${pct(entry.hit_rate)}<small>HIT RATE</small></div>
        </article>`).join('')
      : '<div class="empty">No market has a graded leg yet.</div>';
  }

  /* ---------- ledger ---------- */
  function loadLedger() {
    state.ledger = readStore(LEDGER_KEY, []);
    state.bank = { ...state.bank, ...readStore(BANK_KEY, {}) };
    $('#bankroll').value = state.bank.bankroll;
    $('#max-bet').value = state.bank.maxBet;
  }
  const saveLedger = () => { writeStore(LEDGER_KEY, state.ledger); window.BetSync?.touch(); };

  function addEntry(entry) {
    const dialog=$('#wager-dialog');
    $('#wager-title').textContent=entry.title;
    $('#wager-price').value=''; $('#wager-book').value='';
    $('#wager-stake').value=Math.min(Number(state.bank.maxBet)||10,10);
    $('#wager-error').textContent='';
    $('#wager-form').onsubmit=event=>{
      event.preventDefault();
      const price=Number($('#wager-price').value),stake=Number($('#wager-stake').value),book=$('#wager-book').value.trim();
      if(!Q.validPrice(price)||!Number.isFinite(stake)||stake<=0||!book){$('#wager-error').textContent='Enter the actual American price (±100 or greater), positive stake and sportsbook.';return;}
      const next={...entry,id:'bet-'+crypto.randomUUID(),added_at:new Date().toISOString(),stake,price_american:price,book,result:'Pending',note:'',confirmed_actual:true,ledger_schema:'props-v3'};
      writeStore(LEDGER_KEY,[next,...state.ledger]); state.ledger.unshift(next);
      window.BetSync?.touch(); renderLedger(); dialog.close();
    };
    dialog.showModal();
  }

  function profit(entry) {
    const stake = Number(entry.stake) || 0, price = Number(entry.price_american) || 0;
    if (entry.result === 'Win') return price > 0 ? stake * price / 100 : stake * 100 / Math.abs(price);
    if (entry.result === 'Loss') return -stake;
    return 0;
  }

  function renderLedger() {
    const unverified=state.ledger.filter(e=>!e.confirmed_actual);
    $('#legacy-ledger-note').hidden=!unverified.length;
    $('#legacy-ledger-count').textContent=unverified.length;
    const settled = state.ledger.filter((entry) => ['Win', 'Loss', 'Push', 'Void'].includes(entry.result));
    const pending = state.ledger.filter((entry) => entry.result === 'Pending');
    const pl = settled.reduce((total, entry) => total + profit(entry), 0);
    const staked = settled.reduce((total, entry) => total + (Number(entry.stake) || 0), 0);
    const exposure = pending.reduce((total, entry) => total + (Number(entry.stake) || 0), 0);
    const wins = settled.filter((entry) => entry.result === 'Win').length;
    $('#ledger-kpis').innerHTML = [
      [state.ledger.length, 'Bets'], [pending.length, 'Pending'], [`${wins}-${settled.filter((e) => e.result === 'Loss').length}`, 'Record'],
      [money(exposure), 'Open exposure'], [money(state.sharedBank ? state.sharedBank.available : Number(state.bank.bankroll) - exposure + pl), 'Available'], [money(pl), 'Profit / loss'],
      [staked ? Math.round((pl / staked) * 100) + '%' : '—', 'ROI'],
    ].map(([value, label]) => `<div class="kpi"><b class="${label === 'Profit / loss' && pl ? (pl > 0 ? 'won' : 'lost') : ''}">${esc(value)}</b><span>${esc(label)}</span></div>`).join('');
    $('#ledger').innerHTML = state.ledger.length ? state.ledger.map((entry) => `<article class="ledger-row" data-id="${esc(entry.id)}">
      <header><b>${esc(entry.title)}</b><span class="${entry.result === 'Win' ? 'won' : entry.result === 'Loss' ? 'lost' : 'muted'}">${odds(entry.price_american)} · ${esc(entry.result)} · ${money(profit(entry))}</span></header>
      ${entry.legs && entry.legs.length > 1 ? `<ul class="ledger-legs">${entry.legs.map((leg) => `<li>${esc(leg)}</li>`).join('')}</ul>` : ''}
      <div class="ledger-controls">
        <label>Actual odds <input type="number" value="${Number(entry.price_american) || 0}" data-field="price_american"></label>
        <label>Book <input type="text" value="${esc(entry.book || '')}" data-field="book"></label>
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
  const parseCsv = text => Q.parseCsv(text,state.legs,Date.now(),maxQuoteAge());
  function downloadTemplate() {
    const rows=state.legs.slice(0,12).map(leg=>[leg.event_id,leg.player,leg.market,leg.line??'','','','','','','',leg.matchup]);
    const csv=[['event_id','player','market','line','over_odds','under_odds','yes_odds','no_odds','book','observed_at','matchup'],...rows]
      .map(row=>row.map(cell=>'"'+String(cell??'').replace(/"/g,'""')+'"').join(',')).join('\n');
    const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
    link.download='kevbot-props-lines-template.csv';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),4000);
  }


  /* ---------- pasted odds (any sportsbook or odds screen) ---------- */
  const MARKET_WORDS = [
    [/anytime|any time|\batd\b|touchdown scorer|to score/i, 'Anytime touchdown'],
    [/pass(ing)?\s*(yards|yds)/i, 'Passing yards'],
    [/pass(ing)?\s*(tds?|touchdowns?)/i, 'Passing touchdowns'],
    [/pass(ing)?\s*attempts/i, 'Pass attempts'],
    [/completions/i, 'Pass completions'],
    [/interceptions/i, 'Pass interceptions'],
    [/rush(ing)?\s*(yards|yds)/i, 'Rushing yards'],
    [/rush(ing)?\s*(attempts|carries)/i, 'Rush attempts'],
    [/rush(ing)?\s*(tds?|touchdowns?)/i, 'Rushing touchdowns'],
    [/receiv(ing)?\s*(yards|yds)/i, 'Receiving yards'],
    [/receptions|catches/i, 'Receptions'],
    [/targets/i, 'Targets'],
    [/longest\s*(pass|completion)/i, 'Longest pass'],
    [/longest\s*rush/i, 'Longest rush'],
    [/longest\s*reception/i, 'Longest reception'],
    [/kicking\s*points/i, 'Kicking points'],
    [/field\s*goals?/i, 'Field goals made'],
    [/extra\s*points?/i, 'Extra points made'],
    [/tackles/i, 'Tackles + assists'],
    [/sacks/i, 'Sacks'],
  ];

  function parsePastedLine(raw) {
    const text = String(raw).replace(/\s+/g, ' ').trim();
    if (!text || text.length < 6) return null;
    const price = text.match(/(?:^|[\s(,:])([+-]\d{2,5})(?!\.?\d*\s*(?:yards|yds|receptions|targets))/);
    if (!price) return null;
    const market = (MARKET_WORDS.find(([pattern]) => pattern.test(text)) || [])[1];
    if (!market) return null;
    const anytime = market === 'Anytime touchdown';
    const side = anytime ? 'yes' : /\bunder\b|\bu\s?\d/i.test(text) ? 'under' : 'over';
    const lineMatch = anytime ? null : text.match(/(?:over|under|o|u)\s*([0-9]+(?:\.[05])?)|\b([0-9]+\.5)\b/i);
    const line = anytime ? null : Number((lineMatch && (lineMatch[1] || lineMatch[2])) ?? NaN);
    if (!anytime && !Number.isFinite(line)) return null;
    // The player is what is left once the market words, the line and the price are removed.
    const NOISE = /\b(anytime|any ?time|touchdowns?|tds?|scorer|to score|passing|pass|rushing|rush|receiving|reception|receptions|catches|targets|attempts|carries|completions|interceptions|longest|field|goals?|extra|points|kicking|tackles|assists|sacks|yards|yds|over|under|o|u|yes|no|alt|line|odds|prop|a|an|the|to)\b/ig;
    const player = text
      .slice(0, price.index === undefined ? text.length : price.index)
      .replace(NOISE, ' ')
      .replace(/[0-9]+(?:\.[05])?/g, ' ')
      .replace(/[|,:;()\-–—+]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    if (player.split(' ').length < 2) return null;
    return { key: `${norm(player)}|${norm(market)}|${side}|${anytime ? '' : line}`, price: Number(price[1]), player, market, side, line };
  }

  function applyPasted(text) {
    const rows=String(text).split(/\r?\n/),found={},missed=[];let parsed=0;
    const event_id=$('#paste-game').value,book=$('#paste-book').value.trim(),observed_at=new Date().toISOString();
    for(const raw of rows){
      if(!raw.trim())continue;
      const row=parsePastedLine(raw);if(!row){missed.push(raw);continue;} parsed++;
      const q={...row,event_id,book,observed_at};
      const leg=state.legs.find(l=>importKey(l)===importKey(q));
      if(Q.valid(q,leg,Date.now(),maxQuoteAge()))found[importKey(q)]=q;else missed.push(raw);
    }
    state.imported={...state.imported,...found};writeStore(IMPORT_KEY,state.imported);
    return {parsed,matched:Object.keys(found).length,missed};
  }

  /* ---------- share card ---------- */
  const SWATCH = { gridiron: 'linear-gradient(135deg,#ffd772,#8a5a12 55%,#111)', ballpark: 'linear-gradient(135deg,#f6ecd6 50%,#0c1a2e 50%)', scoreboard: 'radial-gradient(circle,#ffb000 30%,#050608 32%)', northern: 'linear-gradient(90deg,#c8102e 28%,#fff 28% 72%,#c8102e 72%)', slip: 'repeating-linear-gradient(0deg,#fff 0 4px,#ddd 4px 6px)' };
  let cardStyle = 'gridiron', cardPayload = null, drawing = 0;
  try { const saved = localStorage.getItem('kevbot-props-card-style'); if (saved) cardStyle = saved; } catch (_) {}

  function cardTicket(payload) {
    return {
      day: payload.day || Q.day(new Date().toISOString()),
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
    const { legs, american, decimal, probability, estimated } = ticketPrice(ticket);
    return {
      id: ticket.id,
      day: Q.day(ticket.start_time),
      override: {
        title: 'PARLAY', titleCase: 'Parlay', subtitle: `${ticket.leg_count} LEG · ${odds(american)}`,
        stubKicker: `${ticket.leg_count} LEG PARLAY · ${odds(american)}`, ribbon: 'TRUE NORTH PARLAY',
        slipTitle: `${ticket.leg_count} LEG SCENARIO ${odds(american)}`, stamp: 'RESEARCH',
        kicker: estimated ? 'MODEL SCENARIO · ESTIMATED PRICES' : 'RESEARCH · CONFIRM COMBINED PRICE',
        legal: 'Research scenario · Estimated or individual-leg prices · Combined price and same-game probability unverified',
        stats: [['LEGS', String(ticket.leg_count)], ['PRICE', odds(american)], ['MODEL', pct(probability)], ['PAYS $10', money(10 * decimal)]],
        slipLines: [['PARLAY PRICE', odds(american)], ['MODEL CHANCE', pct(probability)], ['PAYS ON $10', money(10 * decimal)]],
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
      day: Q.day(new Date().toISOString()),
      override: {
        title: 'CHEAT SHEET', titleCase: 'Cheat Sheet', subtitle: state.sheetMarket.toUpperCase(),
        stubKicker: `${state.sheetMarket.toUpperCase()} · MODEL BOARD`, ribbon: 'TRUE NORTH CHEAT SHEET',
        slipTitle: `${state.sheetMarket.toUpperCase()} CHEAT SHEET`, stamp: 'MODEL',
        kicker: 'MODEL RESEARCH · CHECK PRICE AND TIME',
        legal: 'Model projections · Prices may be estimates · Confirm current line, price and availability',
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
    if (name === 'record') renderRecord();
    if (name === 'ledger') renderLedger();
    if (name === 'parlays') renderParlays();
    window.dispatchEvent(new CustomEvent('props:tab',{detail:name}));
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
    $('#real-only').addEventListener('change', (event) => {
      state.realLinesOnly = event.target.checked;
      renderBoard(); renderSheet();
    });
    $('#board-search').addEventListener('input', renderBoard);
    $('#board').addEventListener('click', (event) => {
      const button = event.target.closest('[data-action=single]'); if (!button) return;
      const leg = pricedLeg(state.legs.find((row) => row.id === button.dataset.id) || {});
      if (!leg.id) return;
      addEntry({ title: leg.pick, price_american: leg.price_american, legs: [leg.pick], model_prob: leg.model_prob, kind: 'single' });

    });
    $('#parlays').addEventListener('click', async (event) => {
      const button = event.target.closest('[data-action]'); if (!button) return;
      const id = button.closest('.ticket').dataset.id;
      const ticket = (state.parlays.tickets || []).find((row) => row.id === id); if (!ticket) return;
      const { legs, american, probability } = ticketPrice(ticket);
      const text = legs.map((leg) => `${leg.player} — ${leg.market === 'Anytime touchdown' ? 'anytime TD' : `${leg.side} ${leg.line ?? ''} ${leg.market.toLowerCase()}`} (${odds(leg.price_american)}${leg.price_source === 'model' ? ' est' : ''}) · ${leg.matchup}`);
      if (button.dataset.action === 'copy') {
        const payload = `KEVBOT ${ticket.leg_count}-leg parlay ${odds(american)} · model ${pct(probability)}\n` + text.map((row, index) => `${index + 1}. ${row}`).join('\n');
        try { await navigator.clipboard.writeText(payload); button.textContent = 'Copied ✓'; }
        catch (_) { button.textContent = 'Copy failed'; }
        setTimeout(() => { button.textContent = 'Copy legs'; }, 1600);
      }
      if (button.dataset.action === 'ledger') {
        addEntry({ title: `${ticket.leg_count}-leg parlay · ${ticket.scope === 'game' ? ticket.label : ticket.scope}`, price_american: american, legs: text, model_prob: probability, kind: 'parlay' });

      }
      if (button.dataset.action === 'card') openCard(parlayCardPayload(ticket));
    });
    $('#ledger').addEventListener('change', (event) => {
      const field = event.target.dataset.field; if (!field) return;
      const id = event.target.closest('.ledger-row').dataset.id;
      const entry = state.ledger.find((row) => row.id === id); if (!entry) return;
      if(field==='stake'&&(!Number.isFinite(Number(event.target.value))||Number(event.target.value)<=0)){renderLedger();return;}
      if(field==='price_american'&&!Q.validPrice(event.target.value)){renderLedger();return;}
      entry[field] = ['stake','price_american'].includes(field) ? Number(event.target.value) : event.target.value;
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
    $('#paste-lines').addEventListener('click', () => {
      const dialog = $('#paste-dialog');
      const games=[...new Map(state.legs.filter(l=>Date.parse(l.start_time)>Date.now()).map(l=>[l.event_id,l])).values()];
      $('#paste-game').innerHTML=games.map(l=>`<option value="${esc(l.event_id)}">${esc(l.matchup+' · '+clock(l.start_time))}</option>`).join('');
      $('#paste-status').textContent = Object.keys(state.imported).length ? `${Object.keys(state.imported).length} price${Object.keys(state.imported).length === 1 ? '' : 's'} saved in this browser.` : '';
      if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
      $('#paste-box').focus();
    });
    $('#paste-close').addEventListener('click', () => $('#paste-dialog').close && $('#paste-dialog').close());
    $('#paste-apply').addEventListener('click', () => {
      const { parsed, matched, missed } = applyPasted($('#paste-box').value);
      $('#paste-status').textContent = parsed
        ? `Read ${parsed} line${parsed === 1 ? '' : 's'}, ${matched} matched a leg on the board.${missed.length ? ` Skipped ${missed.length}: ${missed.slice(0, 2).join(' / ')}` : ''}`
        : 'Nothing read. Select the game and enter your sportsbook. Each line must match the exact published player, market and line, with a real price — "Tee Higgins over 58.5 receiving yards -115".';
      freshness(); renderParlays(); renderSheet(); renderBoard();
    });
    $('#paste-clear').addEventListener('click', () => {
      state.imported = {}; writeStore(IMPORT_KEY, {});
      $('#paste-status').textContent = 'Imported prices cleared. Published prices and estimates are shown.';
      freshness(); renderParlays(); renderSheet(); renderBoard();
    });
    $('#export-ledger').addEventListener('click', exportLedger);
    $('#template').addEventListener('click', downloadTemplate);
    $('#import-lines').addEventListener('click', () => $('#csv-input').click());
    $('#csv-input').addEventListener('change', async (event) => {
      const file = event.target.files && event.target.files[0]; if (!file) return;
      const found = parseCsv(await file.text());
      state.imported = { ...state.imported, ...found };
      writeStore(IMPORT_KEY, state.imported);
      alert(`${Object.keys(found).length} valid event-scoped prices imported. CSV rows need event_id, book and observed_at with timezone; blank or expired prices are skipped.`);
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
      const tab = new URLSearchParams(location.search).get('tab')==='accuracy'?'accuracy':(location.hash || '#parlays').slice(1);
      showTab(['parlays','sheet','board','record','ledger','best','projections','simulator','accuracy','sources'].includes(tab)?tab:'parlays');
    } catch (error) {
      $('#freshness').textContent = 'The model files could not be loaded. The last build may still be running.';
      $('#parlays').innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    }
  }

  window.PropsApp={state,showTab,esc,odds,pct,money,clock,addEntry,saveLedger,renderLedger,readStore,writeStore,LEDGER_KEY,ticketPrice,parlayCardPayload,
    applySharedBank:bank=>{state.sharedBank=bank;state.bank.bankroll=bank.current;$('#bankroll').value=bank.current;$('#bankroll').readOnly=true;renderLedger();},
    replaceLedger:rows=>{const unverified=state.ledger.filter(e=>!e.confirmed_actual);const ids=new Set(rows.map(e=>e.id));const next=[...rows,...unverified.filter(e=>!ids.has(e.id))];writeStore(LEDGER_KEY,next);state.ledger=next;renderLedger();}};
  state.imported = readStore(IMPORT_KEY, {});
  loadLedger(); wire(); refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 600000);
})();
