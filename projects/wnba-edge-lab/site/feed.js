/* Publication health and loading only. Never calculates projections or stakes. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./eligibility.js'));
  else root.WNBAFeed = factory(root.QuoteEligibility);
})(typeof self !== 'undefined' ? self : this, function (eligibility) {
  'use strict';
  const FILES = ['board','games','summary','meta','index','performance','simulator','news','calibration','results'];
  const arrayFiles = new Set(['board','games','news','results']);
  function timestamp(value) {
    return typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? Date.parse(value) : NaN;
  }
  function ageLabel(value, now = Date.now()) {
    const at = timestamp(value);
    if (!Number.isFinite(at)) return 'age unknown';
    if (at > now + 300000) return 'timestamp in the future';
    const minutes = Math.max(0, Math.floor((now - at) / 60000));
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`;
    return `${Math.floor(minutes / 1440)}d ago`;
  }
  function health(meta = {}, rows = [], now = Date.now(), refreshError = false) {
    const age = ageLabel(meta.generated_at, now), at = timestamp(meta.generated_at);
    const odds = meta.odds_health || {};
    const upcoming = rows.filter(row => timestamp(row.tipoff || row.start_time) > now);
    const priced = new Set(upcoming.map(row => row.game_id)).size;
    const fresh = new Set(upcoming.filter(row => !eligibility.blockReason(row, row.max_odds_age_hours ?? 12, now)).map(row => row.game_id)).size;
    let level = 'ok', label = 'OBSERVED DATA', message;
    if (meta.source_status === 'no-live-data' || !Number.isFinite(at)) {
      level = 'error'; label = 'DATA UNAVAILABLE';
      message = 'No verified publication is available. No sample or fabricated picks are substituted.';
    } else if (meta.source_status === 'cached-live-data') {
      level = 'partial'; label = 'CACHED DATA';
      message = 'The source refresh failed. A previous real-data cache remains visible; existing price-age and start-time checks still apply.';
    } else if (at > now + 300000 || now - at >= 12 * 3600000 || (priced && fresh === 0)) {
      level = 'partial'; label = 'STALE / UNVERIFIED';
      message = 'The publication or its prices are stale or unverified. Check Data Sources; expired quotes cannot be added to the ledger.';
    } else {
      message = `${fresh} upcoming games have fresh observed quotes; ${odds.upcoming_games || 0} games in the published upcoming window. Prices are snapshots, not a live sportsbook stream.`;
      if (odds.status !== 'ok' || fresh < priced) level = 'partial';
      if (!priced) label = 'SCHEDULE DATA';
    }
    if (meta.errors?.length) {
      if (level === 'ok') level = 'partial';
      message += ` ${meta.errors.length} source warning(s): reports may be incomplete. See Data Sources before using a pick.`;
    }
    if (refreshError) {
      if (level === 'ok') level = 'partial';
      message += ' Could not check the newest publication; previous data is retained and an automatic retry is scheduled.';
    }
    return {level, label, message, age, fresh};
  }
  async function read(fetcher, currentStamp, signal) {
    async function get(name) {
      const response = await fetcher(`data/${name}.json`, {cache:'no-store', signal});
      if (!response.ok) {
        if (name === 'results' && response.status === 404) return [];
        throw new Error(`Unable to load ${name}`);
      }
      const value = await response.json();
      if (arrayFiles.has(name) ? !Array.isArray(value) : !value || typeof value !== 'object' || Array.isArray(value))
        throw new Error(`Invalid ${name} publication`);
      return value;
    }
    const meta = await get('meta');
    if (!Number.isFinite(timestamp(meta.generated_at))) throw new Error('Invalid publication timestamp');
    if (currentStamp && timestamp(meta.generated_at) < timestamp(currentStamp)) throw new Error('Older publication received');
    if (meta.generated_at === currentStamp) return null;
    const payload = await Promise.all(FILES.map(name => name === 'meta' ? meta : get(name)));
    const index = payload[FILES.indexOf('index')];
    if (!Array.isArray(index.dates) || index.generated_at !== meta.generated_at)
      throw new Error('Publication files are not from the same refresh');
    const after = await get('meta');
    if (after.generated_at !== meta.generated_at) throw new Error('Publication changed during download');
    return payload;
  }
  return {FILES, ageLabel, health, read};
});
