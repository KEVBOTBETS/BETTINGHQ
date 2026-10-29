"""Report remaining coverage gaps after the keyless refresh and its fallbacks."""
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    try:
        result = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except ValueError:
        return None


def prop_coverage(root, sport, now):
    folder = root / f'projects/props-edge/site/data/labs/{sport}'
    manifest = json.loads((folder / 'manifest.json').read_text())
    games = {str(g['game_id']): g for g in manifest['games']
             if (at := instant(g.get('date'))) and now < at <= now + dt.timedelta(hours=24)}
    priced = set()
    for chunk in manifest['chunks']:
        # Only examine chunks containing an upcoming game; never trust paths from data.
        if not any(instant(g['date']).astimezone(ZoneInfo('America/Toronto')).date().isoformat() == chunk['day'] for g in games.values()):
            continue
        name = chunk['file']
        if Path(name).name != name or not name.startswith('day-') or not name.endswith('.json'):
            raise ValueError('Invalid daily chunk filename')
        data = json.loads((folder / name).read_text())
        if any(data.get(key) != manifest.get(key) for key in ('generated_at', 'source_model_at')):
            raise ValueError('Mixed daily feed versions')
        for quote in data.get('quotes', []):
            observed = instant(quote.get('observed_at') or quote.get('captured_at'))
            price = quote.get('price_american')
            if (str(quote.get('event_id')) in games and observed and
                    dt.timedelta(0) <= now - observed <= dt.timedelta(hours=3) and
                    isinstance(price, (int, float)) and not isinstance(price, bool) and
                    abs(price) >= 100 and quote.get('book') and quote.get('price_source') == 'book'):
                priced.add(str(quote['event_id']))
    return {'upcoming_24h': len(games), 'with_fresh_observed_props': len(priced),
            'without_fresh_observed_props': [g for key, g in games.items() if key not in priced]}


def review(root=ROOT, now=None, refresh_outcome='unknown'):
    now = now or dt.datetime.now(dt.timezone.utc)
    findings = []
    try:
        health = json.loads((root / 'projects/bet-ledger-hq/data/tickets/health.json').read_text())
        checked = instant(health.get('checked_at'))
        if not checked or not dt.timedelta(0) <= now - checked <= dt.timedelta(hours=1):
            findings.append('Hub health report is missing a recent check; do not treat old health as a successful refresh.')
    except (OSError, ValueError):
        health = {}
        findings.append('Hub health report could not be read.')
    if refresh_outcome != 'success':
        findings.append(f'Refresh step outcome: {refresh_outcome}; inspect the workflow logs.')
    for sport, feed in health.get('feeds', {}).items():
        for warning in feed.get('warnings', []):
            findings.append(f'{sport.upper()}: {warning}')
        if feed.get('freshness') not in ('recent', 'fresh'):
            findings.append(f"{sport.upper()}: feed freshness is {feed.get('freshness', 'unknown')}.")
    props = {}
    for sport in ('nba', 'nhl'):
        try:
            props[sport] = prop_coverage(root, sport, now)
            missing = props[sport]['without_fresh_observed_props']
            if missing:
                findings.append(f'{sport.upper()}: {len(missing)} upcoming games lack fresh observed player prices. Estimates are not book offers.')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            findings.append(f'{sport.upper()}: daily prop feed could not be verified ({type(exc).__name__}).')
    return {'checked_at': now.isoformat(), 'local_day': now.astimezone(ZoneInfo('America/Toronto')).date().isoformat(),
            'refresh_outcome': refresh_outcome, 'status': 'review' if findings else 'healthy',
            'feeds': health.get('feeds', {}), 'props': props, 'findings': findings,
            'policy': 'Automatic refresh uses existing retries and public fallbacks; unresolved gaps remain flagged. No bets are forced and no model prices become observed offers. Source-code repairs require a tested change.'}


def main():
    result = review(refresh_outcome=os.environ.get('REFRESH_OUTCOME', 'unknown'))
    Path('review-report.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['## BETTINGHQ coverage review', '', f"Checked: {result['checked_at']} | Status: {result['status']}", '',
             *['- ' + finding.replace('\n', ' ') for finding in result['findings']], '', result['policy']]
    text = '\n'.join(lines) + '\n'
    Path('review-report.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
            out.write(text)
    for finding in result['findings']:
        safe = finding.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::warning::' + safe)
    print(json.dumps({'status': result['status'], 'findings': len(result['findings'])}))


if __name__ == '__main__':
    main()
