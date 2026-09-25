"""The dashboard's own ledger, modelled on mlb-edge-lab's My Ledger.

Same idea, adapted to a ladder. Tap "Select bet" on any candidate and it lands at
that price with the rung's stake prefilled. Tap the stake to change it. Tap the
button again to remove it. Entries settle themselves against
docs/data/results.json, which every build publishes.

The difference from a flat bet ledger: a ladder is sequential. Rung N's stake is
rung N-1's return, so the whole chain is recomputed from scratch on every change.
Editing one stake reflows everything after it.

Storage is this browser's localStorage, per device, and nothing leaves the page.
Export writes JSON or CSV; import merges by id without duplicating.
"""

LEDGER_CSS = """
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
.lgr .settle{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.lgr .result{border:1px solid var(--line);background:var(--bg);border-radius:7px;
  padding:7px 11px;font-size:11px;font-weight:650;cursor:pointer}
.lgr .result.win{color:var(--win);border-color:rgba(46,204,113,.45)}
.lgr .result.loss{color:var(--loss);border-color:rgba(231,76,60,.45)}
.lgr .result.push{color:var(--dim)}
.lgr .result:hover{background:var(--line)}
.lgr .sync{display:flex;align-items:center;justify-content:space-between;gap:10px;
  background:var(--panel);border:1px solid var(--line);border-radius:9px;
  padding:9px 11px;margin:-3px 0 12px;color:var(--dim);font-size:12px}
.lgr .sync.win{border-color:rgba(46,204,113,.45);color:var(--win)}
.lgr .sync.loss{border-color:rgba(231,76,60,.45);color:var(--loss)}
.addbtn{background:rgba(240,180,41,.12);border:1px solid rgba(240,180,41,.45);
  color:var(--gold);border-radius:7px;padding:8px 12px;font-size:12px;
  cursor:pointer;font-weight:600}
.addbtn:hover{background:rgba(240,180,41,.22)}
.addbtn:disabled{opacity:.45;cursor:not-allowed;background:var(--panel)}
.addbtn.on{background:rgba(46,204,113,.15);border-color:rgba(46,204,113,.5);
  color:var(--win)}
.tools{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.exp{background:var(--bg);border:1px solid var(--line);border-radius:8px;
  padding:10px;margin-top:10px;font-size:11px;font-family:ui-monospace,monospace;
  color:var(--dim);max-height:170px;overflow:auto;white-space:pre-wrap;
  word-break:break-all}
.manual{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:13px 15px;margin-top:12px}
.manual h3{margin:0 0 4px;font-size:14px}
.manual .fields{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap;margin-top:10px}
.manual label{display:flex;flex-direction:column;gap:3px;color:var(--dim);
  font-size:10px;text-transform:uppercase;letter-spacing:.07em}
.manual input{background:var(--bg);border:1px solid var(--line);color:var(--ink);
  border-radius:7px;padding:8px 9px;font-size:13px;min-width:110px}
.manual input.pickin{min-width:220px}
.manual input:focus{outline:none;border-color:var(--gold)}
"""

LEDGER_HTML = """
<section class=lgr>
  <h2>My ladder <span id=lgr-count style="color:var(--dim);font-weight:400"></span></h2>
  <div class=sub style="margin:-4px 0 12px">Choose one bet at a time. Mark it
    Win, Loss or Push yourself, or leave the page open and it will check the
    official result every minute. Win advances; loss restarts at rung 0.</div>
  <div class=sync id=lgr-sync><span id=lgr-sync-text>Checking results…</span>
    <button class=mini id=lgr-check type=button>Check now</button></div>
  <div class=grid id=lgr-stats></div>
  <div id=lgr-rows></div>
  <div class=manual>
    <h3>Use a different bet</h3>
    <div class=sub>For a pick from your sportsbook that is not on the option board.</div>
    <div class=fields>
      <label>Selection<input class=pickin id=lgr-custom-pick placeholder="Team or selection"></label>
      <label>American odds<input id=lgr-custom-am type=number step=1 placeholder="-171"></label>
      <label>Stake<input id=lgr-custom-stake type=number step=.01 min=.01></label>
      <button class=addbtn id=lgr-custom type=button>Select custom bet</button>
    </div>
  </div>
  <div class=tools>
    <button class=mini id=lgr-json type=button>Export JSON</button>
    <button class=mini id=lgr-csv type=button>Export CSV</button>
    <button class=mini id=lgr-imp type=button>Import</button>
    <button class=mini id=lgr-seed type=button>Load repo history</button>
    <button class=mini id=lgr-clear type=button>Clear</button>
  </div>
  <div class=exp id=lgr-out style="display:none"></div>
  <div class=k style="margin-top:10px;text-transform:none;letter-spacing:0">
    Stored in this browser only, per device. Nothing leaves the page. Export to
    move it or to survive a cleared browser.
  </div>
</section>
"""

