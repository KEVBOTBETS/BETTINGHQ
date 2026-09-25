import json
from pathlib import Path

from ladder import espn
from ladder.oddsmath import (american_to_decimal, decimal_to_american,
                             ladder_stakes, ladder_ev, survival)
from ladder.selector import collect, rank, screen_event
from ladder.state import Ladder

FIX = json.loads((Path(__file__).parent / "fixtures" / "espn_sample.json").read_text())
WIN = dict(min_decimal=1.50, max_decimal=1.667)


def fetch(league, date=None):
    return FIX.get(league, [])


# ---------- odds math ----------
def test_odds_conversion():
    assert round(american_to_decimal(-150), 4) == 1.6667
    assert round(american_to_decimal(-200), 4) == 1.5
    assert round(decimal_to_american(1.5)) == -200


def test_ladder_stakes_compound():
    assert ladder_stakes(5.0, [1.5] * 3) == [5.0, 7.5, 11.25]


def test_ev_decays_with_length():
    assert ladder_ev(5, 0.62, 1.55, 10) < ladder_ev(5, 0.62, 1.55, 3)
    assert survival(0.62, 8) < survival(0.62, 3)


# ---------- ESPN parsing ----------
def test_parses_off_moneyline_as_missing():
    assert espn._clean_american("OFF") is None
    assert espn._clean_american("-2400") == -2400
    assert espn._clean_american("+1200") == 1200
    assert espn._clean_american("EVEN") == 100


def test_off_market_yields_no_candidate():
    ev = [e for e in FIX["mlb"] if e["id"] == "g5"][0]
    assert screen_event(ev, "mlb", 1.0, 100.0) == []


# ---------- screening ----------
def test_window_excludes_too_long_and_too_short():
    cands, _ = collect(["mlb"], horizon_hours=1e9, fetch=fetch, **WIN)
    ids = {c.event_id for c in cands}
    assert "g1" in ids and "g2" in ids     # -185, -162
    assert "g3" not in ids                 # -140 is too long
    assert "g4" not in ids                 # -600 is too short
    assert all(1.50 <= c.decimal <= 1.667 for c in cands)


def test_completed_games_are_skipped():
    cands, _ = collect(["mlb"], horizon_hours=1e9, fetch=fetch, **WIN)
    assert "g9" not in {c.event_id for c in cands}


def test_rank_picks_highest_fair_prob():
    cands, _ = collect(["mlb", "nfl", "epl"], horizon_hours=1e9, fetch=fetch, **WIN)
    top = rank(cands)[0]
    assert top.fair_prob == max(c.fair_prob for c in cands)


def test_live_collect_scans_each_date_in_the_horizon(monkeypatch):
    calls = []
    def fake_events(league, date=None):
        calls.append((league, date))
        return []
    monkeypatch.setattr(espn, "events", fake_events)
    collect(["mlb"], horizon_hours=48, **WIN)
    assert len(calls) == 3
    assert all(league == "mlb" and len(date) == 8 for league, date in calls)


def test_three_way_soccer_costs_more_hold():
    cands, _ = collect(["mlb", "epl"], horizon_hours=1e9, fetch=fetch, **WIN)
    epl = [c for c in cands if c.league == "epl"][0]
    mlb = [c for c in cands if c.league == "mlb"][0]
    assert epl.hold > mlb.hold


def test_negative_hold_is_rejected_as_bad_data():
    bad = json.loads(json.dumps(FIX["mlb"][0]))
    ml = bad["competitions"][0]["odds"][0]["moneyline"]
    ml["home"] = {"close": {"odds": "-150"}}
    ml["away"] = {"close": {"odds": "+200"}}   # sums under 1.0 -> arbitrage
    assert screen_event(bad, "mlb", 1.0, 100.0) == []


# ---------- grading ----------
def test_grade_win_loss_and_pending():
    won = [e for e in FIX["mlb"] if e["id"] == "g9"][0]
    assert espn.grade(won, "home")[0] == "win"
    assert espn.grade(won, "away")[0] == "loss"
    unplayed = [e for e in FIX["mlb"] if e["id"] == "g1"][0]
    assert espn.grade(unplayed, "home")[0] == "pending"


def test_grade_draw():
    drew = [e for e in FIX["epl"] if e["id"] == "e9"][0]
    assert espn.grade(drew, "draw")[0] == "win"
    assert espn.grade(drew, "home", "epl")[0] == "loss"


