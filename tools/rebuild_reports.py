"""Recompute reports from saved history, without inventing new predictions."""
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
code='''from pathlib import Path
import json
from pipeline import predict, grade
report=predict.summary()
report['calibration']=predict.calibration()
report['recovery_note']='Recomputed from recovered pregame history; no new forecasts or results fetched.'
Path('docs/data/predictions.json').write_text(json.dumps(report,indent=2)+'\\n')
Path('docs/data/performance.json').write_text(json.dumps(grade.summarise(),indent=2)+'\\n')
print(json.dumps({'scope':report['scope'],'overall':report['overall']}))
'''
subprocess.run([sys.executable,'-c',code],cwd=ROOT/'projects/mlb-edge',check=True)
