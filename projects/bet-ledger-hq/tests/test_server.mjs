/*
 * Two devices, one sheet, the real code on both sides.
 *
 * The unit tests check the sync layer's reasoning in isolation. This one checks
 * that both halves agree: the actual Apps Script from apps-script/Code.gs runs
 * against an in-memory spreadsheet, two independent browsers run the actual
 * betsync.js, and the only thing faked is the wire between them.
 *
 * The story it tells is the one that matters: a bet added on the phone reaches
 * the laptop, a result graded on the laptop reaches the phone, a stale phone
 * cannot un-settle it, a cleared browser cannot wipe the sheet, and the bankroll
 * every board sizes against is the same number on both.
 *
 *   node tests/test_server.mjs
 */
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import {randomUUID} from "node:crypto";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");

let passed = 0;
const cases = [];
const test = (name, fn) => cases.push([name, fn]);

/* ------------------------------------------------------- the spreadsheet -- */

function fakeSheet(name) {
  const cells = [];                                  // 1-indexed rows of arrays
  const get = (r, c) => (cells[r - 1] || [])[c - 1];
  return {
    name,
    getLastRow: () => cells.length,
    getLastColumn: () => cells.reduce((m, r) => Math.max(m, r.length), 0),
    setFrozenRows: () => {},
    getRange(row, col, rows, cols) {
      return {
        getValues() {
          const out = [];
          for (let r = row; r < row + rows; r++) {
            const line = [];
            for (let c = col; c < col + cols; c++) line.push(get(r, c) ?? "");
            out.push(line);
          }
          return out;
        },
        setValues(values) {
          values.forEach((line, i) => {
            const r = row + i;
            while (cells.length < r) cells.push([]);
            line.forEach((v, j) => { cells[r - 1][col + j - 1] = v; });
          });
          return this;
        },
        setFontWeight() { return this; }
      };
    },
    _dump: () => cells.map(r => r.slice())
  };
}

function fakeSpreadsheet() {
  const sheets = new Map();
  return {
    getSheetByName: n => sheets.get(n) || null,
    insertSheet(n) { const s = fakeSheet(n); sheets.set(n, s); return s; },
    _sheets: sheets
  };
}

/** Load the real Code.gs against an in-memory spreadsheet. */
function server() {
  const ss = fakeSpreadsheet();
  const props = new Map();
  const ctx = vm.createContext({
    SpreadsheetApp: { getActiveSpreadsheet: () => ss },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: k => (props.has(k) ? props.get(k) : null),
        setProperty: (k, v) => props.set(k, v)
      })
    },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
    ContentService: {
      MimeType: { JSON: "json", JAVASCRIPT: "js" },
      createTextOutput: t => ({ _t: t, setMimeType() { return this; }, getContent: () => t })
    },
    Logger: { log: () => {} },
    Utilities: {
      getUuid: randomUUID,
      formatDate: (d) => d.toISOString().slice(0, 10)
    },
    JSON, Date, String, Number, Math, Object, Array, isNaN
  });
  vm.runInContext(fs.readFileSync(path.join(root, "apps-script", "Code.gs"), "utf8"), ctx);
  const token = vm.runInContext("setup()", ctx);

  return {
    token,
    ss,
    sheet: () => ss.getSheetByName("bets"),
    settings: () => ss.getSheetByName("settings"),
    /** Answer a request exactly as the deployed web app would. */
    post(payload) {
      ctx.__payload = JSON.stringify(payload);
      const out = vm.runInContext(
        "doPost({ postData: { contents: __payload }, parameter: {} })", ctx);
      return JSON.parse(out.getContent());
    }
  };
}

/* ----------------------------------------------------------- the devices -- */

/* A board, reduced to what the sync layer actually requires of one: somewhere to
 * keep rows, and a way to hand them over. The five real boards each wrap their
 * own ledger module in exactly this shape - their versions of these tests live
 * in their own repositories.
 */
