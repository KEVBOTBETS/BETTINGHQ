/* Native canvas keeps names, odds and result letters exact. Artwork is reused unchanged. */
(function(root){
  const NEW={gridiron:'Gridiron Gold',ballpark:'Ballpark Stubs',scoreboard:'Jumbotron',northern:'True North',slip:'Sportsbook Slip (printer friendly)'};
  const styles={...NEW,classic:'Classic ticket',baseball:'Beaver at the ballpark',hockey:'Beaver on the ice',football:'Beaver on the sideline'};
  const load=src=>new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('Artwork unavailable. Choose Classic ticket or retry.'));img.src=src;});
  const odds=v=>v==null?'—':(v>0?'+':'')+v;
  function fit(ctx,value,width){let s=String(value||'');if(ctx.measureText(s).width<=width)return s;while(s&&ctx.measureText(s+'…').width>width)s=s.slice(0,-1);return s+'…';}
  async function draw(canvas,ticket,{style='gridiron',results=null}={}){
    if(NEW[style]&&root.MoneylineCard)return root.MoneylineCard.drawTicket(canvas,ticket,{style,results,outcomeKey:r=>root.KevTickets.outcomeKey(r)});
    if(NEW[style])style='classic';
    const rows=ticket.picks||[],ctx=canvas.getContext('2d'),art=style!=='classic';canvas.width=1080;canvas.height=1350;
    ctx.fillStyle='#09121c';ctx.fillRect(0,0,1080,1350);ctx.fillStyle='#da1524';ctx.fillRect(0,0,1080,16);
    const logo=await load('kevbot-logo.jpg');ctx.drawImage(logo,48,38,100,100);
    ctx.fillStyle='#fff';ctx.font='900 55px Arial, sans-serif';ctx.fillText('KEVBOT BETS',173,93);
    ctx.fillStyle='#7be7bd';ctx.font='800 25px Arial, sans-serif';ctx.fillText(results?'TOP PICKS · RESULTS':'DAILY TOP PICKS',176,133);
    if(art){const img=await load('assets/tickets/'+style+'.webp');ctx.save();ctx.beginPath();ctx.rect(0,162,1080,370);ctx.clip();ctx.drawImage(img,0,-130,1080,1350);ctx.restore();}
    const top=art?570:195,rowH=art?59:94,start=top+91;
    ctx.fillStyle='#a7b6c8';ctx.font='600 23px Arial, sans-serif';ctx.fillText(ticket.day+' · '+rows.length+' qualified pick'+(rows.length===1?'':'s'),48,top);
    ctx.fillStyle='#d71920';ctx.fillRect(48,top+19,984,49);ctx.fillStyle='#fff';ctx.font='bold 20px Arial, sans-serif';ctx.fillText('PLAY',111,top+51);ctx.fillText('ODDS',823,top+51);if(results)ctx.fillText('RESULT',931,top+51);
    rows.forEach((r,i)=>{const y=start+i*rowH,entry=results?.[root.KevTickets.outcomeKey(r)],status=entry?.result?.status||'Pending';
      ctx.fillStyle=i%2?'#13212f':'#0d1a25';ctx.fillRect(48,y,984,rowH-6);ctx.fillStyle='#7be7bd';ctx.font='900 25px Arial, sans-serif';ctx.fillText(String(i+1).padStart(2,'0'),59,y+32);
      ctx.fillStyle='#fff';ctx.font='bold '+(art?23:26)+'px Arial, sans-serif';ctx.fillText(fit(ctx,r.pick,685),111,y+29);
      ctx.fillStyle='#a7b6c8';ctx.font=(art?17:19)+'px Arial, sans-serif';ctx.fillText(fit(ctx,r.source+' · '+r.event+(art?'':' · '+r.tier),680),111,y+(art?49:62));
      ctx.fillStyle='#fff';ctx.font='bold 24px Arial, sans-serif';ctx.fillText(odds(r.price),822,y+33);
      if(results){ctx.fillStyle=({Win:'#7be7bd',Loss:'#ff6b78',Pending:'#ffd166',Push:'#a8c9fa',Void:'#a8c9fa'})[status]||'#ffd166';ctx.font='bold '+(['Win','Loss'].includes(status)?29:14)+'px Arial, sans-serif';ctx.fillText(({Win:'W',Loss:'L',Pending:'PENDING',Push:'PUSH',Void:'VOID'})[status]||'PENDING',942,y+33);}
    });
    if(!rows.length){ctx.fillStyle='#fff';ctx.font='bold 30px Arial, sans-serif';ctx.fillText('No qualified picks for this date.',75,start+70);}
    ctx.fillStyle='#92a7b9';ctx.font='17px Arial, sans-serif';ctx.fillText(fit(ctx,(ticket.id?'Ticket '+ticket.id+' · ':'')+(results?'W = Win · L = Loss · Unverified results remain pending':'Prices captured '+(ticket.published_at||'').replace('T',' ').slice(0,16)+' UTC'),975),48,1290);
    ctx.fillText('19+ · Bet responsibly · Original odds retained · Verify current prices before betting',48,1318);
    return canvas;
  }
  root.KevTicketRenderer={styles,draw};
})(window);
