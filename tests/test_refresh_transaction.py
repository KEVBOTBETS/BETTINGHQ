from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from model_refresh import refresh_project

class RefreshTransaction(unittest.TestCase):
    def test_failed_partial_refresh_retains_original_files(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)/'props-edge';(project/'site/data').mkdir(parents=True)
            meta=project/'site/data/meta.json';meta.write_text('original')
            command=[sys.executable,'-c',"from pathlib import Path; Path('site/data/meta.json').write_text('partial'); raise SystemExit(1)"]
            with self.assertRaises(subprocess.CalledProcessError):refresh_project(project,command)
            self.assertEqual(meta.read_text(),'original')

    def test_success_copies_data_without_replacing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)/'props-edge';(project/'site/data').mkdir(parents=True)
            (project/'source.py').write_text('original source')
            command=[sys.executable,'-c',"from pathlib import Path; Path('site/data/meta.json').write_text('complete'); Path('source.py').write_text('temporary')"]
            refresh_project(project,command)
            self.assertEqual((project/'site/data/meta.json').read_text(),'complete')
            self.assertEqual((project/'source.py').read_text(),'original source')
