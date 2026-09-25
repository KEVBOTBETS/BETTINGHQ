"""Render the ladder as a self-contained HTML dashboard.

No build step, no CDN, no JS framework. One file you can open locally or
publish to GitHub Pages.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from .oddsmath import decimal_to_american
from .webledger import LEDGER_CSS, LEDGER_HTML, LEDGER_JS

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0b0f14; --panel:#131a23; --line:#1e2936; --ink:#e6edf3;
  --dim:#7d8da1; --gold:#f0b429; --win:#2ecc71; --loss:#e74c3c;
  --cool:#4aa3ff;
}
body{background:var(--bg);color:var(--ink);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Inter,sans-serif;
  padding:20px 16px 60px;max-width:820px;margin:0 auto}
h1{font-size:19px;letter-spacing:.02em;font-weight:650}
.sub{color:var(--dim);font-size:12.5px;margin-top:3px}
.hero{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:18px 0 4px}
.rungnum{font-size:54px;font-weight:750;line-height:1;
  background:linear-gradient(180deg,var(--gold),#b9791a);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.of{color:var(--dim);font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:10px;margin:16px 0}
.card{background:var(--panel);border:1px solid var(--line);
  border-radius:12px;padding:12px 14px}
.k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.07em}
.v{font-size:21px;font-weight:640;margin-top:4px;font-variant-numeric:tabular-nums}
.pos{color:var(--win)} .neg{color:var(--loss)} .gold{color:var(--gold)}
section{margin-top:26px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;
  color:var(--dim);font-weight:620;margin-bottom:10px}
.pill{display:inline-block;padding:2px 9px;border-radius:99px;
  font-size:11px;font-weight:620;letter-spacing:.03em}
.pill.win{background:rgba(46,204,113,.15);color:var(--win)}
.pill.loss{background:rgba(231,76,60,.15);color:var(--loss)}
.pill.push{background:rgba(125,141,161,.15);color:var(--dim)}
.pill.live{background:rgba(240,180,41,.15);color:var(--gold)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--dim);font-weight:600;font-size:11px;
  text-transform:uppercase;letter-spacing:.06em;padding:6px 8px;
  border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);
  font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
.bet{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:13px 15px;margin-bottom:9px}
.bet.top{border-color:rgba(240,180,41,.45);
  box-shadow:0 0 0 1px rgba(240,180,41,.12),0 6px 22px -12px rgba(240,180,41,.5)}
.betrow{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.pick{font-weight:640;font-size:15px}
.price{font-variant-numeric:tabular-nums;font-weight:640;color:var(--gold)}
.meta{color:var(--dim);font-size:12px;margin-top:3px}
.bar{height:5px;background:var(--line);border-radius:99px;margin-top:9px;
  overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#b9791a,var(--gold))}
.odds{display:flex;gap:8px;align-items:flex-end;margin:10px 0 6px;flex-wrap:wrap}
.odds label{display:flex;flex-direction:column;gap:3px;font-size:10px;
  color:var(--dim);text-transform:uppercase;letter-spacing:.07em}
.odds input{background:var(--bg);border:1px solid var(--line);color:var(--ink);
  border-radius:7px;padding:7px 9px;font-size:14px;width:96px;
  font-variant-numeric:tabular-nums;font-family:ui-monospace,monospace}
.odds input:focus{outline:none;border-color:var(--gold)}
.mini{background:var(--line);border:none;color:var(--dim);border-radius:7px;
  padding:8px 11px;font-size:11px;cursor:pointer}
.mini:hover{color:var(--ink)}
.cmdbox{background:var(--panel);border:1px solid rgba(240,180,41,.35);
  border-radius:12px;padding:13px 15px;margin-top:12px}
.cmdpick{font-weight:640;font-size:15px;margin:4px 0 9px;color:var(--gold)}
.cmdrow{display:flex;gap:8px;align-items:center}
.cmdrow code{flex:1;background:var(--bg);border:1px solid var(--line);
  border-radius:7px;padding:9px 11px;font-size:12px;overflow-x:auto;
  white-space:nowrap;font-family:ui-monospace,monospace;color:var(--cool)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.scroll table{min-width:640px}
.lgr{margin-top:26px}
.lgr .row{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:11px 13px;margin-bottom:8px}
.lgr .row.pend{border-color:rgba(240,180,41,.4)}
.lgr .top{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.lgr .nm{font-weight:640;font-size:14px}
.lgr .sub2{color:var(--dim);font-size:12px;margin-top:2px}
.lgr .line{display:flex;align-items:center;gap:8px;margin-top:8px;flex-wrap:wrap;
  font-size:12.5px}
.lgr input.stk{background:var(--bg);border:1px solid var(--line);color:var(--ink);
  border-radius:6px;padding:5px 8px;width:84px;font-size:13px;
  font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums}
.lgr input.stk:focus{outline:none;border-color:var(--gold)}
.lgr .x{background:none;border:1px solid var(--line);color:var(--dim);
  border-radius:6px;padding:5px 9px;font-size:11px;cursor:pointer}
.lgr .x:hover{color:var(--loss);border-color:var(--loss)}
.addbtn{background:rgba(240,180,41,.12);border:1px solid rgba(240,180,41,.45);
  color:var(--gold);border-radius:7px;padding:8px 12px;font-size:12px;
  cursor:pointer;font-weight:600}
.addbtn:hover{background:rgba(240,180,41,.22)}
.addbtn.on{background:rgba(46,204,113,.15);border-color:rgba(46,204,113,.5);
  color:var(--win)}
.tools{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.exp{background:var(--bg);border:1px solid var(--line);border-radius:8px;
  padding:10px;margin-top:10px;font-size:11px;font-family:ui-monospace,monospace;
  color:var(--dim);max-height:170px;overflow:auto;white-space:pre-wrap;
  word-break:break-all}
.empty{background:var(--panel);border:1px dashed var(--line);border-radius:12px;
  padding:18px;text-align:center;color:var(--dim);font-size:13.5px}
.foot{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);
  color:var(--dim);font-size:11.5px;line-height:1.7}
.warn{background:rgba(231,76,60,.07);border:1px solid rgba(231,76,60,.25);
  border-radius:10px;padding:11px 13px;color:#f0a79f;font-size:12.5px;
  margin-top:16px}
"""



