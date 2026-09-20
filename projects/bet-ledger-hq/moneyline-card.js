/* KEVBOT card artwork: five canvas styles shared by the Moneyline winner card and
   the Daily Top Picks ticket. Names, prices, times and percentages are drawn as
   text so they stay exact. */
(function(root){
  'use strict';
  const STYLES={
    gridiron:{name:'Gridiron Gold',note:'Stadium art, gold trim'},
    ballpark:{name:'Ballpark Stubs',note:'Ticket-stub picks'},
    scoreboard:{name:'Jumbotron',note:'LED scoreboard'},
    northern:{name:'True North',note:'Red & white poster'},
    slip:{name:'Sportsbook Slip',note:'Printer friendly'}
  };
  const W=1080,SPORT={nfl:'NFL',ncaaf:'NCAAF',mlb:'MLB',wnba:'WNBA',props:'PROPS',ladder:'LADDER'};
  const tz='America/Toronto';
  const fmt=(v,o)=>new Intl.DateTimeFormat('en-CA',{timeZone:tz,...o}).format(new Date(v));
  const clock=v=>{const t=Date.parse(v);return Number.isFinite(t)?fmt(t,{hour:'numeric',minute:'2-digit'}).replace(/\s?([ap])\.?m\.?/i,(_,x)=>x.toUpperCase()+'M'):'';};
  const pct=p=>p==null?'—':Math.round(p*100)+'%';
  const odds=v=>v==null||!Number.isFinite(Number(v))?'—':(v>0?'+':'')+Math.round(v);
  const prob=v=>{const n=Number(v);return v!=null&&v!==''&&Number.isFinite(n)&&n>=0&&n<=1?n:null;};
  const images={};
  function image(src){
    src=(root.MoneylineCard&&root.MoneylineCard.base?root.MoneylineCard.base:'')+src;
    if(!images[src])images[src]=new Promise(resolve=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>resolve(null);img.src=src;});
    return images[src];
  }
  async function fonts(){
    if(!document.fonts?.load)return;
    const wanted=['800 40px "Barlow Condensed"','italic 900 40px "Barlow Condensed"','40px Anton','700 20px "DM Sans"','400 20px "Share Tech Mono"'];
    await Promise.race([Promise.all(wanted.map(f=>document.fonts.load(f).catch(()=>null))),new Promise(r=>setTimeout(r,2500))]);
  }
  function hash(text){let h=2166136261;for(const c of String(text)){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
  const oneIn=p=>p==null||p<=0?'—':p>=.5?pct(p):'1 in '+(1/p>=100?Math.round(1/p).toLocaleString('en-CA'):(1/p).toFixed(1));
  const mixOf=rows=>Object.entries(rows.reduce((m,r)=>(m[r.sport]=(m[r.sport]||0)+1,m),{})).map(([k,n])=>n+' '+k).join(' · ');
  const product=list=>list.length&&list.every(p=>p!=null)?list.reduce((a,p)=>a*p,1):null;
  const average=list=>{const k=list.filter(p=>p!=null);return k.length?k.reduce((a,p)=>a+p,0)/k.length:null;};
  const dayParts=day=>{const d=day+'T12:00:00Z';return {long:fmt(d,{weekday:'long',month:'long',day:'numeric',year:'numeric'}),short:fmt(d,{weekday:'short',month:'short',day:'numeric'}).replace(/\./g,'')};};

  /* ---------- drawing helpers ---------- */
  function rr(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}
  function fit(ctx,t,max){let s=String(t??'');if(ctx.measureText(s).width<=max)return s;while(s.length>1&&ctx.measureText(s+'…').width>max)s=s.slice(0,-1);return s+'…';}
  function text(ctx,value,x,y,{font,color,align='left',max,spacing=0}){
    ctx.font=font;ctx.fillStyle=color;ctx.textAlign=align;ctx.textBaseline='alphabetic';
    if('letterSpacing' in ctx)ctx.letterSpacing=spacing+'px';
    ctx.fillText(max?fit(ctx,value,max):String(value??''),x,y);
    if('letterSpacing' in ctx)ctx.letterSpacing='0px';ctx.textAlign='left';
  }
  /* Big headline text that shrinks to fit, then truncates. Returns drawn width. */
  function big(ctx,value,x,y,{size,family,color,max,min=Math.round(size*.55)}){
    let s=size;ctx.font=family.replace('{s}',s);
    while(s>min&&ctx.measureText(value).width>max){s-=2;ctx.font=family.replace('{s}',s);}
    text(ctx,value,x,y,{font:ctx.font,color,max});ctx.font=family.replace('{s}',s);
    return Math.min(max,ctx.measureText(value).width);
  }
  function logo(ctx,img,x,y,size,ring){
    ctx.save();if(ring){ctx.beginPath();ctx.arc(x+size/2,y+size/2,size/2,0,Math.PI*2);ctx.fillStyle=ring;ctx.fill();}
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
    while(cx<x+w){s=Math.imul(s^(s>>>15),2246822507)>>>0;const b=1+(s%4),gap=1+((s>>>8)%3);if(cx+b*2>x+w)break;ctx.fillRect(cx,y,b*2,h);cx+=b*2+gap*2;}
  }
  function bar(ctx,x,y,w,h,p,fg,bg){rr(ctx,x,y,w,h,h/2);ctx.fillStyle=bg;ctx.fill();if(p!=null){rr(ctx,x,y,Math.max(h,w*p),h,h/2);ctx.fillStyle=fg;ctx.fill();}}
  function grid(n){const cols=n>8?2:1;return {cols,rows:Math.max(1,Math.ceil(n/cols))};}
  function cell(i,cols,x0,colW,gap,top,rowH,rgap){const c=cols===1?0:i%cols,r=cols===1?i:Math.floor(i/cols);return {x:x0+c*(colW+gap),y:top+r*(rowH+rgap)};}
  function dotText(ctx,value,x,y,{size,font,on,off,step,max}){
    const c=document.createElement('canvas'),g=c.getContext('2d');let s=size,f=font.replace('{s}',s);g.font=f;
    while(max&&s>size*.5&&g.measureText(value).width>max){s-=2;f=font.replace('{s}',s);g.font=f;}
    const w=Math.ceil(g.measureText(value).width)+4,h=Math.ceil(size*1.25);c.width=w;c.height=h;
    g.font=f;g.fillStyle='#fff';g.textBaseline='top';g.fillText(value,2,Math.round(size*.08+(size-s)*.5));
    const data=g.getImageData(0,0,w,h).data,r=step*.38;
    for(let yy=step/2;yy<h;yy+=step)for(let xx=step/2;xx<w;xx+=step){
      const lit=data[(Math.floor(yy)*w+Math.floor(xx))*4+3]>110;
      if(!lit&&!off)continue;ctx.beginPath();ctx.arc(x+xx,y+yy,r,0,Math.PI*2);ctx.fillStyle=lit?on:off;ctx.fill();
    }
    return w;
  }
  const TONE={good:'#16794f',bad:'#c8102e',neutral:'#8a6d1f'};
  function footer(ctx,H,color,accent,card,max=W-80){
    text(ctx,card.legal,W/2,H-34,{font:'500 '+(max<W-80?15:17)+'px "DM Sans", Arial, sans-serif',color,align:'center',max});
    text(ctx,card.serial+(card.mix?' · '+card.mix:'')+' · kevbotbets',W/2,H-62,{font:'700 17px "DM Sans", Arial, sans-serif',color:accent,align:'center',spacing:2,max});
  }
  async function heroArt(ctx,src,H,bg){
    const art=await image(src);ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
    if(art){ctx.save();ctx.beginPath();ctx.rect(0,0,W,760);ctx.clip();ctx.drawImage(art,0,0,W,W*art.height/art.width);ctx.restore();}
    const g=ctx.createLinearGradient(0,470,0,780);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,bg);ctx.fillStyle=g;ctx.fillRect(0,470,W,320);
  }

  /* ---------- styles: each takes a normalized card ---------- */
  async function gridiron(canvas,card){
    const rows=card.rows,{cols,rows:n}=grid(rows.length),rowH=cols===1?118:112,top=1000,H=Math.max(1350,top+n*(rowH+14)+150);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    await heroArt(ctx,'assets/tickets/football.webp',H,'#0b0d12');
    const gold=ctx.createLinearGradient(0,0,W,0);gold.addColorStop(0,'#8a5a12');gold.addColorStop(.5,'#ffd772');gold.addColorStop(1,'#8a5a12');
    ctx.fillStyle=gold;ctx.fillRect(48,760,W-96,4);
    big(ctx,card.title,48,850,{size:96,family:'italic 900 {s}px "Barlow Condensed", Arial, sans-serif',color:'#ffd772',max:520});
    text(ctx,card.subtitle,48,888,{font:'800 30px "Barlow Condensed", Arial, sans-serif',color:'#fff',spacing:6});
    ctx.font='800 30px "Barlow Condensed", Arial, sans-serif';const dl=ctx.measureText(card.dayLong.toUpperCase()).width<=W-180-540?card.dayLong:card.dayShort;
    text(ctx,dl.toUpperCase(),W-180,846,{font:'800 30px "Barlow Condensed", Arial, sans-serif',color:'#fff',align:'right',max:W-180-540});
    text(ctx,card.kicker,W-180,884,{font:'700 15px "DM Sans", Arial, sans-serif',color:'#b99b55',align:'right',spacing:2,max:W-180-300});
    logo(ctx,await image('kevbot-logo.jpg'),W-160,770,112,'#ffd772');
    card.stats.forEach(([k,v],i)=>{const x=48+i*248;text(ctx,k,x,934,{font:'700 14px "DM Sans", Arial, sans-serif',color:'#b99b55',spacing:2});text(ctx,v,x,972,{font:'800 34px "Barlow Condensed", Arial, sans-serif',color:i===3?'#ffd772':'#fff',max:230});});
    const colW=(W-96-(cols-1)*18)/cols;
    rows.forEach((r,i)=>{
      const {x,y}=cell(i,cols,48,colW,18,top,rowH,14);
      rr(ctx,x,y,colW,rowH,14);const g=ctx.createLinearGradient(x,y,x,y+rowH);g.addColorStop(0,'#1a1712');g.addColorStop(1,'#101014');ctx.fillStyle=g;ctx.fill();ctx.strokeStyle='rgba(255,215,114,.55)';ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle='#d71920';rr(ctx,x,y,10,rowH,5);ctx.fill();
      const bx=x+colW-(cols===1?230:150),bw=cols===1?200:128;
      text(ctx,r.n+'  ·  '+r.sport+'  ·  '+r.time+(cols===1&&r.name?'  ·  '+r.name:''),x+30,y+30,{font:'700 16px "DM Sans", Arial, sans-serif',color:'#c9ae6a',spacing:.5,max:bx-x-50});
      const tw=big(ctx,r.big,x+28,y+rowH-(cols===1?20:18),{size:cols===1?64:48,family:'italic 900 {s}px "Barlow Condensed", Arial, sans-serif',color:'#fff',max:bx-x-(r.vs?150:50)});
      if(r.vs)text(ctx,r.vs,x+42+tw,y+rowH-(cols===1?22:20),{font:'700 '+(cols===1?30:22)+'px "Barlow Condensed", Arial, sans-serif',color:'#9a8c6a',max:bx-x-tw-60});
      text(ctx,r.value,bx+bw,y+(cols===1?54:48),{font:'800 '+(cols===1?40:32)+'px "Barlow Condensed", Arial, sans-serif',color:'#ffd772',align:'right'});
      if(r.valueNote&&cols===1)text(ctx,r.valueNote,bx,y+(cols===1?54:48),{font:'700 14px "DM Sans", Arial, sans-serif',color:'#9a8c6a',spacing:1});
      bar(ctx,bx,y+(cols===1?68:60),bw,10,r.prob,'#ffd772','#2d2718');
      text(ctx,r.chip,bx+bw,y+rowH-20,{font:'800 14px "DM Sans", Arial, sans-serif',color:r.tone==='good'?'#7be7bd':r.tone==='bad'?'#ff8e8e':'#ffd772',align:'right',spacing:1,max:bw+60});
    });
    footer(ctx,H,'#8f8a7c','#ffd772',card);
  }

  async function ballpark(canvas,card){
    const rows=card.rows,{cols,rows:n}=grid(rows.length),rowH=cols===1?130:118,top=1040,H=Math.max(1350,top+n*(rowH+16)+150);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    await heroArt(ctx,'assets/tickets/baseball.webp',H,'#0c1a2e');
    ctx.strokeStyle='#e8474f';ctx.lineWidth=3;ctx.setLineDash([10,9]);ctx.beginPath();ctx.moveTo(48,772);ctx.lineTo(W-48,772);ctx.stroke();ctx.setLineDash([]);
    big(ctx,card.titleCase,48,868,{size:104,family:'italic 900 {s}px "Barlow Condensed", Arial, sans-serif',color:'#fff',max:560});
    text(ctx,card.stubKicker,52,904,{font:'700 22px "DM Sans", Arial, sans-serif',color:'#f2c14e',spacing:4,max:560});
    text(ctx,card.dayLong,W-48,846,{font:'800 32px "Barlow Condensed", Arial, sans-serif',color:'#fff',align:'right',max:400});
    text(ctx,card.mix,W-48,884,{font:'600 20px "DM Sans", Arial, sans-serif',color:'#9fb6d6',align:'right',max:400});
    const gap=16,tw=(W-96-gap*3)/4;
    card.stats.forEach(([k,v],i)=>{const x=48+i*(tw+gap);rr(ctx,x,920,tw,104,14);ctx.fillStyle='#12284a';ctx.fill();ctx.strokeStyle='#27477a';ctx.lineWidth=2;ctx.stroke();
      text(ctx,k,x+tw/2,952,{font:'700 15px "DM Sans", Arial, sans-serif',color:'#9fb6d6',align:'center',spacing:1.5,max:tw-12});
      text(ctx,v,x+tw/2,1004,{font:'800 40px "Barlow Condensed", Arial, sans-serif',color:i===3?'#f2c14e':'#fff',align:'center',max:tw-16});});
    const colW=(W-96-(cols-1)*18)/cols;
    rows.forEach((r,i)=>{
      const {x,y}=cell(i,cols,48,colW,18,top,rowH,16),stub=cols===1?190:120;
      ctx.save();rr(ctx,x,y,colW,rowH,10);ctx.clip();ctx.fillStyle='#f6ecd6';ctx.fillRect(x,y,colW,rowH);
      ctx.fillStyle='#e9dcbd';ctx.fillRect(x+colW-stub,y,stub,rowH);
      for(let yy=y+8;yy<y+rowH;yy+=14){ctx.fillStyle='#0c1a2e';ctx.beginPath();ctx.arc(x+colW-stub,yy,3,0,Math.PI*2);ctx.fill();}
      ctx.fillStyle='#0c1a2e';ctx.beginPath();ctx.arc(x+colW-stub,y,12,0,Math.PI*2);ctx.arc(x+colW-stub,y+rowH,12,0,Math.PI*2);ctx.fill();ctx.restore();
      ctx.fillStyle='#c8102e';ctx.fillRect(x,y+rowH-12,colW-stub-14,4);
      const room=colW-stub-40;
      text(ctx,r.sport+' · GAME '+r.n+(cols===1?' · '+r.time+' ET':''),x+20,y+30,{font:'800 15px "DM Sans", Arial, sans-serif',color:'#c8102e',spacing:2,max:room});
      const w=big(ctx,r.big,x+20,y+(cols===1?84:78),{size:cols===1?58:44,family:'italic 900 {s}px "Barlow Condensed", Arial, sans-serif',color:'#0c1a2e',max:room-(r.vs?90:0)});
      if(r.vs)text(ctx,r.vs,x+30+w,y+(cols===1?84:78),{font:'700 '+(cols===1?28:20)+'px "Barlow Condensed", Arial, sans-serif',color:'#6b6250',max:room-w-10});
      if(cols===1&&r.name)text(ctx,r.name,x+20,y+rowH-22,{font:'500 16px "DM Sans", Arial, sans-serif',color:'#6b6250',max:room});
      const sx=x+colW-stub/2;
      text(ctx,r.valueLabel,sx,y+(cols===1?34:30),{font:'800 13px "DM Sans", Arial, sans-serif',color:'#6b6250',align:'center',spacing:3});
      text(ctx,r.value,sx,y+(cols===1?80:70),{font:'800 '+(cols===1?46:32)+'px "Barlow Condensed", Arial, sans-serif',color:'#0c1a2e',align:'center',max:stub-16});
      text(ctx,r.chipShort,sx,y+rowH-(cols===1?22:14),{font:'800 13px "DM Sans", Arial, sans-serif',color:TONE[r.tone],align:'center',spacing:1,max:stub-10});
    });
    footer(ctx,H,'#8ea3c2','#f2c14e',card);
  }

  async function scoreboard(canvas,card){
    const rows=card.rows,{cols,rows:n}=grid(rows.length),rowH=cols===1?120:108,top=560,H=Math.max(1350,top+n*(rowH+14)+170);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#050608';ctx.fillRect(0,0,W,H);
    ctx.fillStyle='#0d1014';for(let y=6;y<H;y+=12)for(let x=6;x<W;x+=12)ctx.fillRect(x,y,3,3);
    rr(ctx,30,30,W-60,470,18);ctx.fillStyle='#0b0d10';ctx.fill();ctx.strokeStyle='#2b2f36';ctx.lineWidth=6;ctx.stroke();
    logo(ctx,await image('kevbot-logo.jpg'),64,70,150,'#ffb000');
    dotText(ctx,'KEVBOT',250,64,{size:92,font:'900 {s}px "Barlow Condensed", Arial, sans-serif',on:'#ffb000',off:'#1c1609',step:7,max:760});
    dotText(ctx,card.title,250,168,{size:92,font:'900 {s}px "Barlow Condensed", Arial, sans-serif',on:'#ff3b30',off:'#1c0b09',step:7,max:760});
    text(ctx,card.dayLong.toUpperCase(),64,300,{font:'400 30px "Share Tech Mono", monospace',color:'#ffb000',spacing:2,max:600});
    text(ctx,card.mix.toUpperCase(),W-64,300,{font:'400 26px "Share Tech Mono", monospace',color:'#7a6630',align:'right',max:320});
    card.stats.forEach(([k,v],i)=>{const x=64+i*238;rr(ctx,x,330,218,140,10);ctx.fillStyle='#000';ctx.fill();ctx.strokeStyle='#23272e';ctx.lineWidth=3;ctx.stroke();
      text(ctx,k,x+109,362,{font:'400 20px "Share Tech Mono", monospace',color:'#8b93a1',align:'center',spacing:3,max:200});
      text(ctx,v,x+109,440,{font:'400 '+(String(v).length>6?38:58)+'px "Share Tech Mono", monospace',color:i===3?'#ff3b30':'#ffb000',align:'center',max:200});});
    text(ctx,card.boardLeft,64,536,{font:'400 20px "Share Tech Mono", monospace',color:'#5d6573',spacing:4});
    text(ctx,card.boardRight,W-64,536,{font:'400 20px "Share Tech Mono", monospace',color:'#5d6573',align:'right',spacing:4});
    const colW=(W-96-(cols-1)*18)/cols;
    rows.forEach((r,i)=>{
      const {x,y}=cell(i,cols,48,colW,18,top,rowH,14);
      rr(ctx,x,y,colW,rowH,8);ctx.fillStyle='#000';ctx.fill();ctx.strokeStyle='#1d2127';ctx.lineWidth=2;ctx.stroke();
      const size=cols===1?60:44,step=cols===1?5:4,vw=cols===1?190:120;
      let w1;const room=colW-vw-(r.vs?120:40);
      if(r.big.length<=5)w1=dotText(ctx,r.big,x+18,y+14,{size,font:'900 {s}px "Barlow Condensed", Arial, sans-serif',on:'#ffb000',off:null,step,max:room});
      else{ctx.save();ctx.shadowColor='rgba(255,176,0,.7)';ctx.shadowBlur=14;w1=big(ctx,r.big,x+18,y+(cols===1?66:52),{size:cols===1?52:36,family:'400 {s}px "Share Tech Mono", monospace',color:'#ffb000',max:room});ctx.restore();}
      if(r.vs)text(ctx,r.vs.toUpperCase(),x+30+w1,y+(cols===1?64:52),{font:'400 '+(cols===1?30:22)+'px "Share Tech Mono", monospace',color:'#6c5a2a',max:colW-vw-w1-40});
      const mark=r.tone==='good'?'◆ ':r.tone==='bad'?'✕ ':'◇ ';
      const segs=cols===1?20:12,sw=cols===1?9:7,mx=x+colW-18-segs*(sw+3),lit=r.prob==null?0:Math.round(r.prob*segs);
      text(ctx,r.sport+' '+r.time+'  '+mark+r.chipShort,x+18,y+rowH-16,{font:'400 18px "Share Tech Mono", monospace',color:r.tone==='good'?'#39d98a':r.tone==='bad'?'#ff6b6b':'#8b93a1',max:mx-x-30});
      for(let s=0;s<segs;s++){ctx.fillStyle=s<lit?(s>=segs*.7?'#39d98a':s>=segs*.5?'#ffb000':'#ff3b30'):'#15181d';ctx.fillRect(mx+s*(sw+3),y+rowH-30,sw,14);}
      text(ctx,r.value,x+colW-18,y+(cols===1?60:48),{font:'400 '+(cols===1?46:34)+'px "Share Tech Mono", monospace',color:'#ffb000',align:'right',max:vw});
    });
    ctx.fillStyle='rgba(255,255,255,.025)';for(let y=0;y<H;y+=4)ctx.fillRect(0,y,W,1);
    footer(ctx,H,'#6d7480','#ffb000',card);
  }

  async function northern(canvas,card){
    const rows=card.rows,{cols,rows:n}=grid(rows.length),rowH=cols===1?116:108,top=700,H=Math.max(1350,top+n*(rowH+14)+160);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#c8102e';ctx.fillRect(0,0,W,H);
    ctx.fillStyle='#a50d26';ctx.fillRect(0,0,120,H);ctx.fillRect(W-120,0,120,H);
    ctx.save();ctx.globalAlpha=.08;ctx.strokeStyle='#fff';ctx.lineWidth=14;for(let x=-H;x<W;x+=46){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x+H,H);ctx.stroke();}ctx.restore();
    ctx.save();ctx.globalAlpha=.14;maple(ctx,W/2,330,330,'#fff');ctx.restore();
    logo(ctx,await image('kevbot-logo.jpg'),W/2-120,54,240,'#fff');
    ctx.save();ctx.shadowColor='rgba(0,0,0,.35)';ctx.shadowOffsetY=6;
    ctx.font='140px Anton, "Barlow Condensed", Impact, sans-serif';let ts=140;while(ts>80&&ctx.measureText(card.title).width>760){ts-=4;ctx.font=ts+'px Anton, "Barlow Condensed", Impact, sans-serif';}
    text(ctx,card.title,W/2,440,{font:ts+'px Anton, "Barlow Condensed", Impact, sans-serif',color:'#fff',align:'center',spacing:4});ctx.restore();
    ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(190,470);ctx.lineTo(W-190,470);ctx.lineTo(W-160,500);ctx.lineTo(W-190,530);ctx.lineTo(190,530);ctx.lineTo(160,500);ctx.closePath();ctx.fill();
    text(ctx,card.ribbon+' · '+card.dayShort.toUpperCase(),W/2,510,{font:'800 26px "Barlow Condensed", Arial, sans-serif',color:'#c8102e',align:'center',spacing:2,max:W-420});
    card.stats.forEach(([k,v],i)=>{const x=150+i*195+97;text(ctx,v,x,610,{font:'54px Anton, "Barlow Condensed", Impact, sans-serif',color:'#fff',align:'center',max:185});text(ctx,k,x,642,{font:'800 15px "DM Sans", Arial, sans-serif',color:'#ffd4d9',align:'center',spacing:2,max:190});});
    const colW=(W-300-(cols-1)*16)/cols;
    rows.forEach((r,i)=>{
      const {x,y}=cell(i,cols,150,colW,16,top,rowH,14);
      ctx.save();ctx.shadowColor='rgba(80,0,10,.35)';ctx.shadowOffsetY=8;rr(ctx,x,y,colW,rowH,6);ctx.fillStyle='#fff';ctx.fill();ctx.restore();
      maple(ctx,x+(cols===1?50:34),y+rowH/2,cols===1?30:20,'#c8102e');
      const tx=x+(cols===1?100:66),vw=cols===1?170:96;
      const w=big(ctx,r.big,tx,y+(cols===1?70:60),{size:cols===1?60:42,family:'{s}px Anton, "Barlow Condensed", Impact, sans-serif',color:'#1b1b1f',max:colW-(tx-x)-vw-(r.vs?70:10)});
      if(r.vs)text(ctx,r.vs,tx+w+12,y+(cols===1?70:60),{font:'800 '+(cols===1?26:18)+'px "Barlow Condensed", Arial, sans-serif',color:'#9a8f90',max:colW-(tx-x)-vw-w-20});
      text(ctx,r.sport+' · '+r.time+(cols===1&&r.name?' · '+r.name:''),tx,y+rowH-(cols===1?20:16),{font:'600 '+(cols===1?16:13)+'px "DM Sans", Arial, sans-serif',color:'#6d6566',max:colW-(tx-x)-vw});
      text(ctx,r.value,x+colW-20,y+(cols===1?64:52),{font:(cols===1?52:36)+'px Anton, "Barlow Condensed", Impact, sans-serif',color:'#c8102e',align:'right',max:vw-10});
      text(ctx,r.chipShort,x+colW-20,y+rowH-(cols===1?20:16),{font:'800 13px "DM Sans", Arial, sans-serif',color:TONE[r.tone],align:'right',spacing:1,max:vw});
    });
    footer(ctx,H,'#ffd4d9','#fff',card);
  }

  async function slip(canvas,card){
    const rows=card.rows,{cols,rows:n}=grid(rows.length),rowH=cols===1?104:96,top=560,H=Math.max(1350,top+n*rowH+400);
    canvas.width=W;canvas.height=H;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#ecebe6';ctx.fillRect(0,0,W,H);
    const px=110,pw=W-220;ctx.save();ctx.shadowColor='rgba(0,0,0,.18)';ctx.shadowBlur=24;ctx.beginPath();ctx.moveTo(px,26);
    for(let x=px;x<=px+pw;x+=20)ctx.lineTo(x+10,x/20%2?16:36);ctx.lineTo(px+pw,H-36);for(let x=px+pw;x>=px;x-=20)ctx.lineTo(x-10,x/20%2?H-16:H-36);ctx.closePath();ctx.fillStyle='#fff';ctx.fill();ctx.restore();
    const img=await image('kevbot-logo.jpg');ctx.save();ctx.filter='grayscale(1) contrast(1.2)';logo(ctx,img,W/2-60,60,120,null);ctx.restore();
    const mono='"Share Tech Mono", "Courier New", monospace',ink='#111',faint='#777';
    text(ctx,'KEVBOT BETS',W/2,236,{font:'44px Anton, "Barlow Condensed", Impact, sans-serif',color:ink,align:'center',spacing:6});
    text(ctx,'*** '+card.slipTitle+' ***',W/2,276,{font:'400 26px '+mono,color:ink,align:'center',max:pw-80});
    const dash=y=>{ctx.strokeStyle='#333';ctx.lineWidth=2;ctx.setLineDash([8,7]);ctx.beginPath();ctx.moveTo(px+40,y);ctx.lineTo(px+pw-40,y);ctx.stroke();ctx.setLineDash([]);};
    dash(300);
    text(ctx,'DATE   '+card.day,px+50,340,{font:'400 24px '+mono,color:ink});
    text(ctx,'SLIP   '+card.serial,px+50,372,{font:'400 24px '+mono,color:ink,max:420});
    text(ctx,'LEGS   '+rows.length,px+pw-50,340,{font:'400 24px '+mono,color:ink,align:'right'});
    text(ctx,card.mix.toUpperCase(),px+pw-50,372,{font:'400 20px '+mono,color:faint,align:'right',max:320});
    dash(398);
    const colW=(pw-100-(cols-1)*30)/cols,mx=cols===1?250:150;
    for(let c=0;c<cols;c++){const hx=px+50+c*(colW+30),hf={font:'400 19px '+mono,color:faint};text(ctx,'#',hx,440,hf);text(ctx,'PICK',hx+48,440,hf);text(ctx,cols===1?'MATCHUP':'',hx+mx+48,440,hf);if(cols===1)text(ctx,'TIME',hx+560,440,hf);text(ctx,card.slipValue,hx+colW,440,{...hf,align:'right'});}
    dash(470);
    rows.forEach((r,i)=>{
      const c=cols===1?0:i%cols,rr_=cols===1?i:Math.floor(i/cols),x=px+50+c*(colW+30),y=top+rr_*rowH-50;
      text(ctx,r.n,x,y+34,{font:'400 22px '+mono,color:faint});
      const w=big(ctx,r.big,x+48,y+38,{size:cols===1?40:32,family:'{s}px Anton, "Barlow Condensed", Impact, sans-serif',color:ink,max:cols===1?mx:colW-150});
      if(cols===1)text(ctx,r.matchup,x+mx+48,y+34,{font:'400 22px '+mono,color:ink,max:560-mx-60});
      else text(ctx,r.vs||r.sport,x+60+w,y+34,{font:'400 16px '+mono,color:faint,max:colW-w-150});
      if(cols===1)text(ctx,r.time,x+560,y+34,{font:'400 22px '+mono,color:ink});
      text(ctx,r.value,x+colW,y+34,{font:'400 '+(cols===1?26:20)+'px '+mono,color:ink,align:'right'});
      text(ctx,(cols===1&&r.name?r.name+'  ':'')+'['+r.chip+']',x+48,y+68,{font:'400 '+(cols===1?18:15)+'px '+mono,color:r.tone==='bad'?'#b0102a':faint,max:colW-48});
    });
    const y=top+n*rowH-20;dash(y);
    card.slipLines.forEach(([k,v],i)=>{text(ctx,k,px+50,y+40+i*32,{font:'400 24px '+mono,color:ink});text(ctx,v,px+pw-50,y+40+i*32,{font:'400 24px '+mono,color:ink,align:'right'});});
    dash(y+126);
    barcode(ctx,hash(card.serial),px+140,y+150,pw-280,90,ink);
    text(ctx,card.serial,W/2,y+272,{font:'400 22px '+mono,color:ink,align:'center',spacing:6,max:pw-80});
    ctx.save();ctx.translate(px+pw-150,118);ctx.rotate(-.22);ctx.strokeStyle='rgba(200,16,46,.75)';ctx.lineWidth=5;rr(ctx,-110,-38,220,76,10);ctx.stroke();
    text(ctx,card.stamp,0,12,{font:'38px Anton, "Barlow Condensed", Impact, sans-serif',color:'rgba(200,16,46,.8)',align:'center',spacing:3,max:200});ctx.restore();
    footer(ctx,H-10,'#555','#111',card,pw-60);
  }
  const DRAW={gridiron,ballpark,scoreboard,northern,slip};

  /* ---------- Moneyline winner card ---------- */
  function moneylineCard(picks,day){
    const list=picks.slice().sort((a,b)=>String(a.start).localeCompare(String(b.start)));
    const model=list.filter(p=>p.predicted),agree=model.filter(p=>p.predicted===p.team).length;
    const probs=list.map(p=>prob(p.prob)),d=dayParts(day);
    const serial='ML-'+day.replace(/-/g,'').slice(2)+'-'+hash(list.map(p=>p.key+p.team).join('|')).toString(36).toUpperCase().padStart(6,'0').slice(0,6);
    const rows=list.map((p,i)=>{const opp=p.team===p.home?p.away:p.home,pr=prob(p.prob),agrees=p.predicted===p.team;
      return {n:String(i+1).padStart(2,'0'),sport:SPORT[p.sport]||String(p.sport).toUpperCase(),time:clock(p.start),big:p.team,vs:(p.team===p.home?'vs ':'@ ')+opp,
        name:p.teamName||'',matchup:(p.team===p.home?'vs ':'@ ')+opp+' · '+(SPORT[p.sport]||''),value:pct(pr),valueLabel:'WIN',prob:pr,
        chip:agrees?'MODEL PICK ✓':p.predicted?'AGAINST MODEL':'TOSS-UP',chipShort:agrees?'MODEL ✓':p.predicted?'UPSET CALL':'TOSS-UP',tone:agrees?'good':p.predicted?'bad':'neutral'};});
    return {rows,serial,day,dayLong:d.long,dayShort:d.short,mix:mixOf(rows),title:'MONEYLINE',titleCase:'Moneyline',subtitle:'WINNER CARD',kicker:'KICK OFF · FIRST PITCH · WINNERS ONLY',
      stubKicker:'ADMIT ONE · WINNER PICKS',ribbon:'TRUE NORTH WINNER PICKS',slipTitle:'MONEYLINE WINNER SLIP',slipValue:'WIN',stamp:'LOCKED IN',boardLeft:'TEAM',boardRight:'WIN %',
      stats:[['PICKS',String(list.length)],['MODEL AGREES',model.length?agree+'/'+model.length:'—'],['AVG WIN',pct(average(probs))],['ALL-HIT',oneIn(product(probs))]],
      slipLines:[['MODEL AGREES',model.length?agree+' / '+model.length:'--'],['AVG WIN CHANCE',pct(average(probs))],['ALL LEGS HIT',oneIn(product(probs))]],
      legal:'19+ · Play responsibly · Winner picks only — not a wager. Model estimates are not guarantees; check current prices.',
      meta:{serial,count:list.length,agree,modelCount:model.length}};
  }

  /* ---------- Daily Top Picks ticket ---------- */
  const RESULT={Win:['WIN ✓','W','good'],Loss:['LOSS','L','bad'],Push:['PUSH','PUSH','neutral'],Void:['VOID','VOID','neutral'],Pending:['PENDING','PENDING','neutral']};
  function ticketCard(ticket,results,key){
    const list=(ticket.picks||[]).slice(),d=dayParts(ticket.day||'');
    const probs=list.map(r=>prob(r.probability)),best=list.filter(r=>/BEST/i.test(r.tier||'')).length;
    const serial='TK-'+String(ticket.day||'').replace(/-/g,'').slice(2)+'-'+String(ticket.id||hash(JSON.stringify(list.map(r=>r.pick)))).replace(/^local-/,'').replace(/-/g,'').slice(0,6).toUpperCase();
    const status=r=>results?(results[key(r)]?.result?.status||'Pending'):null;
    const tally=results?list.reduce((m,r)=>(m[status(r)]=(m[status(r)]||0)+1,m),{}):null;
    const record=tally?(tally.Win||0)+'-'+(tally.Loss||0)+(tally.Push?'-'+tally.Push:''):null;
    const rows=list.map((r,i)=>{const s=status(r),res=s?RESULT[s]||RESULT.Pending:null,tier=String(r.tier||'').toUpperCase();
      return {n:String(i+1).padStart(2,'0'),sport:String(r.sport||SPORT[r.key]||r.source||'').toUpperCase(),time:clock(r.start),big:r.pick||'—',vs:r.event||'',
        name:r.book?'Price: '+r.book:'',matchup:r.event||'',value:odds(r.price),valueLabel:'ODDS',valueNote:prob(r.probability)!=null?pct(prob(r.probability))+' MODEL':'',prob:prob(r.probability),
        chip:res?res[0]:tier||'PICK',chipShort:res?res[1]:tier||'PICK',tone:res?res[2]:/BEST/.test(tier)?'good':'neutral'};});
    const statsLive=[['PICKS',String(list.length)],['BEST BETS',String(best)],['AVG MODEL',pct(average(probs))],['ALL-HIT',oneIn(product(probs))]];
    const statsDone=[['PICKS',String(list.length)],['RECORD',record],['PENDING',String(tally?.Pending||0)],['HIT RATE',(tally?.Win||0)+(tally?.Loss||0)?pct((tally.Win||0)/((tally.Win||0)+(tally.Loss||0))):'—']];
    return {rows,serial,day:ticket.day||'',dayLong:d.long,dayShort:d.short,mix:mixOf(rows),title:results?'RESULTS':'TOP PICKS',titleCase:results?'Results':'Top Picks',
      subtitle:results?'DAILY TICKET · GRADED':'DAILY TICKET',kicker:'QUALIFIED PLAYS · ORIGINAL PRICES',stubKicker:results?'FINAL · GRADED TICKET':'ADMIT ONE · DAILY TOP PICKS',
      ribbon:results?'TRUE NORTH RESULTS':'TRUE NORTH TOP PICKS',slipTitle:results?'DAILY TICKET · RESULTS':'DAILY TOP PICKS SLIP',slipValue:'ODDS',stamp:results?'GRADED':'LOCKED IN',
      boardLeft:'PLAY',boardRight:'ODDS',stats:results?statsDone:statsLive,
      slipLines:results?[['RECORD',record],['PENDING',String(tally?.Pending||0)],['PRICES CAPTURED',String(ticket.published_at||'').slice(0,16).replace('T',' ')+' UTC']]:[['BEST BETS',String(best)],['AVG MODEL',pct(average(probs))],['PRICES CAPTURED',String(ticket.published_at||'').slice(0,16).replace('T',' ')+' UTC']],
      legal:'19+ · Bet responsibly · Original odds retained · Verify current prices before betting'+(results?' · Unverified results stay pending':''),
      meta:{serial,count:list.length}};
  }

  async function render(canvas,card,style){await fonts();await (DRAW[style]||gridiron)(canvas,card);return canvas;}
  async function draw(canvas,picks,{style='gridiron',day}={}){
    const card=moneylineCard(picks,day||picks[0]?.day||'');await render(canvas,card,style);return {canvas,meta:card.meta};
  }
  async function drawTicket(canvas,ticket,{style='gridiron',results=null,outcomeKey,override=null}={}){
    const card={...ticketCard(ticket,results,outcomeKey||(r=>root.KevTickets?.outcomeKey(r))),...(override||{})};
    await render(canvas,card,style);return canvas;
  }
  root.MoneylineCard={styles:STYLES,draw,drawTicket,base:''};
})(window);
