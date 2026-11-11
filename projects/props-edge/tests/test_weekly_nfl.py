import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from pipeline.weekly_nfl import build_snapshot,merge_history,publish,schedule_events,extra_form

NOW=datetime(2026,11,11,18,tzinfo=timezone.utc)
A={'id':'1','displayName':'Alfa','abbreviation':'ALF'};B={'id':'2','displayName':'Beta','abbreviation':'BET'}
C={'id':'3','displayName':'Charlie','abbreviation':'CHA'};D={'id':'4','displayName':'Delta','abbreviation':'DEL'}
def event(week,home=A,away=B):
 return {'id':f'{home["id"]}-{week}','date':(NOW+timedelta(days=1+7*(week-11))).isoformat(),'season':{'year':2026,'type':2},'week':{'number':week},'status':{'type':{'state':'pre' if week>=11 else 'post','completed':week<11}},'competitions':[{'competitors':[{'homeAway':'home','team':home},{'homeAway':'away','team':away}]}]}
def roster(team,rows):
 return team['displayName'],{'team':team,'athletes':[{'items':[{'id':str(i),'displayName':name,'position':{'abbreviation':pos},'status':{'name':'Active'},**({'injuries':[{'status':'Out'}]} if name=='Out Player' else {})} for i,name,pos in rows]}]}
def fixtures():
 events=[event(w) for w in range(1,19) if w!=12]+[event(w,C,D) for w in range(1,19)]
 rosters=[roster(A,[(1,'Quarterback','QB'),(2,'Receiver','WR'),(3,'Lineman','OT'),(4,'Defender','LB'),(5,'Kicker','K'),(6,'Punter','P'),(7,'Out Player','RB'),(8,'Long Snapper','LS')]),roster(B,[(9,'Other Receiver','WR')])]
 projections=[]
 for week in range(11,19):
  for player,market,value in [('Quarterback','Passing yards',281.4),('Quarterback','Pass attempts',35.2),('Receiver','Receptions',0),('Defender','Tackles + assists',7.2),('Kicker','Field goals made',1.8),('Out Player','Rushing yards',45)]:
   projections.append({'player':player,'team':'Alfa','event_id':f'1-{week}','market':market,'projection':value,'samples':8,'roster_verified':True})
 summaries=[{'_weekly_completed':True,'_weekly_event_date':(NOW-timedelta(days=7*i)).isoformat(),'boxscore':{'players':[{'statistics':[{'type':'punting','keys':['punts','puntingYards'],'athletes':[{'athlete':{'id':'6'},'stats':['4','180']}]}]}]}} for i in (1,2)]
 return projections,rosters,events,summaries

