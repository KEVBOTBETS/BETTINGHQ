import unittest
from datetime import datetime,timezone
from tools.daily_ticket_evidence import build
NOW=datetime(2026,11,17,23,tzinfo=timezone.utc)
class DailyEvidenceTests(unittest.TestCase):
 def row(self,**extra):
  return dict(id='1',sport='nba',season=2027,version='v1',start='2026-11-17T20:00:00Z',captured_at='2026-11-17T19:00:00Z',result_at='2026-11-17T22:00:00Z',p=.6,y=1,margin=4,market_margin=3,actual_margin=3,total=220,market_total=215,actual_total=225,**extra)
 def test_forecast_accuracy_does_not_invent_roi(self):
  d=build({'records':[self.row()]},{'records':[]},{'records':[]},NOW)
  by={r['market']:r for r in d['cohorts']};self.assertEqual(by['ML']['all']['wins'],1);self.assertIsNone(by['ML']['all']['roi']);self.assertEqual(by['ATS']['all']['pushes'],1);self.assertEqual(by['TOTAL']['all']['wins'],1)
 def test_original_prices_only_and_preferred_price_range(self):
  m=dict(self.row(),event_id='1',price=-110,quote_at='2026-11-17T18:55:00Z',result={'status':'Win','verified_at':'2026-11-17T22:00:00Z'})
  d=build({'records':[self.row()]},{'records':[m,m]},{'records':[]},NOW);r=next(r for r in d['cohorts'] if r['market']=='ML');self.assertEqual(r['all']['n'],1);self.assertEqual(r['preferred']['priced'],1);self.assertAlmostEqual(r['preferred']['roi'],100/110)
  m['quote_at']='2026-11-17T21:00:00Z';d=build({'records':[self.row()]},{'records':[m]},{'records':[]},NOW);self.assertTrue(all(r['preferred']['priced']==0 for r in d['cohorts']))
  m.update(quote_at='2026-11-17T18:55:00Z',price=-500);d=build({'records':[self.row()]},{'records':[m]},{'records':[]},NOW);r=next(r for r in d['cohorts'] if r['market']=='ML');self.assertEqual(r['all']['priced'],1);self.assertEqual(r['preferred']['priced'],0)
 def test_no_future_results_or_postgame_capture(self):
  for k,value in [('captured_at','2026-11-17T21:00:00Z'),('result_at','2026-11-18T01:00:00Z')]:
   r=self.row();r[k]=value;self.assertFalse(build({'records':[r]},{'records':[]},{'records':[]},NOW)['cohorts'])
 def test_versions_and_seasons_do_not_mix(self):
  r=self.row();other={**r,'id':'2','version':'v2'};future={**r,'id':'3','season':2028};d=build({'records':[r,other,future]},{'records':[]},{'records':[]},NOW);self.assertEqual(len([x for x in d['cohorts'] if x['market']=='ML']),3)

class SourceVersionTests(unittest.TestCase):
 def test_version_comes_from_publisher_not_historical_results(self):
  import tempfile
  from pathlib import Path
  from tools.system_report import forecast_version
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);file=root/'projects/test/pipeline/model_accuracy.py';file.parent.mkdir(parents=True);file.write_text('VERSION = "publisher-v2"\n')
   self.assertEqual(forecast_version(root,'test',{}),'publisher-v2')
   self.assertEqual(forecast_version(root,'test',{'model_version':'explicit-v3'}),'explicit-v3')
   file.write_text('VERSION = str("dynamic")\n')
   self.assertIsNone(forecast_version(root,'test',{}))
