"""Catch up stale boards when a narrow scheduled refresh is the next run to start."""
import datetime as dt
import json

PUBLICATIONS = {
    **{name: f'projects/{name}/site/data/meta.json' for name in
       ['ncaab-edge-lab', 'nfl-edge-lab', 'ncaaf-edge-lab', 'nba-edge-lab', 'nhl-edge-lab', 'props-edge', 'wnba-edge-lab']},
    'mlb-edge': 'projects/mlb-edge/docs/data/latest.json',
    'ladderbet': 'projects/ladderbet/docs/data/accuracy.json',
}


def publication_max_age(root, name, now):
    # The NBA/NHL parlay labs expire observed leg prices after 90 minutes.
    # Start recovery at 60 minutes instead of waiting two hours.
    if name not in ('nba-edge-lab','nhl-edge-lab'):return dt.timedelta(hours=2)
    try:
        games=json.loads((root/f'projects/{name}/site/data/games.json').read_text())
        for g in games:
            at=dt.datetime.fromisoformat(str(g.get('date')).replace('Z','+00:00'))
            if at.tzinfo and now<at<=now+dt.timedelta(hours=24) and not g.get('completed') and not g.get('canceled') and not g.get('postponed'):
                return dt.timedelta(hours=1)
    except (OSError,ValueError,TypeError):return dt.timedelta(hours=1)
    return dt.timedelta(hours=2)


def recovery_projects(root, selected, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    missing = []
    for name, relative in PUBLICATIONS.items():
        if name in selected:
            continue
        try:
            data = json.loads((root / relative).read_text())
            stamp = dt.datetime.fromisoformat(str(data['generated_at']).replace('Z', '+00:00'))
            if stamp.tzinfo and dt.timedelta(0) <= now - stamp <= publication_max_age(root,name,now):
                continue
        except (OSError, ValueError, TypeError, KeyError):
            pass
        missing.append(name)
    return missing
