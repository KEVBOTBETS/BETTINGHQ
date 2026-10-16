import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from tools.football_public_odds import parse,bundles,enrich,agreement,start_time
from tools.research.cfb_ingest import aggregate
from tools.research.insights import stats,first,groups,price_band,price_group,drift,team_bias,capture_context,weekly,CONTEXT,build
N=datetime(2026,10,16,23,tzinfo=timezone.utc)
def football_html(price='-150',line=None):
 def cell(side,p):return '<div class="'+side+'-cell"><a class="odds-cta">'+('' if line is None else ('-3.5' if side=='home' else '+3.5'))+'<span class="__american">'+p+'</span></a></div>'
 return '<div>Last updated Oct 16, 2026, 6:55 PM ET</div><table id="'+('moneyline-table' if line is None else 'spread-table')+'"><tr class="oddsGameRow"><td><div class="game-time">Tomorrow, 12:00</div><div class="teams-div"><div class="away-cell"><strong>A</strong></div><div class="home-cell"><strong>H</strong></div></div></td><td class="liveOddsCell" data-book="DraftKings">'+cell('away','+130')+cell('home',price)+'</td></tr></table>'
def call(i,status='Win',price=None,version='v1',p=.7):
 return {'sport':'nfl','event_id':str(i),'version':version,'matchup':'A @ H','start':(N-timedelta(days=60-i)).isoformat(),'captured_at':(N-timedelta(days=61-i)).isoformat(),'p':p,'price':price,'recommendation':'Research only','result':None if status=='Pending' else {'status':status,'verified_at':(N-timedelta(days=59-i)).isoformat(),'unit_profit':(1 if status=='Win' else -1) if price else None}}
