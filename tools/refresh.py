"""Refresh public forecasts; each board keeps its last good files on outage."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from model_refresh import refresh_project

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--sport',choices=['all','football','mlb','wnba','nhl','props','ladder','archive'],default='all')
args=parser.parse_args()
selected={'all':['nfl-edge-lab','ncaaf-edge-lab','mlb-edge','props-edge','wnba-edge-lab','nhl-edge-lab','ladderbet'],'football':['nfl-edge-lab','ncaaf-edge-lab','props-edge'],'mlb':['mlb-edge'],'nhl':['nhl-edge-lab'],'wnba':['wnba-edge-lab'],'props':['props-edge'],'ladder':['ladderbet'],'archive':[]}[args.sport]
for repo in selected:
    command=['bash','scripts/run_build.sh'] if repo=='mlb-edge' else [sys.executable,'-m','ladder','render','--public','--out','docs/index.html'] if repo=='ladderbet' else [sys.executable,'-m','pipeline.build']
    try:
        refresh_project(ROOT/'projects'/repo,command,timeout=1800)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        # Stale feeds retain their original timestamps and cannot qualify as new picks.
        print(f'::warning::{repo} refresh failed ({type(exc).__name__}); inspect freshness before using its board.')
if args.sport in ['all','football','nhl','props']:
    try:
        subprocess.run([sys.executable,'-m','pipeline.multisport'],cwd=ROOT/'projects/props-edge',check=True,timeout=600)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
        print('::warning::Multisport props refresh failed; prior quote timestamps retained.')
subprocess.run([sys.executable,'tools/spread_tracking.py'],cwd=ROOT,check=True,timeout=90)
subprocess.run([sys.executable,'tools/newsletters.py'],cwd=ROOT,check=True,timeout=90)
if args.sport in ['all','football','props']:
    subprocess.run([sys.executable,'-m','tools.research.ingest'],cwd=ROOT,timeout=180,check=False)
subprocess.run([sys.executable,'-m','tools.research.build','--capture'],cwd=ROOT,check=True,timeout=180)
subprocess.run([sys.executable,'tools/build_site.py'],cwd=ROOT,check=True)
env={**os.environ,'LOCAL_SITE_ROOT':str(ROOT/'_site')}
subprocess.run(['node','scripts/refresh-tickets.mjs'],cwd=ROOT/'projects/bet-ledger-hq',env=env,check=True,timeout=600)
health=json.loads((ROOT/'projects/bet-ledger-hq/data/tickets/health.json').read_text())
summary=['## Public feed health','', '| Feed | Freshness | Coverage | Notes |','| --- | --- | --- | --- |']
for sport, feed in health.get('feeds',{}).items():
    notes='; '.join(feed.get('warnings',[])) or 'No reported gaps'
    summary.append(f"| {sport.upper()} | {feed.get('freshness','unknown')} | {feed.get('coverage','unknown')} | {notes.replace('|','/')} |")
    if feed.get('warnings'):print(f'::warning::{sport.upper()}: {notes}')
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as report:report.write('\n'.join(summary)+'\n')
subprocess.run([sys.executable,'tools/build_site.py'],cwd=ROOT,check=True)
