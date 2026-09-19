/**
 * Shared Bet Ledger - the cloud half.
 *
 * One Google Sheet behind all five boards (MLB Edge, NCAAF Edge Lab,
 * NFL Edge Lab, Props Edge, Ladder). Every board keeps working exactly as it
 * does now, against the browser's own storage; this script is the place those
 * copies meet, so a bet added on a phone shows up on a laptop and a bet settled
 * on the laptop shows up on the phone.
 *
 * HOW TO INSTALL  (there is a step-by-step version of this in SETUP-SYNC.md)
 *   1. Make a new Google Sheet. Name it "Bet Ledger".
 *   2. Extensions -> Apps Script. Delete whatever is in the editor.
 *   3. Paste this whole file in. Save.
 *   4. Pick "setup" in the function dropdown and press Run. Authorise it.
 *      The Execution log prints your secret token - copy it somewhere safe.
 *   5. Deploy -> New deployment -> type "Web app".
 *        Execute as:      Me
 *        Who has access:  Anyone
 *      Deploy, copy the /exec URL.
 *   6. Open each board, tap "Sync", paste the URL and the token, tap Connect.
 *
 * "Anyone" only means anyone who knows the URL can reach the script. The token
 * is what actually lets them in, so treat it like a password: it is typed into
 * each device once and is never committed to any of the public repositories.
 */

var SHEET_BETS = 'bets';
var SHEET_SETTINGS = 'settings';
var SHEET_DEVICES = 'devices';
var SCHEMA = 2;
var FEATURES = ['audit-v2', 'undo-v2'];
var AUDIT_COLUMNS = ['id', 'at', 'state', 'entity', 'entity_id', 'action', 'device', 'app', 'payload_row', 'before_parts', 'after_parts', 'undo_of'];

/* The flat columns exist so the sheet is readable and sortable by hand. The
 * app's own record travels verbatim in native_json, so a board can be restored
 * to the exact shape its own code expects without this script having to know
 * anything about run lines, ladders or player props. */
var COLUMNS = [
  'id', 'app', 'sport', 'placed_at', 'event_date', 'event', 'market',
  'selection', 'side', 'line', 'price', 'book', 'stake', 'tier', 'edge',
  'model_prob', 'status', 'pnl', 'closing_price', 'score', 'notes',
  'updated_at', 'device', 'deleted', 'native_json'
];

var NUMERIC = { line: 1, price: 1, stake: 1, edge: 1, model_prob: 1, pnl: 1, closing_price: 1 };

/* ------------------------------------------------------------------ setup */

function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureSheet_(ss, SHEET_BETS, COLUMNS);
  ensureSheet_(ss, SHEET_SETTINGS, ['key', 'value', 'updated_at']);
  ensureSheet_(ss, SHEET_DEVICES, ['device', 'app', 'last_seen', 'rows_pushed']);

  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('TOKEN');
  if (!token) {
    token = randomToken_();
    props.setProperty('TOKEN', token);
  }
  var settings = readSettings_(ss);
  if (settings.starting_bankroll == null) {
    writeSetting_(ss, 'starting_bankroll', 250);
    writeSetting_(ss, 'currency', 'CAD');
  }

  Logger.log('=================================================');
  Logger.log('  Your sync token:  ' + token);
  Logger.log('=================================================');
  Logger.log('Paste it, with the deployment URL, into the Sync panel on each board.');
  Logger.log('Starting bankroll is on the "settings" tab - edit it there.');
  return token;
}

/** Run this if you ever want a fresh token (every device must be reconnected). */
function resetToken() {
  var token = randomToken_();
  PropertiesService.getScriptProperties().setProperty('TOKEN', token);
  Logger.log('New token: ' + token);
  return token;
}

function randomToken_() {
  var chars = 'abcdefghijkmnpqrstuvwxyz23456789';
  var out = '';
  for (var i = 0; i < 28; i++) out += chars.charAt(Math.floor(Math.random() * chars.length));
  return out;
}

