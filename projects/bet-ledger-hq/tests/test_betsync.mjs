/*
 * Tests for the sync layer's decision-making — the parts that decide what gets
 * sent, what wins a conflict, and what the shared bankroll comes to. The
 * network and the browser are deliberately not involved: everything here is a
 * pure function, and these are the answers that cost money when they are wrong.
 *
 *   node tests/test_betsync.mjs
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const BS = require("../betsync.js");

let passed = 0;
const cases = [];
const test = (name, fn) => cases.push([name, fn]);

const bet = (over = {}) => ({
  id: "mlb-edge:777|ML|Yankees", app: "mlb-edge", sport: "MLB",
  event: "Mets @ Yankees", market: "ML", selection: "Yankees",
  price: -150, stake: 20, status: "Pending", updated_at: "2026-09-13T10:00:00.000Z",
  ...over
});

/* ------------------------------------------------------------ canonical -- */

test("canonical fills every field, so equal bets hash equal", () => {
  const sparse = BS.canonical({ id: "a", app: "x" });
  const verbose = BS.canonical({ id: "a", app: "x", line: "", notes: undefined, edge: null });
  assert.equal(BS.contentHash(sparse), BS.contentHash(verbose));
});

test("stable stringify ignores the order keys were added in", () => {
  assert.equal(BS.stable({ b: 1, a: 2 }), BS.stable({ a: 2, b: 1 }));
  assert.equal(BS.stable({ x: { q: 1, p: 2 } }), BS.stable({ x: { p: 2, q: 1 } }));
});

test("numbers survive a round trip through the sheet's strings", () => {
  const fromSheet = BS.canonical({ id: "a", app: "x", price: "-150", stake: "20", line: "" });
  assert.equal(fromSheet.price, -150);
  assert.equal(fromSheet.stake, 20);
  assert.equal(fromSheet.line, null);
});

test("a row read back from the sheet hashes the same as the one sent", () => {
  const local = BS.canonical(bet({ native: { gamePk: 777, stake: 20 } }));
  const roundTripped = BS.canonical({
    ...local, price: "-150", stake: "20", deleted: "false",
    native: undefined, native_json: JSON.stringify(local.native)
  });
  assert.equal(BS.contentHash(local), BS.contentHash(roundTripped));
});

test("timestamp and device are not part of what a bet means", () => {
  const a = BS.canonical(bet());
  const b = BS.canonical(bet({ updated_at: "2026-09-13T23:00:00.000Z", device: "iPhone" }));
  assert.equal(BS.contentHash(a), BS.contentHash(b));
});

/* ---------------------------------------------------------------- merge -- */

test("the newer write wins", () => {
  const older = bet({ stake: 20, updated_at: "2026-09-13T10:00:00.000Z" });
  const newerRow = bet({ stake: 35, updated_at: "2026-09-13T11:00:00.000Z" });
  assert.equal(BS.mergeRows([older], [newerRow])[0].stake, 35);
  assert.equal(BS.mergeRows([newerRow], [older])[0].stake, 35);
});

test("on an exact tie the settled copy wins, never the pending one", () => {
  const t = "2026-09-13T10:00:00.000Z";
  const pending = bet({ status: "Pending", updated_at: t });
  const won = bet({ status: "Win", pnl: 13.33, updated_at: t });
  assert.equal(BS.mergeRows([pending], [won])[0].status, "Win");
  assert.equal(BS.mergeRows([won], [pending])[0].status, "Win");
});

test("on a full tie the sheet's answer wins, and both devices agree on it", () => {
  const t = "2026-09-13T10:00:00.000Z";
  const cached = bet({ stake: 12.5, updated_at: t });
  const fromSheet = bet({ stake: 33, updated_at: t });
  // Two devices, each folding what the sheet just said into what it had cached.
  assert.equal(BS.mergeRows([cached], [fromSheet])[0].stake, 33);
  assert.equal(BS.mergeRows([fromSheet], [cached])[0].stake, 12.5);
  // Which is only safe because a settled row still out-ranks a pending one.
  const settled = bet({ status: "Win", pnl: 6, updated_at: t });
  const pending = bet({ status: "Pending", stake: 99, updated_at: t });
  assert.equal(BS.mergeRows([settled], [pending])[0].status, "Win");
});