function device(srv, name, { url = "https://script.google.com/macros/s/x/exec", app = "mlb-edge" } = {}) {
  const store = new Map();
  const localStorage = {
    getItem: k => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: k => store.delete(k)
  };
  const noop = () => {};
  const win = {
    localStorage, console,
    setInterval: noop, clearInterval: noop, setTimeout, clearTimeout,
    addEventListener: noop,
    navigator: { userAgent: name },
    document: { visibilityState: "visible", addEventListener: noop, readyState: "complete" },
    Storage: { prototype: { setItem: localStorage.setItem } },
    Promise, JSON, Date, Math, Object, Array, String, Number, isFinite, isNaN, Error,
    fetch: async (u, opts) => {
      const res = srv.post(JSON.parse(opts.body));
      return { ok: true, status: 200, text: async () => JSON.stringify(res) };
    }
  };
  win.window = win; win.self = win; win.globalThis = win;
  const ctx = vm.createContext(win);
  vm.runInContext(fs.readFileSync(path.join(root, "betsync.js"), "utf8"), ctx,
                  { filename: "betsync.js" });

  const BS = ctx.window.BetSync;
  const KEY = "board.ledger";
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; } };

  BS.start = () => {};
  BS.register({
    app,
    storageKey: KEY,
    readLocal: () => read(),
    writeLocal: rows => localStorage.setItem(KEY, JSON.stringify(rows)),
    applyBankroll: bank => { ctx.__bankroll = bank; }
  });
  BS.saveConfig({ url, token: srv.token, device: name });

  return {
    name, ctx, BS,
    sync: opts => BS.sync(opts),
    entries: () => read(),
    put: rows => localStorage.setItem(KEY, JSON.stringify(rows)),
    bankroll: () => ctx.__bankroll
  };
}

const entry = (over = {}) => ({
  id: "mlb-edge:777|ML|Yankees", app: "mlb-edge", sport: "MLB",
  placed_at: "2026-09-13T15:00:00.000Z", event_date: "2026-09-13",
  event: "New York Mets @ New York Yankees", market: "ML",
  selection: "Yankees ML", side: "New York Yankees",
  line: null, price: -186, book: "DraftKings", stake: 12.5,
  tier: "GOOD", edge: 0.031, model_prob: 0.641,
  status: "Pending", pnl: null, closing_price: null, score: "", notes: "",
  native: { gamePk: 777, label: "Yankees ML", tier: "GOOD" },
  ...over
});

/* ------------------------------------------------------------------ tests - */

test("setup() prints a token and lays out the three tabs", async () => {
  const srv = server();
  assert.equal(typeof srv.token, "string");
  assert.equal(srv.token.length, 28);
  assert.ok(srv.sheet(), "bets tab");
  assert.ok(srv.settings(), "settings tab");
  assert.equal(srv.post({ token: srv.token, action: "ping" }).ok, true);
});

test("a wrong token is refused and writes nothing", async () => {
  const srv = server();
  const res = srv.post({ token: "wrong", action: "push", rows: [{ id: "x", app: "mlb-edge" }] });
  assert.equal(res.ok, false);
  assert.equal(res.error, "bad_token");
  assert.equal(srv.sheet().getLastRow(), 1, "header only");
});

test("a bet placed on the phone reaches the laptop", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  phone.put([entry()]);
  await phone.sync();
  assert.equal(srv.sheet().getLastRow(), 2, "one bet on the sheet");

  assert.equal(laptop.entries().length, 0);
  await laptop.sync();
  assert.equal(laptop.entries().length, 1);
  assert.equal(laptop.entries()[0].selection, "Yankees ML");
  assert.equal(laptop.entries()[0].stake, 12.5);
  assert.equal(laptop.entries()[0].status, "Pending");
});

test("a result graded on the laptop reaches the phone", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  phone.put([entry()]);
  await phone.sync();
  await laptop.sync();

  laptop.put([{ ...laptop.entries()[0], status: "Win", pnl: 6.72, score: "NYM 3 @ NYY 5" }]);
  await laptop.sync();

  await phone.sync();
  const seen = phone.entries()[0];
  assert.equal(seen.status, "Win");
  assert.equal(seen.pnl, 6.72);
  assert.equal(seen.score, "NYM 3 @ NYY 5");
});