class UpgradeTests(unittest.TestCase):
 def test_exact_identity_stamp_pairing_and_future_gate(self):
  g={'game_id':'1','state':'pre','home':'H','away':'A','date':'2026-10-17T16:00Z'};r=parse(football_html(),[g],N,'ncaaf');self.assertEqual(len(r),2);self.assertEqual(bundles(r)[0][1]['ml_home'],-150)
  self.assertEqual(parse(football_html(),[{**g,'date':'2026-10-17T17:00Z'}],N,'ncaaf'),[])
  self.assertEqual(parse(football_html(),[g],N+timedelta(hours=2),'ncaaf'),[])
  self.assertEqual(parse(football_html().replace('+130','bad'),[g],N,'ncaaf'),[])
  self.assertEqual(parse(football_html().replace('DraftKings','consensus'),[g],N,'ncaaf'),[])
 def test_fallback_does_not_overwrite_complete_primary_or_renew_stamp(self):
  g={'game_id':'1','home':'H','away':'A','date':'2026-10-17T16:00Z','odds':{'book':'DraftKings','observed_at':N.isoformat()}}
  r=enrich([g],'ncaaf',N,football_html(),publish=False);self.assertEqual(r['repaired_games'],1);self.assertEqual(g['odds']['observed_at'],'2026-10-16T22:55:00+00:00')
  g['odds']['ml_home']=-180;self.assertEqual(enrich([g],'ncaaf',N,football_html(),publish=False)['repaired_games'],0);self.assertEqual(g['odds']['ml_home'],-180)
 def test_same_book_is_one_vote_and_line_changes_not_price_matches(self):
  q={'book':'Draft Kings','observed_at':N.isoformat(),'ml_home':-150,'ml_away':130};v={**q,'book':'DraftKings','ml_home':-220};a=agreement(q,v,N)[0];self.assertTrue(a['same_book']);self.assertEqual(a['independent_books'],1);self.assertEqual(a['status'],'Price disagreement')
  self.assertEqual(agreement(q,{**v,'observed_at':(N-timedelta(hours=2)).isoformat()},N),[])
 def test_explicit_date_and_year_rollover(self):
  self.assertEqual(start_time('Oct 18, 9:30',N).hour,9);self.assertEqual(start_time('Jan 2, 13:00',datetime(2026,12,31,tzinfo=timezone.utc)).year,2027)
 def test_favourite_bands_and_missing_prices(self):
  rows=[call(1,price=-150),call(2,'Loss',price=200),call(3),call(4,'Pending')];s=stats(rows);self.assertEqual(s['graded'],3);self.assertEqual(s['priced'],2);self.assertEqual(s['profit'],0);self.assertEqual(s['pending'],1)
  self.assertEqual(price_group(rows[2]),'No recorded odds');self.assertIn('−101',price_band(rows[0]));self.assertIn('+200',price_band(rows[1]));self.assertEqual(len(groups(rows,price_group)),3)
 def test_first_capture_and_version_dedup(self):
  a=call(1);b={**a,'version':'v2','captured_at':(N-timedelta(days=60)+timedelta(hours=1)).isoformat(),'p':.2};self.assertEqual(first([b,a])[0]['p'],.7);self.assertEqual(first([b,a],'v2')[0]['p'],.2)
 def test_drift_requires_games_dates_and_matching_version(self):
  rows=[{**call(i,'Win' if i<30 else 'Loss',p=.9),'start':(N-timedelta(days=21-i//3)).isoformat()} for i in range(60)];d=drift(rows);self.assertTrue(d['alert']);self.assertGreater(d['change'],0)
  self.assertEqual(drift(rows[:20])['needed'],60);rows[-1]['version']='new';self.assertEqual(drift(rows)['status'],'Choose one model version')
 def test_team_bias_point_of_view(self):
  r={'id':'a','sport':'nfl','version':'v','matchup':'A @ H','start':N.isoformat(),'captured_at':(N-timedelta(days=1)).isoformat(),'margin':3,'actual_margin':7};d={x['team']:x for x in team_bias([r],'nfl')};self.assertEqual(d['H']['bias'],4);self.assertEqual(d['A']['bias'],-4);self.assertFalse(d['H']['enough'])
 def test_availability_context_immutable_and_not_invented_confirmation(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);g={'sport':'nfl','event_id':'a','matchup':'A @ H','start':(N+timedelta(days=1)).isoformat(),'models':[{'model':'current','version':'v','source_observed_at':N.isoformat()}],'availability':{'sides':[{'team':'H','starter':'Q','starter_confirmed':False,'role_status':'expected','source':'Depth chart','observed_at':N.isoformat()}]}}
   a=capture_context(root,{'games':[g]},N);b=capture_context(root,{'games':[g]},N+timedelta(minutes=1));self.assertEqual(a,b);self.assertFalse(a[0]['sides'][0]['starter_confirmed']);g['availability']['sides'][0]['role_status']='uncertain';c=capture_context(root,{'games':[g]},N+timedelta(minutes=2));self.assertEqual(len(c),2);self.assertEqual(c[0],a[0])
 def test_weekly_uses_toronto_result_time_not_guessed_start(self):
  r=call(58);r['result']['verified_at']='2026-10-12T01:00Z';s=weekly([r],N);self.assertEqual(s['current']['graded'],0);self.assertEqual(s['previous']['graded'],1);r['result']['verified_at']=None;self.assertEqual(weekly([r],N)['previous']['graded'],0)
 def test_future_results_do_not_enter_diagnostics(self):
  with tempfile.TemporaryDirectory() as t:
   r=call(2);r['result']['verified_at']=(N+timedelta(days=1)).isoformat();d=build(Path(t),calls={'records':[r]},performance={'records':[]},research={'games':[]},now=N);s=next(x for x in d['sections'] if x['sport']=='nfl' and x['version']=='all');self.assertEqual(s['summary']['graded'],0);self.assertEqual(s['summary']['pending'],1)
 def test_cfb_official_results_and_play_exclusions(self):
  g={'game_id':'1','completed':True,'date_utc':'2026-10-10T16:00Z','home':{'abbr':'H'},'away':{'abbr':'A'},'home_score':20,'away_score':10};rows=[]
  for side,team in [(1,'H'),(2,'A')]:
   for i in range(20):rows.append({'game_id':1,'id':str(side)+'-'+str(i),'season':2026,'seasonType':2,'status_type_completed':True,'homeTeamAbbrev':'H','awayTeamAbbrev':'A','homeFinalScore':20,'awayFinalScore':10,'homeTeamId':1,'awayTeamId':2,'pos_team_id':side,'rush':True,'EPA':.2,'statYardage':4})
  rows+=[{**rows[0],'id':'kneel','kneel_down':True}];out=aggregate(rows,{'1':g},N);self.assertEqual(len(out),2);self.assertEqual(sum(r['plays'] for r in out),40);self.assertEqual(aggregate(rows,{'1':{**g,'home_score':21}},N),[]);self.assertEqual(aggregate(rows,{'1':{**g,'completed':False}},N),[])
