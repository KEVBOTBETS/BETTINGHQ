from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from model_refresh import refresh_project

class RefreshTransaction(unittest.TestCase):
    def test_failed_partial_refresh_retains_original_files(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)/'props-edge';(project/'site/data').mkdir(parents=True)
            meta=project/'site/data/meta.json';meta.write_text('original')
            command=[sys.executable,'-c',"from pathlib import Path; Path('site/data/meta.json').write_text('partial'); raise SystemExit(1)"]
            with self.assertRaises(subprocess.CalledProcessError):refresh_project(project,command)
            self.assertEqual(meta.read_text(),'original')

    def test_success_copies_data_without_replacing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)/'props-edge';(project/'site/data').mkdir(parents=True)
            (project/'source.py').write_text('original source')
            command=[sys.executable,'-c',"from pathlib import Path; Path('site/data/meta.json').write_text('complete'); Path('source.py').write_text('temporary')"]
            refresh_project(project,command)
            self.assertEqual((project/'site/data/meta.json').read_text(),'complete')
            self.assertEqual((project/'source.py').read_text(),'original source')

    def test_isolated_props_retains_full_season_january_schedule(self):
        import datetime
        import json
        import shutil
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'props-edge'
            (project/'site/data').mkdir(parents=True)
            (project/'pipeline').mkdir()
            weekly=Path(__file__).resolve().parents[1]/'projects/props-edge/pipeline/weekly_nfl.py'
            shutil.copy2(weekly,project/'pipeline/weekly_nfl.py')
            schedule=root/'nfl-edge-lab/site/data';schedule.mkdir(parents=True)
            now=datetime.datetime.now(datetime.timezone.utc)
            # Use next January while preserving the current NFL season label.
            season=now.year if now.month>=7 else now.year-1
            team_a={'id':'1','displayName':'Alfa'}
            team_b={'id':'2','displayName':'Beta'}
            events=[{'id':'nov','date':now.isoformat(),'season':{'year':season,'type':2},
                     'week':{'number':10},'competitions':[{'competitors':[
                         {'homeAway':'home','team':team_a},{'homeAway':'away','team':team_b}]}]}]
            original=json.dumps([{'game_id':'january','date':str(season+1)+'-01-10T18:00Z',
                'week':18,'season_type':2,'home_name':'Alfa','away_name':'Beta','completed':False,'status':'TBD'}])
            (schedule/'meta.json').write_text(json.dumps({'season':season,'generated_at':now.isoformat()}))
            (schedule/'games.json').write_text(original)
            (schedule/'not-a-dependency.txt').write_text('do not copy unrelated files')
            code=(
                "import json; from pathlib import Path; from datetime import datetime; "
                "from pipeline.weekly_nfl import schedule_events; "
                "schedule=Path.cwd().parent/'nfl-edge-lab/site/data'; "
                "assert sorted(p.name for p in schedule.iterdir())==['games.json','meta.json']; "
                "rows=schedule_events("+repr(events)+","+str(season)+",datetime.fromisoformat("+repr(now.isoformat())+"),schedule); "
                "assert any(e['id']=='january' and e['week']['number']==18 for e in rows); "
                "Path('site/data/meta.json').write_text(json.dumps({'weeks':[e['week']['number'] for e in rows]})); "
                "(schedule/'games.json').write_text('isolated mutation')"
            )
            refresh_project(project,[sys.executable,'-c',code])
            self.assertIn(18,json.loads((project/'site/data/meta.json').read_text())['weeks'])
            self.assertEqual((schedule/'games.json').read_text(),original)