test("a stake edited on one device is not clobbered by the other", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  phone.put([entry()]);
  await phone.sync();
  await laptop.sync();

  laptop.put([{ ...laptop.entries()[0], stake: 40 }]);
  await laptop.sync();
  await phone.sync();
  assert.equal(phone.entries()[0].stake, 40);

  // The phone, now current, syncs again and must not push the old figure back.
  await phone.sync();
  await laptop.sync();
  assert.equal(laptop.entries()[0].stake, 40);
});

test("a phone that was offline cannot un-settle a bet the sheet has graded", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  phone.put([entry()]);
  await phone.sync();
  await laptop.sync();

  // The laptop grades it while the phone is away.
  laptop.put([{ ...laptop.entries()[0], status: "Win", pnl: 6.72 }]);
  await laptop.sync();

  // The phone wakes up still holding the pending copy and edits the stake.
  phone.put([{ ...phone.entries()[0], stake: 30 }]);
  await phone.sync();

  const row = srv.sheet()._dump()[1];
  const statusCol = 17;                                    // 'status' in COLUMNS
  assert.equal(row[statusCol - 1], "Win", "the result must survive");
  assert.equal(laptop.entries()[0].status, "Win");
});

test("a bet added while a sync is in flight is not erased by its answer", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");

  /* This is how the first attempt at importing a season of MLB bets vanished.
     The page had a sync in flight that had already read an empty ledger; the
     bets were written while it was still out; its answer came back knowing
     nothing about them and wrote its emptiness over the top. The bets existed
     nowhere afterwards - not on the device, not on the sheet. */
  let injected = false;
  const realFetch = phone.ctx.window.fetch;
  phone.ctx.window.fetch = async (u, opts) => {
    const res = await realFetch(u, opts);
    if (!injected) {           // a bet lands mid-flight, exactly once
      injected = true;
      phone.put([entry({ id: "mlb-edge:new", selection: "Added mid-sync" })]);
    }
    return res;
  };

  await phone.sync();
  assert.equal(phone.entries().length, 1, "the bet must survive the answer");
  assert.equal(phone.entries()[0].selection, "Added mid-sync");

  phone.ctx.window.fetch = realFetch;
  await phone.sync();
  const onSheet = srv.post({ token: srv.token, action: "pull", since: "" });
  assert.equal(onSheet.rows.length, 1, "and must reach the sheet on the next sync");
  assert.equal(onSheet.rows[0].id, "mlb-edge:new");
});

test("a mid-sync bet is not double-counted once it has been sent", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  let injected = false;
  const realFetch = phone.ctx.window.fetch;
  phone.ctx.window.fetch = async (u, opts) => {
    const res = await realFetch(u, opts);
    if (!injected) { injected = true; phone.put([entry({ id: "mlb-edge:new" })]); }
    return res;
  };
  await phone.sync();
  phone.ctx.window.fetch = realFetch;
  await phone.sync();
  await phone.sync();
  await phone.sync();
  assert.equal(phone.entries().length, 1);
  assert.equal(srv.sheet().getLastRow(), 2, "one header row, one bet");
});

test("a bet removed on one device is removed on the other", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  phone.put([entry({ id: "mlb-edge:1" }), entry({ id: "mlb-edge:2" }), entry({ id: "mlb-edge:3" })]);
  await phone.sync();
  await laptop.sync();
  assert.equal(laptop.entries().length, 3);

  phone.put([entry({ id: "mlb-edge:1" }), entry({ id: "mlb-edge:3" })]);
  await phone.sync();
  await laptop.sync();
  assert.equal(laptop.entries().length, 2);
  assert.deepEqual(laptop.entries().map(e => e.id).sort(), ["mlb-edge:1", "mlb-edge:3"]);
});

test("a cleared browser does not wipe the sheet", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  phone.put(Array.from({ length: 12 }, (_, i) => entry({ id: "mlb-edge:" + (100 + i) })));
  await phone.sync();
  await laptop.sync();
  assert.equal(laptop.entries().length, 12);

  // Somebody taps Clear on the phone.
  phone.put([]);
  await phone.sync();

  assert.equal(phone.BS.state().status, "blocked", "the sync should hold back");
  await laptop.sync();
  assert.equal(laptop.entries().length, 12, "the laptop keeps its bets");

  // Confirmed on purpose, it goes through.
  await phone.sync({ confirmDeletes: true });
  await laptop.sync();
  assert.equal(laptop.entries().length, 0);
});