# ---------- ladder ----------
def test_win_rolls_full_return_forward():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=8)
    lad.place({"pick": "A", "decimal": 1.6})
    lad.settle("win")
    assert lad.rung == 1 and lad.next_stake() == 8.0
    lad.place({"pick": "B", "decimal": 1.5})
    lad.settle("win")
    assert lad.next_stake() == 12.0


def test_loss_resets_and_caps_risk_at_base():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    for _ in range(3):
        lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("loss")
    assert lad.rung == 0 and lad.next_stake() == 5.0
    assert lad.net == -5.0


def test_push_holds_position():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("push")
    assert lad.rung == 0 and lad.next_stake() == 5.0


def test_max_rung_cashes_out():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=3)
    for _ in range(3):
        lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    assert lad.rung == 0 and lad.runs_completed == 1 and lad.net > 0


def test_no_double_pending():
    lad = Ladder(one_bet_per_day=False)
    lad.place({"pick": "A", "decimal": 1.6})
    try:
        lad.place({"pick": "B", "decimal": 1.6})
    except RuntimeError:
        return
    raise AssertionError("should refuse a second pending bet")


# ---------- line movement ----------
def test_drift_detects_shortening_line():
    ev = json.loads(json.dumps(FIX["mlb"][0]))
    ml = ev["competitions"][0]["odds"][0]["moneyline"]
    ml["home"] = {"close": {"odds": "-185"}, "open": {"odds": "-150"}}
    ml["away"] = {"close": {"odds": "+155"}, "open": {"odds": "+130"}}
    c = [x for x in screen_event(ev, "mlb", 1.0, 100.0) if x.side == "home"][0]
    assert c.open_american == -150
    assert c.drift > 0                       # price shortened
    assert "shortened" in c.steam


def test_missing_open_leaves_drift_none():
    ev = json.loads(json.dumps(FIX["mlb"][0]))
    ml = ev["competitions"][0]["odds"][0]["moneyline"]
    ml["home"] = {"close": {"odds": "-185"}}
    ml["away"] = {"close": {"odds": "+155"}}
    c = [x for x in screen_event(ev, "mlb", 1.0, 100.0) if x.side == "home"][0]
    assert c.drift is None and c.steam == ""


# ---------- rendering ----------
def test_render_produces_standalone_html():
    from ladder import render as rnd
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=5)
    lad.place({"pick": "Toronto Blue Jays", "decimal": 1.54, "american": -185,
               "league": "mlb", "matchup": "CWS @ TOR"})
    doc = rnd.render(lad.__dict__, [], [], 1.667, (1.50, 1.667))
    assert doc.startswith("<!doctype html>")
    assert "<svg" in doc and "Toronto Blue Jays" in doc
    # Fully offline: the only http reference allowed is the SVG namespace.
    body = doc.split("<div class=foot>")[0].replace(
        'xmlns="http://www.w3.org/2000/svg"', "")
    assert "http://" not in body and "https://" not in body


def test_render_escapes_team_names():
    from ladder import render as rnd
    lad = Ladder(one_bet_per_day=False)
    lad.place({"pick": "<script>x</script>", "decimal": 1.6, "american": -166})
    doc = rnd.render(lad.__dict__, [], [], 1.667, (1.50, 1.667))
    assert "<script>x</script>" not in doc
    assert "&lt;script&gt;" in doc


def test_empty_state_renders():
    from ladder import render as rnd
    doc = rnd.render(Ladder(one_bet_per_day=False).__dict__, [], [], 1.667, (1.50, 1.667))
    assert "No qualifying bet" in doc


# ---------- real fill price, slippage, CLV ----------
def test_place_records_actual_price_not_screened():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    b = lad.place({"pick": "A", "decimal": 1.60}, price=1.54)
    assert b["screened_decimal"] == 1.60
    assert b["decimal"] == 1.54
    assert round(b["slippage"], 4) == -0.06
    assert b["to_return"] == 7.70          # compounds the REAL price


def test_amend_updates_price_stake_and_return():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    lad.place({"pick": "A", "decimal": 1.60})
    b = lad.amend(price=1.52, stake=4.75)
    assert b["decimal"] == 1.52 and b["stake"] == 4.75
    assert b["to_return"] == round(4.75 * 1.52, 2)
    assert round(b["slippage"], 4) == -0.08


def test_amend_rejects_bad_price():
    lad = Ladder(one_bet_per_day=False)
    lad.place({"pick": "A", "decimal": 1.6})
    for bad in (1.0, 0.5, -2):
        try:
            lad.amend(price=bad)
        except ValueError:
            continue
        raise AssertionError(f"should reject price {bad}")


