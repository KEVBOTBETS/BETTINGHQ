# College basketball research

The NBA and college collectors share tested transport, event identity checks, named-book quote parsing and frozen-history grading. `pipeline/build.py` selects independent college endpoints, state, publication files and the `ncaab-scoring-research-1.0` version. The refresh isolation helper bundles the shared package; it never writes NBA history into this project.

College scoring blends current overall scoring rates with a 12-game prior from the previous season. Home court adds a 2-point home/away differential except at neutral venues. Margin SD 12 and total SD 18 are disclosed research assumptions. Roster turnover, opponent strength and injuries are not adjusted. Missing prior teams remain unpredicted. All offers remain research; automatic qualification is off.

Run `python -m pipeline.build` here. No key or login is required. Only real pregame forecasts are frozen; actual results may be recovered later, but predictions are never backfilled.