test("syncing twice with nothing new sends nothing and changes nothing", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  phone.put([entry()]);
  await phone.sync();
  const first = JSON.stringify(srv.sheet()._dump());
  await phone.sync();
  await phone.sync();
  assert.equal(JSON.stringify(srv.sheet()._dump()), first, "the sheet must be untouched");
  assert.equal(phone.entries().length, 1);
});

test("a bankroll saved right after setup still takes, whatever the clocks say", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");

  /* This one failed about one run in eight before it was fixed. The sheet had
     just stamped its default bankroll; the client sent its own timestamp with
     the new figure; the two landed in the same millisecond, the server read that
     as "you are working from an older revision", and the number the person typed
     was dropped without a word. A device whose clock sits a few seconds behind
     Google's would have lost every save, not one in eight. */
  await phone.BS.setStartingBankroll(400);

  const after = srv.post({ token: srv.token, action: "pull", since: "" });
  assert.equal(after.settings.starting_bankroll, 400);
  assert.equal(phone.BS.state().bankroll.starting, 400);
});

test("the shared bankroll is one number on every device", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  const laptop = device(srv, "Mac");

  await phone.BS.setStartingBankroll(500);
  phone.put([
    entry({ id: "mlb-edge:1", status: "Win", pnl: 40, stake: 50 }),
    entry({ id: "mlb-edge:2", status: "Loss", pnl: -25, stake: 25 }),
    entry({ id: "mlb-edge:3", stake: 30 })
  ]);
  await phone.sync();
  await laptop.sync();

  const a = phone.BS.state().bankroll;
  const b = laptop.BS.state().bankroll;
  assert.equal(a.current, 515);
  assert.equal(b.current, 515);
  assert.equal(b.exposure, 30);
  assert.equal(b.available, 485);

  // And it is handed to the board, which is what sizes its stakes with it.
  assert.equal(laptop.bankroll().current, 515);
});

test("bets from other boards count toward the bankroll but stay out of this ledger", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  await phone.BS.setStartingBankroll(250);

  // A row from the props board, as its own adapter would have sent it.
  srv.post({
    token: srv.token, action: "push", device: "iPad", app: "props",
    rows: [{ id: "props:abc", app: "props", sport: "NFL", event: "A @ B",
             market: "Receiving yards", selection: "Someone Over 72.5",
             price: -115, stake: 6, status: "Loss", pnl: -6 }],
    since: ""
  });

  phone.put([entry({ status: "Win", pnl: 10, stake: 20 })]);
  await phone.sync();

  assert.equal(phone.entries().length, 1, "only this board's bets land here");
  assert.equal(phone.BS.state().bankroll.current, 254);
  const byApp = Object.fromEntries(phone.BS.state().bankroll.by_app.map(a => [a.app, a.pnl]));
  assert.deepEqual(byApp, { "mlb-edge": 10, props: -6 });
});

test("the sheet stays readable: one row per bet, columns in order", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  phone.put([entry()]);
  await phone.sync();

  const [header, row] = srv.sheet()._dump();
  assert.equal(header[0], "id");
  assert.equal(header[1], "app");
  assert.equal(header.at(-1), "native_json");
  assert.equal(row[0], "mlb-edge:777|ML|Yankees");
  assert.equal(row[1], "mlb-edge");
  assert.equal(row[header.indexOf("event")], "New York Mets @ New York Yankees");
  assert.equal(row[header.indexOf("price")], -186);
  assert.ok(String(row[header.indexOf("native_json")]).startsWith("{"));
});

test("a third device joining later gets the whole history", async () => {
  const srv = server();
  const phone = device(srv, "iPhone");
  phone.put([entry({ id: "mlb-edge:1" }),
             entry({ id: "mlb-edge:2", status: "Loss", pnl: -12.5 })]);
  await phone.sync();

  const newTablet = device(srv, "iPad");
  await newTablet.sync();
  assert.equal(newTablet.entries().length, 2);
  assert.equal(newTablet.entries().find(e => e.id === "mlb-edge:2").status, "Loss");
});

