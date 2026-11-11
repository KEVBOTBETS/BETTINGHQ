import copy
from datetime import datetime,timedelta,timezone
import unittest
from tools.research import market

class ArchiveIndexTests(unittest.TestCase):
    def test_index_matches_exact_closes_without_modifying_history(self):
        at=datetime(2026,11,1,tzinfo=timezone.utc)
        rows=[]
        for event in ('one','two'):
            for book in ('A','B'):
                for side in ('home','away'):
                    for line in (-3,-3.5):
                        for hour in range(8):
                            rows.append({'contract':['nfl',event,'ATS','',line,'full-game'], 'book':book,'side':side,'observed_at':(at+timedelta(hours=hour)).isoformat(),'start':(at+timedelta(hours=6)).isoformat(),'decimal':1.8+hour/10})
        rows.append({**rows[0], 'decimal':9})  # Preserve first quote on an exact timestamp tie.
        selections=[*rows,{**rows[0],'observed_at':'invalid'}, {**rows[0],'start':(at+timedelta(hours=3)).isoformat()}]
        before=copy.deepcopy(rows)
        now=at+timedelta(days=1)
        expected=[(s,c) for s in selections if (c:=market.closing_value(s,rows,now))]
        self.assertEqual(market.closing_values(selections,rows,now),expected)
        self.assertEqual(rows,before)
        self.assertFalse(market.closing_values(selections,rows,at-timedelta(days=1)))

    def test_historical_contract_index_retains_exact_first_and_latest(self):
        now=datetime(2026,11,1,tzinfo=timezone.utc)
        raw={'sport':'nfl','event_id':'one','book':'A','market':'ATS','side':'home','line':-3,'price':-110,'observed_at':now.isoformat(),'start':(now+timedelta(days=1)).isoformat()}
        first=market.normalize(raw,now)
        later={**raw,'observed_at':(now+timedelta(hours=1)).isoformat(),'price':120}
        unrelated={**first,'id':'unrelated','contract':['nfl','other','ATS','',-3,'full-game']}
        result,saved=market.audit([later],[first,unrelated],now+timedelta(hours=1))
        group=result['groups'][0]
        self.assertEqual(group['first'],first)
        self.assertEqual(group['latest']['price'],120)
        self.assertIn(unrelated,saved)
        self.assertEqual(len(saved),3)

if __name__ == '__main__':unittest.main()