def test_clv_sign():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    lad.place({"pick": "A", "decimal": 1.60})
    lad.settle("win", closing=1.50)
    assert lad.history[-1]["clv"] > 0      # took 1.60, closed 1.50 -> beat it
    lad.place({"pick": "B", "decimal": 1.55})
    lad.settle("loss", closing=1.62)
    assert lad.history[-1]["clv"] < 0


# ---------- stake rounding and ceiling ----------
def test_stake_rounds_down_never_up():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, stake_increment=0.25)
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    assert lad.next_stake() == 8.00        # 8.00 exact
    lad2 = Ladder(one_bet_per_day=False, base_stake=5.0, stake_increment=0.25)
    lad2.place({"pick": "A", "decimal": 1.54}); lad2.settle("win")
    assert lad2.next_stake() == 7.50       # 7.70 rounds DOWN to 7.50


def test_max_stake_blocks_place_and_suggests_cashout():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_stake=7.0)
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    assert lad.would_exceed_cap()
    try:
        lad.place({"pick": "B", "decimal": 1.6})
    except RuntimeError as e:
        assert "cashout" in str(e)
        return
    raise AssertionError("should refuse to exceed max_stake")


# ---------- ledger ----------
def test_ledger_running_net_and_summary():
    from ladder import ledger
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=5)
    lad.place({"pick": "A", "decimal": 1.60}, price=1.54)
    lad.settle("win", closing=1.50)
    lad.place({"pick": "B", "decimal": 1.58}, price=1.58)
    lad.settle("loss", closing=1.62)
    st = lad.__dict__
    rows = ledger.rows(st)
    assert len(rows) == 2
    assert rows[-1]["running_net"] == -5.0     # only base is new money
    assert rows[0]["profit_loss"] == 2.7
    assert rows[-1]["running_profit_loss"] == -5.0
    s = ledger.summary(st)
    assert s["bets"] == 2 and s["win_rate"] == 0.5
    assert s["profit_loss"] == -5.0
    assert s["avg_slippage"] < 0
    assert s["clv_n"] == 2


def test_ledger_csv_roundtrip():
    import csv as _csv
    from io import StringIO
    from ladder import ledger
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    lad.place({"pick": "A", "decimal": 1.6}, price=1.55)
    lad.settle("win", closing=1.5)
    text = ledger.to_csv(lad.__dict__)
    parsed = list(_csv.DictReader(StringIO(text)))
    assert parsed[0]["pick"] == "A"
    assert float(parsed[0]["decimal"]) == 1.55


def test_ledger_empty_state():
    from ladder import ledger
    assert ledger.rows(Ladder(one_bet_per_day=False).__dict__) == []
    assert ledger.summary(Ladder(one_bet_per_day=False).__dict__)["bets"] == 0


# ---------- guards ----------
def test_one_bet_per_day_lock():
    lad = Ladder(base_stake=5.0, one_bet_per_day=True)
    lad.place({"pick": "A", "decimal": 1.6})
    lad.settle("win")
    try:
        lad.place({"pick": "B", "decimal": 1.6})
    except RuntimeError as e:
        assert "today" in str(e)
        return
    raise AssertionError("should lock to one bet per day")


def test_force_overrides_day_lock():
    lad = Ladder(base_stake=5.0, one_bet_per_day=True)
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    lad.one_bet_per_day = False          # what --force does
    assert lad.place({"pick": "B", "decimal": 1.6})["rung"] == 1


def test_stop_loss_halts_after_n_busts():
    lad = Ladder(base_stake=5.0, one_bet_per_day=False,
                 stop_loss_busts=3, stop_loss_days=30)
    for _ in range(3):
        lad.place({"pick": "A", "decimal": 1.6})
        lad.settle("loss")
    assert lad.recent_busts() == 3 and lad.stop_loss_hit()
    try:
        lad.place({"pick": "B", "decimal": 1.6})
    except RuntimeError as e:
        assert "stop-loss" in str(e) and lad.halted
    lad.halted = False                    # what `ladder resume` does
    lad.stop_loss_busts = 0
    assert lad.place({"pick": "B", "decimal": 1.6})


def test_stop_loss_off_by_default_value_zero():
    lad = Ladder(one_bet_per_day=False, stop_loss_busts=0)
    for _ in range(5):
        lad.place({"pick": "A", "decimal": 1.6}); lad.settle("loss")
    assert not lad.stop_loss_hit()


def test_local_day_uses_configured_timezone():
    lad = Ladder(one_bet_per_day=False, timezone="America/Toronto")
    # 03:00 UTC is still the previous evening in Toronto
    assert lad._local_day("2026-03-02T03:00:00+00:00") == "2026-03-01"
    lad2 = Ladder(one_bet_per_day=False, timezone="UTC")
    assert lad2._local_day("2026-03-02T03:00:00+00:00") == "2026-03-02"


