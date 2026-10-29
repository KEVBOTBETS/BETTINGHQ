import json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from pipeline import public_research as P
NOW=datetime(2026,10,12,16,tzinfo=timezone.utc)
GAME={'game_id':'g','date':'2026-10-12T17:00:00Z','home':'BUF','away':'FLA','home_name':'Buffalo Sabres','away_name':'Florida Panthers'}
class PublicResearch(unittest.TestCase):
 def test_embedded_public_page_and_exact_goalie_confirmation(self):
  raw={'data':[{'dateGmt':GAME['date'],'homeTeamName':'Buffalo Sabres','awayTeamName':'Florida Panthers','awayGoalieName':'Real Goalie','awayNewsStrengthName':'Confirmed','awayNewsCreatedAt':'2026-10-12T15:30Z','awayNewsSourceUrl':'https://example.com/report','homeNewsStrengthName':'Likely'}]}
  html='<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':raw}})+'</script>'
  rows=P.goalie_reports(P.embedded(html),[GAME],NOW,NOW.isoformat());self.assertTrue(rows['g']['away']['confirmed']);self.assertFalse(rows['g']['home']['confirmed'])
  self.assertEqual(P.goalie_reports(raw,[{**GAME,'date':'2026-10-13T17:00Z'}],NOW,NOW.isoformat()),{})
  self.assertEqual(P.goalie_reports(raw,[GAME],NOW,(NOW-timedelta(hours=7)).isoformat()),{})
 def test_roles_merge_powerplay_injured_and_unknown(self):
  data={'combinations':{'teamAbbreviation':'BUF','teamName':'Buffalo Sabres','teamSlug':'buffalo-sabres','updatedAt':NOW.isoformat(),'players':[{'name':'Player One','categoryIdentifier':'ev','groupIdentifier':'f1'},{'name':'Player One','categoryIdentifier':'pp','groupIdentifier':'pp1'},{'name':'Player Two','categoryIdentifier':'oi','groupIdentifier':'ir'}]}}
  r=P.lineup(data,NOW,NOW.isoformat());self.assertEqual(r['players'][0]['power_play'],'pp1');self.assertTrue(r['players'][0]['available']);self.assertFalse(r['players'][1]['available'])
  self.assertIsNone(P.lineup(data,NOW,(NOW-timedelta(days=3)).isoformat()))
 def test_failed_import_never_renews_timestamp(self):
  with tempfile.TemporaryDirectory() as folder:
   cache=P.Cache(NOW,Path(folder)/'cache.json');old=(NOW-timedelta(days=2)).isoformat();cache.data[P.DF]={'at':old,'data':{'old':True}}
   with patch.object(P,'download',side_effect=OSError('No source')):self.assertEqual(cache.get(P.DF,lambda x:x,1),{'old':True})
   self.assertEqual(cache.health[P.DF]['observed_at'],old);self.assertEqual(cache.data[P.DF]['at'],old)
 def test_advertised_downloads_only_and_csv_situations(self):
  urls=P.links('<a href="moneypuck/playerData/seasonSummary/2026/regular/teams.csv">Download</a>');self.assertEqual(urls,['https://moneypuck.com/moneypuck/playerData/seasonSummary/2026/regular/teams.csv'])
  r=P.csv_rows(b'playerId,situation,icetime,I_F_goals,private_field\n1,all,100,1,x\n1,other,10,0,x\n');self.assertEqual(len(r),1);self.assertNotIn('private_field',r[0])
 def test_unknown_goalie_has_no_invented_adjustment(self):
  self.assertIsNone(P.goalie_effect({},'BUF',{'name':'Unknown','confirmed':False}))

 def test_same_name_different_goalie_ids_do_not_mix(self):
  def row(player):return {'playerId':player,'name':'Same Name','team':'BUF','situation':'all','icetime':6000,'xGoals':8,'goals':5}
  data={'year':2026,'statistics':{'2026':{'goalies':{'rows':[row('1')]}},'2025':{'goalies':{'rows':[row('2')]}}}}
  self.assertIsNone(P.goalie_effect(data,'BUF',{'name':'Same Name','confirmed':True}))
  data['statistics']['2025']['goalies']['rows'][0]['playerId']='1'
  self.assertGreater(P.goalie_effect(data,'BUF',{'name':'Same Name','confirmed':True})['gsax_per60'],0)

class CalendarGoalies(unittest.TestCase):
 def test_only_advertised_date_pages_are_retained(self):
  h='<a href="/starting-goalies/2026-10-13">Next</a><a href="https://evil.com/starting-goalies/2026-10-13">Bad</a><script id="__NEXT_DATA__">{"props":{"pageProps":{"data":[]}}}</script>'
  r=P.embedded(h);self.assertEqual(r['_advertised_goalie_pages'],['https://www.dailyfaceoff.com/starting-goalies/2026-10-13']);self.assertEqual(r['data'],[])
