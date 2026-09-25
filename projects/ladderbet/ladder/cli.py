"""ladder — command line interface. No API key required."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from . import espn
from .selector import collect, rank, screen_event
from .state import Ladder
from .sim import simulate
from .oddsmath import survival, ladder_ev
from . import render as rnd
from . import tui
from . import ledger as ldg
from . import backtest as bt

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.json"
DEFAULT_STATE = ROOT / "state" / "ladder.json"


def _cfg(path) -> dict:
    return json.loads(Path(path).read_text())


def _load(args, cfg):
    """Load state, then apply config so settings changes take effect everywhere."""
    lad = Ladder.load(args.state)
    for k, v in cfg.get("ladder", {}).items():
        if not k.startswith("_") and hasattr(lad, k):
            setattr(lad, k, v)
    return lad


def _mock_fetch(path):
    data = json.loads(Path(path).read_text())
    def fetch(league, date=None):
        return data.get(league, [])
    return fetch


# ---------------------------------------------------------------- commands
def cmd_leagues(args, cfg):
    for k, v in espn.LEAGUES.items():
        tag = "  (3-way: draw counts as a separate outcome)" if k in espn.THREE_WAY else ""
        print(f"  {k:<7} {v}{tag}")


def cmd_pick(args, cfg):
    sel = cfg["selection"]
    fetch = _mock_fetch(args.mock) if args.mock else None
    leagues = args.leagues.split(",") if args.leagues else sel["leagues"]

    cands, warnings = collect(
        leagues=leagues,
        min_decimal=sel["min_decimal"],
        max_decimal=sel["max_decimal"],
        horizon_hours=1e9 if args.mock else sel["horizon_hours"],
        max_hold=sel.get("max_hold", 0.10),
        date=args.date,
        fetch=fetch,
    )

    for w in warnings:
        print(f"  - {w}", file=sys.stderr)

    ranked = rank(cands)
    if not ranked:
        print(f"\nNo qualifying bet in the {sel['min_decimal']}–{sel['max_decimal']} "
              f"window ({sel['max_decimal']:.3f} = -150, {sel['min_decimal']:.2f} = -200).")
        print("No bet is a valid day. The ladder holds; it does not reset.")
        return

    lad_stake = _load(args, cfg).next_stake()
    print()
    print(tui.rule(f"{len(ranked)} QUALIFYING  ·  stake ${lad_stake:.2f}"))
    for i, c in enumerate(ranked[:args.top], 1):
        be = 1.0 / c.decimal
        head = tui.bold(c.pick) if i == 1 else c.pick
        star = tui.gold(" *") if i == 1 else "  "
        print(f"\n{tui.dim('[%d]' % i)}{star} {head}  "
              f"{tui.gold('%+.0f' % c.american)} {tui.dim('(%.3f)' % c.decimal)}")
        print(f"      {tui.dim(c.league.upper() + '  ' + c.matchup)}")
        nxt = lad_stake
        ret = nxt * c.decimal
        print(f"      {tui.gold('stake $%.2f -> $%.2f' % (nxt, ret))}"
              f"{tui.dim('  (profit $%.2f)' % (ret - nxt))}")
        print(f"      {tui.probbar(c.fair_prob, 22, be)} "
              f"{tui.bold('%.1f%%' % (c.fair_prob*100))} win  "
              f"{tui.dim('need %.1f%%' % (be*100))}  "
              f"{tui.dim('hold %.2f%%' % (c.hold*100))}")
        line = f"      {tui.dim('starts in %.1fh' % c.starts_in_h)}"
        if c.steam:
            line += tui.dim(f"  ·  {c.steam}")
        print(line)
    print()
    print(tui.dim(f"  choose one:  python -m ladder place N "
                  f"[--price 1.52] [--stake 4.75]"))
    print()

    if args.place:
        lad = _load(args, cfg)
        pick_i = max(1, min(args.pick, len(ranked))) - 1
        if args.force:
            lad.one_bet_per_day, lad.halted = False, False
        try:
            bet = lad.place(ranked[pick_i].to_dict(),
                            price=args.price, stake=args.stake)
        except RuntimeError as e:
            # Expected conditions (bet pending, day lock, stop-loss, cap).
            # Report and exit clean so automation does not go red.
            print(tui.gold(f"  not placed: {e}"))
            return
        lad.save(args.state)
        print(f"PLACED rung {bet['rung']}: ${bet['stake']:.2f} on {bet['pick']} "
              f"@ {bet['decimal']:.3f} -> returns ${bet['to_return']:.2f}")
        sl = bet.get("slippage")
        if sl:
            w = tui.red if sl < 0 else tui.green
            print(f"  screened {bet['screened_decimal']:.3f}, "
                  f"took {bet['decimal']:.3f}  {w('%+.3f' % sl)}")
        if lad.would_exceed_cap():
            print(tui.gold("  note: next rung would exceed max_stake — "
                           "cash out after this one"))


def cmd_backtest(args, cfg):
    from datetime import date, timedelta
    sel = cfg["selection"]
    leagues = args.leagues.split(",") if args.leagues else sel["leagues"]
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)

    n = args.days * len(leagues)
    print(f"replaying {args.days} days x {len(leagues)} leagues "
          f"({start} to {end}, ~{n} requests, cached in .cache/)")
    print(tui.dim("  first run is slow; re-runs are instant\n"))

    def prog(ds, dr):
        if dr is None:
            print(f"  {ds}  {tui.dim('no bet')}")
        else:
            c = tui.green if dr.result == "win" else tui.red if dr.result == "loss" else tui.dim
            tag = c(dr.result.upper().ljust(5))
            print(f"  {ds}  {tag} {dr.pick[:24]:<25}"
                  f"{dr.decimal:.3f}  {tui.dim('%d cands' % dr.n_candidates)}")

    res = bt.run(leagues, start, end, sel["min_decimal"], sel["max_decimal"],
                 sel.get("max_hold", 0.10), use_open=args.use_open,
                 sleep=args.sleep, use_cache=not args.no_cache,
                 progress=None if args.quiet else prog)

    if args.csv:
        Path(args.csv).write_text(bt.to_csv(res))
        print(f"\nwrote {args.csv}")

    s = res.summary(cfg["ladder"]["base_stake"])
    if not s.get("graded"):
        print("\nNo gradeable days. Try more days, more leagues, or check "
              "the leagues were actually in season.")
        return

    print()
    print(tui.rule("BACKTEST"))
    print(f"  {s['days_scanned']} days scanned, {s['days_with_a_bet']} with a "
          f"qualifying bet, {s['no_bet_days']} without")
    print(f"  avg price {s['avg_decimal']:.3f}   longest streak "
          f"{s['longest_streak']}")
    print()
    hit, pred = s["actual_hit_rate"], s["model_predicted"]
    gap, edge = s["calibration_gap"], s["edge_vs_breakeven"]
    gc = tui.green if abs(gap) < 0.03 else tui.gold
    ec = tui.green if edge > 0 else tui.red
    print(f"  actual hit rate   {tui.bold('%.1f%%' % (hit*100))} "
          f"({s['wins']}/{s['graded']})")
    print(f"  95% CI            [{s['ci_low']:.1%}, {s['ci_high']:.1%}]"
          f"   {tui.dim('width %.1f pts' % s['ci_width_pts'])}")
    print(f"  model predicted   {pred:.1%}")
    print(f"  calibration gap   {gc('%+.1f pts' % (gap*100))}  "
          f"{tui.dim('(actual minus predicted)')}")
    print(f"  break-even needed {s['break_even_needed']:.1%}")
    print(f"  edge vs break-even {ec('%+.1f pts' % (edge*100))}")

    print()
    if s["beats_breakeven_significantly"]:
        print(tui.green("  The interval clears break-even. Still only one "
                        "sample — re-run monthly before believing it."))
    elif s["worse_than_breakeven_significantly"]:
        print(tui.red("  The interval sits entirely BELOW break-even. "
                      "This window loses money."))
    else:
        print(tui.gold("  VERDICT: indistinguishable from break-even."))
        print(tui.dim("  The confidence interval straddles the line, so this "
                      "sample cannot tell"))
        print(tui.dim("  an edge from noise. Do not read the calibration gap "
                      "as signal."))
    print(tui.dim(f"  Bets needed to detect a real 5-pt edge: "
                  f"{s['n_needed_for_5pt_edge']:,}   "
                  f"for 2 pts: {s['n_needed_for_2pt_edge']:,}"))
    print(tui.dim(f"  At one bet a day that is "
                  f"{s['n_needed_for_5pt_edge']/365:.1f} and "
                  f"{s['n_needed_for_2pt_edge']/365:.1f} years."))

    if s.get("by_price"):
        print()
        print(tui.rule("BY PRICE BAND"))
        print(tui.dim(f"  {'band':<13}{'n':>4}{'hit':>8}{'95% CI':>18}"
                      f"{'need':>8}"))
        for b in s["by_price"]:
            c = tui.green if b["beats_breakeven"] else tui.dim
            ci = f"[{b['ci_low']:.0%},{b['ci_high']:.0%}]"
            print(f"  {b['range']:<13}{b['n']:>4}{c('%7.1f%%' % (b['hit_rate']*100))}"
                  f"{ci:>18}{b['break_even']:>7.0%}")

    if s.get("by_league") and len(s["by_league"]) > 1:
        print()
        print(tui.rule("BY LEAGUE"))
        for b in s["by_league"]:
            print(f"  {b['league'].upper():<7}{b['n']:>4} bets"
                  f"{b['hit_rate']:>8.1%}   "
                  f"{tui.dim('[%.0f%%, %.0f%%]' % (b['ci_low']*100, b['ci_high']*100))}")
    print()
    print(tui.rule("LADDER, BY CASH-OUT RUNG"))
    print(tui.dim(f"  {'rung':>5}{'net':>10}{'cashouts':>10}{'busts':>8}"
                  f"{'best':>7}"))
    for L in s["ladders"]:
        c = tui.green if L["net"] > 0 else tui.red
        star = tui.gold(" *") if L == max(s["ladders"], key=lambda x: x["net"]) else "  "
        print(f"  {L['max_rung']:>5}{c('%+9.2f' % L['net'])}{L['cashouts']:>10}"
              f"{L['busts']:>8}{L['best_streak']:>7}{star}")
    if s.get("bootstrap"):
        print()
        print(tui.rule("SAME BETS, RESHUFFLED (4000 bootstraps)"))
        print(tui.dim(f"  {'rung':>5}{'actual':>10}{'median':>10}{'p05':>10}"
                      f"{'p95':>10}{'profit':>9}"))
        for b in s["bootstrap"]:
            if not b:
                continue
            c = tui.green if b["median"] > 0 else tui.red
            print(f"  {b['max_rung']:>5}{b['actual']:>+10.2f}"
                  f"{c('%+9.2f' % b['median'])}{b['p05']:>+10.2f}"
                  f"{b['p95']:>+10.2f}{b['pct_profitable']:>8.0%}")
        print(tui.dim("  A ladder's net depends on the ORDER results arrive in."))
        print(tui.dim("  The 'actual' column is one draw from this spread, "
                      "not the expected outcome."))

    print()
    print(tui.dim("  Selection used the CLOSING price, which you cannot know "
                  "when betting."))
    print(tui.dim("  Re-run with --use-open for the pessimistic bound; truth "
                  "is in between."))
    print()


def cmd_amend(args, cfg):
    lad = _load(args, cfg)
    b = lad.amend(price=args.price, stake=args.stake)
    lad.save(args.state)
    print(f"amended: ${b['stake']:.2f} on {b['pick']} @ {b['decimal']:.3f} "
          f"-> ${b['to_return']:.2f}")
    if b.get("slippage"):
        print(f"  vs screened {b['screened_decimal']:.3f}: {b['slippage']:+.3f}")


def cmd_ledger(args, cfg):
    lad = _load(args, cfg)
    st = json.loads(json.dumps(lad.__dict__, default=str))

    if args.csv:
        Path(args.csv).write_text(ldg.to_csv(st))
        print(f"wrote {args.csv}")
        return

    rows = ldg.rows(st)
    if not rows:
        print("no settled bets yet")
        return

    print()
    print(tui.rule("LEDGER"))
    print(tui.dim(f"  {'date':<11}{'pick':<22}{'R':>2} {'price':>7}"
                  f"{'stake':>9}{'ret':>9}{'P/L':>9}{'total':>9}"))
    for r in rows[-args.limit:]:
        res = r["result"]
        col = tui.green if res in ("win", "cashout") else tui.red if res == "loss" else tui.dim
        price = f"{float(r['decimal']):.3f}" if r["decimal"] not in ("", None) else "  —  "
        stake = f"{float(r['stake']):.2f}" if r["stake"] not in ("", None) else "—"
        ret = f"{float(r['returned']):.2f}" if r["returned"] not in ("", None) else "—"
        pl = f"{float(r['profit_loss']):+.2f}" if r["profit_loss"] not in ("", None) else "—"
        total = f"{float(r['running_profit_loss']):+.2f}"
        print(f"  {str(r['settled_at'])[:10]:<11}{col(r['pick'][:21]):<22}"
              f"{r['rung']!s:>2} {price:>7}{stake:>9}{ret:>9}{pl:>9}{total:>9}")

    s = ldg.summary(st)
    print()
    print(tui.rule("SUMMARY"))
    print(f"  {s['bets']} bets   {s['wins']}W-{s['losses']}L   "
          f"win rate {s['win_rate']:.1%}   staked ${s['total_staked']:,.2f}")
    plc = tui.green if s["profit_loss"] > 0 else tui.red if s["profit_loss"] < 0 else tui.dim
    pl_text = f"${s['profit_loss']:+,.2f}"
    print(f"  bet profit/loss {plc(pl_text)}")
    print(f"  runs cashed {s['runs_cashed']}   busted {s['runs_busted']}   "
          f"net ${s['net']:+,.2f}")
    if s["avg_slippage"] is not None:
        c = tui.red if s["avg_slippage"] < 0 else tui.green
        print(f"  avg slippage {c('%+.4f' % s['avg_slippage'])} over "
              f"{s['slippage_n']} bets  {tui.dim('(screened price vs what you took)')}")
    if s["avg_clv"] is not None:
        c = tui.green if s["avg_clv"] > 0 else tui.red
        print(f"  avg CLV {c('%+.4f' % s['avg_clv'])}   beat the close "
              f"{s['clv_beat_rate']:.1%} of {s['clv_n']} bets")
        print(tui.dim("  CLV is the honest scoreboard — outcome luck washes out, "
                      "this does not."))
    print()


def cmd_render(args, cfg):
    sel = cfg["selection"]
    lad = _load(args, cfg)
    fetch = _mock_fetch(args.mock) if args.mock else None
    cands, warnings = collect(
        leagues=sel["leagues"], min_decimal=sel["min_decimal"],
        max_decimal=sel["max_decimal"],
        horizon_hours=1e9 if args.mock else sel["horizon_hours"],
        max_hold=sel.get("max_hold", 0.10), date=args.date, fetch=fetch)
    ranked = [c.to_dict() for c in rank(cands)]
    if not args.mock:
        from . import accuracy
        accuracy.update(Path(args.state).parent / "model_accuracy.json",
                        Path(args.out).parent / "data/accuracy.json", ranked)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    public_state = json.loads(json.dumps(lad.__dict__, default=str))
    if getattr(args, "public", False):
        public_state.update(history=[], pending=None, rung=0, stake=public_state.get("base_stake", 5), net=0, runs_completed=0, runs_busted=0, reset_at="")
    out.write_text(rnd.render(public_state,
                              ranked, warnings, sel["max_decimal"],
                              (sel["min_decimal"], sel["max_decimal"])))
    # results.json: what the browser ledger settles itself against.
    if not args.mock:
        from datetime import date, timedelta
        games = {}
        today = date.today()
        for lg in sel["leagues"]:
            for back in range(0, args.results_days):
                d = (today - timedelta(days=back)).strftime("%Y%m%d")
                try:
                    evs = espn.events(lg, d)
                except espn.ESPNError:
                    continue
                for ev in evs:
                    comp = (ev.get("competitions") or [{}])[0]
                    st = espn.status(comp) or espn.status(ev)
                    if not st.get("completed"):
                        continue
                    tm = espn.teams(comp)
                    if "home" not in tm or "away" not in tm:
                        continue
                    if tm["home"].get("winner"):
                        winner = "home"
                    elif tm["away"].get("winner"):
                        winner = "away"
                    else:
                        winner = "draw"
                    games[str(ev.get("id"))] = {
                        "completed": True, "winner": winner, "league": lg,
                        "date": (ev.get("date") or "")[:10],
                        "score": f"{tm['away']['abbr']} {tm['away'].get('score')}"
                                 f" @ {tm['home']['abbr']} {tm['home'].get('score')}",
                    }
        rd = out.parent / "data"
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "results.json").write_text(json.dumps(
            {"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
             "games": games}, indent=1))
        print(f"wrote {rd/'results.json'} ({len(games)} finished games)")

    badge = out.parent / "badge.svg"
    badge.write_text(rnd.badge_svg(lad.rung, lad.max_rung, lad.net))
    print(f"wrote {out} and {badge}")


def cmd_place(args, cfg):
    """Place a specific candidate by its rank number."""
    sel = cfg["selection"]
    fetch = _mock_fetch(args.mock) if args.mock else None
    cands, _ = collect(
        leagues=args.leagues.split(",") if args.leagues else sel["leagues"],
        min_decimal=sel["min_decimal"], max_decimal=sel["max_decimal"],
        horizon_hours=1e9 if args.mock else sel["horizon_hours"],
        max_hold=sel.get("max_hold", 0.10), date=args.date, fetch=fetch)
    ranked = rank(cands)
    if not ranked:
        print("no qualifying bets right now")
        return
    if args.n < 1 or args.n > len(ranked):
        print(f"pick a number between 1 and {len(ranked)}")
        for i, c in enumerate(ranked, 1):
            print(f"  {i}. {c.pick} {c.american:+.0f} ({c.league.upper()})")
        return

    c = ranked[args.n - 1]
    lad = _load(args, cfg)
    if args.force:
        lad.one_bet_per_day, lad.halted = False, False
    bet = lad.place(c.to_dict(), price=args.price, stake=args.stake)
    lad.save(args.state)

    print(f"\nPLACED #{args.n} rung {bet['rung']}: {tui.bold(bet['pick'])} "
          f"{bet['american']:+.0f}")
    print(f"  {tui.dim(bet.get('league','').upper() + '  ' + bet.get('matchup',''))}")
    print(f"  stake ${bet['stake']:.2f} -> returns ${bet['to_return']:.2f}"
          f"  {tui.dim('(profit $%.2f)' % (bet['to_return'] - bet['stake']))}")
    if bet.get("slippage"):
        w = tui.red if bet["slippage"] < 0 else tui.green
        print(f"  screened {bet['screened_decimal']:.3f}, took "
              f"{bet['decimal']:.3f}  {w('%+.3f' % bet['slippage'])}")
    print()


def cmd_record(args, cfg):
    """Log a bet you already placed and, optionally, already know the result of.

    The automation cannot see your betting account. When you place at the book
    yourself, or when a game has already finished, this is how the ladder finds
    out about it.
    """
    lad = _load(args, cfg)
    if args.force:
        lad.one_bet_per_day, lad.halted = False, False
    if lad.pending and not args.force:
        print(tui.gold(f"  a bet is already pending: {lad.pending.get('pick')}. "
                       f"Settle it first, or pass --force."))
        return

    dec = args.price
    if dec is None and args.american is not None:
        from .oddsmath import american_to_decimal
        dec = american_to_decimal(args.american)
    if dec is None:
        print("give the price: --price 1.599 or --american -167")
        return

    from .oddsmath import decimal_to_american
    cand = {"pick": args.pick, "decimal": dec,
            "american": decimal_to_american(dec),
            "league": args.league or "", "matchup": args.matchup or "",
            "provider": args.book, "side": "", "event_id": "", "start_utc": ""}

    bet = lad.place(cand, price=dec, stake=args.stake)
    if args.on:
        bet["placed_at"] = f"{args.on}T18:00:00+00:00"
    print(f"\nrecorded rung {bet['rung']}: {tui.bold(bet['pick'])} "
          f"{bet['american']:+.0f}   ${bet['stake']:.2f} -> ${bet['to_return']:.2f}")

    if args.result:
        b = lad.settle(args.result)
        if args.on:
            b["settled_at"] = f"{args.on}T23:30:00+00:00"
        c = tui.green if args.result == "win" else tui.red
        print(f"  settled {c(args.result.upper())}   "
              f"returned ${b.get('returned', 0):.2f}")
        print(f"  now at rung {tui.gold(str(lad.rung))}/{lad.max_rung}, "
              f"next stake ${lad.next_stake():.2f}")
    else:
        print(tui.dim("  left pending — settle it with `ladder settle win|loss`"))
    lad.save(args.state)
    print()


def cmd_status(args, cfg):
    lad = _load(args, cfg)
    if args.at:
        d, src = args.at, "your --at override"
    elif lad.pending and lad.pending.get("decimal"):
        d, src = float(lad.pending["decimal"]), "your pending bet"
    else:
        d = (cfg["selection"]["min_decimal"] + cfg["selection"]["max_decimal"]) / 2
        src = "midpoint of your window"
    netc = tui.green if lad.net > 0 else tui.red if lad.net < 0 else tui.dim

    print()
    print(tui.rule("LADDER"))
    print(f"  rung {tui.gold(str(lad.rung))}{tui.dim('/' + str(lad.max_rung))}"
          f"   next {tui.bold('$%.2f' % lad.next_stake())} {lad.currency}"
          f"   net {netc('%+.2f' % lad.net)}")
    print(f"  {tui.dim('new money at risk this run')} ${lad.base_stake:.2f}"
          f"   {tui.dim('cashed')} {lad.runs_completed}"
          f"   {tui.dim('busted')} {lad.runs_busted}")

    settled = [h for h in lad.history if h.get("result") in ("win", "loss")]
    if settled:
        w = sum(1 for h in settled if h["result"] == "win")
        rate, be = w / len(settled), 1.0 / d
        rc = tui.green if rate >= be else tui.red
        s = ldg.summary(lad.__dict__)
        plc = tui.green if s["profit_loss"] > 0 else tui.red if s["profit_loss"] < 0 else tui.dim
        pl_text = f"${s['profit_loss']:+,.2f}"
        print(f"  {tui.dim('record')} {w}-{len(settled)-w}"
              f"   {tui.dim('win rate')} {rc('%.1f%%' % (rate*100))}"
              f"   {tui.dim('need')} {be:.1%}"
              f"   {tui.dim('P/L')} {plc(pl_text)}")

    if lad.pending:
        p = lad.pending
        print()
        print(tui.rule("PENDING"))
        print(f"  {tui.bold(p['pick'])}  {tui.gold('%+.0f' % p.get('american', 0))}"
              f"  {tui.dim('(' + p.get('provider', '?') + ')')}")
        print(f"  {tui.dim(p.get('league','?').upper() + '  ' + p.get('matchup',''))}")
        print(f"  ${p['stake']:.2f} -> ${p['to_return']:.2f}")

    print()
    from .oddsmath import decimal_to_american as _d2a
    print(tui.rule(f"PROJECTION @ {d:.3f} ({_d2a(d):+.0f})"))
    print(tui.dim(f"  based on {src} — a shorter price shrinks every rung"))
    print(tui.ladder_bars(lad.rung, lad.max_rung, lad.base_stake, d,
                          lad.next_stake(), lad.current_run_stakes()))
    print()


def cmd_settle(args, cfg):
    lad = _load(args, cfg)
    if not lad.pending:
        print("no pending bet")
        return

    result = args.result
    if result == "auto":
        p = lad.pending
        result, detail = espn.grade_bet(
            p.get("league"), p.get("event_id"), p.get("side"),
            args.date, p.get("start_utc"))
        print(f"ESPN says: {result} ({detail})")
        if result == "pending":
            print("Game is not final yet. Nothing settled.")
            return

    closing = args.closing
    if closing is None and lad.pending.get("event_id") and not args.no_clv:
        try:
            ev = espn.find_event(
                lad.pending.get("league"), lad.pending["event_id"],
                args.date or espn.date_of(lad.pending.get("start_utc", "")))
            if ev:
                comp = (ev.get("competitions") or [{}])[0]
                for b in espn.moneylines(comp):
                    v = b.get(lad.pending.get("side"))
                    if v is not None:
                        from .oddsmath import american_to_decimal
                        closing = american_to_decimal(v)
                        break
        except Exception:
            closing = None

    bet = lad.settle(result, closing=closing)
    lad.save(args.state)
    if bet.get("clv") is not None:
        w = tui.green if bet["clv"] > 0 else tui.red
        print(f"  closing {bet['closing_decimal']:.3f}, you had "
              f"{bet['decimal']:.3f}  CLV {w('%+.3f' % bet['clv'])}")
    print(f"settled {bet['pick']}: {bet['result']} (returned ${bet.get('returned', 0):.2f})")
    print(f"now at rung {lad.rung}, next stake ${lad.next_stake():.2f}")


def cmd_cashout(args, cfg):
    lad = _load(args, cfg)
    banked = lad.cash_out()
    lad.save(args.state)
    print(f"banked ${banked:.2f}; ladder reset to rung 0")


def cmd_resume(args, cfg):
    lad = _load(args, cfg)
    lad.halted = False
    lad.save(args.state)
    print(f"resumed — {lad.recent_busts()} busts in the last "
          f"{lad.stop_loss_days} days")


def cmd_reset(args, cfg):
    lad = _load(args, cfg)
    lad.pending = None
    lad.reset_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    lad._reset()
    lad.save(args.state)
    print("ladder reset to rung 0")


def cmd_sim(args, cfg):
    r = simulate(base=cfg["ladder"]["base_stake"], decimal=args.decimal,
                 true_prob=args.prob, max_rung=cfg["ladder"]["max_rung"],
                 days=args.days, trials=args.trials)
    w = max(len(k) for k in r)
    for k, v in r.items():
        print(f"  {k:<{w}}  {v}")
    base, p = cfg["ladder"]["base_stake"], r["assumed_true_prob"]
    print("\nstreak probability at the assumed win rate:")
    for n in (3, 5, 8, 10, 15):
        print(f"  {n:>2} straight: {survival(p, n):>7.3%}   "
              f"pays ${base * args.decimal ** n:>10,.2f}   "
              f"EV ${ladder_ev(base, p, args.decimal, n):.2f}")


def cmd_dump(args, cfg):
    """Save today's raw ESPN payload as a test fixture."""
    out = {lg: espn.events(lg, args.date) for lg in args.leagues.split(",")}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"wrote {args.out} ({sum(len(v) for v in out.values())} events)")


