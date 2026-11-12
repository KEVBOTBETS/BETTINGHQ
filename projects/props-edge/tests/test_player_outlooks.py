import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from pipeline.player_outlooks import nba_rows,nhl_rows,publish,minutes
NOW=dt.datetime(2026,11,12,22,tzinfo=dt.timezone.utc)
GAME={'game_id':'1','date':(NOW+dt.timedelta(hours=2)).isoformat(),'away':'A','home':'B'}
def nba_history(pid='1',values=None):
 return [dict(player_id=pid,team='A',game_id=str(i),start=(NOW-dt.timedelta(days=i*2+1)).isoformat(),state='post',stats=dict(MIN='24:30',PTS='12',REB='5',AST='4',STL='0',BLK='1',TO='2',FG='4-8',**{'3PT':'2-4','FT':'2-2','OREB':'1','DREB':'4'})) for i in range(4)]
class OutlookTests(unittest.TestCase):
 def test_cached_injury_reports_preserve_original_freshness(self):
  from pipeline.nba_research import injury_coverage_usable
  for status in ['ok','cached','retained']:
   source={'status':status,'observed_at':(NOW-dt.timedelta(minutes=20)).isoformat()}
   self.assertTrue(injury_coverage_usable([],source,NOW))
   self.assertFalse(injury_coverage_usable([],source,NOW+dt.timedelta(hours=6)))
   self.assertFalse(injury_coverage_usable(None,source,NOW))
  self.assertFalse(injury_coverage_usable([],{'status':'unavailable','observed_at':NOW.isoformat()},NOW))
  self.assertFalse(injury_coverage_usable([],{'status':'cached','observed_at':(NOW+dt.timedelta(minutes=1)).isoformat()},NOW))

 def test_nba_real_zero_and_component_consistency(self):
  who={'id':'1','player':'Starter','position':'G'}
  rows=nba_rows([GAME],nba_history(),{'A':[who]},[],{},NOW)
  self.assertEqual(len(rows),1);s=rows[0]['stats']
  self.assertEqual(s['steals'],0);self.assertEqual(s['points'],12);self.assertEqual(s['rebounds'],5);self.assertEqual(s['pra'],21)
  self.assertEqual(minutes('24:30'),24.5)
 def test_bench_out_players_and_future_game_logs_are_excluded(self):
  who={'id':'1','player':'Starter','position':'G'}
  self.assertFalse(nba_rows([GAME],nba_history(),{'A':[who]},[{'name':'Starter','status':'Out'}],{},NOW))
  history=nba_history()
  for row in history:row['stats']['MIN']='4'
  self.assertFalse(nba_rows([GAME],history,{'A':[who]},[],{},NOW))
  history=nba_history()
  for row in history:row['start']=(NOW+dt.timedelta(days=1)).isoformat()
  self.assertFalse(nba_rows([GAME],history,{'A':[who]},[],{},NOW))
 def test_missing_stat_stays_missing(self):
  history=nba_history()
  for row in history:del row['stats']['AST']
  rows=nba_rows([GAME],history,{'A':[{'id':'1','player':'Starter'}]},[],{},NOW)
  self.assertNotIn('assists',rows[0]['stats']);self.assertNotIn('pra',rows[0]['stats'])
 def test_only_identified_goalie_and_projected_skaters(self):
  roster={'A':[{'id':'1','player':'Skater','position':'C'},{'id':'2','player':'Starter','position':'G'},{'id':'3','player':'Backup','position':'G'}]}
  stats={'A':{'season':20262027,'skaters':[{'playerId':1,'gamesPlayed':10,'goals':3,'assists':4,'points':7,'shots':20}], 'goalies':[{'playerId':2,'gamesPlayed':5,'shotsAgainst':150,'goalsAgainst':10}]}}
  inputs={'lineups':{'A':{'players':[{'name':'Skater','line':'f1','available':True}]}},'goalies':{'1':{'away':{'name':'Starter','confirmed':True}}}}
  rows=nhl_rows([GAME],roster,stats,inputs,[],20262027,NOW)
  self.assertEqual({r['player'] for r in rows},{'Skater','Starter'});self.assertEqual(next(r for r in rows if r['player']=='Starter')['stats']['saves'],28)
  inputs['lineups']['A']['players'][0]['available']=False
  self.assertEqual([r['player'] for r in nhl_rows([GAME],roster,stats,inputs,[],20262027,NOW)],['Starter'])
 def test_replacement_candidate_has_no_invented_history(self):
  rosters={'A':[{'id':'1','player':'Out Starter'},{'id':'2','player':'New Starter'}]}
  depth={'A':{'depthchart':[{'positions':{'pg':{'athletes':[{'id':'1'},{'id':'2'}]}}}]}}
  rows=nba_rows([GAME],[],rosters,[{'name':'Out Starter','status':'Out'}],depth,NOW)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['player'],'New Starter');self.assertEqual(rows[0]['role'],'Replacement candidate');self.assertFalse(rows[0]['stats'])
 def test_fresh_reported_current_season_counts_can_fill_official_outage(self):
  rosters={'A':[{'id':'1','player':'Skater','position':'C'}]}
  inputs={'year':2026,'lineups':{'A':{'players':[{'name':'Skater','line':'f1','available':True,'season':{'gamesPlayed':10,'goals':2,'assists':3,'points':5,'shots':20,'blocks':4}}]}}}
  rows=nhl_rows([GAME],rosters,{},inputs,[],20262027,NOW)
  self.assertEqual(rows[0]['stats']['shots'],2);self.assertEqual(rows[0]['stats']['blocks'],.4)
  inputs['year']=2025
  self.assertFalse(nhl_rows([GAME],rosters,{},inputs,[],20262027,NOW)[0]['stats'])
 def test_partial_nba_index_does_not_hide_uncovered_games(self):
  from pipeline.nba_research import uncovered_games
  games=[{'game_id':str(i)} for i in range(4)]
  missing=uncovered_games(games,[{'event_id':'0'},{'event_id':'1'}])
  self.assertEqual([g['game_id'] for g in missing],['2','3'])
  self.assertEqual(uncovered_games(games,[{'event_id':str(i)} for i in range(4)]),[])
 def test_no_prior_season_relabelling(self):
  self.assertFalse(nhl_rows([GAME],{'A':[{'id':'1','player':'Old','position':'C'}]},{'A':{'season':20252026}}, {},[],20262027,NOW))
 def test_freeze_after_start_remove_cancelled_or_ineligible_pregame_rows(self):
  row=dict(status='Pregame',id='r',player='Name',team='A',start=GAME['date'],stats={'points':10},day='2026-11-12')
  with tempfile.TemporaryDirectory() as folder:
   publish(folder,'NBA',[row],[GAME],NOW)
   publish(folder,'NBA',[],[GAME],NOW+dt.timedelta(minutes=1))
   saved=json.loads((Path(folder)/'state/player-stats-NBA-2026-11.json').read_text());self.assertEqual(saved,[])
   publish(folder,'NBA',[row],[GAME],NOW+dt.timedelta(minutes=2))
   publish(folder,'NBA',[],[],NOW+dt.timedelta(hours=3))
   data=json.loads((Path(folder)/'site/data/player-stats/nba/2026-11-12.json').read_text())
   self.assertEqual(data['rows'][0]['stats']['points'],10);self.assertEqual(data['rows'][0]['status'],'Frozen pregame outlook')