INTERACTIVE = """
<script>
(function(){
  var D = JSON.parse(document.getElementById('ladder-data').textContent);
  var cands = D.candidates, st = D.state;
  var sel = 0, prices = cands.map(function(c){ return c.decimal; });

  function a2d(a){ a=parseFloat(a); if(!a||Math.abs(a)<100) return null;
    return a>=100 ? 1+a/100 : 1+100/Math.abs(a); }
  function d2a(d){ return d>=2 ? (d-1)*100 : -100/(d-1); }
  function money(v){ return '$'+v.toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g,','); }

  function stakes(dec){
    var out=[], s = st.rung===0 ? st.base_stake : st.stake, inc = st.stake_increment||0.01;
    for(var i=st.rung;i<st.max_rung;i++){
      s = Math.floor(s/inc+1e-9)*inc;
      out.push({rung:i, stake:s, ret:s*dec});
      s = s*dec;
    }
    return out;
  }

  function drawLadder(dec){
    var rows = stakes(dec), host = document.getElementById('stair');
    if(!rows.length){ host.innerHTML=''; return; }
    var top = rows[rows.length-1].ret, RH=30, GAP=7, W=760;
    var H = 16 + rows.length*(RH+GAP) - GAP;
    var svg = '<svg viewBox="0 0 '+W+' '+H+'" width="100%" xmlns="http://www.w3.org/2000/svg">';
    rows.forEach(function(r,i){
      var y = 8 + (rows.length-1-i)*(RH+GAP);
      var w = Math.max(58, (r.stake/top)*(W-190));
      var live = (r.rung===st.rung);
      svg += '<rect x="46" y="'+y+'" width="'+w.toFixed(1)+'" height="'+RH+'" rx="7" fill="'+(live?'#f0b429':'#182231')+'"/>';
      svg += '<text x="14" y="'+(y+RH/2+4.5)+'" font-size="12" font-family="ui-monospace,monospace" fill="'+(live?'#f0b429':'#5f7085')+'">R'+r.rung+'</text>';
      var lbl = money(r.stake)+' \\u2192 '+money(r.ret);
      if(w>210){ svg += '<text x="58" y="'+(y+RH/2+4.5)+'" font-size="12.5" font-family="ui-monospace,monospace" fill="'+(live?'#1a1205':'#5f7085')+'" font-weight="600">'+lbl+'</text>'; }
      else { svg += '<text x="'+(46+w+10).toFixed(1)+'" y="'+(y+RH/2+4.5)+'" font-size="12.5" font-family="ui-monospace,monospace" fill="#7d8da1">'+lbl+'</text>'; }
    });
    svg += '</svg>';
    host.innerHTML = svg;
    var last = rows[rows.length-1];
    document.getElementById('cashout').textContent =
      'Ride all ' + rows.length + ' remaining rungs and rung ' + last.rung +
      ' pays ' + money(last.ret) + '. Risk stays ' + money(st.base_stake) + ' of new money.';
  }

  function refresh(){
    cands.forEach(function(c,i){
      var dec = prices[i];
      var stake = st.rung===0 ? st.base_stake : st.stake;
      var inc = st.stake_increment||0.01;
      stake = Math.floor(stake/inc+1e-9)*inc;
      var ret = stake*dec;
      document.getElementById('ret'+i).innerHTML =
        'stake '+money(stake)+' &rarr; <b>'+money(ret)+'</b> '+
        '<span style="color:var(--dim)">(profit '+money(ret-stake)+')</span>';
      document.getElementById('be'+i).textContent = (100/dec).toFixed(1)+'%';
      var edge = (c.fair_prob*dec-1)*100;
      var el = document.getElementById('edge'+i);
      el.textContent = (edge>=0?'+':'')+edge.toFixed(2)+'%';
      el.style.color = edge>=0 ? 'var(--win)' : 'var(--dim)';
      document.getElementById('card'+i).className = 'bet'+(i===sel?' top':'');
    });
    drawLadder(prices[sel]);
    var c = cands[sel];
    var cmd = 'python -m ladder place '+(sel+1)+' --price '+prices[sel].toFixed(4);
    document.getElementById('cmd').textContent = cmd;
    document.getElementById('cmdpick').textContent =
      c.pick+'  '+(d2a(prices[sel])>=0?'+':'')+d2a(prices[sel]).toFixed(0);
  }

  cands.forEach(function(c,i){
    var am = document.getElementById('am'+i), de = document.getElementById('de'+i);
    am.addEventListener('input', function(){
      var d = a2d(am.value); if(!d) return;
      prices[i]=d; de.value=d.toFixed(4); refresh();
    });
    de.addEventListener('input', function(){
      var d = parseFloat(de.value); if(!d || d<=1) return;
      prices[i]=d; am.value=d2a(d).toFixed(0); refresh();
    });
    document.getElementById('card'+i).addEventListener('click', function(e){
      if(e.target.tagName==='INPUT') return;
      sel=i; refresh();
    });
    var add = document.getElementById('add'+i);
    if(add) add.addEventListener('click', function(e){
      e.stopPropagation();
      if(window.ladderAdd) window.ladderAdd(i, prices[i]);
    });
    document.getElementById('reset'+i).addEventListener('click', function(e){
      e.stopPropagation();
      prices[i]=c.decimal; am.value=c.american.toFixed(0);
      de.value=c.decimal.toFixed(4); refresh();
    });
  });

  var btn = document.getElementById('copy');
  if(btn) btn.addEventListener('click', function(){
    var t = document.getElementById('cmd').textContent;
    if(navigator.clipboard) navigator.clipboard.writeText(t);
    btn.textContent='copied'; setTimeout(function(){btn.textContent='copy';},1200);
  });

  refresh();
})();
</script>
"""


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _money(v: float) -> str:
    return f"${v:,.2f}"


