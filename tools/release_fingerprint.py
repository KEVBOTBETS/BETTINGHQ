"""Hash tracked release code, not changing model publications.

Only exact successful browser certificates may be reused. Configuration, tests,
dependencies, assets and this workflow itself are part of the fingerprint.
"""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def publication(path):
    parts = Path(path).parts
    if len(parts) < 4 or parts[0] != 'projects':
        return False
    return (parts[2] == 'state' and path.endswith('.json') or
            parts[2:4] in [('site', 'data'), ('docs', 'data')] and path.endswith('.json') or
            parts[1] in ('mlb-edge', 'bet-ledger-hq') and parts[2] == 'data' and path.endswith('.json') or
            path == 'projects/ladderbet/docs/index.html' or
            path in ('projects/ladderbet/docs/badge.svg', 'projects/ladderbet/docs/data/results.json'))

def fingerprint(root=ROOT):
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    digest = hashlib.sha256(b'kevbot-browser-certificate-v1\0')
    for name in sorted(n for n in names if n and not publication(n)):
        digest.update(name.encode() + b'\0')
        digest.update((root / name).read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()

if __name__ == '__main__':
    print(fingerprint())
