from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from ladder import espn, ledger
from ladder.state import Ladder


def test_two_way_tie_pushes_and_three_way_draw_still_loses(monkeypatch):
    fixture = json.loads((Path(__file__).parent / 'fixtures/espn_sample.json').read_text())
    tied = deepcopy(next(ev for ev in fixture['epl'] if ev['id'] == 'e9'))
    monkeypatch.setattr(espn, 'find_event', lambda *args: tied)
    assert espn.grade_bet('nfl', 'e9', 'home')[0] == 'push'
    assert espn.grade_bet('nfl', 'e9', 'away')[0] == 'push'
    assert espn.grade_bet('epl', 'e9', 'home')[0] == 'loss'
    assert espn.grade_bet('epl', 'e9', 'draw')[0] == 'win'


def test_custom_stake_cashout_and_loss_use_actual_money():
    for result, expected in [('win', 10), ('loss', -10), ('push', 0)]:
        lad = Ladder(base_stake=5, max_rung=1)
        lad.place({'decimal': 2}, stake=10)
        lad.settle(result)
        assert lad.net == expected
        assert ledger.summary(asdict(lad))['net'] == expected


def test_amended_stake_survives_reload_and_run_boundaries(tmp_path):
    lad = Ladder(base_stake=5, max_rung=4)
    lad.place({'decimal': 2}, stake=10)
    lad.settle('win')  # $10 profit, still in the run
    lad.place({'decimal': 2})
    lad.amend(stake=7)
    path = tmp_path / 'ladder.json'
    lad.save(path)
    lad = Ladder.load(path)
    lad.settle('loss')
    assert lad.net == 3  # $10 earned, $7 lost
    assert ledger.summary(asdict(lad))['net'] == 3
    lad.place({'decimal': 2}, stake=12)
    lad.settle('win')
    assert lad.cash_out() == 24
    assert lad.net == 15
    assert ledger.summary(asdict(lad))['net'] == 15
