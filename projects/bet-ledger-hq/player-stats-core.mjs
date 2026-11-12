export const fields={
 NBA:{minutes:'Minutes',points:'Points',rebounds:'Rebounds',assists:'Assists',pra:'PTS + REB + AST',threes_made:'3PT made',threes_att:'3PT attempts',fg_made:'FG made',fg_att:'FG attempts',ft_made:'FT made',ft_att:'FT attempts',steals:'Steals',blocks:'Blocks',turnovers:'Turnovers',off_rebounds:'Off. rebounds',def_rebounds:'Def. rebounds',fouls:'Fouls'},
 NHL:{ice_minutes:'Ice minutes',shots:'Shots on goal',goals:'Goals',assists:'Assists',points:'Points',blocks:'Blocked shots',saves:'Saves',shots_against:'Shots against',goals_against:'Goals against',save_pct:'Historical save %'}
};
export const overview={NBA:['minutes','points','rebounds','assists','threes_made','steals','blocks','turnovers'],NHL:['ice_minutes','shots','goals','assists','points','blocks','saves']};
export function select(rows,{team='all',position='all',search='',projected=false,sort='team',direction='asc'}={}){
 const q=search.trim().toLowerCase(),sign=direction==='desc'?-1:1;
 return rows.filter(r=>(team==='all'||r.team===team)&&(position==='all'||r.position===position)&&(!projected||Object.keys(r.stats||{}).length)&&(!q||[r.player,r.team,r.opponent,r.role].some(v=>String(v||'').toLowerCase().includes(q)))).sort((a,b)=>{
  const x=a.stats?.[sort]??a[sort],y=b.stats?.[sort]??b[sort],xm=x==null,ym=y==null;
  return xm!==ym?(xm?1:-1):sign*(xm?0:typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y)))||a.player.localeCompare(b.player)||a.id.localeCompare(b.id);
 });
}
export function format(n){return typeof n==='number'&&Number.isFinite(n)?n.toFixed(1):'—';}
const cell=v=>'"'+(/^[=+\-@\t\r]/.test(String(v??''))?"'":'')+String(v??'').replaceAll('"','""')+'"';
export function csv(rows,sport){const columns=['day','player','team','position','opponent','role','availability','samples','captured_at',...Object.keys(fields[sport])];return '\uFEFF'+[columns.map(k=>cell(fields[sport][k]||({day:'Date',player:'Player',team:'Team',position:'Position',opponent:'Opponent',role:'Expected role',availability:'Availability',samples:'Sample games',captured_at:'Forecast captured UTC'})[k]||k)).join(','),...rows.map(r=>columns.map(k=>cell(r.stats?.[k]??r[k])).join(','))].join('\r\n');}
