/* Moneyline card artwork. Five canvas styles built from the saved winner picks.
   Team names, times and percentages are drawn as text so they stay exact. */
(function(root){
  'use strict';
  const STYLES={
    gridiron:{name:'Gridiron Gold',note:'Stadium art, gold trim'},
    ballpark:{name:'Ballpark Stubs',note:'Ticket-stub picks'},
    scoreboard:{name:'Jumbotron',note:'LED scoreboard'},
    northern:{name:'True North',note:'Red & white poster'},
    slip:{name:'Sportsbook Slip',note:'Printer friendly'}
  };
  const W=1080;
  const SPORT={nfl:'NFL',ncaaf:'NCAAF',mlb:'MLB'};
  const tz='America/Toronto';
  const fmt=(v,o)=>new Intl.DateTimeFormat('en-CA',{timeZone:tz,...o}).format(new Date(v));
  const clock=v=>fmt(v,{hour:'numeric',minute:'2-digit'}).replace(/\s?([ap])\.?m\.?/i,(_,x)=>x.toUpperCase()+'M');
  const longDay=v=>fmt(v+'T12:00:00Z',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
  const pct=p=>p==null?'—':Math.round(p*100)+'%';
  const images={};
  function image(src){
    if(!images[src])images[src]=new Promise(resolve=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>resolve(null);img.src=src;});
    return images[src];
  }
  async function fonts(){
    if(!document.fonts?.load)return;
    const wanted=['800 40px "Barlow Condensed"','italic 900 40px "Barlow Condensed"','40px Anton','700 20px "DM Sans"','400 20px "Share Tech Mono"'];
    await Promise.race([Promise.all(wanted.map(f=>document.fonts.load(f).catch(()=>null))),new Promise(r=>setTimeout(r,2500))]);
  }
  function hash(text){let h=2166136261;for(const c of text){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}

  /* ---------- summary numbers shown on every style ---------- */
  function summarize(picks,day){
    const known=picks.filter(p=>p.prob!=null);
    const withModel=picks.filter(p=>p.predicted);
    const agree=withModel.filter(p=>p.predicted===p.team).length;
    const all=known.length===picks.length&&picks.length?known.reduce((a,p)=>a*p.prob,1):null;
    const avg=known.length?known.reduce((a,p)=>a+p.prob,0)/known.length:null;
    const best=known.slice().sort((a,b)=>b.prob-a.prob)[0]||null;
    const mix=Object.entries(picks.reduce((m,p)=>(m[p.sport]=(m[p.sport]||0)+1,m),{})).map(([k,n])=>n+' '+(SPORT[k]||k)).join(' · ');
    const first=picks.map(p=>Date.parse(p.start)).filter(Number.isFinite).sort((a,b)=>a-b)[0];
    const serial='ML-'+day.replace(/-/g,'').slice(2)+'-'+hash(picks.map(p=>p.key+p.team).join('|')).toString(36).toUpperCase().padStart(6,'0').slice(0,6);
    return {count:picks.length,agree,modelCount:withModel.length,avg,all,best,mix,first:first?new Date(first).toISOString():null,serial,day,dayLabel:longDay(day),shortDay:fmt(day+'T12:00:00Z',{weekday:'short',month:'short',day:'numeric'})};
  }
  const oneIn=p=>p==null||p<=0?'—':p>=.5?pct(p):'1 in '+(1/p>=100?Math.round(1/p).toLocaleString('en-CA'):(1/p).toFixed(1));

  /* ---------- drawing helpers ---------- */
  function rr(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}
  function fit(ctx,text,max){let s=String(text??'');if(ctx.measureText(s).width<=max)return s;while(s.length>1&&ctx.measureText(s+'…').width>max)s=s.slice(0,-1);return s+'…';}
  function text(ctx,value,x,y,{font,color,align='left',max,spacing=0,base='alphabetic'}){
    ctx.font=font;ctx.fillStyle=color;ctx.textAlign=align;ctx.textBaseline=base;
    if('letterSpacing' in ctx)ctx.letterSpacing=spacing+'px';
    ctx.fillText(max?fit(ctx,value,max):String(value),x,y);
    if('letterSpacing' in ctx)ctx.letterSpacing='0px';ctx.textAlign='left';ctx.textBaseline='alphabetic';
  }
  function logo(ctx,img,x,y,size,ring){
    ctx.save();ctx.beginPath();ctx.arc(x+size/2,y+size/2,size/2,0,Math.PI*2);ctx.closePath();
    if(ring){ctx.fillStyle=ring;ctx.fill();}
    ctx.beginPath();ctx.arc(x+size/2,y+size/2,size/2-(ring?7:0),0,Math.PI*2);ctx.clip();
    if(img)ctx.drawImage(img,x,y,size,size);else{ctx.fillStyle='#7be7bd';ctx.fillRect(x,y,size,size);}
    ctx.restore();
  }
  function maple(ctx,cx,cy,s,color){
    const pts=[[0,-1],[.13,-.72],[.3,-.8],[.23,-.36],[.5,-.6],[.56,-.47],[.83,-.53],[.73,-.25],[.88,-.17],[.45,.2],[.52,.36],[.06,.29],[.06,.74],[-.06,.74],[-.06,.29],[-.52,.36],[-.45,.2],[-.88,-.17],[-.73,-.25],[-.83,-.53],[-.56,-.47],[-.5,-.6],[-.23,-.36],[-.3,-.8],[-.13,-.72]];
    ctx.beginPath();pts.forEach(([x,y],i)=>i?ctx.lineTo(cx+x*s,cy+y*s):ctx.moveTo(cx+x*s,cy+y*s));ctx.closePath();ctx.fillStyle=color;ctx.fill();
  }
  function barcode(ctx,seed,x,y,w,h,color){
    let s=seed||1,cx=x;ctx.fillStyle=color;
    while(cx<x+w){s=Math.imul(s^(s>>>15),2246822507)>>>0;const bar=1+(s%4),gap=1+((s>>>8)%3);if(cx+bar>x+w)break;ctx.fillRect(cx,y,bar*2,h);cx+=bar*2+gap*2;}
  }
  function bar(ctx,x,y,w,h,p,fg,bg){rr(ctx,x,y,w,h,h/2);ctx.fillStyle=bg;ctx.fill();if(p!=null){rr(ctx,x,y,Math.max(h,w*p),h,h/2);ctx.fillStyle=fg;ctx.fill();}}
  function grid(n){const cols=n>8?2:1;const rows=Math.max(1,Math.ceil(n/cols));return {cols,rows};}
  function dotText(ctx,value,x,y,{size,font,on,off,step,align='left'}){
    const c=document.createElement('canvas'),g=c.getContext('2d');g.font=font;
    const w=Math.ceil(g.measureText(value).width)+4,h=Math.ceil(size*1.25);c.width=w;c.height=h;
    g.font=font;g.fillStyle='#fff';g.textBaseline='top';g.fillText(value,2,Math.round(size*.08));
    const data=g.getImageData(0,0,w,h).data,ox=align==='center'?x-w/2:align==='right'?x-w:x,r=step*.38;
    for(let yy=step/2;yy<h;yy+=step)for(let xx=step/2;xx<w;xx+=step){
      const lit=data[(Math.floor(yy)*w+Math.floor(xx))*4+3]>110;
      if(!lit&&!off)continue;ctx.beginPath();ctx.arc(ox+xx,y+yy,r,0,Math.PI*2);ctx.fillStyle=lit?on:off;ctx.fill();
    }
    return w;
  }
  function footer(ctx,H,color,accent,meta,max=W-80){
    text(ctx,'19+ · Play responsibly · Winner picks only — not a wager. Model estimates are not guarantees; check current prices.',W/2,H-34,{font:'500 17px "DM Sans", Arial, sans-serif',color,align:'center',max});
    text(ctx,meta.serial+(meta.mix?' · '+meta.mix:'')+' · kevbotbets',W/2,H-62,{font:'700 17px "DM Sans", Arial, sans-serif',color:accent,align:'center',spacing:2});
  }

  /* ---------- styles ---------- */
  async function heroArt(ctx,src,H,bg,fade){
    const art=await image(src);ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
    if(art){ctx.save();ctx.beginPath();ctx.rect(0,0,W,760);ctx.clip();const h=W*art.height/art.width;ctx.drawImage(art,0,0,W,h);ctx.restore();}
    const g=ctx.createLinearGradient(0,470,0,780);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,fade);ctx.fillStyle=g;ctx.fillRect(0,470,W,320);
  }
  function statTiles(ctx,y,meta,{tile,border,label,value,accent,font='800 46px "Barlow Condensed", Arial, sans-serif',radius=14}){
    const items=[['PICKS',String(meta.count)],['MODEL AGREES',meta.modelCount?meta.agree+'/'+meta.modelCount:'—'],['AVG WIN CHANCE',pct(meta.avg)],['ALL-HIT CHANCE',oneIn(meta.all)]];
    const gap=16,w=(W-96-gap*3)/4;
    items.forEach(([k,v],i)=>{const x=48+i*(w+gap);rr(ctx,x,y,w,104,radius);ctx.fillStyle=tile;ctx.fill();if(border){ctx.strokeStyle=border;ctx.lineWidth=2;ctx.stroke();}
      text(ctx,k,x+w/2,y+32,{font:'700 15px "DM Sans", Arial, sans-serif',color:label,align:'center',spacing:1.5});
      text(ctx,v,x+w/2,y+84,{font,color:i===3?accent:value,align:'center',max:w-16});});
    return y+104;
  }

  async function gridiron(canvas,picks,meta){
    const {cols,rows}=grid(picks.length),rowH=cols===1?118:112,top=1000,H=Math.max(1350,top+rows*(rowH+14)+150);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    await heroArt(ctx,'assets/tickets/football.webp',H,'#0b0d12','#0b0d12');
    // gold rule + title band
    const gold=ctx.createLinearGradient(0,0,W,0);gold.addColorStop(0,'#8a5a12');gold.addColorStop(.5,'#ffd772');gold.addColorStop(1,'#8a5a12');
    ctx.fillStyle=gold;ctx.fillRect(48,760,W-96,4);
    text(ctx,'MONEYLINE',48,850,{font:'italic 900 96px "Barlow Condensed", Arial, sans-serif',color:'#ffd772',spacing:2});
    text(ctx,'WINNER CARD',48,888,{font:'800 30px "Barlow Condensed", Arial, sans-serif',color:'#fff',spacing:6});
    text(ctx,meta.dayLabel.toUpperCase(),W-180,846,{font:'800 30px "Barlow Condensed", Arial, sans-serif',color:'#fff',align:'right',max:W-180-540});
    text(ctx,'KICK OFF · FIRST PITCH · WINNERS ONLY',W-180,884,{font:'700 15px "DM Sans", Arial, sans-serif',color:'#b99b55',align:'right',spacing:2});
    const img=await image('kevbot-logo.jpg');logo(ctx,img,W-160,770,112,'#ffd772');
    const quick=[['PICKS',meta.count],['MODEL AGREES',meta.modelCount?meta.agree+'/'+meta.modelCount:'—'],['AVG WIN',pct(meta.avg)],['ALL-HIT',oneIn(meta.all)]];
    quick.forEach(([k,v],i)=>{const x=48+i*248;text(ctx,k,x,934,{font:'700 14px "DM Sans", Arial, sans-serif',color:'#b99b55',spacing:2});text(ctx,String(v),x,972,{font:'800 34px "Barlow Condensed", Arial, sans-serif',color:i===3?'#ffd772':'#fff'});});
    const colW=(W-96-(cols-1)*18)/cols;
    picks.forEach((p,i)=>{
      const c=cols===1?0:i%cols,r=cols===1?i:Math.floor(i/cols),x=48+c*(colW+18),y=top+r*(rowH+14);
      rr(ctx,x,y,colW,rowH,14);const g=ctx.createLinearGradient(x,y,x,y+rowH);g.addColorStop(0,'#1a1712');g.addColorStop(1,'#101014');ctx.fillStyle=g;ctx.fill();ctx.strokeStyle='rgba(255,215,114,.55)';ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle='#d71920';rr(ctx,x,y,10,rowH,5);ctx.fill();
      const big=cols===1?64:48,bx=x+colW-(cols===1?230:150),bw=cols===1?200:128;
      text(ctx,String(i+1).padStart(2,'0')+'  ·  '+SPORT[p.sport]+'  ·  '+clock(p.start)+(cols===1?'  ·  '+p.teamName:''),x+30,y+30,{font:'700 16px "DM Sans", Arial, sans-serif',color:'#c9ae6a',spacing:.5,max:bx-x-50});
      text(ctx,p.team,x+28,y+rowH-(cols===1?20:18),{font:'italic 900 '+big+'px "Barlow Condensed", Arial, sans-serif',color:'#fff'});
      const opp=p.team===p.home?p.away:p.home,vs=(p.team===p.home?'vs ':'@ ')+opp;
      ctx.font='italic 900 '+big+'px "Barlow Condensed", Arial, sans-serif';const tw=ctx.measureText(p.team).width;
      text(ctx,vs,x+28+tw+14,y+rowH-(cols===1?22:20),{font:'700 '+(cols===1?30:22)+'px "Barlow Condensed", Arial, sans-serif',color:'#9a8c6a'});
      text(ctx,pct(p.prob),bx+bw,y+(cols===1?54:48),{font:'800 '+(cols===1?40:32)+'px "Barlow Condensed", Arial, sans-serif',color:'#ffd772',align:'right'});
      bar(ctx,bx,y+(cols===1?68:60),bw,10,p.prob,'#ffd772','#2d2718');
      const chip=p.predicted===p.team?'MODEL PICK ✓':p.predicted?'FADE THE MODEL':'COIN FLIP';
      text(ctx,chip,bx+bw,y+rowH-20,{font:'800 14px "DM Sans", Arial, sans-serif',color:p.predicted===p.team?'#7be7bd':'#ff9b73',align:'right',spacing:1});
    });
    footer(ctx,H,'#8f8a7c','#ffd772',meta);
  }

  async function ballpark(canvas,picks,meta){
    const {cols,rows}=grid(picks.length),rowH=cols===1?130:118,top=1040,H=Math.max(1350,top+rows*(rowH+16)+150);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    await heroArt(ctx,'assets/tickets/baseball.webp',H,'#0c1a2e','#0c1a2e');
    // chalk stitching
    ctx.strokeStyle='#e8474f';ctx.lineWidth=3;ctx.setLineDash([10,9]);ctx.beginPath();ctx.moveTo(48,772);ctx.lineTo(W-48,772);ctx.stroke();ctx.setLineDash([]);
    text(ctx,'Moneyline',48,868,{font:'italic 900 104px "Barlow Condensed", Arial, sans-serif',color:'#fff'});
    text(ctx,'ADMIT ONE · WINNER PICKS',52,904,{font:'700 22px "DM Sans", Arial, sans-serif',color:'#f2c14e',spacing:4});
    text(ctx,meta.dayLabel,W-48,846,{font:'800 32px "Barlow Condensed", Arial, sans-serif',color:'#fff',align:'right'});
    text(ctx,meta.mix||'',W-48,884,{font:'600 20px "DM Sans", Arial, sans-serif',color:'#9fb6d6',align:'right'});
    statTiles(ctx,920,meta,{tile:'#12284a',border:'#27477a',label:'#9fb6d6',value:'#fff',accent:'#f2c14e',font:'800 40px "Barlow Condensed", Arial, sans-serif'});
    // re-position the tiles above rows: drawn at 920 → rows start at 1040
    const colW=(W-96-(cols-1)*18)/cols;
    picks.forEach((p,i)=>{
      const c=cols===1?0:i%cols,r=cols===1?i:Math.floor(i/cols),x=48+c*(colW+18),y=top+r*(rowH+16),stub=cols===1?190:120;
      // stub body with punched notches
      ctx.save();rr(ctx,x,y,colW,rowH,10);ctx.clip();ctx.fillStyle='#f6ecd6';ctx.fillRect(x,y,colW,rowH);
      ctx.fillStyle='#e9dcbd';ctx.fillRect(x+colW-stub,y,stub,rowH);
      for(let yy=y+8;yy<y+rowH;yy+=14){ctx.fillStyle='#0c1a2e';ctx.beginPath();ctx.arc(x+colW-stub,yy,3,0,Math.PI*2);ctx.fill();}
      ctx.fillStyle='#0c1a2e';ctx.beginPath();ctx.arc(x+colW-stub,y,12,0,Math.PI*2);ctx.arc(x+colW-stub,y+rowH,12,0,Math.PI*2);ctx.fill();ctx.restore();
      ctx.fillStyle='#c8102e';ctx.fillRect(x,y+rowH-12,colW-stub-14,4);
      text(ctx,SPORT[p.sport]+' · GAME '+String(i+1).padStart(2,'0'),x+20,y+30,{font:'800 15px "DM Sans", Arial, sans-serif',color:'#c8102e',spacing:2});
      const big=cols===1?58:44;
      text(ctx,p.team,x+20,y+(cols===1?90:78),{font:'italic 900 '+big+'px "Barlow Condensed", Arial, sans-serif',color:'#0c1a2e'});
      ctx.font='italic 900 '+big+'px "Barlow Condensed", Arial, sans-serif';const tw=ctx.measureText(p.team).width;
      const opp=p.team===p.home?p.away:p.home;
      text(ctx,(p.team===p.home?'vs ':'at ')+opp,x+30+tw,y+(cols===1?90:78),{font:'700 '+(cols===1?28:20)+'px "Barlow Condensed", Arial, sans-serif',color:'#6b6250'});
      if(cols===1)text(ctx,p.teamName+' · '+clock(p.start)+' ET',x+20,y+rowH-22,{font:'500 16px "DM Sans", Arial, sans-serif',color:'#6b6250',max:colW-stub-40});
      const sx=x+colW-stub/2;
      text(ctx,'WIN',sx,y+(cols===1?34:30),{font:'800 13px "DM Sans", Arial, sans-serif',color:'#6b6250',align:'center',spacing:3});
      text(ctx,pct(p.prob),sx,y+(cols===1?80:70),{font:'800 '+(cols===1?46:32)+'px "Barlow Condensed", Arial, sans-serif',color:'#0c1a2e',align:'center'});
      text(ctx,p.predicted===p.team?'MODEL ✓':p.predicted?'UPSET CALL':'TOSS-UP',sx,y+rowH-(cols===1?22:14),{font:'800 13px "DM Sans", Arial, sans-serif',color:p.predicted===p.team?'#16794f':'#c8102e',align:'center',spacing:1});
    });
    footer(ctx,H,'#8ea3c2','#f2c14e',meta);
  }

  async function scoreboard(canvas,picks,meta){
    const {cols,rows}=grid(picks.length),rowH=cols===1?120:108,top=560,H=Math.max(1350,top+rows*(rowH+14)+170);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#050608';ctx.fillRect(0,0,W,H);
    // dim LED field texture
    ctx.fillStyle='#0d1014';for(let y=6;y<H;y+=12)for(let x=6;x<W;x+=12){ctx.fillRect(x,y,3,3);}
    // cabinet
    rr(ctx,30,30,W-60,470,18);ctx.fillStyle='#0b0d10';ctx.fill();ctx.strokeStyle='#2b2f36';ctx.lineWidth=6;ctx.stroke();
    const img=await image('kevbot-logo.jpg');logo(ctx,img,64,70,150,'#ffb000');
    dotText(ctx,'KEVBOT',250,64,{size:92,font:'900 92px "Barlow Condensed", Arial, sans-serif',on:'#ffb000',off:'#1c1609',step:7});
    dotText(ctx,'MONEYLINE',250,168,{size:92,font:'900 92px "Barlow Condensed", Arial, sans-serif',on:'#ff3b30',off:'#1c0b09',step:7});
    text(ctx,meta.dayLabel.toUpperCase(),64,300,{font:'400 30px "Share Tech Mono", monospace',color:'#ffb000',spacing:2});
    text(ctx,(meta.mix||'').toUpperCase(),W-64,300,{font:'400 26px "Share Tech Mono", monospace',color:'#7a6630',align:'right'});
    const cells=[['PICKS',String(meta.count)],['MODEL',meta.modelCount?meta.agree+'/'+meta.modelCount:'--'],['AVG',pct(meta.avg)],['ALL HIT',oneIn(meta.all)]];
    cells.forEach(([k,v],i)=>{const x=64+i*238;rr(ctx,x,330,218,140,10);ctx.fillStyle='#000';ctx.fill();ctx.strokeStyle='#23272e';ctx.lineWidth=3;ctx.stroke();
      text(ctx,k,x+109,362,{font:'400 20px "Share Tech Mono", monospace',color:'#8b93a1',align:'center',spacing:3});
      text(ctx,v,x+109,440,{font:'400 '+(v.length>6?38:58)+'px "Share Tech Mono", monospace',color:i===3?'#ff3b30':'#ffb000',align:'center',max:200});});
    text(ctx,'TEAM',64,536,{font:'400 20px "Share Tech Mono", monospace',color:'#5d6573',spacing:4});
    text(ctx,'WIN %',W-64,536,{font:'400 20px "Share Tech Mono", monospace',color:'#5d6573',align:'right',spacing:4});
    const colW=(W-96-(cols-1)*18)/cols;
    picks.forEach((p,i)=>{
      const c=cols===1?0:i%cols,r=cols===1?i:Math.floor(i/cols),x=48+c*(colW+18),y=top+r*(rowH+14);
      rr(ctx,x,y,colW,rowH,8);ctx.fillStyle='#000';ctx.fill();ctx.strokeStyle='#1d2127';ctx.lineWidth=2;ctx.stroke();
      const opp=p.team===p.home?p.away:p.home,size=cols===1?60:44,step=cols===1?5:4;
      const w1=dotText(ctx,p.team,x+18,y+14,{size,font:'900 '+size+'px "Barlow Condensed", Arial, sans-serif',on:'#ffb000',off:null,step});
      text(ctx,(p.team===p.home?'VS ':'@ ')+opp,x+30+w1,y+(cols===1?64:52),{font:'400 '+(cols===1?30:22)+'px "Share Tech Mono", monospace',color:'#6c5a2a'});
      text(ctx,SPORT[p.sport]+' '+clock(p.start)+(p.predicted===p.team?'  ◆ MODEL':p.predicted?'  ◇ FADE':''),x+18,y+rowH-16,{font:'400 18px "Share Tech Mono", monospace',color:p.predicted===p.team?'#39d98a':'#8b93a1'});
      // segment meter
      const segs=cols===1?20:12,sw=cols===1?9:7,mx=x+colW-18-segs*(sw+3),lit=p.prob==null?0:Math.round(p.prob*segs);
      for(let s=0;s<segs;s++){ctx.fillStyle=s<lit?(s>=segs*.7?'#39d98a':s>=segs*.5?'#ffb000':'#ff3b30'):'#15181d';ctx.fillRect(mx+s*(sw+3),y+rowH-30,sw,14);}
      text(ctx,pct(p.prob),x+colW-18,y+(cols===1?60:48),{font:'400 '+(cols===1?46:34)+'px "Share Tech Mono", monospace',color:'#ffb000',align:'right'});
    });
    // scanlines
    ctx.fillStyle='rgba(255,255,255,.025)';for(let y=0;y<H;y+=4)ctx.fillRect(0,y,W,1);
    footer(ctx,H,'#6d7480','#ffb000',meta);
  }

  async function northern(canvas,picks,meta){
    const {cols,rows}=grid(picks.length),rowH=cols===1?116:108,top=700,H=Math.max(1350,top+rows*(rowH+14)+160);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#c8102e';ctx.fillRect(0,0,W,H);
    // flag bars and diagonal texture
    ctx.fillStyle='#a50d26';ctx.fillRect(0,0,120,H);ctx.fillRect(W-120,0,120,H);
    ctx.save();ctx.globalAlpha=.08;ctx.strokeStyle='#fff';ctx.lineWidth=14;for(let x=-H;x<W;x+=46){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x+H,H);ctx.stroke();}ctx.restore();
    ctx.save();ctx.globalAlpha=.14;maple(ctx,W/2,330,330,'#fff');ctx.restore();
    const img=await image('kevbot-logo.jpg');logo(ctx,img,W/2-120,54,240,'#fff');
    ctx.save();ctx.shadowColor='rgba(0,0,0,.35)';ctx.shadowOffsetY=6;ctx.shadowBlur=0;
    text(ctx,'MONEYLINE',W/2,440,{font:'140px Anton, "Barlow Condensed", Impact, sans-serif',color:'#fff',align:'center',spacing:4});ctx.restore();
    // ribbon
    ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(190,470);ctx.lineTo(W-190,470);ctx.lineTo(W-160,500);ctx.lineTo(W-190,530);ctx.lineTo(190,530);ctx.lineTo(160,500);ctx.closePath();ctx.fill();
    text(ctx,'TRUE NORTH WINNER PICKS · '+meta.shortDay.toUpperCase().replace(/\./g,''),W/2,510,{font:'800 26px "Barlow Condensed", Arial, sans-serif',color:'#c8102e',align:'center',spacing:2,max:W-420});
    const s=[['PICKS',meta.count],['MODEL AGREES',meta.modelCount?meta.agree+'/'+meta.modelCount:'—'],['AVG WIN',pct(meta.avg)],['ALL-HIT',oneIn(meta.all)]];
    s.forEach(([k,v],i)=>{const x=150+i*(780/4)+780/8;text(ctx,String(v),x,610,{font:'54px Anton, "Barlow Condensed", Impact, sans-serif',color:'#fff',align:'center',max:180});text(ctx,k,x,642,{font:'800 15px "DM Sans", Arial, sans-serif',color:'#ffd4d9',align:'center',spacing:2});});
    const colW=(W-300-(cols-1)*16)/cols;
    picks.forEach((p,i)=>{
      const c=cols===1?0:i%cols,r=cols===1?i:Math.floor(i/cols),x=150+c*(colW+16),y=top+r*(rowH+14);
      ctx.save();ctx.shadowColor='rgba(80,0,10,.35)';ctx.shadowOffsetY=8;rr(ctx,x,y,colW,rowH,6);ctx.fillStyle='#fff';ctx.fill();ctx.restore();
      maple(ctx,x+(cols===1?50:34),y+rowH/2,cols===1?30:20,'#c8102e');
      const tx=x+(cols===1?100:66),big=cols===1?60:42;
      text(ctx,p.team,tx,y+(cols===1?70:60),{font:big+'px Anton, "Barlow Condensed", Impact, sans-serif',color:'#1b1b1f'});
      ctx.font=big+'px Anton, "Barlow Condensed", Impact, sans-serif';const tw=ctx.measureText(p.team).width,opp=p.team===p.home?p.away:p.home;
      text(ctx,(p.team===p.home?'vs ':'@ ')+opp,tx+tw+12,y+(cols===1?70:60),{font:'800 '+(cols===1?26:18)+'px "Barlow Condensed", Arial, sans-serif',color:'#9a8f90'});
      text(ctx,SPORT[p.sport]+' · '+clock(p.start)+(cols===1?' · '+p.teamName:''),tx,y+rowH-(cols===1?20:16),{font:'600 '+(cols===1?16:13)+'px "DM Sans", Arial, sans-serif',color:'#6d6566',max:colW-(tx-x)-(cols===1?170:96)});
      text(ctx,pct(p.prob),x+colW-20,y+(cols===1?64:52),{font:(cols===1?52:36)+'px Anton, "Barlow Condensed", Impact, sans-serif',color:'#c8102e',align:'right'});
      text(ctx,p.predicted===p.team?'MODEL ✓':p.predicted?'GUT CALL':'TOSS-UP',x+colW-20,y+rowH-(cols===1?20:16),{font:'800 13px "DM Sans", Arial, sans-serif',color:p.predicted===p.team?'#16794f':'#c8102e',align:'right',spacing:1});
    });
    footer(ctx,H,'#ffd4d9','#fff',meta);
  }

  async function slip(canvas,picks,meta){
    const {cols,rows}=grid(picks.length),rowH=cols===1?104:96,top=560,H=Math.max(1350,top+rows*rowH+400);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#ecebe6';ctx.fillRect(0,0,W,H);
    // paper with torn zigzag edges
    const px=110,pw=W-220;ctx.save();ctx.shadowColor='rgba(0,0,0,.18)';ctx.shadowBlur=24;ctx.beginPath();ctx.moveTo(px,26);
    for(let x=px;x<=px+pw;x+=20)ctx.lineTo(x+10,x/20%2?16:36);ctx.lineTo(px+pw,H-36);for(let x=px+pw;x>=px;x-=20)ctx.lineTo(x-10,x/20%2?H-16:H-36);ctx.closePath();ctx.fillStyle='#fff';ctx.fill();ctx.restore();
    const img=await image('kevbot-logo.jpg');ctx.save();ctx.filter='grayscale(1) contrast(1.2)';logo(ctx,img,W/2-60,60,120,null);ctx.restore();
    const mono='"Share Tech Mono", "Courier New", monospace',ink='#111',faint='#777';
    text(ctx,'KEVBOT BETS',W/2,236,{font:'44px Anton, "Barlow Condensed", Impact, sans-serif',color:ink,align:'center',spacing:6});
    text(ctx,'*** MONEYLINE WINNER SLIP ***',W/2,276,{font:'400 26px '+mono,color:ink,align:'center'});
    const dash=y=>{ctx.strokeStyle='#333';ctx.lineWidth=2;ctx.setLineDash([8,7]);ctx.beginPath();ctx.moveTo(px+40,y);ctx.lineTo(px+pw-40,y);ctx.stroke();ctx.setLineDash([]);};
    dash(300);
    text(ctx,'DATE   '+meta.day,px+50,340,{font:'400 24px '+mono,color:ink});
    text(ctx,'SLIP   '+meta.serial,px+50,372,{font:'400 24px '+mono,color:ink});
    text(ctx,'LEGS   '+meta.count,px+pw-50,340,{font:'400 24px '+mono,color:ink,align:'right'});
    text(ctx,(meta.mix||'').toUpperCase(),px+pw-50,372,{font:'400 20px '+mono,color:faint,align:'right',max:360});
    dash(398);
    const colW=(pw-100-(cols-1)*30)/cols;
    for(let c=0;c<cols;c++){const hx=px+50+c*(colW+30),hf={font:'400 19px '+mono,color:faint};text(ctx,'#',hx,440,hf);text(ctx,'PICK',hx+48,440,hf);text(ctx,'MATCHUP',hx+(cols===1?210:150),440,hf);if(cols===1)text(ctx,'TIME',hx+560,440,hf);text(ctx,'WIN',hx+colW,440,{...hf,align:'right'});}
    dash(470);
    picks.forEach((p,i)=>{
      const c=cols===1?0:i%cols,r=cols===1?i:Math.floor(i/cols),x=px+50+c*(colW+30),y=top+r*rowH-50;
      const opp=p.team===p.home?p.away:p.home;
      text(ctx,String(i+1).padStart(2,'0'),x,y+34,{font:'400 22px '+mono,color:faint});
      text(ctx,p.team,x+48,y+38,{font:(cols===1?40:32)+'px Anton, "Barlow Condensed", Impact, sans-serif',color:ink});
      text(ctx,(p.team===p.home?'vs ':'@ ')+opp+' · '+SPORT[p.sport],x+(cols===1?210:150),y+34,{font:'400 '+(cols===1?22:17)+'px '+mono,color:ink,max:cols===1?300:170});
      if(cols===1)text(ctx,clock(p.start),x+560,y+34,{font:'400 22px '+mono,color:ink});
      text(ctx,pct(p.prob),x+colW,y+34,{font:'400 '+(cols===1?26:20)+'px '+mono,color:ink,align:'right'});
      text(ctx,(cols===1?p.teamName+'  ':'')+(p.predicted===p.team?'[MODEL PICK]':p.predicted?'[AGAINST MODEL]':'[TOSS-UP]'),x+48,y+68,{font:'400 '+(cols===1?18:15)+'px '+mono,color:faint,max:colW-48});
    });
    let y=top+rows*rowH-20;dash(y);
    const line=(k,v,yy)=>{text(ctx,k,px+50,yy,{font:'400 24px '+mono,color:ink});text(ctx,v,px+pw-50,yy,{font:'400 24px '+mono,color:ink,align:'right'});};
    line('MODEL AGREES',meta.modelCount?meta.agree+' / '+meta.modelCount:'--',y+40);line('AVG WIN CHANCE',pct(meta.avg),y+72);line('ALL LEGS HIT',oneIn(meta.all),y+104);
    dash(y+126);
    barcode(ctx,hash(meta.serial),px+140,y+150,pw-280,90,ink);
    text(ctx,meta.serial,W/2,y+272,{font:'400 22px '+mono,color:ink,align:'center',spacing:6});
    // stamp
    ctx.save();ctx.translate(px+pw-150,118);ctx.rotate(-.22);ctx.strokeStyle='rgba(200,16,46,.75)';ctx.lineWidth=5;rr(ctx,-110,-38,220,76,10);ctx.stroke();
    text(ctx,'LOCKED IN',0,12,{font:'38px Anton, "Barlow Condensed", Impact, sans-serif',color:'rgba(200,16,46,.8)',align:'center',spacing:3});ctx.restore();
    footer(ctx,H-10,'#555','#111',meta,pw-60);
  }

  const DRAW={gridiron,ballpark,scoreboard,northern,slip};
  async function draw(canvas,picks,{style='gridiron',day}={}){
    await fonts();
    const list=picks.slice().sort((a,b)=>String(a.start).localeCompare(String(b.start)));
    const meta=summarize(list,day||list[0]?.day||'');
    await (DRAW[style]||gridiron)(canvas,list,meta);
    return {canvas,meta};
  }
  root.MoneylineCard={styles:STYLES,draw,summarize};
})(window);
