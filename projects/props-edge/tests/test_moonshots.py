import unittest,json,datetime as dt
from pathlib import Path
from pipeline.parlays import build_parlays

class Moonshots(unittest.TestCase):
    def test_500_and_moonshots_remain_research_without_padding_or_edge_claim(self):
        settings=json.loads((Path(__file__).parents[1]/'config/settings.json').read_text());now=dt.datetime(2026,10,10,15,tzinfo=dt.timezone.utc)
        legs=[dict(id=str(i),event_id='game',player='Player '+str(i),team='Team',matchup='A @ B',market='Receiving yards',side='over',line=35.5,model_prob=.6,price_american=150,price_decimal=2.5,price_source='book',book='Book',tier='PASS',held=True,samples=8,confidence=.7,updated_at=now.isoformat(),start_time='2026-10-11T17:00Z',validation_policy={'paused':True}) for i in range(2)]
        result=build_parlays(legs,settings,now);tickets=[t for t in result['tickets'] if t['target']==500]
        self.assertTrue(tickets);self.assertIn(50000,result['profiles']['longshot']['targets']);self.assertIn(500,result['profiles']['longshot']['targets'])
        self.assertTrue(any(t['scope']=='game' for t in tickets))
        for t in tickets:self.assertEqual(t['leg_count'],2);self.assertFalse(t['actionable']);self.assertFalse(t['combined_quote_verified']);self.assertIsNone(t['expected_value_on_10']);self.assertEqual(t['price_american'],525)
        self.assertEqual(build_parlays(legs[:1],settings,now)['tickets'],[])
