import unittest
from datetime import datetime,timezone
from pipeline.conference_availability import parse,advertised
NOW=datetime(2026,10,29,2,tzinfo=timezone.utc)
GAME={'game_id':'1','date_utc':'2026-10-31T16:00Z','away':{'id':'a','name':'Wisconsin Badgers'},'home':{'id':'h','name':'Iowa Hawkeyes'}}
def page(date='Wed Oct 28, 5:00 PM'):
 return '<h1>Wisconsin at Iowa</h1><p>Latest: Initial posted '+date+' PT</p><time datetime="2026-10-29T01:00Z">Fresh page</time><a href="https://bigten.org/fb/availability-reports/">Original</a><div class="teams2"><div class="card"><h3><a>Wisconsin</a><span class="counts">1 Out</span></h3><table><tr><td>Player One #3</td><td>QB</td><td>Out</td></tr></table></div><div class="card"><h3><a>Iowa</a></h3><table><tr><td>Player Two #4</td><td>RB</td><td>Questionable</td></tr></table></div></div><section class="unofficial"><table><tr><td>Fake</td><td>QB</td><td>Out</td></tr></table></section>'
class ConferenceAvailability(unittest.TestCase):
 def test_dated_report_with_original_source_and_no_unofficial_rows(self):
  rows=parse(page(),GAME,'Wisconsin','Iowa','https://kickoffstatus.com/games/2026-10-31-wisconsin-at-iowa/',NOW);self.assertEqual(len(rows),2);self.assertEqual(rows[0][1]['name'],'Player One');self.assertEqual(rows[0][1]['reported_at'],'2026-10-28T17:00:00-07:00');self.assertEqual(rows[0][1]['game_id'],'1');self.assertIn('bigten.org',rows[0][1]['official_source_url']);self.assertNotIn('confirmed',rows[0][1])
  self.assertEqual(parse(page('Tue Oct 20, 5:00 PM'),GAME,'Wisconsin','Iowa','url',NOW),[]);self.assertEqual(parse(page('Fri Oct 30, 5:00 PM'),GAME,'Wisconsin','Iowa','url',NOW),[]);self.assertEqual(parse(page().replace('bigten.org','example.com'),GAME,'Wisconsin','Iowa','url',NOW),[])
 def test_advertised_unique_game_exact_kickoff(self):
  h='<a class="card game" href="/games/2026-10-31-wisconsin-at-iowa/"><div class="meta">Big Ten · Sat Oct 31 · 9:00 AM PT<span class="stage">Initial</span></div><div class="team-line"><span class="nm">Wisconsin</span></div><div class="team-line"><span class="nm">@ Iowa</span></div></a>'
  self.assertEqual(len(advertised(h,[GAME],NOW)),1);self.assertEqual(advertised(h,[GAME,GAME],NOW),[]);self.assertEqual(advertised(h.replace('9:00','10:00'),[GAME],NOW),[]);self.assertEqual(advertised(h.replace('Initial','Pending'),[GAME],NOW),[])
