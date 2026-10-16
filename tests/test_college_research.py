from copy import deepcopy
from datetime import datetime,timedelta,timezone
import unittest
from tools.college_research import diagnostics,freeze,settle,summary
NOW=datetime(2026,10,16,22,tzinfo=timezone.utc)

def ticket():
 legs=[{'game':'ncaaf|1','event_id':'1','sport':'ncaaf','start':'2026-10-17T18:00:00Z','publication_at':NOW.isoformat(),'observed_at':NOW.isoformat(),'book':'Book','price':-110,'probability':.55,'push_prob':.02,'model_version':'v','market':'ATS','side':'away','line':3,'pick':'Away +3'}, {'game':'ncaaf|2','event_id':'2','sport':'ncaaf','start':'2026-10-17T18:00:00Z','publication_at':NOW.isoformat(),'observed_at':NOW.isoformat(),'book':'Book','price':-110,'probability':.55,'push_prob':0,'model_version':'v','market':'TOTAL','side':'over','line':45,'pick':'Over 45'}]
 return {'day':'2026-10-17','target':500,'book':'Book','version':'game-parlays-v1','legs':legs,'metrics':{'base':{'all_win':.3}}}

class CollegeResearch(unittest.TestCase):
 def test_frozen_first_profile_and_no_backfill(self):
  t=ticket();rows=freeze([],[t],NOW);self.assertEqual(len(rows),1);changed=deepcopy(t);changed['legs'][0]['price']=200
  self.assertEqual(freeze(rows,[changed],NOW+timedelta(minutes=5))[0]['legs'][0]['price'],-110)
  self.assertFalse(freeze([],[t],NOW+timedelta(days=2)))
  future=deepcopy(t);future['legs'][0]['observed_at']=(NOW+timedelta(minutes=5)).isoformat();self.assertFalse(freeze([],[future],NOW))
  duplicate=deepcopy(t);duplicate['legs'][1]['game']='ncaaf|1';self.assertFalse(freeze([],[duplicate],NOW))
  mixed=deepcopy(t);mixed['legs'][1]['book']='Other';self.assertFalse(freeze([],[mixed],NOW))
 def test_verified_pushes_and_rescheduled_games(self):
  rows=freeze([],[ticket()],NOW);at=NOW+timedelta(days=1)
  games={k:{'date':'2026-10-17T18:00:00Z','completed':True,'home_score':24,'away_score':21} for k in ['1','2']}
  self.assertEqual(settle(rows,games,at.isoformat(),at)[0]['result']['status'],'All push');games['2']['home_score']=27
  r=settle(rows,games,at.isoformat(),at);self.assertEqual(r[0]['result']['status'],'Push-reduced');self.assertFalse(r[0]['result']['full_win']);self.assertEqual(summary(r)[0]['full_win_rate'],0)
  games['1']['date']='2026-10-18T18:00:00Z';self.assertIsNone(settle(rows,games,at.isoformat(),at)[0]['result'])
  games['1']['date']='2026-10-17T18:00:00Z';games['2']['completed']=False;self.assertIsNone(settle(rows,games,at.isoformat(),at)[0]['result'])
 def test_observed_residual_bands_exclude_future_results(self):
  rows=[]
  for i in range(20):
   start=NOW-timedelta(days=30-i)
   rows.append({'id':str(i),'sport':'ncaaf','event_id':str(i),'model':'current','version':'v1','cohort':'regular season','source_observed_at':(start-timedelta(hours=2)).isoformat(),'captured_at':(start-timedelta(hours=1)).isoformat(),'start':start.isoformat(),'result_observed_at':(start+timedelta(hours=4)).isoformat(),'margin':2,'result':{'margin':2+i-10}})
  bad=deepcopy(rows[0]);bad.update(event_id='bad',result={'margin':10000},result_observed_at=(NOW+timedelta(days=1)).isoformat());rows.append(bad)
  d=diagnostics({'forecasts':rows,'market_forecasts':[]},NOW)['margin_errors'][0]
  self.assertEqual(d['n'],20);self.assertAlmostEqual(d['bias'],-.5);self.assertAlmostEqual(d['mae'],5);self.assertEqual(len(d['residual_90']),2)
