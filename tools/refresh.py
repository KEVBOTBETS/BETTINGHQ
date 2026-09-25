"""Refresh public forecasts; each board keeps its last good files on outage."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from model_refresh import refresh_project

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--sport',choices=['all','football','mlb','wnba','props','ladder','archive'],default='all')
args=parser.parse_args()
selected={'all':['nfl-edge-lab','ncaaf-edge-lab','mlb-edge','props-edge','wnba-edge-lab','ladderbet'],'football':['nfl-edge-lab','ncaaf-edge-lab','props-edge'],'mlb':['mlb-edge'],'wnba':['wnba-edge-lab'],'props':['props-edge'],'ladder':['ladderbet'],'archive':[]}[args.sport]
for repo in selected:
    command=['bash','scripts/run_build.sh'] if repo=='mlb-edge' else [sys.executable,'-m','ladder','render','--public','--out','docs/index.html'] if repo=='ladderbet' else [sys.executable,'-m','pipeline.build']
    try:
        refresh_project(ROOT/'projects'/repo,command,timeout=1800)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        # Stale feeds retain their original timestamps and cannot qualify as new picks.
        print(f'::warning::{repo} refresh failed ({type(exc).__name__}); inspect freshness before using its board.')
subprocess.run([sys.executable,'tools/build_site.py'],cwd=ROOT,check=True)
env={**os.environ,'LOCAL_SITE_ROOT':str(ROOT/'_site')}
subprocess.run(['node','scripts/refresh-tickets.mjs'],cwd=ROOT/'projects/bet-ledger-hq',env=env,check=True,timeout=600)
subprocess.run([sys.executable,'tools/build_site.py'],cwd=ROOT,check=True)