class WeeklyNFLTests(unittest.TestCase):
 def snapshot(self,now=NOW):return build_snapshot(*fixtures(),2026,now)
 def test_all_positions_and_real_zero_are_retained(self):
  result=self.snapshot();rows={r['player']:r for r in result['rows'] if r['week']==11}
  self.assertEqual({r['position'] for r in rows.values()},{'QB','WR','OT','LB','K','P','RB','LS'})
  self.assertEqual(rows['Receiver']['stats']['receptions'],0)
  self.assertEqual(rows['Quarterback']['stats']['pass_att'],35.2)
  self.assertEqual(rows['Punter']['stats']['punts'],4)
  self.assertEqual(rows['Punter']['stats']['punt_avg'],45)
  self.assertFalse(rows['Lineman']['stats']);self.assertFalse(rows['Out Player']['stats'])
  self.assertIn('early',next(r for r in result['rows'] if r['week']==13)['phase'])
 def test_byes_are_derived_only_from_a_complete_17_game_schedule(self):
  result=self.snapshot();rows=[r for r in result['rows'] if r['week']==12 and r['team_id']=='1']
  self.assertTrue(rows);self.assertTrue(all(r['status']=='Bye week' and not r['stats'] for r in rows))
  p,rs,events,s=fixtures();events=[e for e in events if e['id']!='1-18']
  result=build_snapshot(p,rs,events,s,2026,NOW)
  self.assertEqual(next(r for r in result['rows'] if r['week']==12 and r['team_id']=='1')['status'],'Schedule unavailable')
 def test_capture_updates_before_kickoff_and_freezes_after_it(self):
  first=self.snapshot();before=copy.deepcopy(first);history=merge_history({},first,NOW)
  updated=self.snapshot(NOW+timedelta(hours=1));row=next(r for r in updated['rows'] if r['player']=='Quarterback' and r['week']==11);row['stats']['pass_yds']=290
  history=merge_history(history,updated,NOW+timedelta(hours=1));saved=next(r for r in history['rows'] if r['id']==row['id'])
  self.assertEqual(saved['first_captured_at'],NOW.isoformat());self.assertEqual(saved['stats']['pass_yds'],290)
  after=NOW+timedelta(days=2);future=self.snapshot(after);history=merge_history(history,future,after)
  frozen=next(r for r in history['rows'] if r['id']==row['id']);self.assertEqual(frozen['stats']['pass_yds'],290);self.assertEqual(frozen['phase'],'frozen')
  self.assertEqual(first,before)
 def test_past_weeks_are_not_backfilled(self):
  result=self.snapshot(NOW+timedelta(days=2));self.assertFalse(any(r['week']==11 for r in result['rows']))
  fake=self.snapshot();fake['rows']=[{**fake['rows'][0],'start':(NOW-timedelta(days=1)).isoformat(),'captured_at':NOW.isoformat(),'stats':{'pass_yds':999}}]
  rows=merge_history({},fake,NOW)['rows'];self.assertFalse(rows[0]['stats'])
 def test_changed_kickoff_does_not_freeze_a_tbd_game_early(self):
  first=self.snapshot();r=next(r for r in first['rows'] if r['player']=='Quarterback' and r['week']==11)
  history={'rows':[{**r,'start':(NOW-timedelta(hours=1)).isoformat(),'captured_at':(NOW-timedelta(days=1)).isoformat(),'time_tbd':True}]}
  merged=merge_history(history,first,NOW)
  row=next(x for x in merged['rows'] if x['id']==r['id']);self.assertEqual(row['start'],r['start']);self.assertNotEqual(row['phase'],'frozen')
 def test_all_star_rosters_are_not_counted_as_nfl_franchises(self):
  p,rs,events,s=fixtures();rs.append(roster({'id':'31','displayName':'Afc'},[(6,'Punter','P')]))
  result=build_snapshot(p,rs,events,s,2026,NOW)
  self.assertNotIn('31',result['roster_teams'])
  self.assertEqual(next(r for r in result['rows'] if r['week']==11 and r['player']=='Punter')['stats']['punts'],4)
 def test_duplicate_roster_identity_has_no_projection(self):
  p,rs,events,s=fixtures();rs.append(roster(C,[(1,'Quarterback','QB')]))
  result=build_snapshot(p,rs,events,s,2026,NOW)
  self.assertTrue(all(not r['stats'] for r in result['rows'] if r['player_id']=='1'))
 def test_positive_only_interception_rows_do_not_create_inflated_forecasts(self):
  summaries=[]
  for i in range(4):
   groups=[{'type':'defensive','keys':['totalTackles'],'athletes':[{'athlete':{'id':'4'},'stats':['5']}]}]
   if i<2:groups.append({'type':'interceptions','keys':['interceptions'],'athletes':[{'athlete':{'id':'4'},'stats':['1']}]})
   summaries.append({'_weekly_completed':True,'_weekly_event_date':(NOW-timedelta(days=i+1)).isoformat(),'boxscore':{'players':[{'statistics':groups}]}})
  values,_=extra_form(summaries,NOW);self.assertNotIn('def_int',values.get('4',{}))
  for summary in summaries[2:]:summary['boxscore']['players'][0]['statistics'].append({'type':'interceptions','keys':['interceptions'],'athletes':[]})
  values,_=extra_form(summaries,NOW);self.assertLess(values['4']['def_int']['value'],1)
  for summary in summaries:summary['boxscore']['players'][0]['statistics']=[g for g in summary['boxscore']['players'][0]['statistics'] if g['type']!='defensive']
  values,_=extra_form(summaries,NOW);self.assertNotIn('def_int',values.get('4',{}))
 def test_atomic_publication_has_all_weeks_and_exact_versions(self):
  with tempfile.TemporaryDirectory() as folder:
   manifest=publish(self.snapshot(),folder);self.assertEqual(len(manifest['weeks']),18)
   for week in manifest['weeks']:
    data=json.loads((Path(folder)/'site/data/nfl-weekly'/week['file']).read_text())
    self.assertEqual(data['generated_at'],manifest['generated_at']);self.assertEqual(len(data['rows']),week['players'])
   self.assertTrue((Path(folder)/'state/nfl-weekly-2026.json').exists())
 def test_nfl_schedule_supplies_january_week_18(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'meta.json').write_text(json.dumps({'season':2026,'generated_at':NOW.isoformat()}))
   (root/'games.json').write_text(json.dumps([{'game_id':'jan','date':'2027-01-10T18:00Z','week':18,'season_type':2,'home_name':'Alfa','away_name':'Beta','completed':False,'status':'TBD'}]))
   rows=schedule_events([event(11)],2026,NOW,root)
   self.assertEqual(next(e for e in rows if e['id']=='jan')['week']['number'],18)

if __name__=='__main__':unittest.main()
