import json,tempfile,unittest
from pathlib import Path
from pipeline.lab_feeds import publish
class LabFeeds(unittest.TestCase):
 def test_daily_files_are_small_complete_and_legacy_untouched(self):
  with tempfile.TemporaryDirectory() as tmp:
   p={'sport':'NBA','generated_at':'2026-10-29T01:00Z','source_model_at':'2026-10-29T00:30Z','games':[{'game_id':'a','date':'2026-10-29T02:00Z'},{'game_id':'b','date':'2026-10-29T23:00Z'}],'quotes':[{'event_id':'a','price':150}],'watchlist':[{'event_id':'a','player':'One'},{'event_id':'b','player':'Two'}],'milestone_forecasts':[{'event_id':'b','threshold':20}]}
   out=publish(tmp,p);self.assertEqual([r['day'] for r in out['chunks']],['2026-10-28','2026-10-29']);self.assertNotIn('watchlist',out);self.assertEqual(out['counts']['watchlist'],2)
   root=Path(tmp)/'site/data/labs/nba';chunks=[json.loads((root/q['file']).read_text()) for q in out['chunks']];self.assertEqual([q['watchlist'][0]['player'] for q in chunks],['One','Two']);self.assertEqual(chunks[0]['quotes'],p['quotes']);self.assertEqual(p['watchlist'][1]['player'],'Two')
