"""Track screened ladder options, independently of selected wagers."""
from datetime import datetime, timezone
from pathlib import Path
from . import espn
from . import model_accuracy as A


def update(state_path, output_path, candidates):
    log = A.load(state_path)
    A.record(log, [{"kind": "call", "league": c["league"], "event_id": c["event_id"],
                    "start": c["start_utc"], "matchup": c["matchup"], "pick": c["pick"],
                    "market": "ML", "side": c["side"], "price": c["american"],
                    "probability": c["fair_prob"], "tier": "SCREENED",
                    "edge": c.get("cross_book_edge") or 0, "book": c["provider"],
                    "three_way": c["league"] in espn.THREE_WAY} for c in candidates])
    results = {}
    now = datetime.now(timezone.utc)
    for r in log["records"].values():
        if r["result"] != "Pending" or A.instant(r["start"]) > now or r["event_id"] in results:
            continue
        try:
            ev = espn.find_event(r["league"], r["event_id"], espn.date_of(r["start"]))
        except espn.ESPNError:
            continue
        if not ev:
            continue
        comp = (ev.get("competitions") or [{}])[0]
        tm = espn.teams(comp)
        if "home" in tm and "away" in tm:
            results[r["event_id"]] = {"completed": espn.status(comp)["completed"] or espn.status(ev)["completed"],
                                       "home_score": tm["home"].get("score"), "away_score": tm["away"].get("score")}
    A.settle(log, results)
    A.save(state_path, log)
    report = A.report(log, "Ladder screened-option accuracy")
    report["method"] = "Every screened option is saved before the event, whether or not you choose it. Probabilities here are de-vigged market estimates, not an independent sports model. " + report["method"]
    A.save(output_path, report)
