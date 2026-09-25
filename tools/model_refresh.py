"""Run a model in isolation; publish its output only after successful completion."""
from pathlib import Path
import shutil
import subprocess
import tempfile

OUTPUTS={
    'nfl-edge-lab':['state','site/data'],
    'ncaaf-edge-lab':['state','site/data'],
    'props-edge':['state','site/data'],
    'wnba-edge-lab':['state','site/data'],
    'mlb-edge':['data','docs/data'],
    'ladderbet':['state/model_accuracy.json','docs/index.html','docs/data'],
}

def refresh_project(project, command, timeout=1800):
    project=Path(project)
    with tempfile.TemporaryDirectory(prefix='kevbot-refresh-') as folder:
        work=Path(folder)/project.name
        shutil.copytree(project,work,ignore=shutil.ignore_patterns('.git','node_modules','__pycache__','.venv','*.log','*.tmp','_public_site'))
        subprocess.run(command,cwd=work,check=True,timeout=timeout)
        for relative in OUTPUTS[project.name]:
            source=work/relative;destination=project/relative
            if not source.exists():continue
            if source.is_dir():
                shutil.copytree(source,destination,dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,destination)