function ensureSheet_(ss, name, header) {
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  var width = Math.max(header.length, sh.getLastColumn());
  var current = sh.getLastRow() ? sh.getRange(1, 1, 1, width).getValues()[0] : [];
  var same = current.length >= header.length;
  for (var i = 0; same && i < header.length; i++) if (String(current[i]) !== header[i]) same = false;
  if (!same) {
    sh.getRange(1, 1, 1, header.length).setValues([header]);
    sh.getRange(1, 1, 1, header.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}

/* ------------------------------------------------------------- entrypoints */

function doGet(e) {
  if (e && e.parameter && ['push', 'settings', 'undo'].indexOf(e.parameter.action) >= 0) return reply_(e, {ok:false,error:'post_required'});
  return handle_(e, (e && e.parameter) || {});
}

function doPost(e) {
  var body = {};
  try {
    if (e && e.postData && e.postData.contents) body = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply_(e, { ok: false, error: 'bad_json' });
  }
  var params = {};
  var k;
  for (k in (e && e.parameter) || {}) params[k] = e.parameter[k];
  for (k in body) params[k] = body[k];
  return reply_(e, route_(params));
}

function handle_(e, params) {
  return reply_(e, route_(params));
}

function route_(params) {
  var expected = PropertiesService.getScriptProperties().getProperty('TOKEN');
  if (!expected) return { ok: false, error: 'not_set_up', hint: 'Run setup() in the Apps Script editor.' };
  if (!safeEqual_(String(params.token || ''), expected)) return { ok: false, error: 'bad_token' };

  var action = String(params.action || 'pull');
  if (action === 'ping') return { ok: true, now: nowIso_(), schema: SCHEMA, features: FEATURES };
  if (action === 'pull') return pull_(params);
  if (action === 'push') return push_(params);
  if (action === 'settings') return saveSettings_(params);
  if (action === 'audit') return auditHistory_(params);
  if (action === 'undo') return undo_(params);
  return { ok: false, error: 'unknown_action', action: action };
}

/* Length-checked, constant-ish comparison. The token is not a password hash and
 * this is one person's betting ledger, but there is no reason to leak length or
 * to short-circuit on the first wrong character. */
function safeEqual_(a, b) {
  if (a.length !== b.length) return false;
  var diff = 0;
  for (var i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/* ------------------------------------------------------------------- read */

function pull_(params) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var since = String(params.since || '');
  var all = readBets_(ss);
  var rows = [];
  for (var i = 0; i < all.length; i++) {
    if (!since || String(all[i].updated_at) > since) rows.push(all[i]);
  }
  return {
    ok: true,
    now: nowIso_(),
    schema: SCHEMA,
    features: FEATURES,
    full: !since,
    total: all.length,
    rows: rows,
    settings: readSettings_(ss)
  };
}

/* ------------------------------------------------------------------ write */

function push_(params) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(25000)) return { ok: false, error: 'busy' };
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ensureSheet_(ss, SHEET_BETS, COLUMNS);
    var incoming = params.rows || [];
    if (typeof incoming === 'string') incoming = JSON.parse(incoming);
    var now = nowIso_();

    var existing = readBets_(ss, true);       // includes _row
    var index = {};
    for (var i = 0; i < existing.length; i++) index[existing[i].id] = existing[i];

    var applied = 0, skipped = 0, conflicts = [];

    for (var j = 0; j < incoming.length; j++) {
      var row = normalise_(incoming[j]);
      if (!row.id || !row.app) { skipped++; continue; }
      var prev = index[row.id];

      // Tombstones preserve the original record, so a deletion can be audited and undone.
      if (prev && row.deleted) row = Object.assign({}, prev, { deleted: true, base_rev: row.base_rev, device: row.device || params.device });
      if (prev && sameRow_(prev, row)) { applied++; continue; }
      var fence = PropertiesService.getScriptProperties().getProperty('UNDO:' + row.id);
      if (prev && ((row.base_rev && String(row.base_rev) !== String(prev.updated_at)) || (fence && String(row.base_rev || '') < fence))) {
        skipped++; conflicts.push(row.id); continue;
      }

      if (prev) {
        /* A device that has been offline can arrive holding a stale copy of a
         * bet that has since been graded somewhere else. Losing a settlement
         * that way is the one failure that actually costs money to reconstruct,
         * so a Pending write never overwrites a result the sheet already has. */
        if (prev.status && prev.status !== 'Pending' && row.status === 'Pending' &&
            String(prev.updated_at) > String(row.base_rev || '')) {
          skipped++;
          continue;
        }
      }
      row.updated_at = nextRevision_();
      row.device = String(params.device || row.device || (prev && prev.device) || '');
      var rowNumber = prev ? prev._row : sh.getLastRow() + 1;
      var receipt = prepareAudit_(ss, 'bet', row.id, prev ? (row.deleted ? 'delete' : 'edit') : 'add', prev ? cleanRow_(prev) : null, cleanRow_(row), params, '');
      sh.getRange(rowNumber, 1, 1, COLUMNS.length).setValues([toValues_(row)]);
      commitAudit_(ss, receipt);
      row._row = rowNumber;
      index[row.id] = row;
      applied++;
    }

    if (params.settings) applySettings_(ss, params.settings, params);
    if (params.device) touchDevice_(ss, params.device, params.app, applied);

    /* A push doubles as a pull so a board only needs one round trip: everything
     * the sheet has changed since this device last looked comes back with it. */
    var since = String(params.since || '');
    var after = readBets_(ss);
    var back = [];
    for (var k = 0; k < after.length; k++) {
      if (!since || String(after[k].updated_at) > since) back.push(after[k]);
    }

    return {
      ok: true, now: nowIso_(), schema: SCHEMA, features: FEATURES, applied: applied, skipped: skipped, conflicts: conflicts,
      total: after.length, rows: back, settings: readSettings_(ss)
    };
  } finally {
    lock.releaseLock();
  }
}

