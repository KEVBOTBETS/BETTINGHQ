/*
 * Ledger HQ - every bet from every board, in one place.
 *
 * This page keeps no ledger of its own. It reads the sheet the connected boards sync
 * to, and when you settle something here it writes the row straight back, with
 * the board's own record (native_json) passed through untouched: each board is
 * still the only thing that decides what its own entry looks like, and it
 * reconciles its copy the next time it syncs.
 *
 * The one number that matters is the bankroll, and it is deliberately computed
 * the same way here as in betsync.js rather than being recomputed differently -
 * two answers to "how much money do I have" is worse than none.
 */
(function () {
  "use strict";

  var BS = window.BetSync, D = window.KevLedgerDetails;
  var baselineReady=false;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var main = $("#main");

  var S = {
    features: [], audit: [], auditCursor: null, auditError: '',
    rows: [], settings: {}, loaded: false, busy: false, error: "",
    lastSync: null, sourceUrl: null,
    boards: {},              // which boards are shown; empty object means all
    status: "all",           // all | open | settled
    days: 0                  // 0 = everything
  };

  var BOARDS = [
    { app: "mlb-edge", label: "MLB Edge", hue: "var(--b1)" },
    { app: "ncaaf-lab", label: "NCAAF Lab", hue: "var(--b2)" },
    { app: "nfl-lab", label: "NFL Lab", hue: "var(--b3)" },
    { app: "wnba-lab", label: "WNBA Lab", hue: "#b58aff" },
    { app: "props", label: "Props", hue: "var(--b4)" },
    { app: "ladder", label: "Ladder", hue: "var(--b5)" }
  ];
  var BY_APP = {};
  BOARDS.forEach(function (b) { BY_APP[b.app] = b; });

  function board(app) {
    return BY_APP[app] || { app: app, label: app || "Other", hue: "var(--dim)" };
  }

  /* ------------------------------------------------------------- helpers -- */

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function money(v) {
    var n = Number(v || 0);
    return (n < 0 ? "-$" : "$") + Math.abs(n).toFixed(2);
  }
  function signed(v) {
    var n = Number(v || 0);
    return (n > 0 ? "+" : n < 0 ? "-" : "") + "$" + Math.abs(n).toFixed(2);
  }
  function pct(v, digits) {
    return v == null ? "—" : (v * 100).toFixed(digits == null ? 1 : digits) + "%";
  }
  function american(v) {
    if (v == null || v === "") return "—";
    var n = Number(v);
    return (n > 0 ? "+" : "") + n;
  }
  function sgn(v) { return Number(v) > 0 ? "pos" : Number(v) < 0 ? "neg" : ""; }
  function ago(iso) {
    if (!iso) return "";
    var s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    return s < 45 ? "just now" : s < 3600 ? Math.round(s / 60) + "m ago"
      : s < 86400 ? Math.round(s / 3600) + "h ago" : Math.round(s / 86400) + "d ago";
  }
  function day(row) {
    return String(row.event_date || row.placed_at || "").slice(0, 10);
  }

  /* ------------------------------------------------------------ filtering - */

  function live() {
    var chosen = Object.keys(S.boards);
    var cutoff = "";
    if (S.days) {
      var d = new Date();
      d.setDate(d.getDate() - S.days);
      cutoff = d.toISOString().slice(0, 10);
    }
    return S.rows.filter(function (r) {
      if (r.deleted) return false;
      if (chosen.length && !S.boards[r.app]) return false;
      if (S.status === "open" && r.status !== "Pending") return false;
      if (S.status === "settled" && r.status === "Pending") return false;
      if (cutoff && day(r) && day(r) < cutoff) return false;
      return true;
    });
  }

  /* --------------------------------------------------------------- charts - */

  /* Bankroll over time. One series, so no legend - the caption names it - and
     only the last point is labelled: a number on every point is noise. */
  function bankrollCurve(rows, starting) {
    var settled = rows.filter(function (r) { return r.status !== "Pending"; })
      .slice().sort(function (a, b) {
        return String(day(a) + a.id).localeCompare(String(day(b) + b.id));
      });
    if (settled.length < 2) return "";

    var balance = Number(starting || 0);
    var pts = [{ x: 0, v: balance, label: "start", date: "" }];
    settled.forEach(function (r, i) {
      balance += BS.impliedPnl(r);
      pts.push({ x: i + 1, v: Math.round(balance * 100) / 100, date: day(r),
                 label: r.selection, pnl: BS.impliedPnl(r), app: r.app });
    });

    /* A 720x190 frame scaled down to phone width leaves a 95px-tall plot with
       unreadable axis text. Narrow screens get their own proportions instead. */
    var narrow = typeof window !== "undefined" && window.innerWidth <= 560;
    var W = narrow ? 380 : 720, H = narrow ? 215 : 190;
    var PL = narrow ? 44 : 52, PR = 14, PT = 14, PB = 26;

    var lo = Math.min.apply(null, pts.map(function (p) { return p.v; }));
    var hi = Math.max.apply(null, pts.map(function (p) { return p.v; }));
    var pad = Math.max((hi - lo) * 0.12, 5);
    lo -= pad; hi += pad;
    var nice = niceTicks(lo, hi, narrow ? 3 : 4);
    lo = Math.min(lo, nice[0]); hi = Math.max(hi, nice[nice.length - 1]);
    var xOf = function (i) { return PL + (i / (pts.length - 1)) * (W - PL - PR); };
    var yOf = function (v) { return PT + (1 - (v - lo) / (hi - lo || 1)) * (H - PT - PB); };

    var line = pts.map(function (p, i) { return (i ? "L" : "M") + xOf(i).toFixed(1) + " " + yOf(p.v).toFixed(1); }).join(" ");
    var area = line + " L" + xOf(pts.length - 1).toFixed(1) + " " + (H - PB) + " L" + xOf(0).toFixed(1) + " " + (H - PB) + " Z";

    var ticks = nice.map(function (v) {
      return '<line x1="' + PL + '" x2="' + (W - PR) + '" y1="' + yOf(v).toFixed(1) +
        '" y2="' + yOf(v).toFixed(1) + '"/>' +
        '<text x="' + (PL - 7) + '" y="' + (yOf(v) + 3.5).toFixed(1) + '" text-anchor="end">$' +
        Math.round(v) + '</text>';
    }).join("");

    var last = pts[pts.length - 1];
    var first = pts.find(function (p) { return p.date; });

    return '<figure><figcaption>Bankroll after every settled bet, all connected boards' +
      ' — started at ' + money(starting) + '</figcaption>' +
      '<div class="plot" id="curveBox">' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Bankroll over time">' +
      '<g class="grid axis">' + ticks + '</g>' +
      '<path class="curve-fill" d="' + area + '"/>' +
      '<path class="curve" d="' + line + '"/>' +
      '<line class="cross" id="curveCross" x1="0" x2="0" y1="' + PT + '" y2="' + (H - PB) + '" opacity="0"/>' +
      '<circle class="endcap" cx="' + xOf(pts.length - 1).toFixed(1) + '" cy="' + yOf(last.v).toFixed(1) + '" r="4"/>' +
      '<text x="' + (xOf(pts.length - 1) - 6).toFixed(1) + '" y="' +
        Math.max(PT + 9, yOf(last.v) - 11).toFixed(1) +
        '" text-anchor="end" class="endlabel">' + money(last.v) + '</text>' +
      '<g class="axis">' +
        '<text x="' + PL + '" y="' + (H - 8) + '">' + esc(first ? first.date : "") + '</text>' +
        '<text x="' + (W - PR) + '" y="' + (H - 8) + '" text-anchor="end">' + esc(last.date) + '</text>' +
      '</g></svg><div class="tip" id="curveTip"></div></div></figure>';
  }

  /* Axis labels people can read back: round steps, not whatever the padding
     happened to land on. */
  function niceTicks(lo, hi, count) {
    var raw = (hi - lo) / Math.max(1, count - 1);
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; })
      .find(function (s) { return s >= raw; }) || 10 * mag;
    var start = Math.floor(lo / step) * step;
    var out = [];
    for (var v = start; v <= hi + step * 0.001 && out.length < 8; v += step) out.push(Math.round(v * 100) / 100);
    return out.length >= 2 ? out : [lo, hi];
  }

  function wireCurve(pts) {
    var box = $("#curveBox");
    if (!box || !pts || pts.length < 2) return;
    var svg = box.querySelector("svg");
    var cross = $("#curveCross");
    var tip = $("#curveTip");

    function move(e) {
      var r = box.getBoundingClientRect();
      var x = ((e.touches ? e.touches[0].clientX : e.clientX) - r.left) / r.width;
      var i = Math.round(x * (pts.length - 1));
      i = Math.max(0, Math.min(pts.length - 1, i));
      var p = pts[i];
      var vb = svg.viewBox.baseVal;
      var pl = vb.width <= 400 ? 44 : 52;
      var px = pl + (i / (pts.length - 1)) * (vb.width - pl - 14);
      cross.setAttribute("x1", px); cross.setAttribute("x2", px);
      cross.setAttribute("opacity", "1");
      tip.innerHTML = (p.date ? '<b>' + esc(p.date) + '</b><br>' : '') +
        (p.label ? esc(p.label) + '<br>' : '') +
        (p.pnl == null ? '' : '<span class="' + sgn(p.pnl) + '">' + signed(p.pnl) + '</span> → ') +
        '<b>' + money(p.v) + '</b>';
      tip.style.opacity = "1";
      var left = (px / vb.width) * r.width;
      tip.style.left = Math.min(Math.max(6, left - tip.offsetWidth / 2), r.width - tip.offsetWidth - 6) + "px";
      tip.style.top = "4px";
    }
    function leave() { cross.setAttribute("opacity", "0"); tip.style.opacity = "0"; }

    box.addEventListener("pointermove", move);
    box.addEventListener("pointerleave", leave);
    box.addEventListener("touchmove", move, { passive: true });
    box.addEventListener("touchend", leave);
  }

  /* P/L by board. One measure across five names, and the measure is diverging -
     profit one way, loss the other, nothing in the middle - so it gets the
     diverging pair rather than five hues fighting for attention. Each row is
     labelled, so the board's colour is identity, never the only signal. */
  function boardBars(rows) {
    var agg = {};
    rows.forEach(function (r) {
      var a = agg[r.app] || (agg[r.app] = { pnl: 0, bets: 0, open: 0, staked: 0, wins: 0, losses: 0 });
      a.bets++;
      if (r.status === "Pending") { a.open++; return; }
      a.pnl += BS.impliedPnl(r);
      if (r.status === "Win") { a.wins++; a.staked += Number(r.stake || 0); }
      if (r.status === "Loss") { a.losses++; a.staked += Number(r.stake || 0); }
    });
    var list = BOARDS.filter(function (b) { return agg[b.app]; })
      .concat(Object.keys(agg).filter(function (a) { return !BY_APP[a]; }).map(board));
    if (!list.length) return "";

    var span = Math.max.apply(null, list.map(function (b) { return Math.abs(agg[b.app].pnl); }).concat([1]));

    return '<figure><figcaption>Profit and loss by board — bars run right of the ' +
      'zero line when a board is ahead</figcaption><div class="bars">' +
      list.map(function (b) {
        var a = agg[b.app];
        var w = (Math.abs(a.pnl) / span) * 50;
        var style = a.pnl >= 0
          ? 'left:50%;width:' + w.toFixed(1) + '%;background:var(--pos)'
          : 'right:50%;width:' + w.toFixed(1) + '%;background:var(--neg)';
        return '<div class="bar-row">' +
          '<div><span class="dot" style="background:' + b.hue + '"></span>' + esc(b.label) + '</div>' +
          '<div class="bar-track"><span class="axis0" style="left:50%"></span>' +
            '<i style="' + style + '"></i></div>' +
          '<div class="n ' + sgn(a.pnl) + '">' + signed(a.pnl) + '</div>' +
        '</div>';
      }).join("") + '</div></figure>';
  }

  /* --------------------------------------------------------------- blocks - */

  function kpis(rows) {
    var b = BS.bankroll(rows, S.settings.starting_bankroll);
    var clv = clvSummary(rows);
    return '<div class="kpis">' +
      tile("Bankroll", money(b.current), b.starting ? "from " + money(b.starting) : "") +
      tile("Profit / loss", signed(b.pnl), b.staked ? "on " + money(b.staked) + " staked" : "", sgn(b.pnl)) +
      tile("ROI", pct(b.roi), b.settled ? "" : "", sgn(b.roi)) +
      tile("Record", b.wins + "–" + b.losses + (b.pushes ? "–" + b.pushes : ""),
           b.win_rate == null ? "" : pct(b.win_rate, 0) + " win rate") +
      tile("At risk", money(b.exposure), b.pending + " open") +
      tile("Available", money(b.available), "to stake") +
      (clv.n ? tile("ML price change", pct(clv.avg, 2), clv.n + " entries · probability points, not full CLV", sgn(clv.avg)) : "") +
      '</div>';
  }

  function tile(label, value, note, cls) {
    return '<div class="kpi"><span>' + esc(label) + '</span><b class="' + (cls || "") + '">' +
      esc(value) + '</b>' + (note ? '<i>' + esc(note) + '</i>' : '') + '</div>';
  }

  /* Price-only movement is not full closing-line value. Without a closing
     spread/total, comparing different lines is invalid. Restrict this small
     price metric to moneylines and do not infer profitability from it. */
  function clvSummary(rows) {
    var vals = [];
    rows.forEach(function (r) {
      if (!/^(ML|MONEYLINE)$/i.test(String(r.market || "")) || r.line != null) return;
      if (r.closing_price == null || r.price == null || Math.abs(Number(r.price)) < 100 || Math.abs(Number(r.closing_price)) < 100) return;
      var took = BS.decimalOdds(r.price), closed = BS.decimalOdds(r.closing_price);
      if (took <= 1 || closed <= 1) return;
      vals.push((1 / closed) - (1 / took));      // implied probability gained
    });
    if (!vals.length) return { n: 0, avg: null };
    return { n: vals.length, avg: vals.reduce(function (a, b) { return a + b; }, 0) / vals.length };
  }

  function breakdown(rows, key, title, order) {
    var agg = {};
    rows.forEach(function (r) {
      var k = String(r[key] || "—");
      var a = agg[k] || (agg[k] = { n: 0, w: 0, l: 0, p: 0, open: 0, staked: 0, pnl: 0 });
      a.n++;
      if (r.status === "Pending") { a.open++; return; }
      a.pnl += BS.impliedPnl(r);
      if (r.status === "Win") { a.w++; a.staked += Number(r.stake || 0); }
      else if (r.status === "Loss") { a.l++; a.staked += Number(r.stake || 0); }
      else if (r.status === "Push") a.p++;
    });
    var keys = Object.keys(agg);
    if (!keys.length) return "";
    keys.sort(function (x, y) {
      if (order) {
        var ix = order.indexOf(x), iy = order.indexOf(y);
        if (ix >= 0 || iy >= 0) return (ix < 0 ? 99 : ix) - (iy < 0 ? 99 : iy);
      }
      return agg[y].n - agg[x].n;
    });

    return '<h2>' + esc(title) + '</h2><div class="card scroll"><table><thead><tr>' +
      '<th>' + esc(title) + '</th><th class="n">Bets</th><th class="n">Open</th>' +
      '<th class="n">Record</th><th class="n">Staked</th><th class="n">P/L</th><th class="n">ROI</th>' +
      '</tr></thead><tbody>' + keys.map(function (k) {
        var a = agg[k];
        var roi = a.staked ? a.pnl / a.staked : null;
        return '<tr><td>' + (key === "app"
            ? '<span class="dot" style="background:' + board(k).hue + '"></span>' + esc(board(k).label)
            : esc(k)) + '</td>' +
          '<td class="n">' + a.n + '</td><td class="n muted">' + (a.open || "—") + '</td>' +
          '<td class="n">' + a.w + '–' + a.l + (a.p ? '–' + a.p : '') + '</td>' +
          '<td class="n muted">' + money(a.staked) + '</td>' +
          '<td class="n ' + sgn(a.pnl) + '">' + signed(a.pnl) + '</td>' +
          '<td class="n ' + sgn(roi) + '">' + pct(roi) + '</td></tr>';
      }).join("") + '</tbody></table></div>';
  }

  function openBets(rows) {
    var open = rows.filter(function (r) { return r.status === "Pending"; })
      .sort(function (a, b) { return String(day(a)).localeCompare(String(day(b))); });
    if (!open.length) return '<h2>Open bets</h2><div class="card empty">Nothing live right now.</div>';

    return '<h2>Open bets — ' + open.length + '</h2>' + open.map(function (r) {
      var b = board(r.app);
      return '<div class="bet" data-id="' + esc(r.id) + '">' +
        '<div class="top"><div class="nm">' + esc(r.selection || r.event || "Bet") + '</div>' +
          '<div class="n muted">' + american(r.price) + '</div></div>' +
        '<div class="meta"><span class="dot" style="background:' + b.hue + '"></span>' +
          esc(b.label) + ' · ' + esc(r.event || "") + (r.market ? ' · ' + esc(r.market) : '') +
          (day(r) ? ' · ' + esc(day(r)) : '') + '</div>' +
        '<div class="acts">' +
          '<label class="muted" style="font-size:12px">Stake ' +
            '<input class="num" type="number" min="0" step="0.5" data-act="stake" ' +
            'value="' + Number(r.stake || 0).toFixed(2) + '"></label>' +
          '<label class="muted" style="font-size:12px">Close ' +
            '<input class="num" type="number" step="1" placeholder="odds" data-act="closing" ' +
            'value="' + (r.closing_price == null ? "" : esc(r.closing_price)) + '"></label>' +
          '<div class="settle">' + ['Win', 'Loss', 'Push', 'Void'].map(function (s) {
            return '<button class="btn sm" data-act="settle" data-status="' + s + '">' + s + '</button>';
          }).join("") + '</div>' +
        '</div></div>';
    }).join("");
  }

  function allBets(rows) {
    var list = rows.slice().sort(function (a, b) {
      return String(day(b) + b.id).localeCompare(String(day(a) + a.id));
    });
    if (!list.length) return '<h2>All bets</h2><div class="card empty">No bets match these filters.</div>';

    return '<h2>All bets — ' + list.length + '</h2><div class="card scroll"><table><thead><tr>' +
      '<th>Date</th><th>Board</th><th>Bet</th><th class="n">Price</th><th class="n">Stake</th>' +
      '<th>Status</th><th class="n">P/L</th></tr></thead><tbody>' +
      list.map(function (r) {
        var b = board(r.app);
        var pnl = r.status === "Pending" ? null : BS.impliedPnl(r);
        return '<tr><td class="n muted">' + esc(day(r) || "—") + '</td>' +
          '<td><span class="dot" style="background:' + b.hue + '"></span>' + esc(b.label) + '</td>' +
          '<td>' + esc(r.selection || "—") +
            '<div class="muted" style="font-size:11.5px">' + esc(r.event || "") + '</div></td>' +
          '<td class="n">' + american(r.price) + '</td>' +
          '<td class="n">' + money(r.stake) + '</td>' +
          '<td><span class="pill ' + esc(r.status) + '">' + esc(r.status) + '</span></td>' +
          '<td class="n ' + (pnl == null ? "" : sgn(pnl)) + '">' +
            (pnl == null ? '—' : signed(pnl)) + '</td></tr>';
      }).join("") + '</tbody></table></div>' +
      '<div style="margin-top:10px"><button class="btn sm" id="csv">Download CSV</button></div>';
  }

  function filters() {
    var chosen = Object.keys(S.boards);
    return '<div class="filters">' +
      BOARDS.map(function (b) {
        var on = !chosen.length || !!S.boards[b.app];
        return '<button class="btn sm" data-act="board" data-app="' + b.app + '" aria-pressed="' +
          (chosen.length && on) + '"><span class="dot" style="background:' + b.hue +
          ';opacity:' + (on ? 1 : .3) + '"></span>' + esc(b.label) + '</button>';
      }).join("") +
      '<span class="sep"></span>' +
      [["all", "All"], ["open", "Open"], ["settled", "Settled"]].map(function (s) {
        return '<button class="btn sm" data-act="status" data-status="' + s[0] + '" aria-pressed="' +
          (S.status === s[0]) + '">' + s[1] + '</button>';
      }).join("") +
      '<span class="sep"></span>' +
      '<select data-act="days">' + [[0, "All time"], [7, "Last 7 days"], [30, "Last 30 days"], [90, "Last 90 days"]]
        .map(function (d) {
          return '<option value="' + d[0] + '"' + (S.days === d[0] ? " selected" : "") + '>' + d[1] + '</option>';
        }).join("") + '</select>' +
      '</div>';
  }

  function settingsBlock() {
    return '<h2>Settings</h2><div class="card">' +
      '<label class="note">Starting bankroll — every board sizes its stakes off this ' +
      'number plus everything settled since.<br>' +
      '<input class="num" id="starting" type="number" step="1" style="margin-top:7px;width:130px" value="' +
        esc(Number(S.settings.starting_bankroll || 0)) + '"> ' +
      '<button class="btn sm" id="saveStarting">Save</button></label>' +
      '<div class="note" style="margin-top:12px">Connected as <b>' +
        esc((BS.loadConfig() || {}).device || "") + '</b>. ' +
      '<button class="btn sm" id="forget">Disconnect this device</button></div></div>';
  }

  /* ---------------------------------------------------------------- render */

  function render() {
    if (!BS.loadConfig()) return renderGate();

    if (!S.loaded && !S.error) {
      main.innerHTML = '<div class="empty" style="padding:40px 0">Loading the sheet…</div>';
      return;
    }

    var rows = live();
    var pts = null;

    main.innerHTML =
      (S.error ? '<div class="err">' + esc(S.error) + '</div>' : "") +
      filters() +
      '<div style="margin-top:14px">' + kpis(rows) + '</div>' +
      '<h2>Bankroll</h2>' + (bankrollCurve(rows, S.settings.starting_bankroll) ||
        '<div class="card empty">The curve appears once two bets have settled.</div>') +
      '<h2>By board</h2>' + (boardBars(rows) || '<div class="card empty">No bets yet.</div>') +
      openBets(rows) +
      breakdown(rows, "app", "Board") +
      breakdown(rows, "tier", "Tier", ["BEST BET", "GOOD", "LEAN", "PASS"]) +
      breakdown(rows, "market", "Market") +
      allBets(rows) +
      closingDetails(rows) + historyBlock() +
      settingsBlock()+'<section id="recovery"></section>';
    if(!S.error&&!S.busy)window.KevRecoveryView?.mount($('#recovery'),S,pull);

    // the curve needs its own points back to answer a hover
    var settled = rows.filter(function (r) { return r.status !== "Pending"; })
      .slice().sort(function (a, b) { return String(day(a) + a.id).localeCompare(String(day(b) + b.id)); });
    if (settled.length >= 2) {
      var bal = Number(S.settings.starting_bankroll || 0);
      pts = [{ x: 0, v: bal, label: "Starting bankroll", date: "", pnl: null }];
      settled.forEach(function (r, i) {
        bal += BS.impliedPnl(r);
        pts.push({ x: i + 1, v: Math.round(bal * 100) / 100, date: day(r),
                   label: r.selection, pnl: BS.impliedPnl(r) });
      });
      wireCurve(pts);
    }

    $("#stamp").textContent = S.busy ? "syncing…"
      : S.lastSync ? "synced " + ago(S.lastSync) : "";
    $("#sync").hidden = false;
  }

  function closingDetails(rows) {
    return '<h2>Closing lines and prices</h2><p class="note">Save the same book’s last pregame quote. Price comparisons require an unchanged line. These observations do not change a wager or settle it.</p><div class="card scroll"><table><thead><tr><th>Pick</th><th>Original</th><th>Closing line</th><th>Closing odds</th><th>Observed (local time)</th><th></th></tr></thead><tbody>'+rows.slice().sort(function(a,b){return String(b.event_date).localeCompare(String(a.event_date));}).slice(0,100).map(function(r){
      var c=D.closing(S.settings,r.id)||{},localTime=c.observed_at?new Date(Date.parse(c.observed_at)-new Date(c.observed_at).getTimezoneOffset()*60000).toISOString().slice(0,16):'';
      return '<tr data-detail-id="'+esc(r.id)+'"><td>'+esc(r.selection)+'<br><small>'+esc(r.book||'Book unknown')+'</small></td><td>'+american(r.price)+(r.line!=null?' · '+esc(r.line):'')+'</td><td><input aria-label="Closing line" class="num" data-detail="line" type="number" step="0.5" value="'+esc(c.line??'')+'"></td><td><input aria-label="Closing odds" class="num" data-detail="price" type="number" step="1" value="'+esc(c.price??r.closing_price??'')+'"></td><td><input aria-label="Quote observed time" data-detail="observed" type="datetime-local" value="'+esc(localTime)+'"></td><td><button class="btn sm" data-act="save-close">Save quote</button></td></tr>';
    }).join('')+'</tbody></table></div>';
  }
  function hasAudit(){return S.features.indexOf('audit-v2')>=0;}
  function auditChanges(entry, reverse){
    var a=(reverse?entry.after:entry.before)||{},b=(reverse?entry.before:entry.after)||{};
    if(reverse&&!entry.before)b={deleted:true};
    var fields=entry.entity==='setting'?['value']:['selection','event','market','side','line','price','book','stake','status','pnl','closing_price','score','notes','deleted'];
    return fields.filter(function(k){return JSON.stringify(a[k]??null)!==JSON.stringify(b[k]??null);}).map(function(k){return esc(k)+': '+esc(a[k]??'—')+' → '+esc(b[k]??'—');}).join('<br>')||'Board details changed';
  }
  function historyBlock(){
    if(hasAudit())return '<h2>Ledger audit history</h2><p class="note">Every wager and bankroll change sent through the sheet connection is recorded from the server upgrade onward. Direct spreadsheet edits and earlier activity are not reconstructed. Undo requires the record to still match this revision.</p><button class="btn sm" data-act="refresh-audit">Refresh history</button>'+(S.auditError?'<p class="err">'+esc(S.auditError)+'</p>':'')+'<div class="card scroll">'+(S.audit.length?'<table><thead><tr><th>Time / writer</th><th>Record</th><th>Changes</th><th>Undo</th></tr></thead><tbody>'+S.audit.map(function(e){return '<tr><td>'+esc(e.at)+'<br>'+esc(e.device||e.app)+'</td><td>'+esc((e.after&&e.after.selection)||e.entity_id)+'<br>'+esc(e.action)+'</td><td>'+auditChanges(e,false)+'</td><td>'+(e.state!=='applied'?'Unconfirmed write':e.can_undo?'<button class="btn sm" data-act="review-undo" data-audit="'+esc(e.id)+'">Review undo</button>':'Newer revision exists')+'</td></tr>';}).join('')+'</tbody></table>':'<p class="note">No server changes recorded yet.</p>')+'</div>'+(S.auditCursor?'<button class="btn sm" data-act="more-audit">Older changes</button>':'');
    var entries=D.history(S.settings).slice(0,100);return '<h2>Observed ledger changes</h2><p class="note">Your sheet still uses the earlier server. <a href="server-upgrade.html" target="_blank" rel="noopener">Enable full history and safe undo</a>. These observations may miss changes between reads. Latest 100 shown.</p><div class="card scroll">'+(entries.length?'<table><thead><tr><th>Observed</th><th>Pick</th><th>Writer</th><th>Changes</th></tr></thead><tbody>'+entries.map(function(e){return '<tr><td>'+esc(e.observed_at)+'</td><td>'+esc(e.selection||e.id)+'</td><td>'+esc(e.device)+'</td><td>'+e.changes.map(function(c){return esc(c.field)+': '+esc(c.from??'—')+' → '+esc(c.to??'—');}).join('<br>')+'</td></tr>';}).join('')+'</tbody></table>':'<p class="note">No changes observed yet.</p>')+'</div>';
  }
  function loadAudit(more){
    if(!hasAudit())return Promise.resolve();
    return BS.auditHistory(BS.loadConfig(),more?S.auditCursor:null).then(function(res){S.audit=more?S.audit.concat(res.entries||[]):res.entries||[];S.auditCursor=res.next_before;S.auditError='';}).catch(function(err){S.auditError=BS.friendlyError(err);});
  }
  function reviewUndo(id){
    var entry=S.audit.find(function(e){return e.id===id;});if(!entry||!entry.can_undo)return;
    var dialog=document.createElement('dialog');dialog.style.cssText='max-width:560px;width:calc(100% - 32px);background:#101c27;color:#e7f0f7;border:1px solid #54717d;border-radius:14px;padding:24px';
    dialog.innerHTML='<h2>Review undo</h2><p>'+esc((entry.after&&entry.after.selection)||entry.entity_id)+'</p><p>'+auditChanges(entry,true)+'</p><p class="note">Restores this record’s previous saved values and recalculates the shared bankroll. This is recorded as a new change. Any newer edit will block this undo.</p><button class="btn" data-cancel>Cancel</button> <button class="btn primary" data-confirm>Confirm undo</button><p data-error role="status"></p>';
    document.body.appendChild(dialog);dialog.addEventListener('close',function(){dialog.remove();});dialog.querySelector('[data-cancel]').onclick=function(){dialog.close();};
    dialog.querySelector('[data-confirm]').onclick=async function(){
      if(S.busy)return;S.busy=true;this.disabled=true;
      try{var res=await BS.undoChange(BS.loadConfig(),entry.id,entry.after.updated_at);S.rows=(res.rows||[]).map(BS.canonical);S.settings=res.settings||S.settings;S.lastSync=new Date().toISOString();await loadAudit(false);S.busy=false;dialog.close();render();}
      catch(err){S.busy=false;dialog.querySelector('[data-error]').textContent=BS.friendlyError(err);await loadAudit(false);render();}
    };dialog.showModal();
  }
  function logSettings(before,after){var patch={};if(hasAudit())return patch;D.observe(before,after,new Date().toISOString(),BS.deviceName()).forEach(function(e){Object.assign(patch,D.historySetting(e,crypto.randomUUID()));});return patch;}

  function renderGate() {
    $("#sync").hidden = true;
    main.innerHTML = '<div class="gate card">' +
      '<h2 style="margin-top:0">Connect to your sheet</h2>' +
      '<p class="note">The same web app URL and token your connected boards use. They ' +
      'are kept in this browser and go nowhere else.</p>' +
      '<label>Web app URL<input id="url" type="url" spellcheck="false" ' +
        'placeholder="https://script.google.com/macros/s/…/exec"></label>' +
      '<label>Token<input id="token" type="text" spellcheck="false" autocomplete="off"></label>' +
      '<label>Name this device<input id="device" type="text" value="' + esc(BS.deviceName()) + '"></label>' +
      '<button class="btn primary" id="connect">Connect</button>' +
      (S.error ? '<div class="err">' + esc(S.error) + '</div>' : "") +
      '</div>';
  }

  /* ------------------------------------------------------------ the wire -- */

  function pull() {
    var cfg = BS.loadConfig();
    if (!cfg || S.busy) return Promise.resolve();
    S.busy = true; S.error = "";
    if (S.loaded) $("#stamp").textContent = "syncing…";
    return BS.pullAll(cfg, "").then(async function (res) {
      S.features=res.features||[];
      var nextRows=(res.rows || []).map(BS.canonical),observations=baselineReady?logSettings(S.rows,nextRows):{};
      baselineReady=true;S.rows=nextRows;S.settings=res.settings||{};S.sourceUrl=cfg.url;
      if(Object.keys(observations).length){
        return BS.pushRows(cfg,[],observations).then(function(saved){S.settings=saved.settings||S.settings;S.loaded=true;S.lastSync=new Date().toISOString();S.busy=false;render();});
      }
      S.loaded = true;
      S.lastSync = new Date().toISOString();
      await loadAudit(false);
      S.busy = false;
      render();
    }).catch(function (err) {
      S.busy = false;
      S.error = BS.friendlyError(err);
      render();
    });
  }

  /* Write one row back exactly as it came down, with only the fields this page
     changed replaced. native_json rides along untouched. */
  function push(row) {
    var cfg = BS.loadConfig();
    if (!cfg || S.busy) return Promise.resolve();
    S.busy = true;
    row.device=BS.deviceName();
    row.base_rev = row.updated_at;
    var previous=S.rows.slice();
    return BS.pushRows(cfg, [row]).then(async function (res) {
      S.features=res.features||S.features;
      var observations=logSettings(previous,BS.mergeRows(previous,res.rows||[]));
      if(Object.keys(observations).length){try{var logged=await BS.pushRows(cfg,[],observations);res.settings=logged.settings||res.settings;}catch(_){S.error="Wager saved; change history could not be recorded.";}}
      S.rows = BS.mergeRows(S.rows, res.rows || []);
      S.settings = res.settings || S.settings;
      S.lastSync = new Date().toISOString();
      if(res.conflicts&&res.conflicts.length)S.error='Another device changed this wager. The latest saved version is shown; review it before editing again.';
      await loadAudit(false);
      S.busy = false;
      render();
    }).catch(function (err) {
      S.busy = false;
      S.error = BS.friendlyError(err);
      render();
    });
  }

  function find(id) {
    for (var i = 0; i < S.rows.length; i++) if (S.rows[i].id === id) return S.rows[i];
    return null;
  }

  function csv(rows) {
    var cols = ["event_date", "app", "event", "market", "selection", "line", "price",
                "book", "stake", "tier", "status", "pnl", "closing_price", "placed_at"];
    var q = function (v) {
      var s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    return [cols.join(",")].concat(rows.map(function (r) {
      return cols.map(function (c) { return q(c === "pnl" && r.status !== "Pending" ? BS.impliedPnl(r) : r[c]); }).join(",");
    })).join("\n");
  }

  /* ---------------------------------------------------------------- events */

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-act],#connect,#csv,#saveStarting,#forget,#sync");
    if (!t) return;
    if(S.busy && (t.hasAttribute("data-act") || t.id==="saveStarting" || t.id==="sync"))return;

    if (t.id === "sync") return pull();

    if (t.id === "connect") {
      var url = $("#url").value.trim(), token = $("#token").value.trim();
      if (!/^https:\/\/script\.google\.com\/macros\/s\/[^/]+\/exec/.test(url)) {
        S.error = "That does not look like a web app URL. It ends in /exec."; return render();
      }
      if (!token) { S.error = "Paste the token setup() printed."; return render(); }
      BS.saveConfig({ url: url, token: token, device: $("#device").value.trim() });
      S.error = "";
      return pull();
    }

    if (t.id === "forget") {
      if (!window.confirm("Disconnect this device? Your bets stay on the sheet.")) return;
      BS.saveConfig(null);
      S.loaded = false; S.rows = []; S.settings={}; S.features=[];S.audit=[];baselineReady=false;
      return render();
    }

    if (t.id === "saveStarting") {
      var v = Number($("#starting").value);
      if (!isFinite(v) || v < 0) { S.error = "Enter a number."; return render(); }
      var cfg = BS.loadConfig();
      S.busy = true;
      /* No client timestamp: the sheet stamps it. See setStartingBankroll in
         betsync.js for why sending one loses edits on a slow clock. */
      return BS.pushRows(cfg, [], { starting_bankroll: v }).then(async function (res) {
        S.settings = res.settings || S.settings;
        await loadAudit(false);
        S.busy = false; render();
      }).catch(function (err) { S.busy = false; S.error = BS.friendlyError(err); render(); });
    }

    if (t.id === "csv") {
      var blob = new Blob([csv(live())], { type: "text/csv" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "ledger-hq.csv";
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
      return;
    }

    var act = t.getAttribute("data-act");
    if(act==='review-undo')return reviewUndo(t.dataset.audit);
    if(act==='refresh-audit'||act==='more-audit'){S.busy=true;return loadAudit(act==='more-audit').then(function(){S.busy=false;render();});}

    if (act === "board") {
      var app = t.getAttribute("data-app");
      if (S.boards[app]) delete S.boards[app]; else S.boards[app] = true;
      return render();
    }
    if (act === "status") { S.status = t.getAttribute("data-status"); return render(); }

    if (act === "save-close") {
      if(S.busy)return;
      var tr=t.closest('[data-detail-id]'),row=find(tr.dataset.detailId),line=tr.querySelector('[data-detail="line"]').value,price=tr.querySelector('[data-detail="price"]').value,observed=tr.querySelector('[data-detail="observed"]').value;
      if(price===''||Math.abs(Number(price))<100||!Number.isFinite(Number(price))||!observed||!Number.isFinite(Date.parse(observed))||Date.parse(observed)>Date.now()+60000){S.error='Enter valid American odds and the past time you observed that quote.';return render();}
      var value={line:line===''?null:Number(line),price:Number(price),observed_at:new Date(observed).toISOString(),book:row.book||'',device:BS.deviceName()},patch={};
      patch[D.closeKey(row.id)]=JSON.stringify(value);
      var old=D.closing(S.settings,row.id);if(!hasAudit())Object.assign(patch,D.historySetting({id:row.id,selection:row.selection,device:BS.deviceName(),observed_at:new Date().toISOString(),changes:[{field:'closing quote',from:old?JSON.stringify(old):null,to:JSON.stringify(value)}]},crypto.randomUUID()));
      S.busy=true;return BS.pushRows(BS.loadConfig(),[],patch).then(async function(res){S.settings=res.settings||S.settings;await loadAudit(false);S.busy=false;S.error='';render();}).catch(function(err){S.busy=false;S.error=BS.friendlyError(err);render();});
    }
    if (act === "settle") {
      var card = t.closest(".bet");
      var row = find(card.getAttribute("data-id"));
      if (!row) return;
      var next = Object.assign({}, row);
      next.status = t.getAttribute("data-status");
      var stakeInput = card.querySelector('[data-act="stake"]');
      var closeInput = card.querySelector('[data-act="closing"]');
      if (stakeInput && stakeInput.value !== "") next.stake = Number(stakeInput.value);
      next.closing_price = closeInput && closeInput.value !== "" ? Number(closeInput.value) : null;
      /* Leave pnl for the boards and the bankroll to derive from stake and
         price - one formula, one answer. */
      next.pnl = null;
      return push(next);
    }
  });

  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t.getAttribute && t.getAttribute("data-act") === "days") {
      S.days = Number(t.value) || 0;
      return render();
    }
    if (t.getAttribute && (t.getAttribute("data-act") === "stake" || t.getAttribute("data-act") === "closing")) {
      var card = t.closest(".bet");
      var row = find(card.getAttribute("data-id"));
      if (!row) return;
      var next = Object.assign({}, row);
      if (t.getAttribute("data-act") === "stake") next.stake = Number(t.value) || 0;
      else next.closing_price = t.value === "" ? null : Number(t.value);
      return push(next);
    }
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && BS.loadConfig() && S.loaded) pull();
  });
  // An embedded page remains visible to the browser even when its hub panel
  // is hidden. Refresh on returning to Ledger without disturbing an edit.
  window.addEventListener("message", function (event) {
    if (event.source !== window.parent || event.origin !== window.location.origin ||
        !event.data || event.data.type !== "kevbotbets:activate") return;
    var editing = document.activeElement &&
      /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (!editing && !S.busy && BS.loadConfig()) pull();
  });
  setInterval(function () {
    if (document.visibilityState === "visible" && BS.loadConfig()) pull();
  }, 5 * 60 * 1000);
  setInterval(function () {
    var stamp = $("#stamp");
    if (stamp && !S.busy && S.lastSync) stamp.textContent = "synced " + ago(S.lastSync);
  }, 30000);

  /* The chart is drawn at one of two proportions, so a rotation or a resize
     across that threshold has to redraw rather than stretch. */
  var wasNarrow = window.innerWidth <= 560, resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      var now = window.innerWidth <= 560;
      if (now !== wasNarrow) { wasNarrow = now; render(); }
    }, 180);
  });

  render();
  if (BS.loadConfig()) pull();
})();
