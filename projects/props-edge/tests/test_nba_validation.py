import copy,unittest
from datetime import datetime,timezone,timedelta
from pipeline.nba_validation import track,report
class Validation(unittest.TestCase):
 now=datetime(2026,10,29,20,tzinfo=timezone.utc)
 def props(self):return {'generated_at':self.now.isoformat(),'source_model_at':self.now.isoformat(),'milestone_forecasts':[{'event_id':'e','athlete_id':'p','player':'One','team':'A','market':'Points','line':19.5,'threshold':20,'model_version':'v1','model_prob':.6,'start_time':'2026-10-29T23:00Z'}],'quotes':[]}
 def test_only_pregame_capture_first_probability_immutable(self):
  p=self.props();a=track({},p,[],self.now);self.assertEqual(len(a['records']),1);p['milestone_forecasts'][0]['model_prob']=.8;track(a,p,[],self.now+timedelta(minutes=1));self.assertEqual(a['records'][0]['probability'],.6)
  self.assertEqual(track({},p,[],self.now+timedelta(hours=4))['records'],[]);self.assertEqual(track({},p,[],self.now-timedelta(hours=1))['records'],[])
 def test_final_played_boxscores_only_and_correlated_counts(self):
  p=self.props();p['milestone_forecasts'].append({**p['milestone_forecasts'][0],'threshold':25,'line':24.5});a=track({},p,[],self.now)
  row={'game_id':'e','player_id':'p','team':'A','state':'post','start':'2026-10-29T23:00Z','stats':{'MIN':'30','PTS':'24'}}
  track(a,{},[{**row,'state':'in'},{**row,'stats':{'MIN':'0','PTS':'24'}}],self.now+timedelta(hours=5));self.assertTrue(all(r['result'] is None for r in a['records']))
  track(a,{},[row],self.now+timedelta(hours=5));self.assertEqual([r['result'] for r in a['records']],[1,0]);r=report(a,self.now+timedelta(hours=5));self.assertEqual(r['overall']['contracts'],2);self.assertEqual(r['overall']['events'],1);self.assertEqual(r['overall']['players'],1);self.assertFalse(r['validated']);self.assertNotIn('roi',r)
 def test_last_same_book_observed_offer_only_near_start(self):
  p=self.props();q={'event_id':'e','athlete_id':'p','market':'Points','side':'over','line':19.5,'price_american':150,'book':'Book','price_source':'book','observed_at':self.now.isoformat()};p['quotes']=[q];a=track({},p,[],self.now)
  later=self.now+timedelta(hours=2,minutes=45);p['generated_at']=later.isoformat();p['quotes']=[{**q,'price_american':130,'observed_at':later.isoformat()}];track(a,p,[],later);r=report(a,self.now+timedelta(hours=5));self.assertEqual(r['near_start_prices']['pairs'],1);self.assertGreater(r['near_start_prices']['average_decimal_price_advantage'],0)
  p['quotes'][0]['price_source']='model';p['quotes'][0]['price_american']=100;track(a,p,[],later);self.assertEqual(a['records'][0]['prices']['Book']['latest']['price'],130)