/* ------------------------------------------------------------------- rows */

function readBets_(ss, withRowNumbers) {
  var sh = ensureSheet_(ss, SHEET_BETS, COLUMNS);
  var last = sh.getLastRow();
  if (last < 2) return [];
  var values = sh.getRange(2, 1, last - 1, COLUMNS.length).getValues();
  var out = [];
  for (var i = 0; i < values.length; i++) {
    var row = {};
    for (var c = 0; c < COLUMNS.length; c++) row[COLUMNS[c]] = values[i][c];
    if (!row.id) continue;
    row.id = String(row.id);
    row.deleted = row.deleted === true || String(row.deleted).toLowerCase() === 'true';
    row.updated_at = isoish_(row.updated_at);
    row.placed_at = isoish_(row.placed_at);
    row.event_date = dateish_(row.event_date);
    for (var n in NUMERIC) row[n] = row[n] === '' || row[n] == null ? null : Number(row[n]);
    if (withRowNumbers) row._row = i + 2;
    out.push(row);
  }
  return out;
}

function normalise_(raw) {
  var row = {};
  for (var i = 0; i < COLUMNS.length; i++) {
    var key = COLUMNS[i];
    var v = raw[key];
    if (key === 'native_json') {
      if (raw.native != null && v == null) v = JSON.stringify(raw.native);
      row[key] = v == null ? '' : String(v);
    } else if (NUMERIC[key]) {
      row[key] = (v === '' || v == null || isNaN(Number(v))) ? '' : Number(v);
    } else if (key === 'deleted') {
      row[key] = v === true || String(v).toLowerCase() === 'true';
    } else {
      row[key] = v == null ? '' : String(v);
    }
  }
  row.base_rev = raw.base_rev || raw.updated_at || '';
  if (!row.status) row.status = 'Pending';
  return row;
}

function toValues_(row) {
  var out = [];
  for (var i = 0; i < COLUMNS.length; i++) {
    var key = COLUMNS[i];
    var v = row[key];
    out.push(v == null ? '' : v);
  }
  return out;
}

/* --------------------------------------------------------------- settings */

function readSettings_(ss) {
  var sh = ensureSheet_(ss, SHEET_SETTINGS, ['key', 'value', 'updated_at']);
  var last = sh.getLastRow();
  var out = { starting_bankroll: null, currency: 'CAD' };
  if (last < 2) return out;
  var values = sh.getRange(2, 1, last - 1, 3).getValues();
  for (var i = 0; i < values.length; i++) {
    var k = String(values[i][0] || '').trim();
    if (!k) continue;
    var v = values[i][1];
    out[k] = (k === 'starting_bankroll') ? Number(v) || 0 : v;
    out[k + '_updated_at'] = isoish_(values[i][2]);
  }
  return out;
}