# ---------- backtest ----------
def _finished(events, home_wins):
    import copy
    out = copy.deepcopy(events)
    for e in out:
        st = {"type": {"state": "post", "completed": True, "shortDetail": "Final"}}
        e["status"] = st
        e["competitions"][0]["status"] = st
        for c in e["competitions"][0]["competitors"]:
            won = home_wins if c["homeAway"] == "home" else not home_wins
            c["winner"] = won
            c["score"] = "5" if won else "2"
    return out


def test_backtest_grades_days_and_summarises(monkeypatch):
    from datetime import date
    from ladder import backtest as bt
    days = {"20260301": _finished(FIX["mlb"], True),
            "20260302": _finished(FIX["mlb"], False),
            "20260303": _finished(FIX["mlb"], True)}
    monkeypatch.setattr(bt, "fetch_day",
                        lambda lg, d, sleep=0, use_cache=True: days.get(d, []))
    res = bt.run(["mlb"], date(2026, 3, 1), date(2026, 3, 3), 1.50, 1.667, sleep=0)
    assert len(res.days) == 3
    assert [d.result for d in res.days] == ["win", "loss", "win"]
    s = res.summary(5.0)
    assert s["graded"] == 3 and s["wins"] == 2
    assert 0 < s["model_predicted"] < 1
    assert any(l["max_rung"] == 5 for l in s["ladders"])


def test_backtest_skips_days_with_no_qualifying_bet(monkeypatch):
    from datetime import date
    from ladder import backtest as bt
    monkeypatch.setattr(bt, "fetch_day",
                        lambda lg, d, sleep=0, use_cache=True: [])
    res = bt.run(["mlb"], date(2026, 3, 1), date(2026, 3, 2), 1.50, 1.667, sleep=0)
    assert [d.result for d in res.days] == ["skipped", "skipped"]
    assert res.summary(5.0)["graded"] == 0


def test_backtest_use_open_prices_off_the_open():
    import copy
    from ladder.selector import screen_event
    ev = copy.deepcopy(FIX["mlb"][0])
    ml = ev["competitions"][0]["odds"][0]["moneyline"]
    ml["home"] = {"close": {"odds": "-185"}, "open": {"odds": "-160"}}
    ml["away"] = {"close": {"odds": "+155"}, "open": {"odds": "+140"}}
    close = [c for c in screen_event(ev, "mlb", 1.0, 9.0) if c.side == "home"][0]
    opened = [c for c in screen_event(ev, "mlb", 1.0, 9.0, use_open=True)
              if c.side == "home"][0]
    assert close.american == -185 and opened.american == -160


# ---------- statistics ----------
def test_wilson_interval_bounds_and_width():
    from ladder import stats
    lo, hi = stats.wilson(50, 80)
    assert lo < 0.625 < hi
    assert 0.0 <= lo and hi <= 1.0
    # more data narrows the interval
    lo2, hi2 = stats.wilson(500, 800)
    assert (hi2 - lo2) < (hi - lo)


def test_wilson_handles_degenerate_input():
    from ladder import stats
    assert stats.wilson(0, 0) == (0.0, 1.0)
    lo, hi = stats.wilson(0, 10)
    assert lo == 0.0 and 0 < hi < 1
    lo, hi = stats.wilson(10, 10)
    assert hi == 1.0 and 0 < lo < 1


def test_required_n_scales_with_edge_size():
    from ladder import stats
    assert stats.required_n(0.62, 0.02) > stats.required_n(0.62, 0.05)
    assert stats.required_n(0.62, 0.0) == 0


def test_significance_needs_a_real_gap():
    from ladder import stats
    assert not stats.significant(50, 80, 0.60)      # 62.5% vs 60% on n=80
    assert stats.significant(700, 1000, 0.60)       # 70% vs 60% on n=1000


def test_bootstrap_spread_brackets_the_actual_run():
    from ladder import stats
    seq = [("win", 1.55)] * 50 + [("loss", 1.55)] * 30
    b = stats.bootstrap_ladder(seq, 5.0, 5, trials=800, seed=1)
    assert b["p05"] <= b["median"] <= b["p95"]
    assert 0.0 <= b["pct_profitable"] <= 1.0


def test_bootstrap_empty_sequence():
    from ladder import stats
    assert stats.bootstrap_ladder([], 5.0, 5) == {}


