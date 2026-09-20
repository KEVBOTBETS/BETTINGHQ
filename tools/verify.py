"""Offline release checks, isolated per project to avoid pipeline import collisions."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',action='store_true');args=parser.parse_args()
checks=[]
def run(project,command):
    start=time.monotonic();cwd=ROOT/'projects'/project if project else ROOT
    print(f'CHECK {project or "portable"}: {" ".join(command)}',flush=True)
    result=subprocess.run(command,cwd=cwd)
    checks.append(dict(project=project,command=command,passed=result.returncode==0,seconds=round(time.monotonic()-start,2)))
    (ROOT/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    if result.returncode: raise SystemExit(result.returncode)

run('nfl-edge-lab',[sys.executable,'-m','unittest','discover','-s','tests'])
run('ncaaf-edge-lab',[sys.executable,'-m','tests.test_offline'])
run('ncaaf-edge-lab',[sys.executable,'-m','unittest','tests.test_accuracy','tests.test_schedule','tests.test_context','tests.test_privacy'])
run('props-edge',[sys.executable,'-m','unittest','tests.test_offline'])
run('mlb-edge',[sys.executable,'-m','tests.test_pipeline'])
run('mlb-edge',[sys.executable,'-m','unittest','tests.test_prediction_freeze'])
run('mlb-edge',[sys.executable,'-m','tests.test_config'])
run('mlb-edge',['bash','tests/test_build_runner.sh'])
for repo in ['nfl-edge-lab','ncaaf-edge-lab','mlb-edge']:
    for file in ['test_ledger.mjs','test_sync.mjs','test_staking.mjs','test_matchups.js','test_simulator.js','test_schedule.mjs','test_sim_gate.mjs']:
        if (ROOT/'projects'/repo/'tests'/file).exists():run(repo,['node','tests/'+file])
run('mlb-edge',['node','tests/test_sim.mjs','docs/data'])
for file in ['test_betsync.mjs','test_server.mjs','test_alerts_app.mjs','test_recovery_history.mjs','test_tickets.mjs','test_today.mjs','test_moneyline.mjs','test_football.mjs']:
    run('bet-ledger-hq',['node','tests/'+file])
run('',[sys.executable,'tools/build_site.py'])
run('',[sys.executable,'-m','unittest','discover','-s','tests'])
if args.browser:
    run('bet-ledger-hq',['node','tests/test_moneyline_browser.mjs'])
    run('bet-ledger-hq',['node','tests/test_today_browser.mjs'])
    run('bet-ledger-hq',['node','tests/test_weekly_browser.mjs'])
    run('bet-ledger-hq',['node','tests/test_props_browser.mjs'])
print(f'PASS: {len(checks)} release checks')
