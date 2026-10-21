"""Commit only model history/public feeds; never credentials or browser wagers."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
patterns=[
    'projects/bet-ledger-hq/data/tickets/**/*.json',
    'projects/bet-ledger-hq/data/newsletters/**/*.json',
    'projects/bet-ledger-hq/data/spreads/**/*.json',
    'projects/bet-ledger-hq/data/research/**/*.json',
    'projects/bet-ledger-hq/data/research/**/*.json.gz',
    'research/inputs/*.json',
    'projects/mlb-edge/docs/data/*.json',
    'projects/mlb-edge/data/predictions.json',
    'projects/mlb-edge/data/shadow.json',
    'projects/props-edge/site/data/*.json',
    'projects/props-edge/site/data/history/*.json',
    'projects/props-edge/state/*.json',
    'projects/nhl-edge-lab/state/*.json',
    'projects/nhl-edge-lab/site/data/*.json',
    'projects/nba-edge-lab/state/*.json',
    'projects/nba-edge-lab/site/data/*.json',
    'projects/wnba-edge-lab/state/*.json',
    'projects/wnba-edge-lab/site/data/*.json',
    'projects/ladderbet/state/model_accuracy.json',
    'projects/ladderbet/docs/data/*.json',
    'projects/ladderbet/docs/index.html',
]
for repo in ['nfl-edge-lab','ncaaf-edge-lab']:
    patterns += [f'projects/{repo}/site/data/*.json']
    patterns += [f'projects/{repo}/state/{name}' for name in [
        'model_accuracy.json','fpi_*.json','games_*.json','history_*.json',
        'lines.json','context_cache.json','quote_cache.json','rank_history.json',
        'shadow.json','predictions.json','forecasts.json','early_plays.json','qb_quality.json','public_odds_health.json']]
files=sorted({str(p.relative_to(ROOT)) for pat in patterns for p in ROOT.glob(pat)
              if p.is_file() and not (p.parent==ROOT/'projects/nba-edge-lab/state' and p.name=='sources.json') and p.name not in {'ledger.json','summary.json','ladder.json','multisport_cache.json','public_research_cache.json'}})
if files: subprocess.run(['git','add','--',*files],cwd=ROOT,check=True)

# Include the losslessly migrated legacy archive deletion in the data commit.
subprocess.run(['git','add','-u','--','projects/bet-ledger-hq/data/research'],cwd=ROOT,check=True)
