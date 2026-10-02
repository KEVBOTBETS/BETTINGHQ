import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone
from tools.spread_tracking import candidate, settle, update, quote_valid, load_state

class SpreadTracking(unittest.TestCase):
    def snapshot(self,**kw):
        return dict(event_id='42',start='2026-10-04T17:00Z',captured_at='2026-10-02T21:00Z',matchup='A @ H',margin=3,market_spread=-4,**kw)
    def test_home_and_away_covers_push_and_missing_price(self):
        r=candidate('nfl',self.snapshot());settle(r,24,20,'2026-10-04T21:00Z');self.assertEqual(r['status'],'Push');self.assertNotIn('unit_profit',r)
        r=candidate('nfl',self.snapshot());settle(r,24,21,'2026-10-04T21:00Z');self.assertEqual(r['status'],'Win') # away +4
        r=candidate('nfl',{**self.snapshot(),'margin':7});r.update(price=-120,book='Book');settle(r,24,21,'2026-10-04T21:00Z');self.assertEqual(r['status'],'Loss');self.assertEqual(r['unit_profit'],-1)
        r=candidate('nfl',{**self.snapshot(),'margin':7});r.update(price=-120,book='Book');settle(r,30,21,'2026-10-04T21:00Z');self.assertAlmostEqual(r['unit_profit'],100/120)
    def test_missing_line_and_no_call_are_not_decisions(self):
        r=candidate('nfl',{**self.snapshot(),'market_spread':None});settle(r,24,21,'2026-10-04T21:00Z');self.assertEqual(r['status'],'No line');self.assertEqual(r['margin_error'],0)
        r=candidate('nfl',{**self.snapshot(),'market_spread':-3});settle(r,24,21,'2026-10-04T21:00Z');self.assertEqual(r['status'],'No call')
    def test_postgame_and_unaware_snapshots_rejected(self):
        for at in ['2026-10-04T17:00Z','2026-10-05T00:00Z','2026-10-02T21:00:00']:
            self.assertIsNone(candidate('nfl',{**self.snapshot(),'captured_at':at}))
        now=datetime(2026,10,2,21,tzinfo=timezone.utc);start=datetime(2026,10,4,17,tzinfo=timezone.utc)
        self.assertFalse(quote_valid('2026-10-02T22:00Z',now,start));self.assertFalse(quote_valid('2026-10-02T08:00Z',now,start))
    def test_first_prediction_and_qualified_side_are_frozen(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);f=root/'projects/ncaaf-edge-lab/site/data';f.mkdir(parents=True)
            def write(name,data):(f/name).write_text(json.dumps(data))
            write('accuracy.json',{'records':[{'kind':'game',**self.snapshot()}]});write('meta.json',{'generated_at':'2026-10-02T20:00Z'})
            game={'game_id':'42','date':'2026-10-04T17:00Z','away':'A','home':'H','projection':{'mu':3},'odds':{'spread_home':-4,'spread_price_home':-115,'spread_price_away':-105,'book':'Book','observed_at':'2026-10-02T20:00Z'}}
            write('games.json',[game]);write('board.json',[{'game_id':'42','market':'ATS','side':'away','line':-4,'price':-105,'book':'Book','odds_observed_at':'2026-10-02T20:00Z','tier':'GOOD','action_edge':.05}])
            now=datetime(2026,10,2,21,tzinfo=timezone.utc);one=update(root,now)['records'];q=next(r for r in one if r['cohort']=='qualified');self.assertEqual(q['home_spread'],-4);self.assertEqual(q['side'],'away')
            game['projection']['mu']=20;game['odds']['spread_home']=-8;write('games.json',[game]);write('accuracy.json',{'records':[{'kind':'game',**{**self.snapshot(),'margin':20,'market_spread':-8}}]})
            two=update(root,now)['records'];self.assertEqual(one,two)
            game.update(completed=True,home_score=24,away_score=21);write('games.json',[game]);end=update(root,datetime(2026,10,4,21,tzinfo=timezone.utc))['records'];q=next(r for r in end if r['cohort']=='qualified');self.assertEqual(q['status'],'Win');self.assertAlmostEqual(q['unit_profit'],100/105)

    def test_seed_unpacks_originals_without_mutating_sources(self):
        import gzip,base64
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'projects/bet-ledger-hq/data/spreads';folder.mkdir(parents=True)
            data={'schema':1,'records':[candidate('nfl',self.snapshot())]}
            seed={'schema':1,'encoding':'gzip-base64','content':base64.b64encode(gzip.compress(json.dumps(data).encode())).decode()}
            (folder/'seed.json').write_text(json.dumps(seed))
            self.assertEqual(load_state(root),data);self.assertFalse((folder/'history.json').exists())
            newer={'schema':1,'records':[]};(folder/'history.json').write_text(json.dumps(newer));self.assertEqual(load_state(root),newer)