LEDGER_JS = r"""
<script>
(function(){
  var KEY='ladder.ledger.v1', D=null, RESULTS={}, POLL_MS=60000;
  var ESPN_PATH={nfl:'football/nfl',ncaaf:'football/college-football',
    mlb:'baseball/mlb',nba:'basketball/nba',wnba:'basketball/wnba',
    ncaab:'basketball/mens-college-basketball',nhl:'hockey/nhl',
    mls:'soccer/usa.1',epl:'soccer/eng.1',ucl:'soccer/uefa.champions'};
  try{ D=JSON.parse(document.getElementById('ladder-data').textContent); }catch(e){ return; }
  var CFG=D.state, CANDS=D.candidates;

  function load(){ try{ return JSON.parse(localStorage.getItem(KEY))||[]; }catch(e){ return []; } }
  function save(e){ try{ localStorage.setItem(KEY, JSON.stringify(e)); }catch(err){} }
  var entries = load();

  function money(v){ return '$'+(v||0).toFixed(2); }
  function d2a(d){ return d>=2 ? (d-1)*100 : -100/(d-1); }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  // A ladder is sequential: recompute the whole chain whenever anything changes.
  function reflow(){
    entries.sort(function(a,b){ return (a.added||'').localeCompare(b.added||''); });
    var rung=0, stake=CFG.base_stake, inc=CFG.stake_increment||0.01;
    var net=0, runningPL=0, runPL=0, cashed=0, bust=0;
    entries.forEach(function(e){
      var placed=String(e.added||e.placed_at||'');
      if(CFG.reset_at && placed && placed<CFG.reset_at) return;
      var want = Math.floor(stake/inc+1e-9)*inc;
      if(!e.stake_edited) e.stake = want;
      e.rung = rung;
      // Round the payout to cents BEFORE compounding — a book pays whole cents,
      // and carrying full float precision drifts from the Python ladder.
      e.to_return = Math.round(e.stake * e.decimal * 100) / 100;
      if(e.result==='win'){
        e.returned = e.to_return;
        stake = e.to_return; rung += 1;
        if(rung >= CFG.max_rung){ cashed++;
          e.cashed_out = stake; rung=0; stake=CFG.base_stake; }
        else { e.cashed_out = null; }
      } else if(e.result==='loss'){
        e.returned = 0; bust++;
        rung=0; stake=CFG.base_stake; e.cashed_out=null;
      } else if(e.result==='push'){
        e.returned = e.stake; stake = e.stake; e.cashed_out=null;
      } else {
        e.returned = null; e.cashed_out=null;
      }
      var pl = e.result==='win' ? e.returned-e.stake
             : e.result==='loss' ? -e.stake : 0;
      e.profit_loss = Math.round(pl*100)/100;
      runningPL += pl; runPL += pl;
      if(e.result==='loss' || e.cashed_out){ net += runPL; runPL=0; }
      e.running_net = Math.round(net*100)/100;
      e.running_profit_loss = Math.round(runningPL*100)/100;
    });
    return {rung:rung, stake:Math.floor(stake/inc+1e-9)*inc, net:net,
            profitLoss:Math.round(runningPL*100)/100, cashed:cashed, bust:bust};
  }

  function settleFrom(e,r){
    var league=String(e.league || r.league || '').toLowerCase();
    var threeWay=['mls','epl','ucl'].indexOf(league)!==-1;
    if(r.winner==='draw' && e.side!=='draw' && !league) return {pick:e.pick,result:null};
    var res = r.winner===e.side ? 'win'
            : r.winner==='draw' && !threeWay ? 'push' : 'loss';
    e.result = res; e.settled_at = r.date || new Date().toISOString().slice(0,10);
    e.score = r.score || '';
    return {pick:e.pick,result:res};
  }

  // Self-settlement, same shape as the CLI's grade step.
  function autoSettle(){
    var settled=[];
    entries.forEach(function(e){
      if(e.result || !e.event_id) return;
      var r = RESULTS[e.event_id];
      if(!r || !r.completed) return;
      settled.push(settleFrom(e,r));
    });
    if(settled.length) save(entries);
    return settled;
  }

  function resultFromESPN(payload,e){
    var ev=(payload.events||[]).find(function(x){ return String(x.id)===String(e.event_id); });
    if(!ev) return null;
    var comp=(ev.competitions||[])[0]||{};
    var typ=((comp.status||{}).type)||((ev.status||{}).type)||{};
    if(!typ.completed && typ.state!=='post') return null;
    var home=null, away=null;
    (comp.competitors||[]).forEach(function(c){
      if(c.homeAway==='home') home=c; else if(c.homeAway==='away') away=c; });
    if(!home || !away) return null;
    var winner=home.winner?'home':away.winner?'away':null;
    if(!winner && Number(home.score)===Number(away.score)) winner='draw';
    if(!winner) return null;
    var ha=((home.team||{}).abbreviation)||'HOME';
    var aa=((away.team||{}).abbreviation)||'AWAY';
    return {completed:true,winner:winner,date:(ev.date||'').slice(0,10),
      league:e.league,score:aa+' '+away.score+' @ '+ha+' '+home.score};
  }

  // Browser selections live only on this device, so check their event directly.
  // The published results file remains a fallback if ESPN blocks a browser call.
  function checkPendingAtESPN(){
    var e=pending(), path=e&&ESPN_PATH[e.league];
    if(!e || !e.event_id || !path) return Promise.resolve([]);
    var date=(e.start_utc||e.added||'').slice(0,10).replace(/-/g,'');
    var url='https://site.api.espn.com/apis/site/v2/sports/'+path+'/scoreboard';
    if(date) url+='?dates='+date;
    return fetch(url,{cache:'no-store'}).then(function(r){
      if(!r.ok) throw new Error('scoreboard '+r.status); return r.json();
    }).then(function(j){
      var result=resultFromESPN(j,e);
      if(result) RESULTS[e.event_id]=result;
      return autoSettle();
    });
  }

  function syncMessage(settled){
    var box=document.getElementById('lgr-sync');
    var label=document.getElementById('lgr-sync-text');
    var st=reflow(), active=pending();
    box.className='sync';
    if(settled.length){
      var x=settled[settled.length-1];
      if(x.result==='win'){
        box.className='sync win';
        label.textContent=x.pick+' won — advanced to rung '+st.rung+
          '. Next stake '+money(st.stake)+'.';
      } else if(x.result==='loss'){
        box.className='sync loss';
        label.textContent=x.pick+' lost — ladder restarted at rung 0. Next stake '+
          money(CFG.base_stake)+'.';
      } else label.textContent=x.pick+' was void — rung unchanged.';
    } else if(active){
      label.textContent='Auto-settlement active — checking '+active.pick+
        ' every minute. Last check '+new Date().toLocaleTimeString()+'.';
    } else {
      label.textContent='No bet pending — select the next rung at '+money(st.stake)+'.';
    }
  }

  function refreshResults(){
    var label=document.getElementById('lgr-sync-text');
    label.textContent='Checking official results…';
    return fetch('data/results.json?t='+Date.now(),{cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : {}; })
      .catch(function(){ return {}; })
      .then(function(j){
        RESULTS=j.games||RESULTS;
        var settled=autoSettle();
        if(settled.length) return settled;
        return checkPendingAtESPN().catch(function(){ return []; });
      }).then(function(settled){
        draw(); syncButtons(); syncMessage(settled); return settled;
      }).catch(function(){
        draw(); syncButtons();
        label.textContent='Could not reach the score feed. Use Check now or settle manually.';
      });
  }

  function draw(){
    var st = reflow();
    var host = document.getElementById('lgr-rows');
    document.getElementById('lgr-count').textContent =
      entries.length ? '— '+entries.length+' bet'+(entries.length>1?'s':'') : '';

    var done = entries.filter(function(e){ return e.result==='win'||e.result==='loss'; });
    var w = done.filter(function(e){ return e.result==='win'; }).length;
    var accuracy = done.length ? (w/done.length*100).toFixed(1)+'%' : '—';
    var stats = document.getElementById('lgr-stats');
    stats.innerHTML =
      card('Rung', st.rung+' / '+CFG.max_rung, 'gold') +
      card('Next stake', money(st.stake), '') +
      card('Right / wrong', done.length? w+' / '+(done.length-w) : '—', '') +
      card('Accuracy', accuracy, '') +
      card('Profit / loss', (st.profitLoss>=0?'+':'')+money(st.profitLoss),
           st.profitLoss>0?'pos':st.profitLoss<0?'neg':'');

    var customStake=document.getElementById('lgr-custom-stake');
    if(customStake && document.activeElement!==customStake) customStake.value=st.stake.toFixed(2);

    if(!entries.length){
      host.innerHTML='<div class=empty>No bets yet. Tap <b>Select bet</b> on a '+
        'candidate above to start the ladder.</div>';
      return;
    }
    host.innerHTML = entries.slice().reverse().map(function(e,i){
      var idx = entries.length-1-i;
      var pill = e.result ? '<span class="pill '+e.result+'">'+e.result+'</span>'
                          : '<span class="pill live">pending</span>';
      var settle = e.result ? '' : '<div class=settle><span class=sub2>Settle:</span>'+
        '<button class="result win" data-result="win" data-i="'+idx+'" type=button>Win</button>'+
        '<button class="result loss" data-result="loss" data-i="'+idx+'" type=button>Loss</button>'+
        '<button class="result push" data-result="push" data-i="'+idx+'" type=button>Push / void</button></div>';
      var pl=e.profit_loss||0;
      return '<div class="row'+(e.result?'':' pend')+'">'+
        '<div class=top><span class=nm>R'+e.rung+' &middot; '+esc(e.pick)+'</span>'+
        '<span class=price>'+(e.american>=0?'+':'')+Math.round(e.american)+'</span></div>'+
        '<div class=sub2>'+esc((e.league||'').toUpperCase())+' '+esc(e.matchup||'')+
        (e.score?' &middot; '+esc(e.score):'')+'</div>'+
        '<div class=line>'+
          '<span style="color:var(--dim)">stake</span>'+
          '<input class=stk type=number step=0.01 value="'+e.stake.toFixed(2)+
          '" data-i="'+idx+'">'+
          '<span>&rarr; <b>'+money(e.to_return)+'</b></span>'+
          pill+
          '<button class=x data-del="'+idx+'" type=button>remove</button>'+
          '<span style="margin-left:auto;color:var(--dim)">P/L '+
          (pl>=0?'+':'')+money(pl)+' &middot; total '+
          (e.running_profit_loss>=0?'+':'')+money(e.running_profit_loss)+'</span>'+
        '</div>'+settle+'</div>';
    }).join('');

    host.querySelectorAll('input.stk').forEach(function(el){
      el.addEventListener('change', function(){
        var v=parseFloat(el.value); if(!v||v<=0) return;
        var e=entries[+el.dataset.i]; e.stake=v; e.stake_edited=true;
        save(entries); draw(); syncButtons();
      });
    });
    host.querySelectorAll('button[data-del]').forEach(function(el){
      el.addEventListener('click', function(){
        entries.splice(+el.dataset.del,1); save(entries); draw(); syncButtons();
      });
    });
    host.querySelectorAll('button[data-result]').forEach(function(el){
      el.addEventListener('click', function(){
        var e=entries[+el.dataset.i]; if(!e || e.result) return;
        e.result=el.dataset.result; e.settled_at=new Date().toISOString();
        save(entries); draw(); syncButtons();
        syncMessage([{pick:e.pick,result:e.result}]);
      });
    });
  }

  function card(k,v,cls){
    return '<div class=card><div class=k>'+k+'</div>'+
           '<div class="v '+cls+'">'+v+'</div></div>';
  }

  function has(c){ return entries.some(function(e){
    return e.event_id ? (!e.result && e.event_id===c.event_id && e.side===c.side)
                      : (e.pick===c.pick && !e.result); }); }

  function pending(){ return entries.find(function(e){ return !e.result; }); }

  function syncButtons(){
    CANDS.forEach(function(c,i){
      var b=document.getElementById('add'+i); if(!b) return;
      var on=has(c), busy=!!pending();
      var finished=!!(c.event_id && RESULTS[c.event_id] && RESULTS[c.event_id].completed);
      b.className='addbtn'+(on?' on':'');
      b.disabled=finished || (busy&&!on);
      b.textContent = finished ? 'Finished' : on ? 'Selected'
                    : busy ? 'Settle current first' : 'Select bet';
    });
  }

  window.ladderAdd = function(i, decimal){
    var c=CANDS[i];
    if(has(c)){
      entries = entries.filter(function(e){
        return !(e.event_id===c.event_id && e.side===c.side && !e.result); });
    } else {
      var active=pending();
      if(active){ alert('Settle or remove '+active.pick+' before selecting another bet.'); return; }
      entries.push({id:'b'+Date.now()+'_'+i, added:new Date().toISOString(),
        event_id:c.event_id||'', league:c.league||'', matchup:c.matchup||'',
        start_utc:c.start_utc||'', pick:c.pick, side:c.side||'',
        decimal:decimal, american:d2a(decimal),
        stake:0, stake_edited:false, result:null});
    }
    save(entries); draw(); syncButtons(); syncMessage([]);
  };

  function toCSV(){
    var cols=['added','settled_at','league','matchup','pick','rung','decimal',
              'american','stake','to_return','result','returned','profit_loss',
              'running_profit_loss','running_net'];
    var out=[cols.join(',')];
    entries.forEach(function(e){
      out.push(cols.map(function(k){
        var v=e[k]==null?'':e[k];
        return /[",\n]/.test(String(v)) ? '"'+String(v).replace(/"/g,'""')+'"' : v;
      }).join(','));
    });
    return out.join('\n');
  }

  function show(text, name, mime){
    var box=document.getElementById('lgr-out');
    box.style.display='block'; box.textContent=text;
    try{
      var b=new Blob([text],{type:mime}), u=URL.createObjectURL(b);
      var a=document.createElement('a'); a.href=u; a.download=name; a.click();
      setTimeout(function(){ URL.revokeObjectURL(u); },2000);
    }catch(err){}   // embedded viewers block downloads; the text above still works
  }

  document.getElementById('lgr-json').onclick=function(){
    show(JSON.stringify(entries,null,1),'ladder-ledger.json','application/json'); };
  document.getElementById('lgr-csv').onclick=function(){
    show(toCSV(),'ladder-ledger.csv','text/csv'); };
  document.getElementById('lgr-clear').onclick=function(){
    if(confirm('Delete all '+entries.length+' ledger entries on this device?')){
      entries=[]; save(entries); draw(); syncButtons(); } };

  document.getElementById('lgr-custom').onclick=function(){
    var active=pending();
    if(active){ alert('Settle or remove '+active.pick+' before selecting another bet.'); return; }
    var pick=document.getElementById('lgr-custom-pick').value.trim();
    var am=parseFloat(document.getElementById('lgr-custom-am').value);
    var stake=parseFloat(document.getElementById('lgr-custom-stake').value);
    if(!pick){ alert('Enter the team or selection.'); return; }
    if(!am || Math.abs(am)<100){ alert('Enter American odds such as -171.'); return; }
    var dec=am>0 ? 1+am/100 : 1+100/Math.abs(am);
    entries.push({id:'custom_'+Date.now(),added:new Date().toISOString(),event_id:'',
      league:'manual',matchup:'',pick:pick,side:'',decimal:dec,american:am,
      stake:stake>0?stake:0,stake_edited:stake>0,result:null});
    document.getElementById('lgr-custom-pick').value='';
    document.getElementById('lgr-custom-am').value='';
    save(entries); draw(); syncButtons(); syncMessage([]);
  };

  function signature(e){ return [(e.added||e.placed_at||'').slice(0,10),
    (e.pick||'').toLowerCase(),Number(e.stake||0).toFixed(2)].join('|'); }
  function eventKey(e){ return e.event_id ? String(e.event_id)+'|'+(e.side||'') : ''; }
  function mergeRepoHistory(){
    var ids={}, sigs={}, events={}; entries.forEach(function(e){
      ids[e.id]=e; sigs[signature(e)]=e; if(eventKey(e)) events[eventKey(e)]=e; });
    var added=0, updated=0;
    (D.history||[]).forEach(function(h){
      var local=ids[h.id] || events[eventKey(h)] || sigs[signature(h)];
      if(local){
        if(h.result && !local.result){
          var keepId=local.id;
          Object.keys(h).forEach(function(k){ local[k]=h[k]; });
          local.id=keepId||h.id; updated++;
        }
      } else {
        entries.push(h); ids[h.id]=h; sigs[signature(h)]=h;
        if(eventKey(h)) events[eventKey(h)]=h; added++;
      }
    });
    if(added||updated) save(entries);
    return {added:added,updated:updated};
  }
  // Pull the committed state/ladder.json history into this browser, merging by
  // id so nothing duplicates. This is how a new device catches up.
  document.getElementById('lgr-seed').onclick=function(){
    var hist=(D.history||[]);
    if(!hist.length){ alert('No settled bets in the repo state yet.'); return; }
    var merged=mergeRepoHistory();
    save(entries); draw(); syncButtons();
    alert('Added '+merged.added+' and updated '+merged.updated+
          ' from the repo; '+(hist.length-merged.added-merged.updated)+' already current.');
  };

  document.getElementById('lgr-imp').onclick=function(){
    var t=prompt('Paste exported ledger JSON'); if(!t) return;
    var inc; try{ inc=JSON.parse(t); }catch(e){ alert('That is not valid JSON'); return; }
    if(!Array.isArray(inc)){ alert('Expected a JSON array'); return; }
    var seen={}; entries.forEach(function(e){ seen[e.id]=1; });
    var added=0;
    inc.forEach(function(e){ if(e && e.id && !seen[e.id]){ entries.push(e); added++; } });
    save(entries); draw(); syncButtons();
    alert('Merged '+added+' new '+(added===1?'entry':'entries')+
          ', skipped '+(inc.length-added)+' already here.');
  };

  // The shared ledger's adapter lives outside this closure. Hand it the chain,
  // a way to replace it, and a repaint - reflow works the numbers out again
  // from there, so nothing derived ever has to travel.
  window.LadderLedger = {
    STORAGE_KEY: KEY,
    get: function(){ return entries; },
    set: function(rows){ entries = rows; save(entries); draw(); syncButtons(); }
  };

  // The committed record is authoritative and is merged on every load. Local
  // entries remain available, while the same real bet is never duplicated.
  mergeRepoHistory();
  draw(); syncButtons();
  document.getElementById('lgr-check').onclick=refreshResults;
  refreshResults();
  setInterval(refreshResults,POLL_MS);
})();
</script>
"""
