"""Catch up stale boards when a narrow scheduled refresh is the next run to start."""
import datetime as dt
import json

PUBLICATIONS = {
    **{name: f'projects/{name}/site/data/meta.json' for name in
       ['ncaab-edge-lab', 'nfl-edge-lab', 'ncaaf-edge-lab', 'nba-edge-lab', 'nhl-edge-lab', 'props-edge', 'wnba-edge-lab']},
    'mlb-edge': 'projects/mlb-edge/docs/data/latest.json',
    'ladderbet': 'projects/ladderbet/docs/data/accuracy.json',
}


def recovery_projects(root, selected, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    missing = []
    for name, relative in PUBLICATIONS.items():
        if name in selected:
            continue
        try:
            data = json.loads((root / relative).read_text())
            stamp = dt.datetime.fromisoformat(str(data['generated_at']).replace('Z', '+00:00'))
            if stamp.tzinfo and dt.timedelta(0) <= now - stamp <= dt.timedelta(hours=2):
                continue
        except (OSError, ValueError, TypeError, KeyError):
            pass
        missing.append(name)
    return missing