test("merging is order-independent and keeps one row per id", () => {
  const rows = [
    bet({ id: "a", updated_at: "2026-09-13T10:00:00.000Z" }),
    bet({ id: "b", updated_at: "2026-09-13T11:00:00.000Z" }),
    bet({ id: "a", stake: 99, updated_at: "2026-09-13T12:00:00.000Z" })
  ];
  const forwards = BS.mergeRows([], rows);
  const backwards = BS.mergeRows([], rows.slice().reverse());
  assert.equal(forwards.length, 2);
  assert.deepEqual(forwards.map(r => r.id), backwards.map(r => r.id));
  assert.equal(forwards.find(r => r.id === "a").stake, 99);
});

test("a row with no id is dropped rather than merged into a blank one", () => {
  assert.equal(BS.mergeRows([], [bet({ id: "" }), bet()]).length, 1);
});

/* ----------------------------------------------------------------- diff -- */

test("a bet the shadow has never seen is dirty", () => {
  const { dirty, tombstones } = BS.diff([bet()], {}, { device: "Mac" });
  assert.equal(dirty.length, 1);
  assert.equal(dirty[0].device, "Mac");
  assert.equal(tombstones.length, 0);
});

test("an unchanged bet is not sent again", () => {
  const row = BS.canonical(bet());
  const shadow = BS.shadowOf([row]);
  assert.equal(BS.diff([row], shadow, {}).dirty.length, 0);
});

test("an edited stake is sent, carrying the revision it was edited from", () => {
  const row = BS.canonical(bet());
  const shadow = BS.shadowOf([row]);
  const edited = BS.canonical(bet({ stake: 40 }));
  const { dirty } = BS.diff([edited], shadow, {});
  assert.equal(dirty.length, 1);
  assert.equal(dirty[0].base_rev, row.updated_at);
});

test("a bet that vanished locally becomes a tombstone, not a silent drop", () => {
  const shadow = BS.shadowOf([BS.canonical(bet())]);
  const { dirty, tombstones } = BS.diff([], shadow, { device: "Mac" });
  assert.equal(dirty.length, 0);
  assert.equal(tombstones.length, 1);
  assert.equal(tombstones[0].deleted, true);
  assert.equal(tombstones[0].app, "mlb-edge");
});

/* -------------------------------------------------- mass-delete guard ---- */

test("deleting a couple of bets goes through", () => {
  assert.equal(BS.massDeleteGuard(new Array(3), 20), false);
});

test("a ledger emptying itself in one step is held back", () => {
  assert.equal(BS.massDeleteGuard(new Array(20), 20), true);
});

test("a large but partial clear-out is held back too", () => {
  assert.equal(BS.massDeleteGuard(new Array(11), 20), true);
  assert.equal(BS.massDeleteGuard(new Array(6), 20), false);
});

/* ------------------------------------------------------------ bankroll -- */

test("bankroll is the starting figure plus every settled result anywhere", () => {
  const b = BS.bankroll([
    bet({ id: "a", app: "mlb-edge", status: "Win", stake: 20, pnl: 13.33 }),
    bet({ id: "b", app: "nfl-lab", status: "Loss", stake: 25, pnl: -25 }),
    bet({ id: "c", app: "props", status: "Pending", stake: 10 })
  ], 250);
  assert.equal(b.current, 238.33);
  assert.equal(b.exposure, 10);
  assert.equal(b.available, 228.33);
  assert.equal(b.wins, 1);
  assert.equal(b.losses, 1);
  assert.equal(b.pending, 1);
});

