"""Unvalidated, participation-conditional NHL scorer research from official counts.

Gamma-Poisson shrinkage uses 12 baseline games and at most 30 prior club games.
The predictive zero-goal probability includes rate uncertainty. A team's player
rates cannot exceed its regulation goal projection. No shootout goals, prices,
injury adjustments or positive-EV claims are invented.
"""
import math

VERSION = 'nhl-anytime-gamma-1.0'


def count(row, key):
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else 0.0


def forecasts(game, rosters, stats, season):
    projection = game.get('projection') or {}
    if not projection.get('ratings_known') or game.get('season_type') not in (2, 3):
        return []
    result = []
    for side in ('away', 'home'):
        team = game[side]
        current = stats.get(team, {})
        prior = current.get('prior', {})
        current_rows = {str(r.get('playerId')): r for r in current.get('skaters', [])} if current.get('season') == season else {}
        prior_rows = {str(r.get('playerId')): r for r in prior.get('skaters', [])}
        if not prior_rows and current.get('season') != season:
            prior_rows = {str(r.get('playerId')): r for r in current.get('skaters', [])}
        team_stats = game.get(side + '_stats', {})
        c, p = team_stats.get('current', {}), team_stats.get('prior', {})
        cgp, pgp = count(c, 'gp'), count(p, 'gp')
        own_rate = ((c.get('gf_pg') or 3.05)*cgp + (p.get('gf_pg') or 3.05)*20)/(cgp+20)
        projected = projection.get(side + '_goals')
        if not isinstance(projected, (int, float)) or not math.isfinite(projected) or projected <= 0:
            continue
        factor = min(1.25, max(.75, projected / own_rate))
        players = []
        for who in rosters.get(team, []):
            if who.get('position') == 'G':
                continue
            now, old = current_rows.get(who['id'], {}), prior_rows.get(who['id'], {})
            gp, prior_gp = count(now, 'gamesPlayed'), count(old, 'gamesPlayed')
            if gp + prior_gp < 5:
                continue
            weight = min(30, prior_gp) / prior_gp if prior_gp else 0
            baseline = .06 if who.get('position') == 'D' else .20
            alpha = 12 * baseline + count(now, 'goals') + count(old, 'goals') * weight
            beta = 12 + gp + prior_gp * weight
            players.append((who, now, old, alpha, beta, gp, prior_gp))
        rate_sum = sum(alpha / beta * factor for _, _, _, alpha, beta, _, _ in players)
        # A partial roster remains partial; never inflate it to claim all team goals.
        factor *= min(1, projected / rate_sum) if rate_sum else 1
        for who, now, old, alpha, beta, gp, prior_gp in players:
            probability = 1 - (beta / (beta + factor)) ** alpha
            rate = alpha / beta * factor
            fair = 100 * (1/probability - 1) if probability < .5 else -100 * probability/(1-probability)
            result.append({'sport': 'NHL', 'event_id': str(game['game_id']), 'start_time': game['date'],
                'matchup': game['away']+' @ '+game['home'], 'team': team, **who,
                'athlete_id': who['id'], 'market': 'Anytime goal', 'side': 'yes', 'line': None,
                'average': round(count(now, 'goals')/gp, 3) if gp else round(count(old, 'goals')/prior_gp, 3),
                'samples': int(gp+prior_gp), 'current_games': int(gp), 'current_goals': int(count(now, 'goals')),
                'prior_games': int(prior_gp), 'prior_goals': int(count(old, 'goals')),
                'history_season': str(season), 'recent': [], 'expected_goals': round(rate, 4),
                'model_prob': round(probability, 6), 'model_fair_american': round(fair),
                'model_version': VERSION, 'probability_basis': 'Conditional on playing; regulation + OT, shootout excluded',
                'actionable': False, 'research_only': True,
                'history_note': 'Official club goal counts; early-season and prior rates shrink toward a position baseline. '
                    'Prior club history can be incomplete after a transfer. Current roster does not confirm participation.',
                'source_url': 'https://www.nhl.com/stats/players',
                'inputs': {'prior_weight_games': min(30, prior_gp), 'baseline_games': 12,
                    'matchup_factor': round(factor, 4), 'team_goal_projection': projected}})
    return sorted(result, key=lambda r: -r['model_prob'])
