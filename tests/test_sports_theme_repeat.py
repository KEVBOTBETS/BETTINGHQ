import importlib.util
import tempfile
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('theme_repeat',Path(__file__).resolve().parents[1]/'tools/sports_theme.py')
theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
class ThemeRepeat(unittest.TestCase):
 def test_repeated_staging_keeps_one_navigation_and_stylesheet(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'props-edge').mkdir();page=root/'props-edge/multisport.html';page.write_text('<html lang="en"><head></head><body><main>Player research</main></body></html>')
   theme.apply(root);once=page.read_text();theme.apply(root);self.assertEqual(page.read_text(),once);self.assertEqual(once.count('class="kb-network"'),1);self.assertEqual(once.count('sports-theme.css'),1);self.assertEqual(once.count('data-kb-sport='),1)
