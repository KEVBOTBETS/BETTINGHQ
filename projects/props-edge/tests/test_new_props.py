import unittest
import datetime as dt
import json
from pathlib import Path
from copy import deepcopy
from pipeline.parlays import core_tickets, core_eligible
from pipeline.parlay_audit import audit
from pipeline.multisport import parse_offers

class CoreTests(unittest.TestCase):
    now=dt.datetime(2026,10,2,20,tzinfo=dt.timezone.utc)
    def leg(self,n,**extra):
        r=dict(id=str(n),event_id=str(n),player='Player '+str(n),team='Team',matchup='A @ H',market='Receptions',side='over',line=4.5,model_prob=.7,price_american=-150,price_decimal=1+100/150,price_source='book',book='Book',tier='GOOD',samples=8,confidence=.7,action_edge=.05,updated_at=self.now.isoformat(),start_time='2026-10-04T17:00Z');r.update(extra);return r
    def test_core_never_pads_and_uses_one_book_distinct_events(self):
        settings=json.loads((Path(__file__).parents[1]/'config/settings.json').read_text());legs=[self.leg(n) for n in range(6)]+[self.leg(8,book='Other')]
        tickets=core_tickets(legs,settings,self.now);self.assertTrue(tickets)
        for t in tickets:
            self.assertIn(t['leg_count'],[2,3]);self.assertEqual(len({r['book'] for r in t['legs']}),1);self.assertEqual(len({r['event_id'] for r in t['legs']}),t['leg_count']);self.assertFalse(t['estimated_prices']);self.assertFalse(t['actionable']);self.assertIsNone(t['expected_value_on_10'])
        self.assertEqual(core_tickets([self.leg(1),self.leg(2,event_id='1')],settings,self.now),[])
    def test_reject_held_pass_stale_estimated_thin_and_bad_prices(self):
        self.assertTrue(core_eligible(self.leg(1),self.now))
        for extra in [dict(held=True),dict(tier='PASS'),dict(samples=2),dict(price_source='model'),dict(action_edge=-.1),dict(price_decimal=9),dict(updated_at='2026-10-01T00:00Z'),dict(updated_at='2026-10-03T00:00Z')]:self.assertFalse(core_eligible(self.leg(1,**extra),self.now))
    def test_overlap_audit_preserves_losses_and_final_leg(self):
        l=self.leg(1);l.update(result='Loss',pick='Player 1 over 4.5')
        rows=[dict(result='Loss',same_game=True,estimated_prices=True,legs=[l],scope='game',leg_count=1,target=1000),dict(result='Loss',same_game=True,estimated_prices=True,legs=[{**l,'result':'Pending'}],scope='game',leg_count=1,target=1000)]
        original=deepcopy(rows);a=audit(rows);self.assertEqual(rows,original);self.assertEqual(a['losses'],2);self.assertEqual(a['distinct_events'],1);self.assertEqual(a['unique_legs'],1);self.assertEqual(a['repeated_legs'][0]['result'],'Loss')
    def test_public_offer_requires_exact_current_player_and_event(self):
        card=['RECEIVING YARDS','BYU @ TCU','TCU','J. Scott','DraftKings logo','o25.5','-118']
        game=dict(game_id='1',away='BYU',home='TCU',date='2026-10-04T17:00Z');roster={'TCU':[dict(id='9',player='Jordan Scott')]}
        q=parse_offers([card],[game],roster,'NCAAF',self.now.isoformat());self.assertEqual(len(q),1);self.assertEqual(q[0]['price_american'],-118);self.assertIsNone(q[0]['model_prob'])
        self.assertEqual(parse_offers([card],[game,game],roster,'NCAAF',self.now.isoformat()),[])
        self.assertEqual(parse_offers([card],[game],{'TCU':[dict(id='8',player='Jake Scott'),*roster['TCU']]},'NCAAF',self.now.isoformat()),[])
        self.assertEqual(parse_offers([card],[{**game,'away':'UCF'}],roster,'NCAAF',self.now.isoformat()),[])
