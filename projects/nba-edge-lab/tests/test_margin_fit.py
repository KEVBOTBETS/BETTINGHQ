import unittest
from datetime import datetime, timedelta, timezone
from pipeline.margin_fit import fit_margins

class MarginFit(unittest.TestCase):
 def sample(self, relation):
  base=datetime(2026,11,1,18,tzinfo=timezone.utc);records={}
  for d in range(9):
   for i in range(30):
    start=base+timedelta(days=d);x=i-15
    records[f'{d}-{i}']={'event_id':f'{d}-{i}','kind':'game','league':'NCAAB','season':2027,'version':'ncaab-scoring-research-1.0','result':'Graded','start':start.isoformat(),'captured_at':(start-timedelta(hours=2)).isoformat(),'graded_at':(start+timedelta(hours=3)).isoformat(),'margin':x,'actual_margin':relation(x,d)}
  return {'records':records},base+timedelta(days=10)
 def test_forward_only_and_sufficient_sample(self):
  log,now=self.sample(lambda x,d:2*x+3)
  self.assertTrue(fit_margins(log,now,2027)['active'])
  self.assertFalse(fit_margins(log,now-timedelta(days=8),2027)['active'])
  self.assertFalse(fit_margins(log,now,2028)['active'])
  for r in log['records'].values():r['captured_at']=r['graded_at']
  self.assertEqual(fit_margins(log,now,2027)['games'],0)
 def test_does_not_promote_bad_later_date_correction(self):
  log,now=self.sample(lambda x,d:2*x+3 if d<6 else x)
  self.assertFalse(fit_margins(log,now,2027)['active'])
 def test_deduplicates_events(self):
  log,now=self.sample(lambda x,d:2*x)
  log['records'].update({'copy-'+k:dict(v) for k,v in list(log['records'].items())})
  self.assertEqual(fit_margins(log,now,2027)['games'],270)
