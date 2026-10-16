import unittest,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from tools.moneyline_tracking import freeze,settle,build,ARCHIVE
from tools.research.common import write
class Calls(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,16,18,tzinfo=timezone.utc);self.g={'sport':'nfl','event_id':'g','model_version':'v1','matchup':'A @ H','home':'H','away':'A','start':'2026-10-17T18:00:00Z','publication_at':self.now.isoformat(),'forecast_available':True,'p_home':.4,'selections':[]}
 def test_unpriced_held_call_is_frozen_and_cannot_change(self):
  r=freeze([],[self.g],self.now);self.assertEqual(r[0]['side'],'away');self.assertEqual(r[0]['recommendation'],'Research only');self.assertIsNone(r[0]['price']);self.g['p_home']=.9;self.assertEqual(freeze(r,[self.g],self.now)[0]['p'],.4)
 def test_missing_and_postgame_are_not_backfilled(self):
  self.assertEqual(freeze([],[self.g],self.now+timedelta(days=2)),[]);self.g['forecast_available']=False;self.assertEqual(freeze([],[self.g],self.now),[])
 def test_quote_rejected_without_verification(self):
  self.g['selections']=[{'market':'ML','side':'away','price':150,'book':'Book','observed_at':self.now.isoformat(),'fresh':False}];r=freeze([],[self.g],self.now);self.assertIsNone(r[0]['price']);self.g['selections'][0]['fresh']=True;r=freeze([],[self.g],self.now);self.assertEqual(r[0]['price'],150)
 def test_result_requires_original_start_verified_time(self):
  self.g['selections']=[{'market':'ML','side':'away','price':150,'book':'Book','observed_at':self.now.isoformat(),'fresh':True}];r=freeze([],[self.g],self.now);end=self.now+timedelta(days=2);f={'sport':'nfl','id':'g','start':self.g['start'],'result_at':end.isoformat(),'y':0,'home_score':10,'away_score':20};s=settle(r,{'records':[f]},end);self.assertEqual(s[0]['result']['unit_profit'],1.5);f['start']='2026-10-18T18:00:00Z';self.assertIsNone(settle(r,{'records':[f]},end)[0]['result'])
 def test_legacy_no_price_or_recommendation_inferred(self):
  with tempfile.TemporaryDirectory() as t:
   f={'sport':'nfl','id':'g','version':'v','matchup':'A @ H','start':'2026-10-10T18:00Z','captured_at':'2026-10-09T18:00Z','p':.7,'y':1,'home_score':20,'away_score':10};r=build(Path(t),performance={'records':[f]},now=self.now)['records'][0];self.assertEqual(r['result']['status'],'Win');self.assertIsNone(r['price']);self.assertEqual(r['recommendation'],'Not recorded')
