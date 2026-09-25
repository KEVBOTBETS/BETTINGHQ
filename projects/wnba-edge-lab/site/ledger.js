/* My Ledger — only wagers the user explicitly confirms. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.WNBALedger = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STORAGE_KEY = "wnbaedge.ledger.v2";
  const SCHEMA = 2;

  const decimal = american => {
    const price = Number(american);
    if (!isFinite(price) || price === 0) return 1;
    return 1 + (price > 0 ? price / 100 : 100 / Math.abs(price));
  };

  const keyOf = row => `${row.game_id}|${row.market}|${row.side}`;

  function entryFrom(row, stakeOverride) {
    const stake = stakeOverride == null ? Number(row.stake || 0) : Number(stakeOverride);
    return {
      id: keyOf(row), candidate_id: row.candidate_id, game_id: row.game_id,
      date: row.date, tipoff: row.tipoff, matchup: row.matchup,
      market: row.market, side: row.side, pick: row.pick,
      line: row.line == null ? null : Number(row.line), price: Number(row.price),
      book: row.book || null, model_prob: Number(row.model_prob),
      market_fair_prob: row.market_fair_prob == null ? null : Number(row.market_fair_prob),
      breakeven: Number(row.breakeven), edge: Number(row.edge), tier: row.tier,
      stake: Math.round(Math.max(0, stake) * 100) / 100,
      added_at: new Date().toISOString(), result: null, profit: null, final_score: null,
    };
  }

  function settle(entry, game) {
    if (!game || !game.completed || !game.away || !game.home ||
        game.away.score == null || game.home.score == null) return null;
    const away = Number(game.away.score), home = Number(game.home.score);
    let result = null;
    if (entry.market === "ML") {
      const mine = entry.side === "away" ? away : home;
      const theirs = entry.side === "away" ? home : away;
      result = mine > theirs ? "Win" : mine < theirs ? "Loss" : "Push";
    } else if (entry.market === "ATS") {
      const mine = entry.side === "away" ? away : home;
      const theirs = entry.side === "away" ? home : away;
      const adjusted = mine + Number(entry.line || 0);
      result = adjusted > theirs ? "Win" : adjusted < theirs ? "Loss" : "Push";
    } else if (entry.market === "TOTAL") {
      const total = away + home, line = Number(entry.line);
      if (!isFinite(line)) return null;
      result = total === line ? "Push" : ((total > line) === (entry.side === "over") ? "Win" : "Loss");
    }
    if (!result) return null;
    const stake = Number(entry.stake || 0);
    const profit = result === "Win" ? stake * (decimal(entry.price) - 1)
                 : result === "Loss" ? -stake : 0;
    return {result, profit: Math.round(profit * 100) / 100,
            final_score: `${away}-${home}`, settled_at: new Date().toISOString()};
  }

  function settleAll(entries, games) {
    const byId = new Map((games || []).map(game => [String(game.game_id), game]));
    let changed = 0;
    const rows = entries.map(entry => {
      if (entry.result) return entry;
      const result = settle(entry, byId.get(String(entry.game_id)));
      if (!result) return entry;
      changed++;
      return Object.assign({}, entry, result);
    });
    return {entries: rows, changed};
  }

  function summarise(entries, startingBankroll) {
    const settled = entries.filter(row => row.result);
    const profit = settled.reduce((sum, row) => sum + Number(row.profit || 0), 0);
    const risked = settled.filter(row => row.result !== "Push")
      .reduce((sum, row) => sum + Number(row.stake || 0), 0);
    const wins = settled.filter(row => row.result === "Win").length;
    const losses = settled.filter(row => row.result === "Loss").length;
    const pushes = settled.filter(row => row.result === "Push").length;
    return {
      bankroll: Math.round((Number(startingBankroll || 0) + profit) * 100) / 100,
      profit: Math.round(profit * 100) / 100, risked: Math.round(risked * 100) / 100,
      roi: risked ? profit / risked : null, wins, losses, pushes,
      pending: entries.filter(row => !row.result).length, settled: settled.length,
      at_risk: Math.round(entries.filter(row => !row.result)
        .reduce((sum, row) => sum + Number(row.stake || 0), 0) * 100) / 100,
    };
  }

  function load() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      const rows = Array.isArray(parsed) ? parsed : (parsed && parsed.entries) || [];
      return rows.filter(row => row && row.game_id && row.market && row.side);
    } catch (_) { return []; }
  }

  function save(entries) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({schema: SCHEMA,
        saved_at: new Date().toISOString(), entries}));
      return true;
    } catch (_) { return false; }
  }

  function merge(existing, incoming) {
    const byKey = new Map(existing.map(row => [keyOf(row), row]));
    let added = 0;
    incoming.forEach(row => {
      if (!row || !row.game_id || !row.market || !row.side) return;
      const key = keyOf(row);
      if (!byKey.has(key)) { byKey.set(key, row); added++; }
    });
    return {entries: [...byKey.values()], added};
  }

  const CSV_COLS = ["date","matchup","market","side","pick","line","price","book",
    "stake","tier","edge","model_prob","result","profit","final_score","added_at"];
  function toCSV(entries) {
    const quote = value => {
      const text = value == null ? "" : String(value);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    return [CSV_COLS.join(",")].concat(entries.map(row => CSV_COLS.map(key => quote(row[key])).join(","))).join("\n");
  }

  return {STORAGE_KEY, SCHEMA, decimal, keyOf, entryFrom, settle, settleAll,
          summarise, load, save, merge, toCSV, CSV_COLS};
});