function writeSetting_(ss, key, value, revision) {
  var sh = ensureSheet_(ss, SHEET_SETTINGS, ['key', 'value', 'updated_at']);
  var last = sh.getLastRow();
  var now = revision || nextRevision_();
  if (last >= 2) {
    var keys = sh.getRange(2, 1, last - 1, 1).getValues();
    for (var i = 0; i < keys.length; i++) {
      if (String(keys[i][0]).trim() === key) {
        sh.getRange(i + 2, 2, 1, 2).setValues([[value, now]]);
        return;
      }
    }
  }
  sh.getRange(sh.getLastRow() + 1, 1, 1, 3).setValues([[key, value, now]]);
}

/* A setting only loses to the sheet's copy when the caller says, with a
 * <key>_updated_at, that it is working from an older revision. No client sends
 * one: a browser clock a few seconds behind Google's would make every save the
 * person typed look stale and be dropped in silence. Saving a bankroll is an
 * explicit instruction, so it wins and the sheet records when it landed. */
function applySettings_(ss, incoming, actor) {
  var current = readSettings_(ss);
  for (var key in incoming) {
    if (key.indexOf('_updated_at') >= 0) continue;
    if (key === 'starting_bankroll') {
      if (!isFinite(Number(incoming[key])) || Number(incoming[key]) < 0) throw Error('invalid_bankroll');
      incoming[key] = Number(incoming[key]);
    }
    var stamp = incoming[key + '_updated_at'] || '';
    var mine = current[key + '_updated_at'] || '';
    if (current[key] != null && mine && stamp && stamp <= mine) continue;
    if (current[key] === incoming[key]) continue;
    var revision = nextRevision_();
    // Ticket backups and the legacy observed-history log are not money edits.
    if (key.indexOf('kevbot_ticket_v1_') === 0 || key.indexOf('kevbot_history_v1_') === 0) {
      writeSetting_(ss, key, incoming[key], revision); continue;
    }
    var before = { exists: current[key] != null, value: current[key] == null ? null : current[key], updated_at: current[key + '_updated_at'] || '' };
    var after = { exists: true, value: incoming[key], updated_at: revision };
    var receipt = prepareAudit_(ss, 'setting', key, 'edit', before, after, actor || {}, '');
    writeSetting_(ss, key, incoming[key], revision);
    commitAudit_(ss, receipt);
  }
}

function saveSettings_(params) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(25000)) return { ok: false, error: 'busy' };
  try { var ss = SpreadsheetApp.getActiveSpreadsheet();applySettings_(ss, params.settings || {}, params);
    return { ok: true, now: nowIso_(), features: FEATURES, settings: readSettings_(ss) };
  } finally { lock.releaseLock(); }
}

/* Append-only journal. Before/after snapshots are chunked below the sheet cell
 * limit. A prepared receipt is written BEFORE a mutation, followed by an applied
 * receipt. Interrupted writes remain visible as unconfirmed and cannot be undone. */