/* ------------------------------------------------------------------- HQ --- */

/* The HQ page holds no ledger. It reads rows, edits the flat columns, and writes
   them back - and the thing that must not break is the board's own record
   travelling through untouched. */

test("settling from HQ reaches the board, with its own record intact", async () => {
  const srv = server();
  const laptop = device(srv, "Mac");
  laptop.put([entry()]);
  await laptop.sync();

  // HQ reads the sheet the way the page does.
  const BS = laptop.BS;
  const pulled = srv.post({ token: srv.token, action: "pull", since: "" });
  const rows = pulled.rows.map(BS.canonical);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].native.gamePk, 777, "native came down parsed");

  // Somebody taps Win on their phone, on the HQ page.
  const edited = Object.assign({}, rows[0], {
    status: "Win", closing_price: -210, pnl: null, base_rev: rows[0].updated_at
  });
  srv.post({ token: srv.token, action: "push", device: "iPhone", app: "hq",
             rows: [Object.assign({}, edited, { native_json: JSON.stringify(edited.native) })],
             since: "" });

  // The board picks it up and reconciles its own entry.
  await laptop.sync();
  const e = laptop.entries()[0];
  assert.equal(e.status, "Win");
  assert.equal(e.native.gamePk, 777, "the board's record survived the trip through HQ");
  assert.equal(e.native.label, "Yankees ML");
  assert.equal(e.tier, "GOOD");
  assert.equal(e.stake, 12.5);
});

test("HQ cannot blank a board's record by writing a row back", async () => {
  const srv = server();
  const laptop = device(srv, "Mac");
  laptop.put([entry()]);
  await laptop.sync();

  const header = srv.sheet()._dump()[0];
  const nativeCol = header.indexOf("native_json");
  const before = srv.sheet()._dump()[1][nativeCol];
  assert.ok(String(before).length > 20);

  const pulled = srv.post({ token: srv.token, action: "pull", since: "" });
  const row = pulled.rows[0];
  srv.post({ token: srv.token, action: "push", device: "iPhone", app: "hq",
             rows: [Object.assign({}, row, { stake: 33 })], since: "" });

  const after = srv.sheet()._dump()[1][nativeCol];
  assert.equal(after, before, "native_json must round-trip byte for byte");
  await laptop.sync();
  assert.equal(laptop.entries()[0].stake, 33);
  assert.equal(laptop.entries()[0].native.gamePk, 777);
});

test("the bankroll HQ shows is the one the boards size against", async () => {
  const srv = server();
  const laptop = device(srv, "Mac");
  const BS = laptop.BS;

  await BS.setStartingBankroll(400);
  laptop.put([
    entry({ id: "mlb-edge:1", status: "Win", pnl: 20, stake: 25 }),
    entry({ id: "mlb-edge:2", status: "Loss", pnl: -25, stake: 25 }),
    entry({ id: "mlb-edge:3", stake: 18 })
  ]);
  await laptop.sync();

  const pulled = srv.post({ token: srv.token, action: "pull", since: "" });
  const hq = BS.bankroll(pulled.rows.map(BS.canonical), pulled.settings.starting_bankroll);
  const board = laptop.bankroll();
  assert.equal(hq.current, board.current);
  assert.equal(hq.exposure, board.exposure);
  assert.equal(hq.available, board.available);
  assert.equal(hq.current, 395);
});

