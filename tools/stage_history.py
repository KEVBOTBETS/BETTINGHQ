"""Commit only model history/public feeds; never credentials or browser wagers."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
patterns=[
    'projects/bet-ledger-hq/data/tickets/**/*.json',
    'projects/mlb-edge/docs/data/*.json',
    'projects/mlb-edge/data/predictions.json',
    'projects/mlb-edge/data/shadow.json',
]
for repo in ['nfl-edge-lab','ncaaf-edge-lab']:
    patterns += [f'projects/{repo}/site/data/*.json']
    patterns += [f'projects/{repo}/state/{name}' for name in [
        'model_accuracy.json','fpi_*.json','games_*.json','history_*.json',
        'lines.json','context_cache.json','quote_cache.json','rank_history.json',
        'shadow.json','predictions.json','forecasts.json']]
files=sorted({str(p.relative_to(ROOT)) for pat in patterns for p in ROOT.glob(pat)
              if p.is_file() and p.name not in {'ledger.json','summary.json'}})
if files: subprocess.run(['git','add','--',*files],cwd=ROOT,check=True)
