/*
 * Shared-ledger round trip for the Ladder.
 *
 * A ladder is the awkward one to sync: it is a chain, not a list. Rung N's stake
 * is rung N-1's return, so stake, rung, return and running net are all worked
 * out again from scratch on every draw. Sending those derived numbers to the
 * sheet as part of a bet's identity would make every device look permanently
 * out of step with every other. These tests hold the adapter to sending only the
 * facts a person actually entered, and to leaving the chain alone when nothing
 * has really changed.
 *
 *   node tests/test_sync.mjs
 */
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const web = path.join(root, "docs");

let passed = 0;
const cases = [];
const test = (name, fn) => cases.push([name, fn]);

/* The ladger's own ledger lives inside the page's closure and hands out a small
   door (window.LadderLedger). That door is what the adapter uses, so that is
   what this stands in for. */
function ladderInPage(initial) {
  const store = new Map();
  const localStorage = {
    getItem: k => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: k => store.delete(k)
  };
  const noop = () => {};
  const win = {
    localStorage, console, Promise, JSON, Date, Math, Object, Array,
    String, Number, isFinite, isNaN, Error,
    setInterval: noop, clearInterval: noop, setTimeout, clearTimeout,
    addEventListener: noop,
    navigator: { userAgent: "node" },
    document: { visibilityState: "visible", addEventListener: noop, readyState: "complete" },
    Storage: { prototype: { setItem: localStorage.setItem } }
  };
  win.window = win; win.self = win; win.globalThis = win;
  const ctx = vm.createContext(win);

  let entries = initial ? initial.slice() : [];
  let writes = 0;
  ctx.window.LadderLedger = {
    STORAGE_KEY: "ladder.ledger.v1",
    get: () => entries,
    set: rows => { writes++; entries = rows; }
  };

  const run = f => vm.runInContext(fs.readFileSync(f, "utf8"), ctx, { filename: f });
  run(path.join(web, "betsync.js"));
  let adapter = null;
  const register = ctx.window.BetSync.register;
  ctx.window.BetSync.register = a => { adapter = a; return register(a); };
  ctx.window.BetSync.start = () => {};
  run(path.join(web, "sync-adapter.js"));
  assert.ok(adapter, "sync-adapter.js registered nothing");

  return { ctx, adapter, get: () => entries, writes: () => writes };
}

const rung = (over = {}) => ({
  id: "b1757800000000_0", added: "2026-09-13T15:00:00.000Z",
  event_id: "401872925", league: "nfl", matchup: "Tampa Bay @ Cincinnati",
  start_utc: "2026-09-13T17:00Z", pick: "Cincinnati Bengals", side: "home",
  decimal: 1.4878, american: -205, stake: 27.66, stake_edited: false, result: null,
  // everything below is reflow's, recomputed on every draw
  rung: 4, to_return: 41.15, returned: null, profit_loss: 0,
  running_net: 22.66, running_profit_loss: 0, cashed_out: null,
  ...over
});

/* --------------------------------------------------------------------------- */

test("only the facts travel; nothing reflow works out does", () => {
  const b = ladderInPage([rung()]);
  const row = b.adapter.readLocal()[0];
  assert.equal(row.app, "ladder");
  assert.equal(row.id, "ladder:b1757800000000_0");
  assert.equal(row.price, -205);
  assert.equal(row.sport, "NFL");

  const sent = Object.keys(row.native);
  for (const derived of ["rung", "to_return", "returned", "profit_loss",
                         "running_net", "running_profit_loss", "cashed_out"]) {
    assert.ok(!sent.includes(derived),
      derived + " is reflow's to compute; sending it makes every device disagree");
  }
  assert.ok(sent.includes("decimal"), "the price actually taken must travel");
  assert.ok(sent.includes("stake_edited"), "whether a stake was typed by hand must travel");
});

test("an unchanged chain is left alone, so a sync never disturbs a draw", () => {
  const b = ladderInPage([rung()]);
  b.adapter.writeLocal(b.adapter.readLocal());
  assert.equal(b.writes(), 0);
});

test("a result settled on another device lands on the rung", () => {
  const b = ladderInPage([rung()]);
  const row = b.adapter.readLocal()[0];
  b.adapter.writeLocal([{ ...row, status: "Win", score: "TB 17 @ CIN 24" }]);
  assert.equal(b.writes(), 1);
  assert.equal(b.get()[0].result, "win");
  assert.equal(b.get()[0].score, "TB 17 @ CIN 24");
  assert.equal(b.get()[0].decimal, 1.4878, "the price taken must survive settling");
});

test("rungs come back in the order the ladder was played", () => {
  const b = ladderInPage([]);
  b.adapter.writeLocal([
    { id: "ladder:c", app: "ladder", price: -150, status: "Pending",
      native: { id: "c", added: "2026-09-05T00:00:00.000Z", pick: "C", decimal: 1.66 } },
    { id: "ladder:a", app: "ladder", price: -150, status: "Pending",
      native: { id: "a", added: "2026-09-02T00:00:00.000Z", pick: "A", decimal: 1.66 } },
    { id: "ladder:b", app: "ladder", price: -150, status: "Pending",
      native: { id: "b", added: "2026-09-03T00:00:00.000Z", pick: "B", decimal: 1.66 } }
  ]);
  assert.deepEqual(b.get().map(e => e.id), ["a", "b", "c"],
    "a ladder read out of order is not a ladder");
});

test("a rung arriving with no decimal price gets one from the American odds", () => {
  const b = ladderInPage([]);
  b.adapter.writeLocal([{ id: "ladder:x", app: "ladder", price: -200, status: "Pending",
                          sport: "MLB", event: "A @ B", selection: "B", native: null }]);
  assert.equal(b.get()[0].decimal, 1.5);
});

test("the generated page still hands the adapter its door", () => {
  const source = fs.readFileSync(path.join(root, "ladder", "webledger.py"), "utf8");
  assert.ok(/window\.LadderLedger\s*=/.test(source),
    "webledger.py must export LadderLedger or a synced bet never reaches the chain");
  for (const fn of ["STORAGE_KEY", "get", "set"])
    assert.ok(source.includes(fn + ":"), "LadderLedger." + fn + " is missing");

  const built = fs.readFileSync(path.join(web, "index.html"), "utf8");
  assert.ok(built.includes("window.LadderLedger"), "the built page is behind the generator");
  assert.ok(built.includes("betsync.js"), "the built page does not load the sync layer");
});

for (const [name, fn] of cases) {
  try { fn(); passed++; }
  catch (err) { console.error("FAIL  " + name + "\n      " + err.message); process.exitCode = 1; }
}
console.log(passed + "/" + cases.length + " passed");