test("P/L is worked out from the price when a board did not record it", () => {
  const b = BS.bankroll([bet({ status: "Win", price: 150, stake: 10, pnl: null })], 100);
  assert.equal(b.pnl, 15);
  assert.equal(b.current, 115);
});

test("pushes move the bankroll nowhere and stay out of the ROI denominator", () => {
  const b = BS.bankroll([
    bet({ id: "a", status: "Push", stake: 50 }),
    bet({ id: "b", status: "Win", price: 100, stake: 10, pnl: 10 })
  ], 100);
  assert.equal(b.pnl, 10);
  assert.equal(b.staked, 10);
  assert.equal(b.roi, 1);
  assert.equal(b.win_rate, 1);
});

test("a deleted bet counts for nothing", () => {
  const b = BS.bankroll([bet({ status: "Loss", stake: 50, pnl: -50, deleted: true })], 100);
  assert.equal(b.current, 100);
  assert.equal(b.by_app.length, 0);
});

test("exposure is pending stakes across every board at once", () => {
  const b = BS.bankroll([
    bet({ id: "a", app: "mlb-edge", status: "Pending", stake: 10 }),
    bet({ id: "b", app: "ladder", status: "Pending", stake: 27.66 }),
    bet({ id: "c", app: "props", status: "Pending", stake: 5 })
  ], 250);
  assert.equal(b.exposure, 42.66);
  assert.equal(b.available, 207.34);
  assert.equal(b.by_app.length, 3);
});

test("ROI is null rather than zero when nothing has settled", () => {
  const b = BS.bankroll([bet({ status: "Pending", stake: 10 })], 250);
  assert.equal(b.roi, null);
  assert.equal(b.win_rate, null);
});

/* ----------------------------------------------------------- odds math -- */

test("American prices convert the way a book pays", () => {
  assert.equal(BS.decimalOdds(100), 2);
  assert.equal(BS.decimalOdds(-200), 1.5);
  assert.equal(BS.decimalOdds(150), 2.5);
  assert.equal(BS.decimalOdds(0), 1);
});

/* ---------------------------------------------------- a two-device story - */

test("a bet added on a phone and settled on a laptop ends up settled on both", () => {
  const placed = BS.canonical(bet({ device: "iPhone", updated_at: "2026-09-13T18:00:00.000Z" }));

  // The laptop pulls it down and its shadow now matches the sheet.
  let laptop = BS.mergeRows([], [placed]);
  const laptopShadow = BS.shadowOf(laptop);
  assert.equal(BS.diff(laptop, laptopShadow, {}).dirty.length, 0);

  // The game ends; the laptop grades it and has something to send.
  const graded = BS.canonical({ ...placed, status: "Win", pnl: 13.33 });
  const { dirty } = BS.diff([graded], laptopShadow, { device: "Mac" });
  assert.equal(dirty.length, 1);
  assert.equal(dirty[0].base_rev, placed.updated_at);

  // The sheet stamps it, and the phone — still holding the pending copy — takes it.
  const stamped = BS.canonical({ ...dirty[0], updated_at: "2026-09-13T22:30:00.000Z" });
  const phone = BS.mergeRows([placed], [stamped]);
  assert.equal(phone.length, 1);
  assert.equal(phone[0].status, "Win");
  assert.equal(phone[0].pnl, 13.33);
});

test("a stale pending copy does not un-settle a graded bet on merge", () => {
  const graded = bet({ status: "Win", pnl: 13.33, updated_at: "2026-09-13T22:30:00.000Z" });
  const stale = bet({ status: "Pending", pnl: null, updated_at: "2026-09-13T18:00:00.000Z" });
  assert.equal(BS.mergeRows([graded], [stale])[0].status, "Win");
});

/* --------------------------------------------------------------- runner - */

for (const [name, fn] of cases) {
  try {
    fn();
    passed++;
  } catch (err) {
    console.error("FAIL  " + name + "\n      " + err.message);
    process.exitCode = 1;
  }
}
console.log(passed + "/" + cases.length + " passed");
