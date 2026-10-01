import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from pipeline.parlay_history import update,outcome
from pipeline.grade import identity

NOW=datetime(2026,10,1,12,tzinfo=timezone.utc)

class ParlayArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.legs=[dict(event_id=str(i),player='Player '+str(i),team='Team',market='Receiving yards',side='over',line=50.5,pick='Over 50.5',start_time=(NOW+timedelta(hours=5+i)).isoformat(),price_american=-110,model_prob=.6) for i in (1,2)]
        self.ticket=dict(id='model-1',legs=self.legs,scope='slate',target=1000,price_american=500)
    def tearDown(self):self.temp.cleanup()
    def archive(self):return json.loads((self.root/'site/data/parlay-history.json').read_text())
    def grade(self,results):
        records={identity(l):{**l,'result':result,'actual':60 if result=='Win' else 40,'graded_at':(NOW+timedelta(hours=12)).isoformat()} for l,result in zip(self.legs,results)}
        (self.root/'state/leg_history.json').write_text(json.dumps({'records':records}))
    def test_freezes_full_ticket_deduplicates_scopes_and_preserves_original_price(self):
        update(self.root,[self.ticket],NOW)
        modified=copy.deepcopy(self.ticket);modified.update(id='different-target',scope='day',price_american=900)
        update(self.root,[modified],NOW+timedelta(minutes=10))
        rows=self.archive()['records'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['price_american'],500)
        self.assertEqual(len(rows[0]['legs']),2);self.assertEqual(rows[0]['captured_at'],NOW.isoformat())
    def test_win_requires_every_leg_and_history_survives_new_empty_slate(self):
        update(self.root,[self.ticket],NOW);self.grade(['Win','Win'])
        update(self.root,[],NOW+timedelta(days=1));row=self.archive()['records'][0]
        self.assertEqual(row['result'],'Win');self.assertEqual(row['legs'][0]['actual'],60)
        update(self.root,[],NOW+timedelta(days=2));self.assertEqual(self.archive()['summary']['Win'],1)
    def test_lost_and_ambiguous_ticket_rules(self):
        self.assertEqual(outcome([{'result':'Loss'},{'result':'Pending'}]),'Loss')
        self.assertEqual(outcome([{'result':'Win'},{'result':'Pending'}]),'Pending')
        self.assertEqual(outcome([{'result':'Push'},{'result':'Win'}]),'Review')
        self.assertEqual(outcome([{'result':'Void'},{'result':'Loss'}]),'Review')
        self.assertEqual(outcome([{'result':'Void'},{'result':'Void'}]),'Void')
    def test_no_post_start_backfill_and_no_duplicate_legs(self):
        update(self.root,[self.ticket],NOW+timedelta(days=1));self.assertEqual(self.archive()['records'],[])
        update(self.root,[{**self.ticket,'legs':[self.legs[0],self.legs[0]]}],NOW);self.assertEqual(self.archive()['records'],[])
    def test_exact_line_and_team_required(self):
        update(self.root,[self.ticket],NOW);self.legs[0]['line']=49.5;self.grade(['Win','Win'])
        update(self.root,[],NOW+timedelta(days=1));self.assertEqual(self.archive()['records'][0]['result'],'Pending')
    def test_corrupt_archive_is_not_replaced(self):
        update(self.root,[self.ticket],NOW);path=self.root/'state/parlay_history.json';path.write_text('broken')
        with self.assertRaises(json.JSONDecodeError):update(self.root,[],NOW)
        self.assertEqual(path.read_text(),'broken')
