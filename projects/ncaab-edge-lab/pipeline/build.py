"""Run the shared collector with college endpoints and an independent data/history root."""
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
shared=ROOT/'_basketball_shared'
if not shared.exists():shared=ROOT.parent/'nba-edge-lab/pipeline'
spec=importlib.util.spec_from_file_location('basketball_shared',shared/'__init__.py',submodule_search_locations=[str(shared)])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
from basketball_shared.build import main
if __name__=='__main__':main(['--league','NCAAB',*sys.argv[1:]],root=ROOT)
