/* Team graphics for the hub pages (Moneyline, Weekly football): logo badges with a
   colour monogram fallback, and a win-chance bar. Presentation only — reads the
   logo/colour fields the model feeds already publish and never fetches anything else. */
(function(root){
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hex=v=>/^#?[0-9a-f]{6}$/i.test(String(v||''))?'#'+String(v).replace('#',''):null;
  const hue=abbr=>{let h=0;for(const ch of String(abbr||''))h=(h*31+ch.charCodeAt(0))%360;return 'hsl('+h+' 45% 40%)';};
  const color=(c,side)=>hex(c[side+'Color'])||hue(c[side]);
  const light=v=>{const h=hex(v);if(!h)return false;const n=parseInt(h.slice(1),16);return (0.299*(n>>16&255)+0.587*(n>>8&255)+0.114*(n&255))>170;};
  function badge(c,side,cls){
    const logo=c[side+'Logo'];
    return '<span class="ml-logo'+(cls?' '+cls:'')+(light(c[side+'Color'])?' lt':'')+'" style="--tc:'+esc(color(c,side))+'" aria-hidden="true">'+esc(String(c[side]).slice(0,4))
      +(logo&&/^https:\/\//.test(logo)?'<img src="'+esc(logo)+'" alt="" loading="lazy" onload="this.classList.add(\'ok\')" onerror="this.remove()">':'')+'</span>';
  }
  function winBar(c){
    if(c.probability==null||!c.predicted)return '';
    const ph=c.predicted==='home'?c.probability:1-c.probability,pa=1-ph;
    return '<div class="ml-win" role="img" aria-label="Model win chance '+esc(c.away)+' '+Math.round(pa*100)+'%, '+esc(c.home)+' '+Math.round(ph*100)+'%"><div class="ml-win-lab"><span>'+esc(c.away)+' '+Math.round(pa*100)+'%</span><span>'+Math.round(ph*100)+'% '+esc(c.home)+'</span></div><div class="ml-win-track"><i style="width:'+(pa*100).toFixed(1)+'%;--c:'+esc(color(c,'away'))+'"></i><i style="width:'+(ph*100).toFixed(1)+'%;--c:'+esc(color(c,'home'))+'"></i></div></div>';
  }
  root.TeamVisuals={esc,color,badge,winBar};
})(typeof self!=='undefined'?self:this);