# ---------------------------------------------------------------- parser
def main(argv=None):
    ap = argparse.ArgumentParser(prog="ladder", description="Daily ladder bet manager (keyless)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pick", help="find and optionally place today's bet")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--place", action="store_true")
    p.add_argument("--pick", type=int, default=1, help="which ranked bet to place")
    p.add_argument("--price", type=float, help="decimal odds you actually got")
    p.add_argument("--stake", type=float, help="override the computed stake")
    p.add_argument("--force", action="store_true",
                   help="override the one-bet-per-day lock")
    p.add_argument("--leagues", help="comma list, overrides config")
    p.add_argument("--date", help="YYYYMMDD")
    p.add_argument("--mock", help="path to a fixture from `ladder dump`")
    p.set_defaults(fn=cmd_pick)

    p = sub.add_parser("settle", help="settle the pending bet")
    p.add_argument("result", choices=["auto", "win", "loss", "push"], default="auto", nargs="?")
    p.add_argument("--date", help="YYYYMMDD of the game")
    p.add_argument("--closing", type=float, help="closing decimal odds, for CLV")
    p.add_argument("--no-clv", action="store_true", help="skip the CLV lookup")
    p.set_defaults(fn=cmd_settle)

    p = sub.add_parser("amend", help="correct the pending bet's price or stake")
    p.add_argument("--price", type=float, help="decimal odds you actually got")
    p.add_argument("--stake", type=float, help="stake you actually placed")
    p.set_defaults(fn=cmd_amend)

    p = sub.add_parser("record", help="log a bet you placed yourself")
    p.add_argument("pick", help='team or selection, e.g. "New York Yankees"')
    p.add_argument("--price", type=float, help="decimal odds, e.g. 1.599")
    p.add_argument("--american", type=float, help="american odds, e.g. -167")
    p.add_argument("--stake", type=float, help="defaults to the current rung stake")
    p.add_argument("--result", choices=["win", "loss", "push"],
                   help="settle it immediately")
    p.add_argument("--league", default="")
    p.add_argument("--matchup", default="")
    p.add_argument("--book", default="manual")
    p.add_argument("--on", help="date the bet was placed, YYYY-MM-DD")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("place", help="place candidate N from the pick list")
    p.add_argument("n", type=int)
    p.add_argument("--price", type=float, help="decimal odds you actually got")
    p.add_argument("--stake", type=float)
    p.add_argument("--leagues")
    p.add_argument("--date")
    p.add_argument("--mock")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_place)

    p = sub.add_parser("backtest", help="replay past days through the selector")
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--leagues")
    p.add_argument("--use-open", action="store_true",
                   help="price off the opening line (pessimistic bound)")
    p.add_argument("--csv")
    p.add_argument("--sleep", type=float, default=0.6)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_backtest)

    p = sub.add_parser("ledger", help="every bet, slippage, CLV, running net")
    p.add_argument("--csv", help="write to this path instead of printing")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(fn=cmd_ledger)

    p = sub.add_parser("dump", help="save raw ESPN JSON as a fixture")
    p.add_argument("--leagues", default="mlb,nfl")
    p.add_argument("--date")
    p.add_argument("--out", default="tests/fixtures/live.json")
    p.set_defaults(fn=cmd_dump)

    p = sub.add_parser("sim", help="monte carlo the ladder")
    p.add_argument("--decimal", type=float, default=1.55)
    p.add_argument("--prob", type=float)
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--trials", type=int, default=20000)
    p.set_defaults(fn=cmd_sim)

    p = sub.add_parser("render", help="build the HTML dashboard")
    p.add_argument("--out", default="docs/index.html")
    p.add_argument("--public", action="store_true", help="publish options without private wager history")
    p.add_argument("--date")
    p.add_argument("--mock")
    p.add_argument("--results-days", type=int, default=4,
                   help="days of finished games to publish for self-settlement")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("status")
    p.add_argument("--at", type=float,
                   help="project the ladder at this decimal price")
    p.set_defaults(fn=cmd_status)
    sub.add_parser("leagues").set_defaults(fn=cmd_leagues)
    sub.add_parser("cashout").set_defaults(fn=cmd_cashout)
    sub.add_parser("resume").set_defaults(fn=cmd_resume)
    sub.add_parser("reset").set_defaults(fn=cmd_reset)

    args = ap.parse_args(argv)
    try:
        args.fn(args, _cfg(args.config))
    except (espn.ESPNError, RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
