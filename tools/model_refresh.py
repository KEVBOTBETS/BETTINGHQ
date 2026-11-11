"""Run a model in isolation; publish its output only after successful completion."""
from pathlib import Path
import shutil
import subprocess
import tempfile

OUTPUTS={
    'ncaab-edge-lab':['state','site/data'],
    'nfl-edge-lab':['state','site/data'],
    'ncaaf-edge-lab':['state','site/data'],
    'props-edge':['state','site/data'],
    'wnba-edge-lab':['state','site/data'],
    'nba-edge-lab':['state','site/data'],
    'nhl-edge-lab':['state','site/data'],
    'mlb-edge':['data','docs/data'],
    'ladderbet':['state/model_accuracy.json','docs/index.html','docs/data'],
}

def refresh_project(project, command, timeout=1800):
    project=Path(project)
    with tempfile.TemporaryDirectory(prefix='kevbot-refresh-') as folder:
        work=Path(folder)/project.name
        shutil.copytree(project,work,ignore=shutil.ignore_patterns('.git','node_modules','__pycache__','.venv','*.log','*.tmp','_public_site'))
        if project.name=='ncaab-edge-lab':
            shutil.copytree(project.parent/'nba-edge-lab/pipeline',work/'_basketball_shared',ignore=shutil.ignore_patterns('__pycache__'))
        # Weekly player forecasts reuse the full NFL season schedule. The
        # isolated props copy must carry this read-only dependency too; the
        # calendar-year scoreboard alone drops January Week 17/18 games.
        if project.name=='props-edge':
            schedule=project.parent/'nfl-edge-lab/site/data'
            for filename in ('meta.json','games.json'):
                source=schedule/filename
                if source.is_file():
                    destination=Path(folder)/'nfl-edge-lab/site/data'/filename
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,destination)
        # Football refreshes run outside the repository. Bundle the stdlib-only
        # reader so quotes and health are written inside the same isolation.
        if project.name in ('nfl-edge-lab','ncaaf-edge-lab'):
            shared=Path(__file__).with_name('football_public_odds.py')
            if shared.exists():
                (work/'pipeline').mkdir(exist_ok=True)
                shutil.copy2(shared,work/'pipeline/public_odds.py')
        subprocess.run(command,cwd=work,check=True,timeout=timeout)
        for relative in OUTPUTS[project.name]:
            source=work/relative;destination=project/relative
            if not source.exists():continue
            if source.is_dir():
                shutil.copytree(source,destination,dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,destination)