def test_ladder_net_depends_on_ordering():
    """The core reason the bootstrap exists."""
    from ladder import stats
    wins, losses = [("win", 1.6)] * 6, [("loss", 1.6)] * 2
    clustered = wins + losses          # 6 straight -> cashes out at rung 5
    alternating = []
    for i in range(2):
        alternating += wins[i * 3:(i + 1) * 3] + [losses[i]]
    assert stats.run_ladder(clustered, 5.0, 5) != stats.run_ladder(alternating, 5.0, 5)


def test_price_buckets_report_intervals():
    from ladder import stats
    rows = [(1.52, "win")] * 20 + [(1.52, "loss")] * 10 + [(1.62, "win")] * 5
    out = stats.buckets(rows, [1.50, 1.55, 1.60, 1.667])
    assert out[0]["n"] == 30 and out[0]["wins"] == 20
    assert out[0]["ci_low"] < out[0]["hit_rate"] < out[0]["ci_high"]
    assert all("beats_breakeven" in b for b in out)


def test_backtest_summary_carries_ci_and_bootstrap(monkeypatch):
    from datetime import date, timedelta
    from ladder import backtest as bt
    days = {}
    start = date(2026, 3, 1)
    for i in range(6):
        d = (start + timedelta(days=i)).strftime("%Y%m%d")
        days[d] = _finished(FIX["mlb"], i % 3 != 0)
    monkeypatch.setattr(bt, "fetch_day",
                        lambda lg, dd, sleep=0, use_cache=True: days.get(dd, []))
    s = bt.run(["mlb"], start, start + timedelta(days=5), 1.50, 1.667,
               sleep=0).summary(5.0)
    assert s["ci_low"] < s["actual_hit_rate"] < s["ci_high"]
    assert s["n_needed_for_5pt_edge"] > 0
    assert any(b["max_rung"] == 5 for b in s["bootstrap"])
    assert s["by_price"]


# ---------- projection uses the real price, not the window top ----------
def test_projection_price_prefers_pending_then_candidate():
    from ladder.render import projection_price
    lad = Ladder(one_bet_per_day=False, base_stake=5.0)
    # nothing in play -> window midpoint, never the flattering top
    d, src = projection_price(lad.__dict__, [], (1.50, 1.667))
    assert abs(d - 1.5835) < 1e-6 and "midpoint" in src
    # a candidate exists -> use its real price
    d, src = projection_price(lad.__dict__, [{"decimal": 1.5236}], (1.50, 1.667))
    assert d == 1.5236 and "candidate" in src
    # a pending bet outranks the candidate
    lad.place({"pick": "A", "decimal": 1.52})
    d, src = projection_price(lad.__dict__, [{"decimal": 1.6}], (1.50, 1.667))
    assert d == 1.52 and "pending" in src


def test_five_dollars_at_minus_191_returns_762():
    """The bug the dashboard shipped with: it projected 1.667 regardless."""
    from ladder.oddsmath import american_to_decimal
    d = american_to_decimal(-191)
    assert round(5 * d, 2) == 7.62
    assert round(5 * american_to_decimal(-167), 2) == 7.99
    # the old behaviour, for contrast
    assert round(5 * 1.667, 2) == 8.34


def test_render_projects_at_candidate_price():
    from ladder import render as rnd
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    doc = rnd.render(lad.__dict__, [{"decimal": 1.5236, "pick": "Rays",
                                     "american": -191, "fair_prob": 0.628,
                                     "league": "mlb", "matchup": "NYM @ TB",
                                     "hold": 0.045, "starts_in_h": 1.6}],
                     [], 1.667, (1.50, 1.667))
    assert "$7.62" in doc          # real return
    assert "$8.34" not in doc      # the old fantasy number
    assert "-191" in doc


def test_ten_rung_ladder_renders_all_rungs():
    from ladder import render as rnd
    svg = rnd.ladder_svg(0, 10, 5.0, 1.5236)
    assert svg.count('<rect x="46"') == 10


# ---------- settlement lookup and manual recording ----------
def test_date_of_converts_iso_to_espn_date():
    assert espn.date_of("2026-09-02T23:05Z") == "20260902"
    assert espn.date_of("2026-09-03T02:00:00+00:00") == "20260903"
    assert espn.date_of("") is None
    assert espn.date_of("not-a-date") is None


