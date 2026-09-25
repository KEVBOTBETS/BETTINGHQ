"""Keep the visible dashboard in sync with the browser-local ladder.

The betting ledger lives in localStorage because GitHub Pages is static.  The
ledger already auto-grades official results, but the large hero/staircase above
it was generated from the last committed repo state.  This post-render patch
makes the visible rung, next stake, candidate returns and staircase follow the
same local ledger immediately after a result is graded.
"""
from __future__ import annotations

from pathlib import Path

MARKER = "ladder-ui-sync-v1"

SCRIPT = r'''
<script>
/* ladder-ui-sync-v1 */
(function(){
  var KEY='ladder.ledger.v1';
  var dataEl=document.getElementById('ladder-data');
  if(!dataEl) return;
  var D;
  try{ D=JSON.parse(dataEl.textContent); }catch(e){ return; }
  var CFG=D.state||{}, CANDS=D.candidates||[];

  function money(v){ return '$'+Number(v||0).toFixed(2); }
  function entries(){
    try{ var x=JSON.parse(localStorage.getItem(KEY)); return Array.isArray(x)?x:[]; }
    catch(e){ return []; }
  }
  function roundCents(v){ return Math.round(Number(v||0)*100)/100; }
  function floorStake(v,inc){ return Math.floor(Number(v||0)/inc+1e-9)*inc; }

  function state(){
    var arr=entries().slice().sort(function(a,b){
      return String(a.added||a.placed_at||'').localeCompare(String(b.added||b.placed_at||''));
    });
    if(CFG.reset_at) arr=arr.filter(function(e){
      var placed=String(e.added||e.placed_at||'');
      return !placed || placed>=CFG.reset_at;
    });
    if(!arr.length){
      var rr=Number(CFG.rung||0), bb=Number(CFG.base_stake||5);
      return {rung:rr, stake:rr===0?bb:Number(CFG.stake||bb), run:[]};
    }
    var base=Number(CFG.base_stake||5), max=Number(CFG.max_rung||10);
    var inc=Number(CFG.stake_increment||.01), rung=0, stake=base, run=[];
    arr.forEach(function(e){
      var want=floorStake(stake,inc);
      var actual=(e.stake_edited && Number(e.stake)>0)?Number(e.stake):want;
      var res=String(e.result||'').toLowerCase();
      if(res==='win'){
        var ret=roundCents(actual*Number(e.decimal||1));
        run.push({rung:rung,stake:actual,ret:ret});
        stake=ret; rung+=1;
        if(rung>=max){ rung=0; stake=base; run=[]; }
      } else if(res==='loss'){
        rung=0; stake=base; run=[];
      } else if(res==='push'){
        // Same rung and same available stake.
      }
    });
    return {rung:rung,stake:floorStake(stake,inc),run:run.slice(-rung)};
  }

  function activeDecimal(){
    var top=document.querySelector("section .bet.top input[id^='de']");
    if(top && Number(top.value)>1) return Number(top.value);
    var d0=document.getElementById('de0');
    if(d0 && Number(d0.value)>1) return Number(d0.value);
    return CANDS.length?Number(CANDS[0].decimal||1.5):1.5;
  }

  function drawStair(st,dec){
    var host=document.getElementById('stair');
    if(!host) return;
    var max=Number(CFG.max_rung||10), base=Number(CFG.base_stake||5);
    var inc=Number(CFG.stake_increment||.01), stakes=[], rets=[];
    var s=base;
    for(var i=0;i<max;i++){
      if(i<st.rung && st.run[i]) s=Number(st.run[i].stake);
      else if(i===st.rung) s=Number(st.stake||base);
      else if(i>st.rung) s=floorStake(rets[i-1],inc);
      stakes[i]=s;
      rets[i]=(i<st.rung && st.run[i])?Number(st.run[i].ret):roundCents(s*dec);
    }
    var W=760,RH=30,GAP=7,PAD=8,H=16+max*(RH+GAP)-GAP;
    var top=Math.max.apply(null,rets.concat([1]));
    var out='<svg viewBox="0 0 '+W+' '+H+'" width="100%" preserveAspectRatio="xMidYMid meet" '+
      'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Live ladder progress">';
    for(var j=0;j<max;j++){
      var y=PAD+(max-1-j)*(RH+GAP), w=Math.max(58,(stakes[j]/top)*(W-190));
      var fill=j<st.rung?'#2ecc71':j===st.rung?'#f0b429':'#182231';
      var tc=j===st.rung?'#1a1205':j<st.rung?'#eafff2':'#5f7085';
      out+='<rect x="46" y="'+y+'" width="'+w.toFixed(1)+'" height="'+RH+'" rx="7" fill="'+fill+'"/>';
      out+='<text x="14" y="'+(y+19.5)+'" font-size="12" font-family="ui-monospace,monospace" fill="'+
        (j===st.rung?'#f0b429':'#5f7085')+'">R'+j+'</text>';
      var label=money(stakes[j])+' → '+money(rets[j]);
      var tx=w>210?58:(46+w+10), anchor=w>210?tc:'#7d8da1';
      out+='<text x="'+tx.toFixed(1)+'" y="'+(y+19.5)+'" font-size="12.5" font-family="ui-monospace,monospace" fill="'+anchor+'">'+label+'</text>';
    }
    out+='</svg>';
    host.innerHTML=out;
    var cash=document.getElementById('cashout');
    if(cash){
      var next=roundCents(st.stake*dec);
      cash.textContent='Live ladder: rung '+st.rung+' · next stake '+money(st.stake)+
        '. A win at the selected price moves to rung '+Math.min(st.rung+1,max)+
        ' with '+money(next)+'. A loss restarts at rung 0 with '+money(base)+'.';
    }
  }

  function sync(){
    var st=state(), base=Number(CFG.base_stake||5), max=Number(CFG.max_rung||10);
    var rung=document.querySelector('.hero .rungnum'); if(rung) rung.textContent=st.rung;
    var of=document.querySelector('.hero .of'); if(of) of.textContent='of '+max+' rungs · live';
    document.title='Ladder — rung '+st.rung;

    var firstGrid=document.querySelector('.hero + .grid');
    if(firstGrid){
      firstGrid.querySelectorAll('.card').forEach(function(card){
        var k=card.querySelector('.k'),v=card.querySelector('.v');
        if(k&&v&&k.textContent.trim()==='Next stake') v.textContent=money(st.stake);
      });
      var note=document.getElementById('ladder-auto-state');
      if(!note){
        note=document.createElement('div'); note.id='ladder-auto-state'; note.className='sync';
        firstGrid.insertAdjacentElement('afterend',note);
      }
      note.textContent='AUTO LADDER · rung '+st.rung+' · next '+money(st.stake)+
        ' · WIN → advance · LOSS → restart at '+money(base);
    }

    CANDS.forEach(function(c,i){
      var de=document.getElementById('de'+i), dec=de&&Number(de.value)>1?Number(de.value):Number(c.decimal||1.5);
      var ret=roundCents(st.stake*dec), el=document.getElementById('ret'+i);
      if(el) el.innerHTML='stake '+money(st.stake)+' &rarr; <b>'+money(ret)+'</b> '+
        '<span style="color:var(--dim)">(profit '+money(ret-st.stake)+')</span>';
    });
    drawStair(st,activeDecimal());
  }

  var scheduled=false;
  function soon(){
    if(scheduled) return; scheduled=true;
    setTimeout(function(){ scheduled=false; sync(); },0);
  }
  var stats=document.getElementById('lgr-stats');
  if(stats && window.MutationObserver) new MutationObserver(soon).observe(stats,{childList:true,subtree:true});
  document.querySelectorAll("input[id^='de'],input[id^='am']").forEach(function(x){ x.addEventListener('input',soon); });
  document.querySelectorAll("section .bet[id^='card']").forEach(function(x){ x.addEventListener('click',soon); });
  window.addEventListener('storage',soon);
  sync();
  setInterval(sync,5000);
})();
</script>
'''


def patch(path: Path) -> bool:
    text = path.read_text()
    if MARKER in text:
        return False
    if "</body>" not in text:
        raise RuntimeError(f"{path} has no </body> tag")
    path.write_text(text.replace("</body>", SCRIPT + "\n</body>", 1))
    return True


if __name__ == "__main__":
    target = Path("docs/index.html")
    changed = patch(target)
    print(f"dashboard live-state patch: {'applied' if changed else 'already present'}")
