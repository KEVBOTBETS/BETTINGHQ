"""Kickoff-hour weather provenance and roof assumptions; no invented observations."""
from .common import instant, number, team
from .readiness import age_status

def review(sport,game,meta,now):
    weather=game.get('weather') or (game.get('context') or {}).get('weather') or {};fc=weather.get('forecast') or {};start=instant(game.get('date'));at=instant(weather.get('observed_at') or fc.get('source_observed_at'))
    hour=instant(fc.get('time_utc')+'Z' if fc.get('time_utc') and not instant(fc['time_utc']) else fc.get('time_utc'))
    roof=weather.get('roof','unknown');gap=abs((start-hour).total_seconds())/3600 if start and hour else None
    missing=[key for key in ['wind_mph','gust_mph','precip_prob','temp_f'] if number(fc.get(key)) is None]
    status='indoors' if roof=='dome' else 'missing' if not fc else 'stale' if not at or age_status(at.isoformat(),now,6)!='fresh' else 'wrong forecast hour' if gap is None or gap>1 else 'review roof' if roof in ['retractable','unknown'] else 'available'
    return {'sport':sport,'event_id':str(game['game_id']),'matchup':f"{team(game,'away')} @ {team(game,'home')}",'start':game.get('date'),'roof':roof,'status':status,'hour_gap':gap,'observed_at':at.isoformat() if at else None,'forecast_hour':fc.get('time_utc'),'wind_mph':fc.get('wind_mph'),'gust_mph':fc.get('gust_mph'),'precip_prob':fc.get('precip_prob'),'temp_f':fc.get('temp_f'),'missing':missing,'total_adjustment':weather.get('total_adj'),'source':fc.get('source') or 'No available hourly source','note':'Retractable roof status is unconfirmed; the current model uses a documented half-effect assumption.' if roof=='retractable' else 'Weather ignored indoors.' if roof=='dome' else 'Missing measurements remain unknown; no substitute zeros are generated.'}
