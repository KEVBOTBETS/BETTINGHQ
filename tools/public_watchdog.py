"""Independent published-data check; never trusts saved freshness labels."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request

FEEDS = ('mlb', 'wnba', 'props', 'ladder', 'nba', 'nfl', 'ncaab', 'ncaaf', 'nhl')
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}


def age_hours(value, now):
    try:
        at = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (now - at).total_seconds() / 3600 if at.tzinfo else None
    except (ValueError, TypeError):
        return None


def assess(health, runs, now):
    errors, warnings = [], []
    def check_time(label, value):
        age = age_hours(value, now)
        if age is None or age < -0.25 or age > 4:
            errors.append(f'{label}: missing, future-dated or older than four hours.')
    check_time('Published health report', health.get('checked_at'))
    feeds = health.get('feeds', {})
    if not isinstance(feeds, dict):
        feeds = {}
    for sport in FEEDS:
        feed = feeds.get(sport) or {}
        if not isinstance(feed, dict):
            feed = {}
        check_time(sport.upper(), feed.get('published_at'))
        warnings.extend(f'{sport.upper()}: {w}' for w in feed.get('warnings', []))
    main_runs = [r for r in runs if r.get('head_branch') == 'main' and r.get('event') != 'pull_request']
    active = any(r.get('status') in ACTIVE for r in main_runs)
    completed = next((r for r in main_runs if r.get('status') == 'completed'), None)
    if completed and completed.get('conclusion') not in ('success', 'cancelled', 'skipped'):
        errors.append('Latest completed release failed; inspect its build logs.')
    if not main_runs:
        errors.append('No main-branch release runs could be verified.')
    return {'checked_at': now.isoformat(), 'errors': errors, 'warnings': warnings,
            'release_active': active, 'request_refresh': bool(errors) and not active,
            'latest_release_url': main_runs[0].get('html_url') if main_runs else None}


def request(url, token=None, payload=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'BETTINGHQ-public-watchdog'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, headers=headers,
                                 data=json.dumps(payload).encode() if payload is not None else None)
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read()
        return json.loads(body) if body else None


def main():
    now = dt.datetime.now(dt.timezone.utc)
    repo = os.environ.get('GITHUB_REPOSITORY', 'KEVBOTBETS/BETTINGHQ')
    token = os.environ.get('GITHUB_TOKEN')
    api = f'https://api.github.com/repos/{repo}/actions/workflows/release.yml'
    fetch_errors = []
    try:
        health = request('https://kevbotbets.github.io/BETTINGHQ/bet-ledger-hq/data/tickets/health.json?watchdog=' + str(int(now.timestamp())))
        if not isinstance(health, dict):
            raise ValueError('Health response is not an object')
    except Exception as exc:
        health = {}
        fetch_errors.append(f'Published health fetch failed ({type(exc).__name__}).')
    runs = None
    try:
        runs = request(api + '/runs?branch=main&per_page=30', token)['workflow_runs']
    except Exception as exc:
        fetch_errors.append(f'Release status fetch failed ({type(exc).__name__}); recovery will not be dispatched blindly.')
    result = assess(health, runs or [], now)
    result['errors'].extend(fetch_errors)
    result['recovery'] = 'not needed'
    if result['errors']:
        if runs is None:
            result['recovery'] = 'blocked: release status unavailable'
        elif result['release_active']:
            result['recovery'] = 'deferred: a release is already active'
        elif result['request_refresh'] and token:
            try:
                request(api + '/dispatches', token, {'ref': 'main', 'inputs': {'sport': 'all'}})
                result['recovery'] = 'one full refresh requested; success must be verified in the release run'
            except Exception as exc:
                result['recovery'] = f'refresh request failed ({type(exc).__name__})'
        else:
            result['recovery'] = 'not dispatched: no built-in GitHub token'
    Path('watchdog-report.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['## Published BETTINGHQ check', '', f"Checked: {result['checked_at']}",
             f"Recovery: {result['recovery']}", '', '### Publication / build problems', '',
             *['- ' + e for e in result['errors']], '', '### Source coverage warnings', '',
             *['- ' + w for w in result['warnings']], '',
             'Coverage warnings alone do not trigger rebuilds. Missing prices remain unavailable; no odds or bets are invented.']
    report = '\n'.join(lines) + '\n'
    Path('watchdog-report.md').write_text(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
            out.write(report)
    print(report)
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
