"""Shot-quality/role challenger. Existing scorer forecasts remain the baseline."""
import math
import unicodedata
VERSION='nhl-role-xg-1.0'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s or '').lower() if c.isalpha() and not unicodedata.combining(c))
def n(x):
 try:
  if isinstance(x,bool):return None
  v=float(x);return v if math.isfinite(v) else None
 except (TypeError,ValueError):return None
CODES={'NJ':'NJD','SJ':'SJS','TB':'TBL','LA':'LAK','MON':'MTL','CAL':'CGY','VEG':'VGK','UTAH':'UTA','CLB':'CBJ','NAS':'NSH'}
def code(t):return CODES.get(t,t)
def role_minutes(role,fallback):
 season=role.get('season',{});recent=role.get('last5',{})
 def mean(r):
  gp=n(r.get('gamesPlayed'));m=n(r.get('toiMinutes'));seconds=n(r.get('toiSeconds')) or 0
  return (m+seconds/60)/gp if gp and gp>0 and m is not None else None
 a,b=mean(season),mean(recent);base=a or fallback
 return max(5,min(28,.6*(b or base)+.4*base)),(b-base) if b is not None else None

def forecasts(game,base,inputs):
 context=game.get('public_context') or {};projection=context.get('projection') or {};year=inputs.get('year')
 if not projection.get('ratings_known') or not year:return {}
 out={};statistics=inputs.get('statistics',{})
 for side in ('home','away'):
  team=code(game[side]);opp='away' if side=='home' else 'home';lineup=inputs.get('lineups',{}).get(team) or {};roles={norm(r['name']):r for r in lineup.get('players',[])}
  if not roles:continue
  team_rates=context.get('team_rates',{}).get(side) or {};opponent=context.get('team_rates',{}).get(opp) or {}
  team_shots=((team_rates.get('shots_for') or 0)+(opponent.get('shots_against') or 0))/2
  if not 15<=team_shots<=50:continue
  team_goals=projection.get(side+'_goals');own=team_rates.get('xgf')
  if not team_goals or not own:continue
  factor=max(.75,min(1.25,team_goals/own));players=[]
  for row in base:
   if code(row['team'])!=team:continue
   role=roles.get(norm(row['player']))
   if not role or role.get('available') is not True:continue
   samples=[]
   for y,w in ((year,1),(year-1,.4)):
    rows=[r for r in statistics.get(str(y),{}).get('skaters',{}).get('rows',[]) if str(r.get('playerId'))==str(row['athlete_id']) and r.get('situation')=='all' and (y!=year or code(r.get('team'))==team)]
    # Ambiguous/traded previous-season joins abstain; do not double-count total rows.
    if len(rows)==1 and norm(rows[0].get('name'))==norm(row['player']) and all(n(rows[0].get(k)) is not None for k in ('icetime','games_played','I_F_xGoals','I_F_goals','I_F_shotsOnGoal')):samples.append((rows[0],w))
   seconds=sum((n(r.get('icetime')) or 0)*w for r,w in samples);games=sum((n(r.get('games_played')) or 0)*w for r,w in samples)
   if seconds<3600 or games<5:continue
   xg=sum((n(r.get('I_F_xGoals')) or 0)*w for r,w in samples);goals=sum((n(r.get('I_F_goals')) or 0)*w for r,w in samples);shots=sum((n(r.get('I_F_shotsOnGoal')) or 0)*w for r,w in samples)
   minutes,trend=role_minutes(role,seconds/60/games)
   baseline=.06 if row.get('position')=='D' else .20
   xg60=(xg+baseline*14)/(seconds/3600+14*18/60)
   finish=max(.75,min(1.25,(goals+10)/(xg+10)))
   mean_goal=xg60*minutes/60*finish*factor
   mean_shots=(shots+28)/(seconds/3600+14*18/60)*minutes/60
   if mean_goal<=0 or mean_shots<=0:continue
   players.append((row,role,minutes,trend,mean_goal,mean_shots,xg60,finish))
  goal_sum=sum(p[4] for p in players);shot_sum=sum(p[5] for p in players)
  scale=min(1,team_goals/goal_sum) if goal_sum else 1;shot_scale=min(1,team_shots/shot_sum) if shot_sum else 1
  for row,role,minutes,trend,goals,shots,xg60,finish in players:
   goals*=scale;shots*=shot_scale;goals=min(goals,shots*.6)
   # Analytic marginal under the same Gamma(20,20) shared-pace hypothesis as simulations.
   chance=1-(1+goals/20)**-20
   out[(str(game['game_id']),str(row['athlete_id']))]={'version':VERSION,'model_prob':round(chance,6),'expected_goals':round(goals,5),'expected_shots':round(shots,5),
    'expected_minutes':round(minutes,2),'minutes_trend':round(trend,2) if trend is not None else None,'line':role.get('line'),'power_play':role.get('power_play'),'questionable':role.get('questionable',False),
    'xg_per60':round(xg60,3),'finishing_factor':round(finish,3),'team_shots':round(team_shots,3),'team_goals':round(team_goals,3),'source_observed_at':lineup.get('observed_at'),'lineup_updated_at':lineup.get('updated_at'),
    'research_only':True,'validated':False,'simulation':{'goals':round(goals,5),'shots':round(shots,5),'team_shots':round(team_shots,3),'pace_shape':20},
    'notes':['Conditional on playing in the projected role.','Shot-quality and ice-time inputs: MoneyPuck.com; projected roles: DailyFaceoff.com.','Power-play assignment is displayed as context; no unvalidated fixed PP boost is added.','Rates are shrunk and capped; model is a prospective challenger.']}
 return out