function cleanRow_(row) {
  var out = {}; for (var i = 0; i < COLUMNS.length; i++) out[COLUMNS[i]] = row[COLUMNS[i]] == null ? '' : row[COLUMNS[i]];
  return out;
}
function sameRow_(a, b) {
  var x = normalise_(a), y = normalise_(b);
  for (var i = 0; i < COLUMNS.length; i++) {
    var k = COLUMNS[i]; if (k === 'updated_at' || k === 'device') continue;
    if (x[k] !== y[k]) return false;
  } return true;
}
function nextRevision_() {
  var props = PropertiesService.getScriptProperties();
  var value = Math.max(Date.now(), Number(props.getProperty('LAST_REVISION_MS') || 0) + 1);
  props.setProperty('LAST_REVISION_MS', String(value));return new Date(value).toISOString();
}
function auditSheet_(ss) { return ensureSheet_(ss, 'audit', AUDIT_COLUMNS); }
function auditPayloadSheet_(ss) { return ensureSheet_(ss, 'audit_payloads', ['id', 'side', 'part', 'json']); }
function appendReceipt_(ss, receipt) {
  var sh = auditSheet_(ss);sh.getRange(sh.getLastRow() + 1, 1, 1, AUDIT_COLUMNS.length).setValues([AUDIT_COLUMNS.map(function(k){return receipt[k] == null ? '' : receipt[k];})]);
}
function prepareAudit_(ss, entity, entityId, action, before, after, actor, undoOf) {
  var id = Utilities.getUuid(), rows = [], counts = {};
  ['before', 'after'].forEach(function(side){var body=JSON.stringify(side==='before'?before:after);counts[side]=0;for(var i=0;i<body.length;i+=30000){rows.push([id,side,counts[side]++,'j:'+body.slice(i,i+30000)]);}});
  var payload = auditPayloadSheet_(ss), start = payload.getLastRow() + 1;
  payload.getRange(start, 1, rows.length, 4).setValues(rows);
  var receipt = { id:id, at:nowIso_(), state:'prepared', entity:entity, entity_id:entityId, action:action, device:String(actor.device||''), app:String(actor.app||''), payload_row:start, before_parts:counts.before, after_parts:counts.after, undo_of:undoOf||'' };
  appendReceipt_(ss,receipt);return receipt;
}
function commitAudit_(ss, receipt) { appendReceipt_(ss,Object.assign({},receipt,{state:'applied',at:nowIso_()})); }
function auditRecords_(ss) {
  var sh=auditSheet_(ss),last=sh.getLastRow();if(last<2)return [];
  var values=sh.getRange(2,1,last-1,AUDIT_COLUMNS.length).getValues(),byId={};
  values.forEach(function(values,i){var r={};AUDIT_COLUMNS.forEach(function(k,j){r[k]=values[j];});r.cursor=i+2;byId[r.id]=r;});
  return Object.keys(byId).map(function(id){return byId[id];}).sort(function(a,b){return b.cursor-a.cursor;});
}
function auditSnapshot_(ss, receipt) {
  var count=Number(receipt.before_parts)+Number(receipt.after_parts),sh=auditPayloadSheet_(ss);
  var values=sh.getRange(Number(receipt.payload_row),1,count,4).getValues(),before='',after='';
  values.forEach(function(row){if(String(row[0])!==String(receipt.id)||String(row[3]).slice(0,2)!=='j:')throw Error('audit_payload_mismatch');if(row[1]==='before')before+=String(row[3]).slice(2);else if(row[1]==='after')after+=String(row[3]).slice(2);});
  return {before:JSON.parse(before),after:JSON.parse(after)};
}
function auditCurrent_(ss, receipt) {
  if(receipt.entity==='bet')return readBets_(ss,true).filter(function(r){return r.id===receipt.entity_id;})[0]||null;
  var settings=readSettings_(ss),k=receipt.entity_id;
  return {exists:settings[k]!=null,value:settings[k]==null?null:settings[k],updated_at:settings[k+'_updated_at']||''};
}
function undoMatches_(receipt, snapshot, current) {
  if(receipt.state!=='applied'||!current||!snapshot.after||String(current.updated_at)!==String(snapshot.after.updated_at))return false;
  return receipt.entity==='bet'?sameRow_(current,snapshot.after):JSON.stringify(current.value)===JSON.stringify(snapshot.after.value);
}
function auditHistory_(params) {
  var ss=SpreadsheetApp.getActiveSpreadsheet(),before=Number(params.before)||Infinity,limit=Math.max(1,Math.min(50,Number(params.limit)||25));
  var rows=auditRecords_(ss).filter(function(r){return r.cursor<before;}),page=rows.slice(0,limit);
  var bets={},settings=readSettings_(ss);readBets_(ss).forEach(function(r){bets[r.id]=r;});
  var entries=page.map(function(r){var k=r.entity_id,snapshots=auditSnapshot_(ss,r),current=r.entity==='bet'?bets[k]:{exists:settings[k]!=null,value:settings[k],updated_at:settings[k+'_updated_at']||''},copy=Object.assign({},r,snapshots,{can_undo:undoMatches_(r,snapshots,current)});
    // The journal retains native_json; list responses do not need the large board payload.
    if(copy.before&&receiptIsBet_(r))delete copy.before.native_json;if(copy.after&&receiptIsBet_(r))delete copy.after.native_json;return copy;});
  return {ok:true,schema:SCHEMA,features:FEATURES,entries:entries,next_before:rows.length>limit?page[page.length-1].cursor:null};
}
function receiptIsBet_(receipt){return receipt.entity==='bet';}
function undo_(params) {
  var lock=LockService.getScriptLock();if(!lock.tryLock(25000))return {ok:false,error:'busy'};
  try {
    var ss=SpreadsheetApp.getActiveSpreadsheet(),record=auditRecords_(ss).filter(function(r){return r.id===String(params.audit_id||'');})[0];
    if(!record)return {ok:false,error:'audit_not_found'};
    var snapshot=auditSnapshot_(ss,record),current=auditCurrent_(ss,record);
    if(!undoMatches_(record,snapshot,current)||String(params.expected_rev||'')!==String(snapshot.after.updated_at))return {ok:false,error:'undo_conflict'};
    var revision=nextRevision_(),next;
    if(record.entity==='bet'){
      next=normalise_(snapshot.before||Object.assign({},snapshot.after,{deleted:true}));next.updated_at=revision;next.device=String(params.device||'');
      var receipt=prepareAudit_(ss,'bet',record.entity_id,'undo',cleanRow_(current),cleanRow_(next),params,record.id);
      // Fence stale clients before restoring a row. A failed write can only make
      // old clients retry after a read; it cannot restore an outdated settlement.
      PropertiesService.getScriptProperties().setProperty('UNDO:'+record.entity_id,revision);
      ensureSheet_(ss,SHEET_BETS,COLUMNS).getRange(current._row,1,1,COLUMNS.length).setValues([toValues_(next)]);commitAudit_(ss,receipt);
    }else{
      var value=snapshot.before&&snapshot.before.exists?snapshot.before.value:'';next={exists:true,value:value,updated_at:revision};
      var settingReceipt=prepareAudit_(ss,'setting',record.entity_id,'undo',current,next,params,record.id);
      writeSetting_(ss,record.entity_id,value,revision);commitAudit_(ss,settingReceipt);
    }
    return {ok:true,now:nowIso_(),schema:SCHEMA,features:FEATURES,rows:readBets_(ss),settings:readSettings_(ss)};
  } finally {lock.releaseLock();}
}

