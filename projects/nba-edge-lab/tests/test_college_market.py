import unittest
from datetime import datetime, timezone, timedelta
from pipeline.college_market import project_market
from pipeline.model import candidates

class CollegeMarket(unittest.TestCase):
 def setUp(self):
  self.now=datetime.now(timezone.utc)
  self.p={'ratings_known':True,'mu':2,'raw_mu':2,'margin_sd':12,'total':150,'total_sd':18,'p_home':.56}
  self.g={'game_id':'42','season':2027,'season_type':2,'home':{'abbr':'H'},'away':{'abbr':'A'},'tipoff':(self.now+timedelta(hours=2)).isoformat(),'state':'pre','projection':self.p,'quotes':[{'book':'Draft Kings','market':'ATS','side':side,'line':line,'price':-110,'opposite_price':-110,'observed_at':self.now.isoformat()} for side,line in [('home',-31),('away',31)]]}
 def test_large_favourite(self):
  p=project_market(self.g,self.now);self.assertEqual(p['mu'],28);self.assertEqual(p['proj_home_pts']-p['proj_away_pts'],28);self.assertEqual(p['raw_mu'],2)
  self.g['projection']=p;rows=candidates(self.g,self.now);self.assertTrue(all(.3<r['model_prob']<.7 for r in rows))
 def test_away_favourite(self):
  for q in self.g['quotes']:q['line']*=-1
  self.assertEqual(project_market(self.g,self.now)['mu'],-28)
 def test_stale_unpaired_wrong_book(self):
  self.assertIs(project_market(self.g,self.now+timedelta(minutes=91)),self.p)
  self.g['quotes'][1]['book']='Other';self.assertIs(project_market(self.g,self.now),self.p)
