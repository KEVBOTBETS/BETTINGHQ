"""Market-informed college research forecast. A projected winner is not an edge."""
from statistics import NormalDist
from .database import market_lines
from .model import instant

VERSION = 'ncaab-dk-margin-1.0'

def project_market(game, now, history=None):
    p = game.get('projection') or {}
    start = instant(game.get('tipoff'))
    if not p.get('ratings_known') or game.get('state') != 'pre' or not start or start <= now:
        return p
    dk = [q for q in game.get('quotes', []) if ''.join(str(q.get('book','')).lower().split()) == 'draftkings']
    lines = market_lines({'quotes': dk}, now)
    if 'spread_home' not in lines:
        return p
    team = p['mu']
    market = -lines['spread_home']
    # Anchor to the observed market; cap influence of an uncalibrated early-season model.
    weight=(history or {}).get('weight',.2)
    margin = market + max(-3., min(3., weight * (team-market)))
    sd = (history or {}).get('validated_sd',12) if p['margin_sd']==12 else p['margin_sd']
    return {**p, 'band_history':history, 'team_margin':team, 'market_anchor':lines['spread_home_source'], 'market_home_line':-market,
            'margin_sd':sd,'mu':round(margin,3), 'p_home':round(NormalDist(0,sd).cdf(margin),6),
            'proj_home_pts':round((p['total']+margin)/2,2), 'proj_away_pts':round((p['total']-margin)/2,2),
            'model_version':VERSION if sd==p['margin_sd'] else VERSION+'-cal1', 'basis':f'DraftKings implies a home margin of {market:+.1f}; team scoring history alone gives {team:+.1f}. The forecast moves {weight:.0%} toward the team estimate, capped at 3 points. Research rule; exact band chances are uncalibrated.'}