test("closing quotes and independent history entries round-trip with the deployed schema",async()=>{
  const srv=server(),a=device(srv,"Mac");a.put([entry()]);await a.sync();
  const before=srv.post({token:srv.token,action:"pull",since:""});
  for(const [key,value] of [["kevbot_close_v1_bet",JSON.stringify({line:3,price:-110})],["kevbot_history_v1_one","first device"],["kevbot_history_v1_two","second device"]])srv.post({token:srv.token,action:"push",rows:[],settings:{[key]:value},since:""});
  const after=srv.post({token:srv.token,action:"pull",since:""});
  assert.equal(after.settings.kevbot_history_v1_one,"first device");assert.equal(after.settings.kevbot_history_v1_two,"second device");assert.equal(JSON.parse(after.settings.kevbot_close_v1_bet).line,3);assert.deepEqual(after.rows,before.rows);
});
test('audit records additions, edits, deletions and preserves full payloads for undo',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,device:'Phone',app:'hq',...p});
  const original=entry({native:{data:'x'.repeat(41000)}});
  let res=call({action:'push',rows:[original]});
  let history=call({action:'audit'});assert.equal(history.entries.length,1);assert.equal(history.entries[0].action,'add');
  assert.equal(history.entries[0].can_undo,true);assert.equal(history.entries[0].after.native_json,undefined);
  res=call({action:'push',rows:[{...res.rows[0],status:'Win',pnl:6.72}]});
  history=call({action:'audit'});const edit=history.entries[0];
  assert.equal(edit.before.status,'Pending');assert.equal(edit.after.status,'Win');assert.equal(history.entries[1].can_undo,false);
  let undone=call({action:'undo',audit_id:edit.id,expected_rev:edit.after.updated_at});
  assert.equal(undone.ok,true);assert.equal(undone.rows[0].status,'Pending');assert.deepEqual(JSON.parse(undone.rows[0].native_json),original.native);
  assert.equal(call({action:'undo',audit_id:edit.id,expected_rev:edit.after.updated_at}).error,'undo_conflict');
  const deletion=call({action:'push',rows:[{id:original.id,app:original.app,deleted:true,base_rev:undone.rows[0].updated_at}]});
  assert.equal(deletion.rows[0].selection,original.selection);assert.equal(deletion.rows[0].deleted,true);
  history=call({action:'audit'});const deleted=history.entries[0];assert.equal(deleted.action,'delete');
  undone=call({action:'undo',audit_id:deleted.id,expected_rev:deleted.after.updated_at});
  assert.equal(undone.rows[0].deleted,false);assert.equal(undone.rows[0].selection,original.selection);
  assert.ok(srv.ss.getSheetByName('audit_payloads')._dump().slice(1).every(r=>r[3].startsWith('j:')&&r[3].length<=30002));
});

test('undo rejects newer edits and stale devices cannot reverse a completed undo',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,device:'Phone',app:'hq',...p});
  let res=call({action:'push',rows:[entry()]});
  res=call({action:'push',rows:[{...res.rows[0],status:'Win',pnl:6.72}]});
  const settled=res.rows[0],audit=call({action:'audit'}).entries[0];
  res=call({action:'push',rows:[{...settled,stake:50}]});
  assert.equal(call({action:'undo',audit_id:audit.id,expected_rev:audit.after.updated_at}).error,'undo_conflict');
  const latest=call({action:'audit'}).entries[0];
  const undone=call({action:'undo',audit_id:latest.id,expected_rev:latest.after.updated_at});
  assert.equal(undone.rows[0].stake,12.5);
  const stale=call({action:'push',rows:[{...settled,stake:90}]});
  assert.equal(stale.skipped,1);assert.equal(stale.rows[0].stake,12.5);
  const unversioned=call({action:'push',rows:[entry({stake:77,status:'Win'})]});
  assert.equal(unversioned.skipped,1);assert.equal(unversioned.rows[0].stake,12.5);
});

test('undo a settlement recalculates the same bankroll on two devices',async()=>{
  const srv=server(),phone=device(srv,'Phone'),laptop=device(srv,'Laptop');
  phone.put([entry()]);await phone.sync();await laptop.sync();
  laptop.put([{...laptop.entries()[0],status:'Win',pnl:6.72}]);await laptop.sync();await phone.sync();
  assert.equal(phone.bankroll().current,256.72);
  const history=await phone.BS.auditHistory(),change=history.entries[0];
  await phone.BS.undoChange(null,change.id,change.after.updated_at);
  await phone.sync();await laptop.sync();
  assert.equal(phone.entries()[0].status,'Pending');assert.equal(laptop.entries()[0].status,'Pending');
  assert.equal(phone.bankroll().current,250);assert.equal(laptop.bankroll().current,250);
});