def ladder_svg(rung: int, max_rung: int, base: float, decimal: float,
               pending: dict | None = None, current_stake: float | None = None,
               past: list[float] | None = None) -> str:
    """Rungs as a climbing staircase. Filled = won, glowing = live, dim = ahead.

    Climbed rungs show the stakes actually bet; rungs ahead compound from the
    live stake, not from base at an assumed price.
    """
    W, RH, GAP, PAD = 760, 30, 7, 8
    H = PAD * 2 + max_rung * (RH + GAP) - GAP

    past = list(past or [])
    stakes = []
    for i in range(min(rung, max_rung)):
        stakes.append(past[i] if i < len(past) else base)
    s = current_stake if current_stake is not None else base
    for _ in range(rung, max_rung):
        stakes.append(round(s, 2))
        s = round(s * decimal, 2)
    top_payout = s

    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" '
             f'preserveAspectRatio="xMidYMid meet" '
             f'xmlns="http://www.w3.org/2000/svg" role="img" '
             f'aria-label="Ladder progress: rung {rung} of {max_rung}">']
    parts.append(
        '<defs>'
        '<linearGradient id="won" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#1d7a45"/><stop offset="1" stop-color="#2ecc71"/>'
        '</linearGradient>'
        '<linearGradient id="live" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#8a5a12"/><stop offset="1" stop-color="#f0b429"/>'
        '</linearGradient>'
        '<filter id="glow" x="-30%" y="-120%" width="160%" height="340%">'
        '<feGaussianBlur stdDeviation="5" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter></defs>')

    for i in range(max_rung):
        y = PAD + (max_rung - 1 - i) * (RH + GAP)
        frac = stakes[i] / top_payout
        w = max(58, frac * (W - 190))

        if i < rung:
            fill, txt, extra = "url(#won)", "#eafff2", ""
        elif i == rung:
            fill, txt, extra = "url(#live)", "#1a1205", ' filter="url(#glow)"'
        else:
            fill, txt, extra = "#182231", "#5f7085", ""

        parts.append(f'<rect x="46" y="{y}" width="{w:.1f}" height="{RH}" rx="7" '
                     f'fill="{fill}"{extra}/>')
        parts.append(f'<text x="14" y="{y + RH / 2 + 4.5}" font-size="12" '
                     f'font-family="ui-monospace,monospace" '
                     f'fill="{"#f0b429" if i == rung else "#5f7085"}">R{i}</text>')
        ret = stakes[i + 1] if (i < rung and i + 1 < len(stakes)) else stakes[i] * decimal
        label = f"{_money(stakes[i])} → {_money(ret)}"
        if w > 210:
            parts.append(f'<text x="58" y="{y + RH / 2 + 4.5}" font-size="12.5" '
                         f'font-family="ui-monospace,monospace" fill="{txt}" '
                         f'font-weight="600">{label}</text>')
        else:
            parts.append(f'<text x="{46 + w + 10:.1f}" y="{y + RH / 2 + 4.5}" '
                         f'font-size="12.5" font-family="ui-monospace,monospace" '
                         f'fill="#7d8da1">{label}</text>')

        if i == rung and pending:
            parts.append(f'<text x="{W - 8}" y="{y + RH / 2 + 4.5}" font-size="12" '
                         f'text-anchor="end" fill="#f0b429" font-weight="600">'
                         f'{_esc(pending.get("pick", ""))[:26]}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _spark(nets: list[float], w: int = 760, h: int = 54) -> str:
    if len(nets) < 2:
        return ""
    lo, hi = min(nets + [0.0]), max(nets + [0.0])
    span = (hi - lo) or 1.0
    step = w / (len(nets) - 1)
    pts = " ".join(f"{i * step:.1f},{h - (v - lo) / span * (h - 8) - 4:.1f}"
                   for i, v in enumerate(nets))
    zero = h - (0 - lo) / span * (h - 8) - 4
    end = nets[-1]
    col = "#2ecc71" if end > 0 else "#e74c3c" if end < 0 else "#7d8da1"
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" '
            f'xmlns="http://www.w3.org/2000/svg" aria-label="Net over time">'
            f'<line x1="0" y1="{zero:.1f}" x2="{w}" y2="{zero:.1f}" '
            f'stroke="#1e2936" stroke-dasharray="3 4"/>'
            f'<polyline points="{pts}" fill="none" stroke="{col}" '
            f'stroke-width="2" stroke-linejoin="round"/></svg>')