def test_grade_bet_finds_game_by_its_own_start_date(monkeypatch):
    """The settle bug: ESPN's default window had already rolled past the game."""
    won = [e for e in FIX["mlb"] if e["id"] == "g9"][0]
    calls = []

    def fake_events(league, date=None):
        calls.append(date)
        return [won] if date == "20260902" else []   # only findable by its date

    monkeypatch.setattr(espn, "events", fake_events)
    res, _ = espn.grade_bet("mlb", "g9", "home", None, "2026-09-02T23:05Z")
    assert res == "win"
    assert "20260902" in calls


def test_grade_bet_gives_up_cleanly():
    import ladder.espn as e
    orig = e.events
    e.events = lambda league, date=None: []
    try:
        res, detail = e.grade_bet("mlb", "nope", "home", None, "2026-09-02T23:05Z")
        assert res == "pending" and "not found" in detail
    finally:
        e.events = orig


def test_record_advances_the_ladder():
    """A bet placed at the book by hand still has to move the rung."""
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    from ladder.oddsmath import american_to_decimal
    lad.place({"pick": "New York Yankees",
               "decimal": american_to_decimal(-167)}, price=american_to_decimal(-167))
    b = lad.settle("win")
    assert lad.rung == 1
    assert round(b["returned"], 2) == 7.99
    assert lad.next_stake() == 7.99


def test_record_loss_resets_to_rung_zero():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    for _ in range(3):
        lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    assert lad.rung == 3
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("loss")
    assert lad.rung == 0 and lad.next_stake() == 5.0
    assert lad.runs_busted == 1 and lad.net == -5.0


def test_ladder_climbs_all_ten_rungs_then_cashes():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10,
                 stake_increment=0.01)
    for i in range(10):
        assert lad.rung == i
        lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    assert lad.rung == 0 and lad.runs_completed == 1
    assert lad.net > 500


# ---------- interactive dashboard ----------
def _page(cands, lad=None):
    import json as j
    from ladder import render as rnd
    lad = lad or Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    return rnd.render(j.loads(j.dumps(lad.__dict__, default=str)),
                      cands, [], 1.667, (1.50, 1.667))


CAND = {"pick": "Milwaukee Brewers", "decimal": 1.633, "american": -158,
        "fair_prob": 0.586, "league": "mlb", "matchup": "MIL @ CHC",
        "hold": 0.045, "starts_in_h": 2.6,
        "start_utc": "2026-09-05T20:00:00Z"}


def test_each_candidate_gets_editable_odds_inputs():
    doc = _page([CAND, dict(CAND, pick="Pittsburgh Pirates")])
    for i in (0, 1):
        assert f"id='am{i}'" in doc and f"id='de{i}'" in doc
        assert f"id='card{i}'" in doc and f"id='reset{i}'" in doc


def test_data_island_is_valid_json_and_script_safe():
    import json as j, re
    doc = _page([dict(CAND, pick="A </script> B")])
    m = re.search(r'id="ladder-data">(.*?)</script>', doc, re.S)
    data = j.loads(m.group(1).replace("<\\/", "</"))
    assert data["state"]["max_rung"] == 10
    assert data["candidates"][0]["decimal"] == 1.633
    # a stray </script> in a team name must not break out of the data island
    assert "A </script> B" not in doc


def test_command_box_present_only_with_candidates():
    assert "id=cmd>" in _page([CAND])
    empty = _page([])
    assert "<div class=cmdbox>" not in empty   # the CSS rule still exists
    assert "id=cmd>" not in empty
    assert "No qualifying bet" in empty


def test_history_table_lists_every_settled_bet():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    for i in range(7):
        lad.place({"pick": f"Team {i}", "decimal": 1.6, "league": "mlb"})
        lad.settle("win" if i % 3 else "loss")
    doc = _page([], lad)
    assert "Bet history — 7 settled" in doc
    for i in range(7):
        assert f"Team {i}" in doc


def test_page_is_fully_offline():
    doc = _page([CAND])
    body = doc.replace('xmlns="http://www.w3.org/2000/svg"', "")
    body = body.split("<div class=foot>")[0]
    assert "http://" not in body and "https://" not in body


# ---------- browser ledger ----------
def test_ledger_ui_is_present_with_controls():
    doc = _page([CAND])
    for probe in ("My ladder", "id=lgr-json", "id=lgr-csv", "id=lgr-imp",
                  "id=lgr-clear", "id=lgr-rows", "id=lgr-stats",
                  "id=lgr-custom", "Right / wrong", "Profit / loss"):
        assert probe in doc, probe


def test_browser_ledger_enforces_one_pending_bet_and_can_settle_it():
    doc = _page([CAND, dict(CAND, pick="B")])
    assert "Settle current first" in doc
    assert "Settle or remove" in doc
    for result in ("win", "loss", "push"):
        assert f'data-result="{result}"' in doc