function touchDevice_(ss, device, app, pushed) {
  var sh = ensureSheet_(ss, SHEET_DEVICES, ['device', 'app', 'last_seen', 'rows_pushed']);
  var last = sh.getLastRow();
  var now = nowIso_();
  var label = String(device) + ' / ' + String(app || '');
  if (last >= 2) {
    var rows = sh.getRange(2, 1, last - 1, 2).getValues();
    for (var i = 0; i < rows.length; i++) {
      if (String(rows[i][0]) + ' / ' + String(rows[i][1]) === label) {
        sh.getRange(i + 2, 3, 1, 2).setValues([[now, pushed]]);
        return;
      }
    }
  }
  sh.getRange(sh.getLastRow() + 1, 1, 1, 4).setValues([[device, app || '', now, pushed]]);
}

/* ------------------------------------------------------------------ utils */

function nowIso_() {
  return new Date(Math.max(Date.now(),Number(PropertiesService.getScriptProperties().getProperty('LAST_REVISION_MS')||0))).toISOString();
}

function isoish_(v) {
  if (v == null || v === '') return '';
  if (Object.prototype.toString.call(v) === '[object Date]') return v.toISOString();
  return String(v);
}

function dateish_(v) {
  if (v == null || v === '') return '';
  if (Object.prototype.toString.call(v) === '[object Date]') return Utilities.formatDate(v, 'UTC', 'yyyy-MM-dd');
  return String(v).slice(0, 10);
}

/* A cross-origin GET from a page cannot always read a normal JSON response, so
 * every reply can also come back wrapped in a callback the page supplied. */
function reply_(e, payload) {
  var cb = e && e.parameter && e.parameter.callback;
  var text = JSON.stringify(payload);
  if (cb && /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(cb)) {
    return ContentService.createTextOutput(cb + '(' + text + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(text).setMimeType(ContentService.MimeType.JSON);
}
