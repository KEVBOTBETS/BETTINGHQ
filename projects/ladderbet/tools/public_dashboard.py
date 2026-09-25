"""Publish current option cards without importing repo-owned wager history."""
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ladder.render import render
from tools.patch_dashboard import patch
path=Path(sys.argv[1])
match=re.search(r'<script type="application/json" id="ladder-data">(.*?)</script>',path.read_text(),re.S)
if not match: raise RuntimeError('Cannot locate Ladder option data; refusing unsafe publication')
data=json.loads(match[1])
if not data.get('history') and not data.get('state',{}).get('rung'):
    patch(path)
    raise SystemExit(0)
cfg=json.loads(Path('config.json').read_text())
state={**cfg['ladder'],'history':[],'pending':None,'rung':0,'stake':cfg['ladder']['base_stake'],'net':0,'runs_completed':0,'runs_busted':0,'reset_at':''}
sel=cfg['selection']
path.write_text(render(state,data['candidates'],[],sel['max_decimal'],(sel['min_decimal'],sel['max_decimal'])))
patch(path)