def projection_price(state: dict, candidates: list[dict],
                     window: tuple[float, float]) -> tuple[float, str]:
    """Which price the staircase should assume.

    Never the top of the window — that flatters every rung. Use the real price
    of the bet in play, or the bet you would actually place next.
    """
    pending = state.get("pending")
    if pending and pending.get("decimal"):
        return float(pending["decimal"]), "your pending bet"
    if candidates:
        d = candidates[0].get("decimal")
        if d:
            return float(d), "today's top candidate"
    return (window[0] + window[1]) / 2, "midpoint of your window (no bets today)"


def render(state: dict, candidates: list[dict], warnings: list[str],
           decimal: float, window: tuple[float, float]) -> str:
    rung = state.get("rung", 0)
    max_rung = state.get("max_rung", 8)
    base = state.get("base_stake", 5.0)
    net = state.get("net", 0.0)
    pending = state.get("pending")
    hist = [h for h in state.get("history", []) if h.get("result")]

    settled = [h for h in hist if h["result"] in ("win", "loss")]
    wins = sum(1 for h in settled if h["result"] == "win")
    rate = (wins / len(settled)) if settled else 0.0
    breakeven = 1.0 / decimal

    best, run = 0, 0
    for h in settled:
        run = run + 1 if h["result"] == "win" else 0
        best = max(best, run)

    nets, acc = [], 0.0
    for h in settled:
        if h["result"] == "loss":
            acc -= base
        elif h.get("cashed_out"):
            acc += h["cashed_out"] - base
        nets.append(round(acc, 2))

    decimal, dec_source = projection_price(state, candidates, window)
    past_stakes = [float(h.get("stake") or 0)
                   for h in state.get("history", []) if h.get("result") == "win"][-rung:] \
        if rung else []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    p = [f"<!doctype html><html lang=en><head><meta charset=utf-8>"
         f"<meta name=viewport content='width=device-width,initial-scale=1'>"
         f"<title>Ladder — rung {rung}</title><style>{CSS}</style></head><body>"]

    p.append("<h1>Ladder</h1>")
    low_am = decimal_to_american(window[0])
    high_am = decimal_to_american(window[1])
    p.append(f"<div class=sub>{_esc(now)} · favourite window "
             f"{window[0]:.2f}–{window[1]:.3f} decimal "
             f"({low_am:+.0f} to {high_am:+.0f}) · up to 10 choices · "
             f"{state.get('currency','CAD')}</div>")

    p.append(f"<div class=hero><span class=rungnum>{rung}</span>"
             f"<span class=of>of {max_rung} rungs</span></div>")

    nxt = base if rung == 0 else state.get("stake", base)
    ncls = "pos" if net > 0 else "neg" if net < 0 else ""
    p.append("<div class=grid>")
    p.append(f"<div class=card><div class=k>Next stake</div>"
             f"<div class='v gold'>{_money(nxt)}</div></div>")
    p.append(f"<div class=card><div class=k>New money at risk</div>"
             f"<div class=v>{_money(base)}</div></div>")
    p.append(f"<div class=card><div class=k>Banked ladder net</div>"
             f"<div class='v {ncls}'>{net:+,.2f}</div></div>")
    p.append(f"<div class=card><div class=k>Cashed / busted</div>"
             f"<div class=v>{state.get('runs_completed',0)} / "
             f"{state.get('runs_busted',0)}</div></div>")
    p.append("</div>")

    amer = decimal_to_american(decimal)
    p.append("<section><h2>Progress</h2>"
             f"<div class=sub style='margin:-4px 0 10px'>Projected at "
             f"<b>{decimal:.3f}</b> ({amer:+.0f}) — {_esc(dec_source)}. "
             f"Every rung compounds the price you actually get, so a shorter "
             f"price shrinks the whole ladder.</div>"
             f"<div id=stair>{ladder_svg(rung, max_rung, base, decimal, pending, nxt, past_stakes)}</div>"
             f"<div class=sub id=cashout style='margin-top:8px'></div>"
             "</section>")

    if pending:
        p.append("<section><h2>Pending</h2>"
                 f"<div class='bet top'><div class=betrow>"
                 f"<span class=pick>{_esc(pending.get('pick'))}</span>"
                 f"<span class=price>{pending.get('american',0):+.0f}</span></div>"
                 f"<div class=meta>{_esc(pending.get('league','').upper())} · "
                 f"{_esc(pending.get('matchup',''))}</div>"
                 f"<div class=meta>{_money(pending.get('stake',0))} → "
                 f"{_money(pending.get('to_return',0))} · "
                 f"<span class='pill live'>awaiting result</span></div>"
                 f"</div></section>")

    p.append("<section><h2>Today's candidates</h2>")
    if candidates:
        for i, c in enumerate(candidates[:10]):
            fair = c.get("fair_prob", 0)
            top = " top" if i == 0 else ""
            cd = float(c.get("decimal") or 0) or 1.0
            ret = nxt * cd
            am = c.get("american", 0)
            p.append(
                f"<div class='bet{top}' id='card{i}'>"
                f"<div class=betrow><span class=pick>"
                f"<span style='color:var(--dim);font-weight:600'>{i+1}.</span> "
                f"{_esc(c.get('pick'))}</span>"
                f"<span class=price id='edge{i}'></span></div>"
                f"<div class=meta>{_esc(c.get('league','').upper())} · "
                f"{_esc(c.get('matchup',''))} · in {c.get('starts_in_h',0):.1f}h</div>"
                f"<div class=odds>"
                f"<label>American<input id='am{i}' type='number' step='1' "
                f"value='{am:.0f}' inputmode='numeric'></label>"
                f"<label>Decimal<input id='de{i}' type='number' step='0.001' "
                f"value='{cd:.4f}' inputmode='decimal'></label>"
                f"<button class=mini id='reset{i}' type=button>reset</button>"
                f"<button class=addbtn id='add{i}' type=button>Select bet</button>"
                f"</div>"
                f"<div class=meta style='color:var(--ink)' id='ret{i}'>"
                f"stake {_money(nxt)} &rarr; <b>{_money(ret)}</b></div>"
                f"<div class=meta>win prob <b>{fair:.1%}</b> · "
                f"break-even <span id='be{i}'></span> · "
                f"hold {c.get('hold',0):.2%}"
                + (f" · {_esc(c.get('steam'))}" if c.get("steam") else "")
                + f"</div>"
                f"<div class=bar><i style='width:{fair*100:.1f}%'></i></div>"
                f"</div>")
    else:
        p.append("<div class=empty>No qualifying bet in the window today.<br>"
                 "<b>No bet is a valid day.</b> The ladder holds; it does not reset."
                 "</div>")
    if candidates:
        p.append("<div class=cmdbox><div class=k>Preview — tap a card to change"
                 "</div><div class=cmdpick id=cmdpick></div>"
                 "<div class=cmdrow><code id=cmd></code>"
                 "<button class=mini id=copy type=button>copy</button></div>"
                 "<div class=k style='margin-top:8px;text-transform:none;"
                 "letter-spacing:0'>Use <b>Select bet</b> to put one option in "
                 "your ladder, or run the command to commit it to the repo.</div></div>")
    p.append("</section>")

    if settled:
        rcls = "pos" if rate >= breakeven else "neg"
        p.append("<section><h2>Record</h2><div class=grid>")
        try:
            from .ledger import summary as _sum
            lsum = _sum(state)
        except Exception:
            lsum = {}
        pl = float(lsum.get("profit_loss", 0) or 0)
        pl_cls = "pos" if pl > 0 else "neg" if pl < 0 else ""
        p.append(f"<div class=card><div class=k>Right / wrong</div>"
                 f"<div class='v gold'>{wins} / {len(settled)-wins}</div></div>")
        p.append(f"<div class=card><div class=k>Accuracy</div>"
                 f"<div class='v {rcls}'>{rate:.1%}</div></div>")
        p.append(f"<div class=card><div class=k>Bet profit / loss</div>"
                 f"<div class='v {pl_cls}'>{pl:+,.2f}</div></div>")
        p.append(f"<div class=card><div class=k>Break-even needed</div>"
                 f"<div class=v>{breakeven:.1%}</div></div>")
        p.append(f"<div class=card><div class=k>Best streak</div>"
                 f"<div class='v gold'>{best}</div></div>")
        p.append("</div>")

        if lsum.get("avg_clv") is not None or lsum.get("avg_slippage") is not None:
            p.append("<div class=grid>")
            if lsum.get("avg_clv") is not None:
                c = "pos" if lsum["avg_clv"] > 0 else "neg"
                p.append(f"<div class=card><div class=k>Avg CLV</div>"
                         f"<div class='v {c}'>{lsum['avg_clv']:+.4f}</div>"
                         f"<div class=k style='margin-top:4px'>beat close "
                         f"{lsum['clv_beat_rate']:.0%}</div></div>")
            if lsum.get("avg_slippage") is not None:
                c = "neg" if lsum["avg_slippage"] < 0 else "pos"
                p.append(f"<div class=card><div class=k>Avg slippage</div>"
                         f"<div class='v {c}'>{lsum['avg_slippage']:+.4f}</div>"
                         f"<div class=k style='margin-top:4px'>screened vs taken"
                         f"</div></div>")
            p.append(f"<div class=card><div class=k>Total staked</div>"
                     f"<div class=v>{_money(lsum.get('total_staked',0))}</div></div>")
            p.append("</div>")
        sp = _spark(nets)
        if sp:
            p.append(f"<div style='margin-top:8px'>{sp}</div>")
        p.append("</section>")

        try:
            from .ledger import rows as _rows
            lrows = _rows(state)
        except Exception:
            lrows = []
        p.append(f"<section><h2>Bet history — {len(settled)} settled</h2>"
                 "<div class=scroll><table><tr><th>Date</th><th>Pick</th>"
                 "<th>R</th><th>Price</th><th>Stake</th><th>Return</th>"
                 "<th>P/L</th><th>Total</th><th></th></tr>")
        for r in reversed(lrows):
            res = r.get("result", "")
            cls = res if res in ("win", "loss", "push") else "push"
            dec = r.get("decimal")
            price = f"{float(dec):.3f}" if dec not in ("", None) else "—"
            stake = _money(float(r["stake"])) if r.get("stake") not in ("", None) else "—"
            ret = _money(float(r["returned"])) if r.get("returned") not in ("", None) else "—"
            row_pl = float(r.get("profit_loss") or 0)
            total_pl = float(r.get("running_profit_loss") or 0)
            pcol = "pos" if row_pl > 0 else "neg" if row_pl < 0 else ""
            tcol = "pos" if total_pl > 0 else "neg" if total_pl < 0 else ""
            p.append(f"<tr><td>{_esc(str(r.get('settled_at',''))[:10])}</td>"
                     f"<td>{_esc(r.get('pick'))}<div class=k "
                     f"style='text-transform:none;letter-spacing:0'>"
                     f"{_esc(r.get('league',''))} {_esc(r.get('matchup',''))}</div></td>"
                     f"<td>{r.get('rung','')}</td><td>{price}</td>"
                     f"<td>{stake}</td><td>{ret}</td>"
                     f"<td class={pcol}>{row_pl:+.2f}</td>"
                     f"<td class={tcol}>{total_pl:+.2f}</td>"
                     f"<td><span class='pill {cls}'>{res}</span></td></tr>")
        p.append("</table></div></section>")

    if warnings:
        p.append("<div class=warn><b>Feed notes</b><br>"
                 + "<br>".join(_esc(w) for w in warnings[:8]) + "</div>")

    p.append("<div class=foot>Odds: ESPN public scoreboard (DraftKings, US line — "
             "your provincial book will differ slightly). Each $5 run is worth "
             "<b>5 × (p × d)<sup>n</sup></b>; since p × d &lt; 1 after the hold, "
             "every extra rung lowers expected value. The $5 cap on new money per "
             "run is the good part of this design, not an edge.<br>"
             "19+ (18+ AB/MB/QC). ConnexOntario 1-866-531-2600 · "
             "Canada Safer Gambling 1-833-353-3234.</div>")
    import json as _json
    p.append('<script type="application/json" id="ladder-data">')
    p.append(_json.dumps({
        "state": {"rung": rung, "max_rung": max_rung, "base_stake": base,
                  "reset_at": state.get("reset_at", ""),
                  "stake": state.get("stake", base),
                  "stake_increment": state.get("stake_increment", 0.01)},
        "candidates": [{"pick": c.get("pick", ""),
                        "decimal": float(c.get("decimal") or 1.5),
                        "american": float(c.get("american") or 0),
                        "fair_prob": float(c.get("fair_prob") or 0),
                        "event_id": str(c.get("event_id") or ""),
                        "side": c.get("side") or "",
                        "league": c.get("league") or "",
                        "matchup": c.get("matchup") or "",
                        "start_utc": c.get("start_utc") or ""}
                       for c in candidates[:10]],
        "history": [{"id": "repo_" + str(h.get("placed_at", ""))[:19] + "_"
                           + str(h.get("pick", ""))[:12],
                     "added": h.get("placed_at", ""),
                     "settled_at": h.get("settled_at", ""),
                     "event_id": str(h.get("event_id") or ""),
                     "side": h.get("side") or "",
                     "league": h.get("league") or "",
                     "matchup": h.get("matchup") or "",
                     "start_utc": h.get("start_utc") or "",
                     "score": h.get("score") or "",
                     "pick": h.get("pick", ""),
                     "decimal": float(h.get("decimal") or 1.5),
                     "american": float(h.get("american") or 0),
                     "stake": float(h.get("stake") or 0),
                     "stake_edited": True,
                     "result": h.get("result")}
                    for h in state.get("history", []) if h.get("result")],
    }).replace("</", "<\\/"))
    p.append("</script>")
    p.append(LEDGER_HTML)
    if candidates:
        p.append(INTERACTIVE)
    p.append(LEDGER_JS)
    p.append('<section id="accuracy"><div data-model-accuracy></div></section><script src="model-accuracy.js"></script>')
    p.append('<!-- Shared ledger: keeps this board in step with the same bets on every other device. Endpoint and token live in this browser only. --><script src="betsync.js"></script><script src="sync-adapter.js"></script><script src="betsync-ui.js"></script>')
    p.append("</body></html>")
    return "".join(p)


def badge_svg(rung: int, max_rung: int, net: float) -> str:
    """Small status badge for the README."""
    label, value = "ladder", f"rung {rung}/{max_rung}"
    col = "#2ecc71" if net > 0 else "#e74c3c" if net < 0 else "#586069"
    lw, vw = 52, 8 + len(value) * 6.6
    w = lw + vw
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="20" '
            f'role="img" aria-label="{label}: {value}">'
            f'<rect width="{lw}" height="20" rx="3" fill="#24292e"/>'
            f'<rect x="{lw}" width="{vw:.0f}" height="20" rx="3" fill="{col}"/>'
            f'<rect x="{lw}" width="7" height="20" fill="{col}"/>'
            f'<g fill="#fff" font-family="Verdana,sans-serif" font-size="11">'
            f'<text x="7" y="14">{label}</text>'
            f'<text x="{lw + 6}" y="14">{value}</text></g></svg>')
