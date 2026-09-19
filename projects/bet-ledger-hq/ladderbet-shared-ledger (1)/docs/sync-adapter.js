/*
 * sync-adapter.js — the Ladder's half of the shared ledger.
 *
 * A ladder is the awkward one: it is a chain, not a list. Rung N's stake is
 * rung N-1's return, so stake, rung, return and running net are all recomputed
 * from scratch every time anything changes. None of those derived numbers are
 * sent to the sheet as part of the bet's identity — only the facts a person
 * actually entered (the pick, the price, an edited stake, the result) travel.
 * Each device recomputes the chain itself, and because reflow is deterministic
 * they all land on the same numbers.
 */
(function () {
  "use strict";
  if (!window.BetSync) return;
  var BS = window.BetSync;
  var APP = "ladder";
  var L = window.LadderLedger;
  if (!L) return;

  var TO_STATUS = { win: "Win", loss: "Loss", push: "Push", void: "Void" };
  var TO_RESULT = { Win: "win", Loss: "loss", Push: "push", Void: "void" };

  /* The facts, without anything reflow works out for itself. */
  var KEEP = ["id", "added", "settled_at", "event_id", "league", "matchup",
              "start_utc", "pick", "side", "decimal", "american",
              "stake", "stake_edited", "result", "score"];

  function facts(e) {
    var out = {};
    for (var i = 0; i < KEEP.length; i++) {
      if (e[KEEP[i]] !== undefined) out[KEEP[i]] = e[KEEP[i]];
    }
    return out;
  }

  function toCanonical(e) {
    return {
      id: APP + ":" + e.id,
      app: APP,
      sport: String(e.league || "mixed").toUpperCase(),
      placed_at: e.added,
      event_date: String(e.added || "").slice(0, 10),
      event: e.matchup,
      market: "ML",
      selection: e.pick,
      side: e.side,
      line: null,
      price: e.american,
      book: "",
      stake: e.stake,
      tier: "LADDER R" + (e.rung == null ? "?" : e.rung),
      edge: null,
      model_prob: null,
      status: TO_STATUS[e.result] || "Pending",
      pnl: e.profit_loss == null ? null : e.profit_loss,
      closing_price: null,
      score: e.score,
      notes: "",
      native: facts(e)
    };
  }

  function fromCanonical(row) {
    var e = row.native ? JSON.parse(JSON.stringify(row.native)) : {
      id: String(row.id).split(":").slice(1).join(":"),
      added: row.placed_at, league: String(row.sport || "").toLowerCase(),
      matchup: row.event, pick: row.selection, side: row.side,
      american: row.price, event_id: "", start_utc: ""
    };
    if (e.decimal == null && row.price != null) {
      var a = Number(row.price);
      e.decimal = a > 0 ? 1 + a / 100 : 1 + 100 / Math.abs(a);
    }
    e.result = TO_RESULT[row.status] || null;
    if (row.score) e.score = row.score;
    return e;
  }

  function fingerprint(entries) {
    return JSON.stringify((entries || []).map(facts)
      .sort(function (a, b) { return String(a.id).localeCompare(String(b.id)); }));
  }

  BS.register({
    app: APP,
    sport: "MIXED",
    storageKey: L.STORAGE_KEY,

    readLocal: function () {
      return (L.get() || []).map(toCanonical);
    },

    writeLocal: function (rows) {
      var next = rows.map(fromCanonical);
      /* A ladder is read in the order it was played. */
      next.sort(function (a, b) { return String(a.added || "").localeCompare(String(b.added || "")); });
      if (fingerprint(L.get()) === fingerprint(next)) return;
      L.set(next);
    }

    /* No bankroll hook: the ladder stakes itself off the previous rung's
     * return, not off a bankroll. Its results still count toward the shared
     * one, which is what the other four boards size against. */
  });

  BS.start();
})();
