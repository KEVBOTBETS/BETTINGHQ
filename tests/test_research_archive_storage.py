import gzip
import json
from pathlib import Path
import tempfile
import unittest
from tools.research.common import read, write
from tools.research.build import ARCHIVE, LEGACY_ARCHIVE, read_archive
from tools.release_fingerprint import publication

class ResearchArchiveStorage(unittest.TestCase):
    def test_lossless_legacy_fallback_and_compressed_precedence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            state={'schema':1,'forecasts':[{'id':'f','p_home':.63,'result':None}], 'quotes':[{'id':'q','price':-110}], 'market_forecasts':[{'result':{'status':'Win'}}]}
            write(root/LEGACY_ARCHIVE,state)
            self.assertEqual(read_archive(root),state)
            write(root/ARCHIVE,state)
            self.assertEqual(read_archive(root),state)
            with gzip.open(root/ARCHIVE,'rt') as f:self.assertEqual(json.load(f),state)
            (root/LEGACY_ARCHIVE).unlink()
            self.assertEqual(read_archive(root),state)
    def test_compressed_failure_retains_last_good_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'history.json.gz';write(p,{'quotes':[1]})
            with self.assertRaises(ValueError):write(p,{'bad':float('nan')})
            self.assertEqual(read(p,{}),{'quotes':[1]})
    def test_stage_includes_gzip_and_legacy_deletion(self):
        source=Path('tools/stage_history.py').read_text()
        self.assertIn('data/research/**/*.json.gz',source)
        self.assertIn("'git','add','-u'",source)

    def test_compressed_publication_does_not_invalidate_code_certificate(self):
        self.assertTrue(publication(str(ARCHIVE)))
        self.assertFalse(publication('projects/bet-ledger-hq/today-desk-core.js'))
