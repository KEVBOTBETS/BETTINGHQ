/* Edge visuals — shared by the NFL and NCAAF boards (byte-identical copies).
 *
 *  - Team logos with a colour monogram fallback, matchup headers, win-probability
 *    bars and a model-vs-market line gauge.
 *  - "Your price" bet dialog: re-prices a play at the odds and line you can actually
 *    get, with the board's own maths, before it goes into My Ledger.
 *  - Closing-line value for My Ledger bets, and the CLV / historical-backtest
 *    panels on the Accuracy tab.
 *
 * Reads only published data. Never writes a wager on its own.
 */
(function (root) {
  "use strict";
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fin = v => v !== null && v !== undefined && v !== "" && isFinite(Number(v));
  const pct = (v, d = 1) => fin(v) ? (Number(v) * 100).toFixed(d) + "%" : "—";
  const spct = (v, d = 1) => fin(v) ? (v > 0 ? "+" : "") + (Number(v) * 100).toFixed(d) + "%" : "—";
  const sgn = (v, d = 1) => fin(v) ? (v > 0 ? "+" : "") + Number(v).toFixed(d) : "—";
  const am = v => fin(v) ? (v > 0 ? "+" : "") + Math.round(v) : "—";
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

  /* ------------------------------------------------------------------ styles */
  const CSS = `
.ev-logo{--tc:#5b6472;position:relative;display:inline-grid;place-items:center;flex:none;width:28px;height:28px;border-radius:50%;
  background:var(--tc);color:#fff;font:700 9.5px/1 var(--sans,system-ui);letter-spacing:-.02em;overflow:hidden;vertical-align:middle}
.ev-logo.lt{color:#111}
.ev-logo img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#f4f6f8;padding:2px;opacity:0;transition:opacity .2s}.ev-logo img.ok{opacity:1}
.ev-logo.sm{width:20px;height:20px;font-size:7.5px}.ev-logo.lg{width:44px;height:44px;font-size:13px}
.ev-pair{display:inline-flex;align-items:center;margin-right:7px;vertical-align:middle}.ev-pair .ev-logo+.ev-logo{margin-left:-6px;box-shadow:0 0 0 2px var(--surface,#fff)}
.ev-match{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:10px;padding:13px 13px 12px;
  background:linear-gradient(90deg,color-mix(in srgb,var(--ta) 22%,transparent),transparent 42%,transparent 58%,color-mix(in srgb,var(--th) 22%,transparent));
  border-bottom:1px solid var(--line)}
.ev-side{display:flex;align-items:center;gap:9px;min-width:0}.ev-side>div{min-width:0}.ev-side.home{flex-direction:row-reverse;text-align:right}
.ev-side b{display:block;font:700 15px/1.1 var(--mono,monospace)}.ev-side small{display:block;color:var(--ink-3);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ev-at{color:var(--ink-3);font:600 11px/1 var(--mono,monospace);text-align:center}.ev-at small{display:block;margin-top:4px;font-weight:500;font-size:10.5px;white-space:nowrap}
.card .ev-vis{display:grid;gap:12px;margin:0 13px;padding:11px 0 12px;border-top:1px solid var(--line)}
.card .grid5{margin:0 13px;padding:10px 0}.card .addbox{margin:0 13px 12px}
.ev-win{margin:2px 0 0}.ev-win .lab{display:flex;justify-content:space-between;font:600 11.5px/1.2 var(--mono,monospace);color:var(--ink-2);margin-bottom:5px}
.ev-win .lab span.pick{color:var(--ink)}.ev-win .lab span.pick::after{content:" ✓";color:var(--good)}
.ev-win .track{display:flex;gap:2px;height:10px;border-radius:99px;overflow:hidden;background:var(--surface-2)}
.ev-win .track i{display:block;height:100%;background:color-mix(in srgb,var(--c) 72%,#fff 28%);min-width:4px}
.ev-win .track i:first-child{border-radius:99px 0 0 99px}.ev-win .track i:last-child{border-radius:0 99px 99px 0}
.ev-win .cap{font-size:10.5px;color:var(--ink-3);margin-top:4px}
.ev-gauge{margin-top:2px}.ev-gauge .gt{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);margin-bottom:2px;display:flex;justify-content:space-between;gap:8px}
.ev-gauge svg{display:block;width:100%;height:34px;overflow:visible}.ev-gauge text{font:600 10px var(--mono,monospace);fill:var(--ink-2)}
.ev-dialog{width:min(430px,calc(100% - 24px));border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--ink);padding:0;box-shadow:0 30px 90px #0009}
.ev-dialog::backdrop{background:#05080dcc}.ev-dialog form{padding:18px 18px 16px;display:grid;gap:12px}
.ev-dialog h3{margin:0;font:700 16px/1.25 var(--sans,system-ui)}.ev-dialog h3 small{display:block;color:var(--ink-3);font-weight:500;font-size:12px;margin-top:3px}
.ev-dialog .row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.ev-dialog label{display:grid;gap:4px;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
.ev-dialog input{width:100%;border:1px solid var(--line);background:var(--surface-2);color:var(--ink);padding:9px;border-radius:8px;font:600 14px/1 var(--mono,monospace)}
.ev-dialog input:disabled{opacity:.45}.ev-verdict{border:1px solid var(--line);border-left:4px solid var(--ink-3);border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.5;color:var(--ink-2)}
.ev-verdict.up{border-left-color:var(--good)}.ev-verdict.down{border-left-color:var(--bad)}.ev-verdict b{color:var(--ink)}
.ev-verdict .big{display:flex;align-items:baseline;gap:10px;margin-bottom:4px}.ev-verdict .big strong{font:700 20px/1 var(--mono,monospace)}
.ev-dialog .acts{display:flex;gap:8px;justify-content:flex-end}.ev-dialog .acts button{border:1px solid var(--line);background:var(--surface-2);color:var(--ink);border-radius:8px;padding:10px 14px;font:600 13px/1 var(--sans,system-ui);cursor:pointer}
.ev-dialog .acts button.primary{background:var(--accent,var(--cool));border-color:var(--accent,var(--cool));color:var(--on-flag,#fff)}
.ev-dialog .fine{font-size:11px;color:var(--ink-3);line-height:1.5;margin:0}
.ev-panel{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:16px 18px;margin:0 0 18px}
.ev-panel h3{margin:0 0 6px!important;font-size:16px}.ev-panel>p{margin:0 0 12px;color:var(--ink-3);font-size:12.5px;line-height:1.55;max-width:80ch}
.ev-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.ev-tile{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--surface-2)}.ev-tile .k{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3)}
.ev-tile .v{font:700 22px/1.15 var(--mono,monospace);margin-top:4px}.ev-tile .m{font-size:11.5px;color:var(--ink-3);margin-top:2px}
.ev-split{display:grid;grid-template-columns:minmax(110px,160px) 1fr 56px;gap:10px;align-items:center;margin:7px 0;font-size:12.5px}
.ev-split .bar{display:flex;gap:2px;height:14px}.ev-split .bar i{display:block;height:100%}
.ev-split .bar i.to{background:var(--good);border-radius:4px 0 0 4px}.ev-split .bar i.aw{background:var(--bad);border-radius:0 4px 4px 0}.ev-split .bar i.eq{background:var(--line)}
.ev-split .n{color:var(--ink-3);font:500 11px var(--mono,monospace);text-align:right}
.ev-legend{display:flex;gap:14px;font-size:11.5px;color:var(--ink-3);margin-top:6px}.ev-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.ev-chart svg{display:block;width:100%;height:auto;overflow:visible}.ev-chart text{font:500 10.5px var(--mono,monospace);fill:var(--ink-3)}
.ev-chart .cap{font-size:11.5px;color:var(--ink-3);margin-top:6px}
.ev-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:760px){.ev-two{grid-template-columns:1fr}.ev-dialog .row{grid-template-columns:1fr 1fr}}
.ev-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;align-items:end;padding:10px 0 12px}
@media(max-width:760px){.ev-strip{grid-template-columns:1fr;gap:10px}}
.ev-clv{font:600 12px/1 var(--mono,monospace)}.ev-clv.pos{color:var(--good)}.ev-clv.neg{color:var(--bad)}
`;
  function injectCSS() {
    if (typeof document === "undefined" || document.getElementById("ev-css")) return;
    const s = document.createElement("style"); s.id = "ev-css"; s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ------------------------------------------------------------ team graphics */
  const hex = c => { const s = String(c || "").replace("#", ""); return /^[0-9a-f]{6}$/i.test(s) ? "#" + s : null; };
  const light = c => { const h = hex(c); if (!h) return false;
    const n = parseInt(h.slice(1), 16), r = n >> 16 & 255, g = n >> 8 & 255, b = n & 255;
    return (0.299 * r + 0.587 * g + 0.114 * b) > 170; };
  function hue(abbr) { let h = 0; for (const ch of String(abbr || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return `hsl(${h} 45% 38%)`; }
  const colorOf = t => hex(t && t.color) || hue(t && t.abbr);

  function logo(t, size) {
    t = t || {};
    const c = colorOf(t);
    const img = t.logo && /^https:\/\//.test(t.logo)
      ? `<img src="${esc(t.logo)}" alt="" loading="lazy" decoding="async" onload="this.classList.add('ok')" onerror="this.remove()">` : "";
    return `<span class="ev-logo ${size || ""} ${light(t.color) ? "lt" : ""}" style="--tc:${esc(c)}" aria-hidden="true">${esc(String(t.abbr || "?").slice(0, 4))}${img}</span>`;
  }
  const pair = (away, home) => `<span class="ev-pair">${logo(away, "sm")}${logo(home, "sm")}</span>`;

  function matchup(away, home, sub, opts) {
    opts = opts || {};
    const side = (t, cls) => `<div class="ev-side ${cls}">${logo(t, "lg")}<div><b>${esc(t.abbr)}${t.rank && t.rank < 26 ? ` <small style="display:inline;color:var(--ink-3)">#${esc(t.rank)}</small>` : ""}</b><small>${esc(t.name || "")}${t.record ? " · " + esc(t.record) : ""}</small></div></div>`;
    return `<div class="ev-match" style="--ta:${esc(colorOf(away))};--th:${esc(colorOf(home))}">${side(away, "away")}
      <div class="ev-at">${opts.neutral ? "vs" : "@"}${sub ? `<small>${esc(sub)}</small>` : ""}</div>${side(home, "home")}</div>`;
  }

  function winBar(away, home, pHome, opts) {
    if (!fin(pHome)) return "";
    opts = opts || {};
    const ph = clamp(Number(pHome), 0.01, 0.99), pa = 1 - ph;
    const fav = ph >= 0.5 ? "home" : "away";
    return `<div class="ev-win" role="img" aria-label="Model win chance: ${esc(away.abbr)} ${pct(pa, 0)}, ${esc(home.abbr)} ${pct(ph, 0)}">
      <div class="lab"><span class="${fav === "away" ? "pick" : ""}">${esc(away.abbr)} ${pct(pa, 0)}</span><span class="${fav === "home" ? "pick" : ""}">${pct(ph, 0)} ${esc(home.abbr)}</span></div>
      <div class="track"><i style="width:${(pa * 100).toFixed(1)}%;--c:${esc(colorOf(away))}"></i><i style="width:${(ph * 100).toFixed(1)}%;--c:${esc(colorOf(home))}"></i></div>
      ${opts.caption ? `<div class="cap">${esc(opts.caption)}</div>` : ""}</div>`;
  }

  /* Model vs market on one axis. Values are HOME margins (or totals). */
  function lineGauge(o) {
    if (!fin(o.market) || !fin(o.model)) return "";
    const m = Number(o.market), p = Number(o.model), span = Math.max(o.span || 7, Math.abs(p - m) + 2);
    const W = 300, x = v => 12 + (v - (m - span)) / (2 * span) * (W - 24);
    const toward = p > m ? 1 : -1, gap = p - m;
    const mx = x(m), px = x(p);
    return `<div class="ev-gauge"><div class="gt"><span>${esc(o.title)}</span><span>${esc(o.note || "")}</span></div>
      <svg viewBox="0 0 ${W} 34" role="img" aria-label="${esc(o.title)}: market ${esc(o.marketLabel)}, model ${esc(o.modelLabel)}">
        <line x1="12" x2="${W - 12}" y1="17" y2="17" stroke="var(--line)" stroke-width="2" stroke-linecap="round"/>
        ${Math.abs(gap) > .05 ? `<line x1="${mx}" x2="${px}" y1="17" y2="17" stroke="var(--accent,var(--cool))" stroke-width="4" stroke-linecap="round" opacity=".55"/>` : ""}
        <line x1="${mx}" x2="${mx}" y1="9" y2="25" stroke="var(--ink-3)" stroke-width="2"/>
        <circle cx="${px}" cy="17" r="5.5" fill="var(--accent,var(--cool))" stroke="var(--surface)" stroke-width="2"/>
        <text x="${mx}" y="7" text-anchor="${toward > 0 ? "end" : "start"}">${esc(o.marketLabel)}</text>
        <text x="${px}" y="33" text-anchor="${toward > 0 ? "start" : "end"}">${esc(o.modelLabel)}</text>
      </svg></div>`;
  }
  /* "BUF -3.5" style text for a home margin. */
  const marginText = (away, home, mu) => !fin(mu) ? "—" : Math.abs(mu) < 0.05 ? "Pick'em"
    : `${mu > 0 ? home.abbr : away.abbr} by ${Math.abs(mu).toFixed(1)}`;

  function gauges(away, home, proj) {
    proj = proj || {};
    const out = [];
    if (fin(proj.market_mu) && fin(proj.mu)) out.push(lineGauge({ title: "Spread · projected margin", note: `gap ${sgn(proj.mu - proj.market_mu)} pts`,
      market: proj.market_mu, model: proj.mu, marketLabel: "Market " + marginText(away, home, proj.market_mu),
      modelLabel: "Model " + marginText(away, home, proj.mu) }));
    if (fin(proj.market_total) && fin(proj.proj_total)) out.push(lineGauge({ title: "Total points", note: `gap ${sgn(proj.proj_total - proj.market_total)} pts`,
      market: proj.market_total, model: proj.proj_total, marketLabel: "Market " + Number(proj.market_total).toFixed(1),
      modelLabel: "Model " + Number(proj.proj_total).toFixed(1), span: 8 }));
    return out.join("");
  }

  /* ------------------------------------------------------------ pricing maths */
  const implied = a => { a = Number(a); return a > 0 ? 100 / (a + 100) : -a / (-a + 100); };
  const decimal = a => { a = Number(a); return a > 0 ? 1 + a / 100 : 1 + 100 / -a; };
  function Phi(x) { // standard normal CDF
    const t = 1 / (1 + 0.2316419 * Math.abs(x)), d = 0.3989423 * Math.exp(-x * x / 2);
    const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    return x > 0 ? 1 - p : p;
  }
  const compress = (x, cap) => cap > 0 ? cap * Math.tanh(x / cap) : x;
  const RANK = { "BEST BET": 0, "GOOD": 1, "LEAN": 2, "PASS": 3 };

  /* Home-spread / total line for this side as the bettor reads it. */
  const sideLine = row => row.line == null ? null
    : row.market === "ATS" && row.side === "away" ? -Number(row.line) : Number(row.line);
  const toRowLine = (row, typed) => row.market === "ATS" && row.side === "away" ? -typed : typed;

  /* The model's cover probability at a different line, shifted along the model's own
     distribution (normal approximation; key numbers are ignored, so treat moves across
     3 and 7 in the NFL as slightly optimistic). */
  function probAtLine(row, newLine, settings) {
    const p0 = Number(row.model_prob);
    if (row.market === "ML" || newLine == null || row.line == null || Number(newLine) === Number(row.line)) return p0;
    const m = (settings && settings.model) || {}, proj = row.projection || {};
    if (row.market === "ATS") {
      const sd = Number(m.margin_sd || 13.5), mu = Number(proj.mu);
      if (!fin(mu)) return p0;
      const cover = l => row.side === "home" ? Phi((mu + l) / sd) : Phi((-l - mu) / sd);
      return clamp(p0 + cover(Number(newLine)) - cover(Number(row.line)), 0.01, 0.99);
    }
    const sd = Number(m.total_sd || 14), t = Number(proj.proj_total);
    if (!fin(t)) return p0;
    const win = l => row.side === "over" ? Phi((t - l) / sd) : Phi((l - t) / sd);
    return clamp(p0 + win(Number(newLine)) - win(Number(row.line)), 0.01, 0.99);
  }

  function reprice(row, myPrice, myLine, settings) {
    settings = settings || {};
    const m = settings.model || {}, t = settings.tiers || {};
    const cap = Number(m.edge_compression || 0.055);
    const conf = clamp(Number(row.confidence ?? 1), 0, 1);
    const push = Number(row.push_prob || 0);
    const p = probAtLine(row, myLine, settings);
    const be = implied(myPrice);
    const ev = (1 - push) * (p * decimal(myPrice) - 1);
    const fair = Number(row.market_fair_prob || 0);
    const nv = fair > 0 ? p / fair - 1 : ev;
    const reserve = Number(m.selection_haircut ?? 0.01) + (1 - conf) * Number(m.confidence_penalty_max ?? 0.018);
    const action = Math.min(compress(nv, cap), compress(ev, cap)) - reserve;
    let tier = action >= Number(t.best_bet) ? "BEST BET" : action >= Number(t.good) ? "GOOD" : action >= Number(t.lean) ? "LEAN" : "PASS";
    const floors = t.min_prob_edge || null, probEdge = p - be;
    if (floors && tier !== "PASS") {
      const order = ["BEST BET", "GOOD", "LEAN"], key = { "BEST BET": "best_bet", "GOOD": "good", "LEAN": "lean" };
      const start = order.indexOf(tier);
      tier = order.slice(start).find(x => floors[key[x]] == null || probEdge >= Number(floors[key[x]])) || "PASS";
    }
    // Lock rules and board caps (timing, soft rails) were decided on information this
    // dialog cannot see; a better price can lift a tier but never past those caps.
    const capped = !!(row.tier_note || row.timing_tier || (row.risk_flags || []).length || row.stake_multiplier < 1);
    if (tier === "BEST BET" && row.tier !== "BEST BET") tier = "GOOD";
    if (capped && RANK[tier] < RANK[row.tier]) tier = row.tier;
    const value=typeof window!=='undefined'&&window.BetValue?window.BetValue.evaluate(row,{sport:"ncaaf",price:myPrice,line:myLine}):null;
    if(value&&!value.passes)tier="PASS";
    return { prob: p, breakeven: be, ev, action_edge: action, tier, prob_edge: probEdge, value };
  }

  /* ------------------------------------------------------------- bet dialog */
  let dlg = null;
  function openBetDialog(o) {
    injectCSS();
    const row = o.row, settings = o.settings || {}, cur = o.currency || "$";
    if (!dlg) { dlg = document.createElement("dialog"); dlg.className = "ev-dialog"; document.body.appendChild(dlg); }
    const hasLine = row.market !== "ML" && row.line != null;
    const bookLine = sideLine(row);
    dlg.innerHTML = `<form method="dialog">
      <h3>${esc(row.pick)} <small>${esc(row.matchup || "")}${row.book ? " · board price " + esc(am(row.price)) + " at " + esc(row.book) : ""}</small></h3>
      <div class="row">
        <label>Your price<input name="price" type="number" step="1" value="${esc(Math.round(row.price))}" inputmode="numeric" required></label>
        <label>${row.market === "TOTAL" ? "Your total" : "Your line"}<input name="line" type="number" step="0.5" value="${hasLine ? esc(bookLine) : ""}" ${hasLine ? "" : "disabled"}></label>
        <label>Stake (${esc(cur)})<input name="stake" type="number" min="0.5" step="0.5" value="${esc(Number(o.stake || 1).toFixed(2))}" required></label>
      </div>
      <div class="ev-verdict" data-verdict></div>
      <p class="fine">Enter the odds and line your sportsbook is showing right now. The play is re-priced with the board's own probability, reserves and tier bars; a different line shifts the model's win chance along its projected ${row.market === "TOTAL" ? "total" : "margin"}. My Ledger records the price you took and grades the bet at it.</p>
      <div class="acts"><button value="cancel" type="submit" formnovalidate>Cancel</button><button value="add" class="primary" type="submit">Add to My Ledger</button></div>
    </form>`;
    const f = dlg.querySelector("form"), out = dlg.querySelector("[data-verdict]");
    function read() {
      const price = Number(f.price.value), line = hasLine && f.line.value !== "" ? Number(f.line.value) : null;
      if (!fin(price) || Math.abs(price) < 100) return null;
      return { price, line: line == null ? row.line : toRowLine(row, line) };
    }
    function update() {
      const r = read();
      if (!r) { out.className = "ev-verdict"; out.innerHTML = "American odds are at least ±100 (e.g. −110 or +125)."; return; }
      const q = reprice(row, r.price, r.line, settings);
      const same = r.price === Number(row.price) && Number(r.line) === Number(row.line);
      const diff = q.action_edge - Number(row.action_edge ?? row.edge ?? 0);
      out.className = "ev-verdict " + (same ? "" : q.tier === "PASS" || diff < -0.002 ? "down" : diff > 0.002 ? "up" : "");
      out.innerHTML = `<div class="big"><strong>${q.tier === "PASS" ? "NO BET" : esc(q.tier)}</strong><span>${spct(q.action_edge)} adjusted return</span></div>
        Model win chance <b>${pct(q.prob)}</b> vs break-even <b>${pct(q.breakeven)}</b> at ${esc(am(r.price))} · raw EV ${spct(q.ev)}.
        ${same ? "Same number as the board." : `Board: <b>${esc(row.tier)}</b> at ${spct(row.action_edge ?? row.edge)}${row.market !== "ML" && Number(r.line) !== Number(row.line) ? ` (line ${esc(sgn(bookLine))})` : ""}.`}
        ${q.value?`<br>Minimum acceptable odds at the published line: <b>${q.value.worst==null?"unavailable":esc(am(q.value.worst))}</b>. Stress return ${q.value.stressEV==null?"unavailable":spct(q.value.stressEV)}. ${esc(q.value.reasons.join("; "))}. 3 percentage-point stress + 2% buffer; not a confidence interval.`:""}${q.tier === "PASS" ? "<br><b>No model recommendation at this contract.</b> Recording a receipt does not endorse it." : ""}`;
    }
    f.addEventListener("input", update); update();
    dlg.onclose = () => {
      if (dlg.returnValue !== "add") return;
      const r = read(), stake = Number(f.stake.value);
      if (!r || !fin(stake) || stake <= 0) return;
      const q = reprice(row, r.price, r.line, settings);
      const pick = row.market === "ML" || r.line === row.line ? row.pick : relabel(row, r.line);
      o.onConfirm({ ...row, pick, price: r.price, line: r.line, model_prob: q.prob, breakeven: q.breakeven,
        board_price: row.price, board_line: row.line, board_model_prob:row.model_prob, board_tier: row.tier, taken_ev: q.ev, taken_edge: q.action_edge, taken_tier: q.tier }, stake);
    };
    dlg.returnValue = "";
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
    setTimeout(() => f.price.focus(), 30);
  }
  function relabel(row, homeLine) {
    const team = String(row.pick || "").split(" ")[0];
    if (row.market === "TOTAL") return `${row.side === "over" ? "Over" : "Under"} ${Number(homeLine)}`;
    const l = row.side === "away" ? -homeLine : homeLine;
    return `${team} ${l > 0 ? "+" : ""}${l}`;
  }

  /* ----------------------------------------------------- closing-line value */
  /* A ledger bet against the last pregame odds stored for that game. */
  function betClv(entry, game) {
    const o = game && game.odds;
    if (!o || !entry) return null;
    const start = Date.parse(game.date || entry.game_date || "");
    if (!game.completed && !(isFinite(start) && start <= Date.now())) return null;
    let points = null, closePrice = null;
    if (entry.market === "ATS" && fin(o.spread_home) && fin(entry.line)) {
      const d = Number(entry.line) - Number(o.spread_home);
      points = entry.side === "home" ? d : -d;
      closePrice = entry.side === "home" ? o.spread_price_home : o.spread_price_away;
    } else if (entry.market === "TOTAL" && fin(o.total) && fin(entry.line)) {
      const d = Number(o.total) - Number(entry.line);
      points = entry.side === "over" ? d : -d;
      closePrice = entry.side === "over" ? o.over_price : o.under_price;
    } else if (entry.market === "ML") {
      closePrice = entry.side === "home" ? o.ml_home : o.ml_away;
    }
    const prob = fin(closePrice) && fin(entry.price) ? implied(closePrice) - implied(entry.price) : null;
    if (points == null && prob == null) return null;
    return { points: points == null ? null : Math.round(points * 10) / 10, prob, close_price: closePrice };
  }
  function clvCell(c) {
    if (!c) return `<span class="ev-clv" style="color:var(--ink-3)">—</span>`;
    const good = c.points ? c.points > 0 : (c.prob || 0) > 0, bad = c.points ? c.points < 0 : (c.prob || 0) < 0;
    const txt = c.points ? `${sgn(c.points)} pts` : spct(c.prob);
    return `<span class="ev-clv ${good ? "pos" : bad ? "neg" : ""}" title="Versus the last pregame number${fin(c.close_price) ? " (" + am(c.close_price) + ")" : ""}">${esc(txt)}</span>`;
  }
  function ledgerClvSummary(entries, games) {
    const map = new Map((games || []).map(g => [String(g.game_id), g]));
    let beat = 0, worse = 0, pts = [], n = 0;
    (entries || []).forEach(e => { const c = betClv(e, map.get(String(e.game_id))); if (!c) return; n++;
      const v = c.points ? c.points : c.prob; if (v > 0) beat++; else if (v < 0) worse++; if (c.points != null) pts.push(c.points); });
    return { n, beat, worse, pct: beat + worse ? beat / (beat + worse) : null, avg_points: pts.length ? pts.reduce((a, b) => a + b, 0) / pts.length : null };
  }

  /* ------------------------------------------------------- accuracy panels */
  function split(label, s) {
    if (!s || !s.n) return `<div class="ev-split"><span>${esc(label)}</span><span class="n" style="text-align:left">no finished games yet</span><span></span></div>`;
    const t = s.toward_model || 0, a = s.away_from_model || 0, u = s.unchanged || 0, n = t + a + u || 1;
    return `<div class="ev-split" title="${t} toward · ${a} away · ${u} unchanged">
      <span>${esc(label)}<br><small style="color:var(--ink-3)">avg ${sgn(s.avg_points, 2)} pts</small></span>
      <span class="bar"><i class="to" style="width:${(t / n * 100).toFixed(1)}%"></i><i class="eq" style="width:${(u / n * 100).toFixed(1)}%"></i><i class="aw" style="width:${(a / n * 100).toFixed(1)}%"></i></span>
      <span class="n">${pct(s.toward_pct, 0)}<br>n=${s.n}</span></div>`;
  }
  function tile(k, v, m, cls) { return `<div class="ev-tile"><div class="k">${esc(k)}</div><div class="v ${cls || ""}">${v}</div><div class="m">${esc(m || "")}</div></div>`; }
  const tone = (v, mid) => !fin(v) ? "" : v > mid ? "pos" : v < mid ? "neg" : "";

  function clvPanel(clv) {
    injectCSS();
    if (!clv) return "";
    const f = clv.forecasts || {}, p = clv.plays || {}, bt = p.by_timing || {}, e = bt.early || {}, l = bt.late || {};
    return `<section class="ev-panel"><h3>Closing-line value — is the model ahead of the market?</h3>
      <p>Win/loss needs a full season to mean anything. Line movement shows up in weeks: if the model knows something, the number should move toward it before kickoff more often than away. Around 50/50 means the market already knew. Every play is locked at the first price it was published at.</p>
      <div class="ev-tiles">
        ${tile("Spread moved toward model", pct((f.spread || {}).toward_pct, 0), `${(f.spread || {}).n || 0} frozen forecasts`, tone((f.spread || {}).toward_pct, .5))}
        ${tile("Total moved toward model", pct((f.total || {}).toward_pct, 0), `${(f.total || {}).n || 0} frozen forecasts`, tone((f.total || {}).toward_pct, .5))}
        ${tile("Plays beat the close", pct(p.beat_close_pct, 0), `${p.closed || 0} closed · ${p.locked || 0} locked`, tone(p.beat_close_pct, .5))}
        ${tile("Avg CLV per play", fin(p.avg_clv_points) ? sgn(p.avg_clv_points, 2) + " pts" : "—", fin(p.avg_clv_prob) ? spct(p.avg_clv_prob) + " in price" : "spreads & totals", tone(p.avg_clv_points, 0))}
        ${tile("Locked-play record", esc(p.record || "0-0-0"), fin(p.win_rate) ? pct(p.win_rate) + " wins" : "graded at the locked price")}
      </div>
      ${split("Spreads", f.spread)}${split("Spreads, 2+ pt gap", f.spread_big)}${split("Totals", f.total)}
      <div class="ev-legend"><span><i style="background:var(--good)"></i>moved toward model</span><span><i style="background:var(--line)"></i>unchanged</span><span><i style="background:var(--bad)"></i>moved away</span></div>
      ${(e.tracked || l.tracked) ? `<h3 style="margin-top:16px;font-size:14px">Early vs late — when is the edge real?</h3>
      <div class="ev-tiles" style="margin-bottom:0">
        ${tile(`Early (${p.early_hours || 96}h+ before kickoff)`, pct(e.beat_close_pct, 0), `beat the close · ${e.closed || 0} closed · ${esc(e.record || "0-0-0")}`, tone(e.beat_close_pct, .5))}
        ${tile("Late", pct(l.beat_close_pct, 0), `beat the close · ${l.closed || 0} closed · ${esc(l.record || "0-0-0")}`, tone(l.beat_close_pct, .5))}
      </div>` : ""}
      ${gateBlock(p.gate)}
    </section>`;
  }

  /* Closing-line gate: which tiers each market group has earned so far. */
  function gateBlock(gate) {
    if (!gate) return "";
    const label = { sides: "Spreads & moneylines", totals: "Totals" };
    const say = (k, g) => {
      const need = `${g.closed || 0}/${g.need || 100} closed`, beat = fin(g.beat_close_pct) ? ` · ${pct(g.beat_close_pct, 0)} beat the close` : "";
      if (g.status === "off") return ["Gate off", "tiers as priced", ""];
      if (g.status === "proven") return ["All tiers", `proven${beat}`, "pos"];
      if (g.status === "failing") return ["LEAN only", `market ahead of the model${beat} · half stakes`, "neg"];
      if (g.untiered) return ["Research only", `not tiered until proven · ${need}${beat}`, ""];
      return ["Up to GOOD", `BEST BET unlocks at ${pct(g.unlock_pct || .53, 0)} · ${need}${beat}`, ""];
    };
    const tiles = ["sides", "totals"].filter(k => gate[k]).map(k => { const [v, m, c] = say(k, gate[k]); return tile(label[k], esc(v), m, c); }).join("");
    return tiles ? `<h3 style="margin-top:16px;font-size:14px">Tier gate — earned by beating the close</h3>
      <p>The 15-season backtest found no reliable edge against the <b>closing</b> line, so tiers are earned by taking numbers before they move. BEST BET stays locked, and totals stay research-only, until 100 tracked plays in that group have closed and at least ${pct((gate.sides || {}).unlock_pct || .53, 0)} beat the closing line.</p>
      <div class="ev-tiles" style="margin-bottom:0">${tiles}</div>` : "";
  }

  function seasonBars(seasons) {
    const rows = (seasons || []).filter(s => s.n);
    if (!rows.length) return "";
    const W = 560, H = 170, pad = 28, max = Math.max(0.12, ...rows.map(s => Math.abs(s.roi || 0)));
    const bw = (W - pad * 2) / rows.length, y0 = H / 2, y = v => y0 - v / max * (H / 2 - 18);
    const bars = rows.map((s, i) => {
      const v = s.roi || 0, x = pad + i * bw + 2, h = Math.abs(y(v) - y0), top = v >= 0 ? y(v) : y0;
      return `<g><title>${s.season}: ${s.record} · ROI ${spct(v)} · ${s.n} plays</title>
        <rect x="${x.toFixed(1)}" y="${top.toFixed(1)}" width="${Math.max(3, bw - 4).toFixed(1)}" height="${Math.max(1, h).toFixed(1)}" rx="3" fill="${v >= 0 ? "var(--good)" : "var(--bad)"}"/>
        ${i % 2 === 0 || rows.length < 10 ? `<text x="${(x + bw / 2 - 2).toFixed(1)}" y="${H - 2}" text-anchor="middle">'${String(s.season).slice(2)}</text>` : ""}</g>`;
    }).join("");
    return `<div class="ev-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Return on selected plays by season">
      <line x1="${pad}" x2="${W - pad}" y1="${y0}" y2="${y0}" stroke="var(--line)"/>
      <text x="${pad - 4}" y="${y(max * 0.8) + 4}" text-anchor="end">${spct(max * 0.8, 0)}</text>
      <text x="${pad - 4}" y="${y(-max * 0.8) + 4}" text-anchor="end">${spct(-max * 0.8, 0)}</text>${bars}</svg>
      <div class="cap">Return per play on the board's selected plays, each season, at closing prices. Hover a bar for the record.</div></div>`;
  }
  function calibrationPlot(rows) {
    rows = (rows || []).filter(r => r.n);
    if (!rows.length) return "";
    const S = 220, pad = 30, lo = 0.1, hi = 0.9, sc = v => pad + (clamp(v, lo, hi) - lo) / (hi - lo) * (S - pad - 8);
    const maxN = Math.max(...rows.map(r => r.n));
    const dots = rows.map(r => `<circle cx="${sc(r.predicted).toFixed(1)}" cy="${(S - sc(r.actual)).toFixed(1)}" r="${(4 + 6 * Math.sqrt(r.n / maxN)).toFixed(1)}" fill="var(--accent,var(--cool))" fill-opacity=".75" stroke="var(--surface)" stroke-width="2"><title>Model said ${pct(r.predicted)} · happened ${pct(r.actual)} · ${r.n} plays</title></circle>`).join("");
    return `<div class="ev-chart"><svg viewBox="0 0 ${S} ${S}" role="img" aria-label="Calibration: predicted versus actual win rate" style="width:100%;max-width:280px;margin:0 auto">
      <line x1="${sc(lo)}" y1="${S - sc(lo)}" x2="${sc(hi)}" y2="${S - sc(hi)}" stroke="var(--line)" stroke-dasharray="4 4"/>
      ${[0.2, 0.5, 0.8].map(v => `<text x="${sc(v)}" y="${S - 6}" text-anchor="middle">${pct(v, 0)}</text><text x="${pad - 5}" y="${S - sc(v) + 4}" text-anchor="end">${pct(v, 0)}</text>`).join("")}
      ${dots}</svg><div class="cap">Every priced side (home spreads, home moneylines, overs): model win chance (across) vs how often it happened (up). Dots on the dashed line mean honest probabilities.</div></div>`;
  }

  function backtestPanel(bt) {
    injectCSS();
    if (!bt || !bt.games) return "";
    const sc = bt.scores || {}, sel = bt.selected || {};
    const verdict = m => { const s = sc[m]; if (!s) return "—"; return s.logloss_edge > 0 ? "Model" : "Market"; };
    const mk = bt.by_market || {}, rs = (bt.research || {}).all;
    const mTile = m => (m === "TOTAL" && !(mk.TOTAL || {}).n && rs && rs.n)
      ? tile("Totals (research only)", spct(rs.roi), `${rs.record} at model tier · not bet · more accurate: ${verdict(m)}`, tone(rs.roi, 0))
      : tile(`${m === "ATS" ? "Spreads" : m === "TOTAL" ? "Totals" : "Moneyline"}`, spct((mk[m] || {}).roi), `${(mk[m] || {}).record || "—"} · more accurate: ${verdict(m)}`, tone((mk[m] || {}).roi, 0));
    return `<section class="ev-panel"><h3>15-season backtest — ${esc(bt.seasons[0])}–${esc(bt.seasons[1])}, ${esc(bt.games.toLocaleString())} games</h3>
      <p>Every week replayed with only the information available before it, priced against the <b>closing</b> line from nflverse's free historical data. ${esc(bt.limits || "")}</p>
      <div class="ev-tiles">
        ${tile("Selected plays", esc(sel.record || "—"), `${sel.n || 0} plays · ${pct(sel.win_pct)} wins`)}
        ${tile("Return per play", spct(sel.roi), "flat stakes at closing prices", tone(sel.roi, 0))}
        ${["ATS", "TOTAL", "ML"].map(mTile).join("")}
      </div>
      <div class="ev-two">${seasonBars(bt.by_season)}${calibrationPlot(bt.calibration_all_home_sides)}</div>
      <p style="margin-top:12px;font-size:12px;color:var(--ink-3)">What it means: against the sharpest number of the week, results-based power ratings alone did not beat the market. The live board adds FPI, injuries, weather and earlier prices — which is exactly what the closing-line tracking above measures. Moneylines longer than +120 are no longer tiered because their edges ran backwards here${rs && rs.n ? `; totals are research-only — at their model tiers they went ${esc(rs.record)} (${spct(rs.roi)} a play)` : ""}. The model's record also faded as the market sharpened — compare the early and recent seasons above — which is why tiers now have to be earned by beating the close.</p>
    </section>`;
  }
  function mountBacktest(host, url) {
    if (!host || typeof fetch === "undefined") return;
    fetch(url || "data/backtest.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : null)
      .then(d => { if (d) host.innerHTML = backtestPanel(d); }).catch(() => {});
  }

  /* Compact visual strip for a board row: win chance + spread + total gauges. */
  const pHome = (mu, sd) => fin(mu) ? clamp(Phi(Number(mu) / Number(sd || 13.5)), 0.01, 0.99) : null;
  function strip(away, home, proj, sd) {
    const w = winBar(away, home, pHome((proj || {}).mu, sd), { caption: "Model win chance" });
    const g = gauges(away, home, proj);
    return w || g ? `<div class="ev-strip">${w}${g}</div>` : "";
  }

  injectCSS();
  const api = { esc, logo, pair, matchup, winBar, lineGauge, gauges, marginText, colorOf, reprice, probAtLine, pHome, strip,
    openBetDialog, betClv, clvCell, ledgerClvSummary, clvPanel, backtestPanel, mountBacktest, implied, decimal };
  root.EdgeVisuals = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
