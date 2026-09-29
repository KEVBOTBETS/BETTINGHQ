import copy, unittest
from datetime import datetime,timezone,timedelta
from pipeline.model import project,score_grid,market_probability,candidates,update_accuracy,accuracy_report
from pipeline.build import quotes,normalize
NOW=datetime(2026,10,10,16,tzinfo=timezone.utc)
class NHLModelTests(unittest.TestCase):
 def setUp(self):
  self.team={'current':{'gp':10,'gf_pg':3.2,'ga_pg':2.8},'prior':{'gp':82,'gf_pg':3.1,'ga_pg':2.9}}
  self.proj=project(self.team,self.team)
  self.game={'game_id':'1','season':2027,'season_type':2,'state':'pre','completed':False,'date':(NOW+timedelta(hours=4)).isoformat(),'day':'2026-10-10','home':'TOR','away':'MTL','projection':self.proj,'p_home':self.proj['p_home'],'home_goalie':{'confirmed':True},'away_goalie':{'confirmed':True},'home_score':None,'away_score':None}
 def test_distribution_normalizes_and_no_final_ties(self):
  grid=score_grid(3.2,2.7);self.assertAlmostEqual(sum(grid.values()),1);self.assertFalse(any(h==a for h,a in grid))
  p,_=market_probability(self.proj,'ML','home');q,_=market_probability(self.proj,'ML','away');self.assertAlmostEqual(p+q,1)
 def test_totals_and_spreads_conserve_probability_with_pushes(self):
  for market,line,sides in [('TOTAL',6,['over','under']),('ATS',-1,['home','away'])]:
   a,push=market_probability(self.proj,market,sides[0],line);b,other=market_probability(self.proj,market,sides[1],line if market=='TOTAL' else -line)
   self.assertAlmostEqual(push,other);self.assertAlmostEqual(a+b+push,1);self.assertGreater(push,0)
 def test_no_team_data_means_no_prediction(self):self.assertFalse(project({},self.team)['ratings_known'])
 def test_rest_adjustment_and_neutral_ice(self):
  self.assertAlmostEqual(project(self.team,self.team,neutral=True)['p_home'],.5)
  self.assertLess(project(self.team,self.team,home_rest=0)['p_home'],self.proj['p_home'])
 def test_real_two_sided_prices_only(self):
  raw={'odds':[{'provider':{'name':'Book'},'details':'TOR -120','overUnder':6}]};self.assertEqual(quotes(raw,NOW.isoformat()),[])
  raw['odds'][0]['moneyline']={'home':{'close':{'odds':'-110'}},'away':{'close':{'odds':'+100'}}}
  q=quotes(raw,NOW.isoformat());self.assertEqual(len(q),2);self.assertEqual(q[0]['opposite_price'],100)
  del raw['odds'][0]['moneyline']['away'];self.assertEqual(quotes(raw,NOW.isoformat()),[])
 def test_stale_preseason_and_unconfirmed_goalies_never_qualify(self):
  self.game['quotes']=[{'market':'ML','side':'home','line':None,'price':110,'opposite_price':-120,'book':'Book','observed_at':NOW.isoformat()}]
  for key,value in [('season_type',1),('state','in'),('stats_stale',True),('home_goalie',{'confirmed':False})]:self.assertTrue(candidates({**self.game,key:value},NOW)[0]['held'],key)
  g=copy.deepcopy(self.game);g['quotes'][0]['observed_at']=(NOW-timedelta(hours=2)).isoformat();self.assertTrue(candidates(g,NOW)[0]['held'])
 def test_market_blending_is_explicit(self):
  self.game['quotes']=[{'market':'ML','side':'home','line':None,'price':110,'opposite_price':-120,'book':'Book','observed_at':NOW.isoformat()}]
  r=candidates(self.game,NOW)[0];self.assertAlmostEqual(r['model_prob'],.25*r['raw_model_prob']+.75*r['market_fair_prob'],places=5)
 def test_freeze_is_immutable_and_results_do_not_backfill(self):
  records=update_accuracy({},[self.game],[],NOW.isoformat());old=copy.deepcopy(records['1'])
  update_accuracy(records,[{**self.game,'p_home':.9}],[],(NOW+timedelta(minutes=10)).isoformat());self.assertEqual(records['1']['p_home'],old['p_home'])
  final={**self.game,'completed':True,'state':'post','home_score':4,'away_score':3}
  update_accuracy(records,[final],[],(NOW+timedelta(hours=7)).isoformat());self.assertTrue(records['1']['result']['home_won'])
  self.assertEqual(update_accuracy({},[final],[],NOW.isoformat()),{});self.assertEqual(accuracy_report(records,2027,NOW.isoformat())['games']['winner']['n'],1)
 def test_toronto_date_and_confirmed_goalie(self):
  event={'id':'1','date':'2026-10-11T00:00Z','season':{'year':2027,'type':2},'status':{'type':{'state':'pre'}},'competitions':[{'competitors':[{'homeAway':s,'team':{'id':i,'abbreviation':s},'probables':[{'name':'probableStartingGoalie','status':{'type':'confirmed'},'athlete':{'displayName':'Goalie'}}]} for s,i in [('home','1'),('away','2')]]}]}
  g=normalize(event,NOW.isoformat());self.assertEqual(g['day'],'2026-10-10');self.assertTrue(g['home_goalie']['confirmed'])
if __name__=='__main__':unittest.main()
