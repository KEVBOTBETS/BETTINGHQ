"""Refresh selected models using real upstream data. Fail before publication."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--sport',choices=['all','football','mlb'],default='all')
args=parser.parse_args()
repos=['nfl-edge-lab','ncaaf-edge-lab'] if args.sport=='football' else ['mlb-edge'] if args.sport=='mlb' else ['nfl-edge-lab','ncaaf-edge-lab','mlb-edge']
for repo in repos:
    command=['bash','scripts/run_build.sh'] if repo=='mlb-edge' else [sys.executable,'-m','pipeline.build']
    subprocess.run(command,cwd=ROOT/'projects'/repo,check=True,timeout=2400)
subprocess.run([sys.executable,'tools/build_site.py'],cwd=ROOT,check=True)
env={**os.environ,'LOCAL_SITE_ROOT':str(ROOT/'_site')}
# The archive records the files from this build, never a different account's
# public site. Old unsupported sports remain preserved in its history.
subprocess.run(['node','scripts/refresh-tickets.mjs'],cwd=ROOT/'projects/bet-ledger-hq',env=env,check=True,timeout=600)
subprocess.run([sys.executable,'tools/build_site.py'],cwd=ROOT,check=True)
