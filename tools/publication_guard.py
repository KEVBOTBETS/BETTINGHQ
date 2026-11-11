"""Permit concurrent data saves without publishing older code or older data."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from tools.release_fingerprint import publication


def timestamp(value):
    try:
        at = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return at if at.tzinfo else None
    except ValueError:
        return None


def allowed(changed, artifact_health, remote_health):
    if not isinstance(artifact_health, dict) or not isinstance(remote_health, dict):
        return False
    if any(not publication(name) for name in changed):
        return False
    artifact = timestamp(artifact_health.get('checked_at'))
    remote = timestamp(remote_health.get('checked_at'))
    return bool(artifact and remote and artifact >= remote)


def main():
    built, remote = sys.argv[1:3]
    try:
        names = subprocess.check_output(['git', 'diff', '--name-only', '-z', built, remote]).decode().split('\0')
        names = [n for n in names if n]
        if not names:
            return 0
        artifact = json.loads(Path('_site/bet-ledger-hq/data/tickets/health.json').read_text())
        current = json.loads(subprocess.check_output(['git', 'show', remote + ':projects/bet-ledger-hq/data/tickets/health.json']))
        if allowed(names, artifact, current):
            print('Concurrent changes contain only publications; the validated artifact is at least as recent.')
            return 0
        print('Publication deferred: release code changed or a newer/uncertain data publication exists.')
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        print(f'Publication deferred: comparison could not be verified ({type(exc).__name__}).')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
