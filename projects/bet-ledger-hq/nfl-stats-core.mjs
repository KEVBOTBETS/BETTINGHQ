export const fields={
 pass_att:['Pass att','Passing attempts'],pass_cmp:['Pass cmp','Pass completions'],pass_yds:['Pass yards','Passing yards'],pass_td:['Pass TD','Passing touchdowns'],pass_int:['Pass INT','Interceptions thrown'],
 rush_att:['Rush att','Rushing attempts'],rush_yds:['Rush yards','Rushing yards'],rush_td:['Rush TD','Rushing touchdowns'],targets:['Targets','Receiving targets'],receptions:['Rec','Receptions'],rec_yds:['Rec yards','Receiving yards'],rec_td:['Rec TD','Receiving touchdowns'],td_scored:['TD scored','Touchdowns scored, excluding passing touchdowns'],
 tackles:['Tackles','Tackles and assists'],solo_tackles:['Solo','Solo tackles'],sacks:['Sacks','Sacks'],def_int:['Def INT','Defensive interceptions'],fumbles_rec:['Fumble rec','Fumbles recovered'],def_td:['Def TD','Defensive touchdowns'],
 fg_att:['FG att','Field goal attempts'],fg_made:['FG made','Field goals made'],xp_att:['XP att','Extra point attempts'],xp_made:['XP made','Extra points made'],kick_points:['Kick points','Kicking points'],punts:['Punts','Punts'],punt_yds:['Punt yards','Punting yards'],punt_avg:['Punt avg','Punting yards per punt'],
};
export const views={
 overview:['pass_att','pass_yds','pass_td','rush_att','rush_yds','receptions','rec_yds','td_scored','tackles','sacks','fg_made','punts'],
 offense:['pass_att','pass_cmp','pass_yds','pass_td','pass_int','rush_att','rush_yds','rush_td','targets','receptions','rec_yds','rec_td','td_scored'],
 defense:['tackles','solo_tackles','sacks','def_int','fumbles_rec','def_td'],
 special:['fg_att','fg_made','xp_att','xp_made','kick_points','punts','punt_yds','punt_avg'],
};
export function value(row,key){return key in fields?row.stats?.[key]:row[key];}
export function selectRows(rows,{team='all',position='all',search='',projected=false,sort='team',direction='asc'}={}){
 const q=search.toLocaleLowerCase().trim(),sign=direction==='desc'?-1:1;
 const filtered=rows.filter(r=>r.role_eligible!==false&&(team==='all'||r.team_id===team)&&(position==='all'||r.position===position)&&(!projected||Object.keys(r.stats||{}).length)&&(!q||[r.player,r.team,r.team_abbreviation,r.position,r.opponent].some(v=>String(v||'').toLocaleLowerCase().includes(q))));
 return filtered.sort((a,b)=>{
  const x=value(a,sort),y=value(b,sort),xm=x==null||x==='',ym=y==null||y==='';
  if(xm!==ym)return xm?1:-1;
  const order=xm?0:(typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y)));
  return sign*order||a.player.localeCompare(b.player)||a.id.localeCompare(b.id);
 });
}
export function formatStat(value){return typeof value==='number'&&Number.isFinite(value)?value.toLocaleString(undefined,{minimumFractionDigits:1,maximumFractionDigits:1}):'—';}
function csvCell(value){const str=String(value??'');return '"'+(/^[=+\-@\t\r]/.test(str)?"'"+str:str).replaceAll('"','""')+'"';}
export function exportCSV(rows){
 const keys=['season','week','player','team','position','opponent','role','status','availability','samples','captured_at',...Object.keys(fields)];
 const labels={season:'Season',week:'Week',player:'Player',team:'Team',position:'Position',opponent:'Opponent',role:'Expected role',status:'Forecast status',availability:'Availability',samples:'Max sample games',captured_at:'Forecast captured (UTC)'};
 return '\uFEFF'+[keys.map(k=>csvCell(fields[k]?.[1]||labels[k]||k)).join(','),...rows.map(r=>keys.map(k=>csvCell(value(r,k))).join(','))].join('\r\n');
}