test('bankroll settings normalize numbers and undo safely; backups do not create money edits',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,...p});
  call({action:'settings',settings:{starting_bankroll:'500'}});
  const change=call({action:'audit'}).entries[0];assert.equal(change.after.value,500);assert.equal(change.can_undo,true);
  const res=call({action:'undo',audit_id:change.id,expected_rev:change.after.updated_at});assert.equal(res.settings.starting_bankroll,250);
  const n=call({action:'audit'}).entries.length;
  call({action:'push',rows:[],settings:{kevbot_ticket_v1_one:'snapshot',kevbot_history_v1_old:'observation'}});
  assert.equal(call({action:'audit'}).entries.length,n);
  assert.throws(()=>call({action:'settings',settings:{starting_bankroll:-1}}),/invalid_bankroll/);
});

test('audit pagination includes all revisions; auth protects history and undo',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,...p});
  call({action:'push',rows:Array.from({length:30},(_,i)=>entry({id:'test:'+i}))});
  const first=call({action:'audit',limit:25}),last=call({action:'audit',before:first.next_before,limit:25});
  assert.equal(first.entries.length,25);assert.equal(last.entries.length,5);assert.equal(last.next_before,null);
  assert.equal(new Set([...first.entries,...last.entries].map(e=>e.id)).size,30);
  assert.equal(srv.post({token:'wrong',action:'audit'}).error,'bad_token');
  assert.equal(srv.post({token:'wrong',action:'undo',audit_id:first.entries[0].id}).error,'bad_token');
});

test('failed journal preparation prevents mutation; failed receipt is visible but cannot be undone',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,...p});call({action:'audit'});
  const audit=srv.ss.getSheetByName('audit'),range=audit.getRange;
  audit.getRange=function(...args){const r=range(...args),set=r.setValues;r.setValues=function(values){if(values[0][2]==='prepared')throw Error('simulated journal failure');return set.call(r,values);};return r;};
  assert.throws(()=>call({action:'push',rows:[entry()]}),/simulated/);assert.equal(srv.sheet().getLastRow(),1);
  audit.getRange=function(...args){const r=range(...args),set=r.setValues;r.setValues=function(values){if(values[0][2]==='applied')throw Error('simulated receipt failure');return set.call(r,values);};return r;};
  assert.throws(()=>call({action:'push',rows:[entry()]}),/simulated/);assert.equal(srv.sheet().getLastRow(),2);
  const receipt=call({action:'audit'}).entries[0];assert.equal(receipt.state,'prepared');assert.equal(receipt.can_undo,false);
  assert.equal(call({action:'undo',audit_id:receipt.id,expected_rev:receipt.after.updated_at}).error,'undo_conflict');
});

test('direct spreadsheet changes invalidate undo even without a changed timestamp',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,...p});call({action:'push',rows:[entry()]});
  const receipt=call({action:'audit'}).entries[0],header=srv.sheet()._dump()[0];
  srv.sheet().getRange(2,header.indexOf('stake')+1,1,1).setValues([[99]]);
  assert.equal(call({action:'undo',audit_id:receipt.id,expected_rev:receipt.after.updated_at}).error,'undo_conflict');
});

test('missing-only recovery never overwrites a concurrent wager or tombstone',async()=>{
  const srv=server(),call=p=>srv.post({token:srv.token,...p});
  const source=entry(),fence='restore-missing-only-v1';
  let saved=call({action:'push',rows:[{...source,base_rev:fence}]});assert.equal(saved.applied,1);
  let existing=call({action:'pull'}).rows.find(r=>r.id===source.id);
  saved=call({action:'push',rows:[{...source,stake:99,base_rev:fence}]});assert.equal(saved.applied,0);assert.ok(saved.conflicts.includes(source.id));
  call({action:'push',rows:[{...existing,deleted:true,base_rev:existing.updated_at}]});
  saved=call({action:'push',rows:[{...source,deleted:false,base_rev:fence}]});assert.equal(saved.applied,0);
  assert.equal(call({action:'pull'}).rows.find(r=>r.id===source.id).deleted,true);
});

for (const [name, fn] of cases) {
  try {
    await fn();
    passed++;
  } catch (err) {
    console.error("FAIL  " + name + "\n      " + (err && err.stack || err));
    process.exitCode = 1;
  }
}
console.log(passed + "/" + cases.length + " passed");