def test_add_button_on_every_candidate():
    doc = _page([CAND, dict(CAND, pick="B"), dict(CAND, pick="C")])
    for i in range(3):
        assert f"id='add{i}'" in doc
    assert "ladderAdd" in doc


def test_candidates_carry_identity_for_self_settlement():
    import json as j, re
    doc = _page([dict(CAND, event_id="401999", side="home")])
    data = j.loads(re.search(r'id="ladder-data">(.*?)</script>', doc, re.S)
                   .group(1).replace("<\\/", "</"))
    c = data["candidates"][0]
    assert c["event_id"] == "401999" and c["side"] == "home"
    assert c["league"] == "mlb" and c["matchup"] == "MIL @ CHC"
    assert c["start_utc"] == "2026-09-05T20:00:00Z"


def test_ledger_fetches_results_feed():
    doc = _page([CAND])
    assert "data/results.json" in doc
    assert "localStorage" in doc and "ladder.ledger.v1" in doc


def test_ledger_continuously_checks_and_reconciles_settlement():
    doc = _page([CAND])
    assert "setInterval(refreshResults,POLL_MS)" in doc
    assert "POLL_MS=60000" in doc
    assert "checkPendingAtESPN" in doc
    assert "id=lgr-check" in doc and "Check now" in doc
    assert "h.result && !local.result" in doc
    assert "advanced to rung" in doc and "restarted at rung 0" in doc


def test_ledger_reflow_matches_python_ladder():
    """The browser recomputes the chain; it must agree with the CLI."""
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10,
                 stake_increment=0.01)
    seq = [("win", 1.6), ("win", 1.55), ("loss", 1.52)]
    stakes = []
    for res, dec in seq:
        stakes.append(lad.next_stake())
        lad.place({"pick": "x", "decimal": dec})
        lad.settle(res)
    assert stakes == [5.0, 8.0, 12.4]      # 5 -> 8 -> 12.40, then reset
    assert lad.rung == 0 and lad.net == -5.0


def test_reset_boundary_preserves_history_but_ends_old_run():
    lad = Ladder(base_stake=5.0, rung=2, stake=12.0,
                 reset_at="2026-09-14T22:00:00+00:00",
                 history=[{"placed_at": "2026-09-05T12:00:00+00:00",
                           "result": "win", "stake": 5, "returned": 8}])
    assert len(lad.history) == 1
    assert lad.current_run_profit() == 0
    assert lad.current_run_stakes() == []


def test_browser_and_python_ladders_agree():
    """Two implementations of the same ladder is exactly what goes quietly wrong.

    This mirrors the JS reflow() in webledger.py and pins it to the Python one.
    The payout must be rounded to cents BEFORE compounding, or the two drift.
    """
    import math
    base, maxr, inc = 5.0, 10, 0.01

    def js_reflow(seq):
        rung, stake, net = 0, base, 0.0
        stakes = []
        for res, dec in seq:
            stk = math.floor(stake / inc + 1e-9) * inc
            stakes.append(round(stk, 2))
            ret = round(stk * dec, 2)
            if res == "win":
                stake = ret
                rung += 1
                if rung >= maxr:
                    net += stake - base
                    rung, stake = 0, base
            elif res == "loss":
                net -= base
                rung, stake = 0, base
        return stakes, rung, round(net, 2)

    seq = [("win", 1.60), ("win", 1.55), ("win", 1.62), ("win", 1.51),
           ("loss", 1.52), ("win", 1.58)]
    js_stakes, js_rung, js_net = js_reflow(seq)

    lad = Ladder(one_bet_per_day=False, base_stake=base, max_rung=maxr,
                 stake_increment=inc)
    py_stakes = []
    for res, dec in seq:
        py_stakes.append(lad.next_stake())
        lad.place({"pick": "x", "decimal": dec})
        lad.settle(res)

    assert js_stakes == py_stakes
    assert js_rung == lad.rung
    assert abs(js_net - lad.net) < 0.005


def test_payout_rounds_to_cents_before_compounding():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10,
                 stake_increment=0.01)
    for dec in (1.60, 1.55, 1.62):
        lad.place({"pick": "x", "decimal": dec}); lad.settle("win")
    # 5 -> 8.00 -> 12.40 -> 20.09 (not 20.08, which full float precision gives)
    assert lad.next_stake() == 20.09


