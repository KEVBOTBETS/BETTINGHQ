"""Regressions for frozen history and separating research from offered prices."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from pipeline.grade import Grader
from pipeline.http import ProviderError
from pipeline.parlays import _ticket, build_parlays, placeable_only
from pipeline.legs import legs_from_lines
from pipeline.schema import Projection
from pipeline.accuracy import migrate_history, update

ROOT=Path(__file__).resolve().parents[1]
SETTINGS=json.loads((ROOT/'config/settings.json').read_text())
NOW='2026-09-23T12:00:00Z'
START='2026-09-25T00:15:00Z'
def leg(**changes):
    return {'id':'a','event_id':'401','player':'Test Player','market':'Receptions','side':'over','line':4.5,'model_prob':.6,'price_source':'model','price_american':-110,'price_decimal':1+100/110,'start_time':START,'matchup':'A @ B',**changes}

class Integrity(unittest.TestCase):
    def test_all_legs_frozen_and_same_outcome_never_overwritten_or_counted_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            g=Grader(Path(folder),{})
            rows=[leg(id=str(i),player=f'Player {i}') for i in range(650)]
            path=g.snapshot(rows,now=NOW);original=json.loads(path.read_text())
            g.snapshot([dict(r,model_prob=.99,price_american=400) for r in rows],now='2026-09-24T13:00:00Z')
            self.assertEqual(original,json.loads(path.read_text()))
            self.assertEqual(len(original['records']),650)
            g.snapshot([leg(player='Player 0',side='under',model_prob=.4)],now=NOW)
            self.assertEqual(sum(r['selected'] for r in json.loads(path.read_text())['records'].values()),650)

    def test_late_naive_or_unidentifiable_observations_are_not_frozen(self):
        with tempfile.TemporaryDirectory() as folder:
            g=Grader(Path(folder),{})
            rows=[leg(start_time=NOW),leg(start_time='2026-09-25T00:15:00'),leg(event_id='date|matchup'),leg(model_prob=1.1),leg(model_prob=float('nan'))]
            path=g.snapshot(rows,now=NOW)
            self.assertEqual(json.loads(path.read_text())['records'],{})

    def test_old_unproven_results_preserved_and_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'site/data').mkdir(parents=True)
            old=[leg(result='Win')];(root/'site/data/graded.json').write_text(json.dumps(old))
            g=Grader(root,{})
            g.snapshot([],now=NOW);report=g.run(now=NOW)
            self.assertEqual(report['legacy_excluded'],1)
            self.assertEqual(report['settled'],0)
            self.assertEqual(json.loads((root/'state/legacy_leg_results.json').read_text()),old)

    def test_failed_result_fetch_keeps_prediction_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            g=Grader(Path(folder),{});path=g.snapshot([leg()],now=NOW)
            class Unavailable:
                def get(self,*args,**kwargs):raise ProviderError('Unavailable')
            g.client=Unavailable();report=g.run(now='2026-09-26T00:00:00Z')
            self.assertEqual(report['settled'],0)
            self.assertEqual(next(iter(json.loads(path.read_text())['records'].values()))['result'],'Pending')

    def test_history_migration_retains_original_forecasts_across_seasons(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'state').mkdir()
            rows={'a':{'id':'a','kind':'prop','league':'NFL','event_id':'10','player':'Test','market':'Receptions','projection':6,'start':'2025-09-24T00:00:00Z','captured_at':'2025-09-20T00:00:00Z','season':2025,'season_type':2,'result':'Graded','actual':5,'version':'original'}}
            (root/'state/model_accuracy.json').write_text(json.dumps({'records':rows}))
            log,_=migrate_history(root)
            self.assertEqual(log['records'],rows)
            self.assertTrue((root/'site/data/accuracy-summary.json').exists())

    def test_priced_line_cannot_borrow_another_events_projection(self):
        p=Projection(sport='NFL',player='Test Player',team='A',matchup='A @ B',market='Receptions',projection=6,samples=6,confidence=.6,standard_deviation=2,recent=[4,5,6,7,8,6],trend=0,event_id='402',start_time=START)
        self.assertEqual(legs_from_lines([leg(book='Book',line_source='posted')],[p],SETTINGS),[])

    def test_all_projections_tracked_but_expired_quotes_cannot_claim_returns(self):
        now=datetime.now(timezone.utc);start=(now+timedelta(days=1)).isoformat()
        quote=leg(book='Book',price_american=-110,updated_at=now.isoformat(),
                  start_time=start,tier='PASS',team='A')
        invalid=[{'updated_at':(now-timedelta(hours=13)).isoformat()},
                 {'updated_at':(now+timedelta(hours=1)).isoformat()},
                 {'updated_at':now.replace(tzinfo=None).isoformat()},
                 {'book':''},{'price_american':50}]
        rows=[quote]+[dict(quote,player=f'Invalid {i}',**change) for i,change in enumerate(invalid)]
        projection=SimpleNamespace(event_id='401',start_time=start,matchup='A @ B',
            player='Unpriced Player',team='A',market='Receptions',projection=6)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);update(root,rows,[projection],[])
            saved=list(json.loads((root/'state/model_accuracy.json').read_text())['records'].values())
            self.assertEqual({(r['kind'],r['player']) for r in saved},
                             {('call','Test Player'),('prop','Unpriced Player')})
            self.assertEqual(next(r for r in saved if r['kind']=='call')['tier'],'PASS')

    def test_estimated_or_same_game_ticket_never_claims_ev_or_qualification(self):
        rows=[leg(),leg(id='b',player='Another Player')]
        t=_ticket(rows,'game','A @ B',1000,SETTINGS)
        self.assertEqual(t['status'],'research')
        self.assertFalse(t['actionable']);self.assertIsNone(t['expected_value_on_10'])
        self.assertAlmostEqual(t['correlation_applied'],1)
        settings=copy.deepcopy(SETTINGS);settings['parlays']['book_lines_only']=True
        self.assertEqual(placeable_only(rows,settings),[])
        self.assertEqual(build_parlays([leg(start_time=NOW)],SETTINGS,now=__import__('datetime').datetime.fromisoformat(NOW.replace('Z','+00:00')))['tickets'],[])

if __name__=='__main__':unittest.main()
