"""Stage the portable site. No account-specific URLs or private ledger files."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
PROJECTS = ROOT / 'projects'


def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    hub = PROJECTS / 'bet-ledger-hq'
    target = OUT / 'bet-ledger-hq'
    target.mkdir()
    suffixes = {'.html', '.js', '.css', '.webmanifest', '.svg', '.png', '.jpg', '.webp'}
    for path in hub.iterdir():
        if path.is_file() and (path.suffix in suffixes or path.name == 'SETUP-SYNC.md'):
            shutil.copy2(path, target / path.name)
    for name in ['assets', 'data/tickets']:
        if (hub / name).exists(): shutil.copytree(hub / name, target / name)
    subprocess.run([sys.executable, 'tools/prepare_public_site.py'], cwd=PROJECTS/'nfl-edge-lab', check=True)
    for repo, folder in [('nfl-edge-lab','_public_site'),('ncaaf-edge-lab','site'),('mlb-edge','docs')]:
        dest=OUT/repo
        shutil.copytree(PROJECTS/repo/folder, dest,
                        ignore=shutil.ignore_patterns('__pycache__','.DS_Store'))
        data=dest/'data';data.mkdir(exist_ok=True)
        # Wagers live in the user's browser/Sheet. Never publish a restored
        # financial ledger just because a model output folder contains it.
        (data/'ledger.json').write_text('[]\n')
        if (data/'summary.json').exists():
            (data/'summary.json').write_text(json.dumps(dict(starting_bankroll=None,
                current_bankroll=None,wins=0,losses=0,pushes=0,settled=0,pending=0,roi=None,pnl=None))+'\n')
    (OUT/'.nojekyll').touch()
    (OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>KEVBOTBETS</title>
<p><a href="./bet-ledger-hq/#football">Open KEVBOTBETS</a></p>
<script>location.replace('./bet-ledger-hq/'+(location.hash||'#football'));</script></html>''')
    print(f'Public site ready: {OUT}')


if __name__=='__main__': main()