def test_results_json_shape():
    """What the browser expects to find in docs/data/results.json."""
    import json as j
    payload = {"generated": "2026-09-03T14:00:00+00:00",
               "games": {"401999": {"completed": True, "winner": "home",
                                    "league": "mlb", "date": "2026-09-02",
                                    "score": "NYM 3 @ TB 6"}}}
    round_tripped = j.loads(j.dumps(payload))
    g = round_tripped["games"]["401999"]
    assert g["completed"] is True and g["winner"] in ("home", "away", "draw")


# ---------- seeded state ----------
def _three_win_fixture():
    """A fixed progression fixture, independent of the user's live wager file."""
    from ladder.oddsmath import american_to_decimal
    lad = Ladder(base_stake=5, max_rung=10, one_bet_per_day=False)
    for name, price in [("Yankees", -167), ("Pirates", -171), ("Liverpool", -195)]:
        lad.place({"pick": name, "decimal": american_to_decimal(price)})
        lad.settle("win")
    return lad


def test_three_wins_advance_to_rung_three():
    lad = _three_win_fixture()
    assert lad.rung == 3 and lad.stake == 19.15
    assert lad.pending is None and len(lad.history) == 3
    assert lad.history[-1]["pick"] == "Liverpool"
    assert lad.history[-1]["stake"] == 12.66
    assert lad.net == 0.0


def test_rounded_decimal_would_give_the_wrong_stake():
    """1.599 pays 8.00; the real -167 (1.5988...) pays 7.99. Store the real one."""
    from ladder.oddsmath import american_to_decimal
    assert round(5 * 1.599, 2) == 8.0
    assert round(5 * american_to_decimal(-167), 2) == 7.99


def test_saved_progression_restores_actual_next_stake(tmp_path):
    path = tmp_path / "ladder.json"
    _three_win_fixture().save(path)
    lad = Ladder.load(path)
    assert lad.next_stake() == 19.15 and lad.rung == 3


def test_repo_history_is_embedded_for_browser_seeding():
    import json as j, re
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    lad.place({"pick": "New York Yankees", "decimal": 1.599, "american": -167,
               "league": "mlb", "matchup": "NYY @ LAA"}, price=1.599)
    lad.settle("win")
    doc = _page([CAND], lad)
    data = j.loads(re.search(r'id="ladder-data">(.*?)</script>', doc, re.S)
                   .group(1).replace("<\\/", "</"))
    assert len(data["history"]) == 1
    assert data["history"][0]["pick"] == "New York Yankees"
    assert data["history"][0]["result"] == "win"
    assert data["history"][0]["id"].startswith("repo_")
    assert "lgr-seed" in doc


# ---------- staircase uses real stakes, not a rebuild from base ----------
def test_staircase_starts_from_the_live_stake():
    """Bug: R1 rendered as $7.92 (base compounded at the window midpoint)
    when the real stake sitting on the table was $7.99."""
    from ladder import tui
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10,
                 stake_increment=0.01)
    from ladder.oddsmath import american_to_decimal
    d = american_to_decimal(-167)          # 1.5988..., NOT the rounded 1.599
    lad.place({"pick": "New York Yankees", "decimal": d}, price=d)
    lad.settle("win")
    assert lad.next_stake() == 7.99, "5.00 at -167 returns 7.99, not 8.00"
    assert lad.rung == 1

    bars = tui.ladder_bars(lad.rung, lad.max_rung, lad.base_stake, 1.583,
                           lad.next_stake(), lad.current_run_stakes())
    assert "7.99" in bars
    assert "7.92" not in bars          # the wrong number


def test_climbed_rung_shows_what_you_actually_collected():
    from ladder import tui
    bars = tui.ladder_bars(1, 10, 5.0, 1.583, 7.99, [5.0])
    r0 = [l for l in bars.splitlines() if "R0" in l][0]
    assert "5.00" in r0 and "7.99" in r0    # not 5.00 -> 7.92


def test_current_run_stakes_stops_at_a_loss():
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10)
    lad.place({"pick": "A", "decimal": 1.6}); lad.settle("win")
    lad.place({"pick": "B", "decimal": 1.6}); lad.settle("loss")
    assert lad.current_run_stakes() == []
    lad.place({"pick": "C", "decimal": 1.6}); lad.settle("win")
    assert lad.current_run_stakes() == [5.0]


def test_dashboard_svg_uses_real_stakes():
    from ladder import render as rnd
    lad = Ladder(one_bet_per_day=False, base_stake=5.0, max_rung=10,
                 stake_increment=0.01)
    from ladder.oddsmath import american_to_decimal
    d = american_to_decimal(-167)
    lad.place({"pick": "A", "decimal": d}, price=d)
    lad.settle("win")
    doc = _page([CAND], lad)
    assert "$7.99" in doc
