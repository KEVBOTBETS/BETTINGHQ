import copy
import unittest
from datetime import datetime,timezone
from pipeline.public_odds import parse,parse_vegas,fetch,URL,VEGAS_URL
from unittest.mock import patch
NOW=datetime(2026,10,10,16,15,tzinfo=timezone.utc)
GAME={'game_id':'g1','date':'2026-10-10T17:00:00Z','state':'pre','home':'BOS','away':'PHI'}
def cell(book,away,home):
 return f'<td class="liveOddsCell" data-book="{book}" data-date="old-price-change"><div class="away-cell"><a class="odds-cta">{away}</a></div><div class="home-cell"><a class="odds-cta">{home}</a></div></td>'
def quote(p):return f'<span class="American __american">{p}</span><span class="__decimal">2.15</span>'
def page(market,cells,away='PHI',home='BOS',time='Today, 13:00',updated='Oct 10, 2026, 12:08 PM'):
 return f'<p>Last updated {updated} ET</p><table id="{market}-table"><tr class="oddsGameRow"><td><div class="game-time">{time}</div><div class="teams-div"><div class="away-cell"><strong>{away}</strong></div><div class="home-cell"><strong>{home}</strong></div></div><div class="opening-lines-div">{quote("+9999")}</div></td>{cells}</tr></table>'
class PublicOdds(unittest.TestCase):
 def test_named_same_book_prices_only_and_source_timestamp(self):
  html=page('moneyline',cell('DraftKings',quote('+115'),quote('−135'))+cell('Consensus',quote('+130'),quote('-140')))
  rows=parse(html,[GAME],NOW);self.assertEqual(len(rows),2);a=rows[0][1];self.assertEqual(a['price'],115);self.assertEqual(a['opposite_price'],-135);self.assertEqual(a['book'],'DraftKings');self.assertEqual(a['observed_at'],'2026-10-10T16:08:00+00:00');self.assertEqual(a['source_price_changed_at'],'old-price-change')
 def test_exact_date_time_and_unique_match(self):
  html=page('moneyline',cell('Book',quote('+115'),quote('-135')))
  self.assertEqual(parse(html,[{**GAME,'date':'2026-10-11T17:00Z'}],NOW),[]);self.assertEqual(parse(html,[GAME,GAME],NOW),[]);self.assertEqual(parse(page('moneyline',cell('Book',quote('+115'),quote('-135')),time='Today, 14:00'),[GAME],NOW),[])
 def test_mismatched_lines_missing_side_and_decimal_rejected(self):
  for html in [page('spread',cell('Book','+1.5 '+quote('-220'),'-2.5 '+quote('+190'))),page('total',cell('Book','o 5.5 '+quote('-115'),'u 6.5 '+quote('-105'))),page('moneyline',cell('Book',quote('2.15'),quote('-135'))),page('moneyline',cell('Book',quote('+115'),'OFF'))]:self.assertEqual(parse(html,[GAME],NOW),[])
 def test_spreads_totals_evens_and_no_openers(self):
  rows=parse(page('spread',cell('Book','+1.5 '+quote('-220'),'-1.5 '+quote('+190'))),[GAME],NOW);self.assertEqual(rows[0][1]['line'],1.5)
  rows=parse(page('total',cell('Book','o 5.5 '+quote('-115'),'u 5.5 '+quote('even'))),[GAME],NOW);self.assertEqual(rows[0][1]['side'],'over');self.assertEqual(rows[1][1]['price'],100)
 def test_stale_future_or_missing_page_timestamp_closed(self):
  cells=cell('Book',quote('+115'),quote('-135'))
  for stamp in ['Oct 09, 2026, 12:08 PM','Oct 10, 2026, 12:30 PM','invalid']:
   self.assertEqual(parse(page('moneyline',cells,updated=stamp),[GAME],NOW),[])

class VegasFallback(unittest.TestCase):
 def test_exact_date_named_book_and_two_sided_prices(self):
  html='<table><thead><tr><th class="book-pinup">Open</th><th class="book-pinup">DraftKings</th><th class="book-pinup">Consensus</th></tr></thead><tbody id="odds-table-moneyline--0"><tr><td><span data-role="localtime" data-value="2026-10-10T17:00:00Z"></span></td></tr>'
  for team,price in [('Philadelphia Flyers','+115'),('Boston Bruins','-135')]:
   html+=f'<tr><td class="game-team"><img alt="{team}"></td><td>+9999</td><td><span class="data-moneyline">{price}</span></td><td><span class="data-moneyline">+9999</span></td></tr>'
  html+='</tbody></table>'
  game={**GAME,'home_name':'Boston Bruins','away_name':'Philadelphia Flyers'}
  rows=parse_vegas(html,[game],NOW);self.assertEqual(len(rows),2);self.assertEqual(rows[0][1]['price'],115);self.assertEqual(rows[0][1]['opposite_price'],-135);self.assertEqual(rows[0][1]['book'],'DraftKings')
  self.assertEqual(parse_vegas(html,[{**game,'date':'2026-10-11T17:00Z'}],NOW),[])
  with patch('pipeline.public_odds.download',side_effect=[OSError('Unavailable'),html]) as read:
   self.assertEqual(len(fetch([game],NOW)),2);self.assertEqual(read.call_args_list[1].args[0],VEGAS_URL)
