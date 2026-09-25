import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from pipeline import build, model
from test_model import CFG, NOW, game, projection


class WNBARegressionTests(unittest.TestCase):
    def price(self, g):
        p = projection(g)
        p.update({'margin':9, 'line_gap':5, 'total':168, 'confidence':.86})
        with patch.object(model, '_utc_now', return_value=NOW):
            rows = model.price_game(g, p, CFG)
        return model.allocate_portfolio(rows, CFG)

    def test_fresh_prices_qualify_but_cache_age_and_tipoff_block(self):
        self.assertTrue(any(row['stake']>0 for row in self.price(game())))
        for stamp in ['2026-01-01T00:00:00Z', None, 'invalid', (NOW+timedelta(hours=1)).isoformat()]:
            g = game()
            g['odds']['fetched_at'] = stamp
            self.assertTrue(all(row['stake']==0 and row['tier']=='AVOID' for row in self.price(g)))
        g = game()
        g['tipoff'] = (NOW-timedelta(minutes=1)).isoformat()
        self.assertTrue(all(row['stake']==0 for row in self.price(g)))

    def test_final_scores_persist_outside_slate_window(self):
        final = game('old', '2026-08-01', status='post', completed=True)
        final['away']['score'], final['home']['score'] = 71, 97
        with tempfile.TemporaryDirectory() as temp:
            state, site = Path(temp)/'state', Path(temp)/'site'
            state.mkdir(); site.mkdir()
            (state/'games_2026.json').write_text(json.dumps({'games':[final]}))
            with patch.object(build,'STATE',state), patch.object(build,'SITE',site):
                output = build.build('2026-09-06', offline=True)
                self.assertEqual(output['games.json'], [])
                self.assertEqual(output['results.json'][0]['home']['score'],97)
                # A later season/cache refresh cannot remove an archived final.
                (state/'games_2026.json').write_text(json.dumps({'games':[]}))
                later = build.build('2026-09-07', offline=True)
                self.assertEqual(later['results.json'],output['results.json'])
