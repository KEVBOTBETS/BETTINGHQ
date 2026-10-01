import copy, json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from pipeline import build, official

NOW = datetime(2026, 10, 10, 16, tzinfo=timezone.utc)
STAMP = NOW.isoformat()
PARTNERS = [{'partnerId': 7, 'name': 'FanDuel', 'country': 'CA'}, {'partnerId': 3, 'name': 'Decimal book', 'country': 'CZ'}]
GAME = {'id': 2026020050, 'season': 20262027, 'gameType': 2, 'startTimeUTC': '2026-10-10T23:00:00Z',
  'gameState': 'FUT', 'gameScheduleState': 'OK', 'gameCenterLink': '/gamecenter/mtl-vs-tor/2026/10/10/2026020050',
  'homeTeam': {'abbrev': 'TOR', 'odds': [{'providerId': 7, 'value': '-115'}, {'providerId': 3, 'value': '1.92'}]},
  'awayTeam': {'abbrev': 'MTL', 'odds': [{'providerId': 7, 'value': '+105'}, {'providerId': 3, 'value': '1.92'}]}}
IDENTITIES = {code: {'id': code, 'abbr': code, 'name': name} for code, name in [('TOR', 'Toronto Maple Leafs'), ('MTL', 'Montréal Canadiens')]}

class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None): return NOW

class NHLSourcesTests(unittest.TestCase):
    def test_only_complete_named_american_prices(self):
        quotes = official.quotes(GAME, PARTNERS, STAMP)
        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0]['book'], 'FanDuel (CA)')
        self.assertEqual(quotes[0]['opposite_price'], 105)
        self.assertEqual(quotes[0]['observed_at'], STAMP)
        g = copy.deepcopy(GAME); g['awayTeam']['odds'] = []
        self.assertEqual(official.quotes(g, PARTNERS, STAMP), [])
        g['awayTeam']['odds'] = [{'providerId': 7, 'value': '1.92'}]
        self.assertEqual(official.quotes(g, PARTNERS, STAMP), [])

    def test_switch_preserves_ids_without_old_goalies_or_quotes(self):
        old = {'game_id': '401234', 'home': 'TOR', 'away': 'MTL', 'date': GAME['startTimeUTC'],
          'home_goalie': {'confirmed': True}, 'quotes': [{'book': 'stale'}]}
        g = official.stabilize(official.normalize(GAME, PARTNERS, STAMP, IDENTITIES), [old])
        self.assertEqual(g['game_id'], '401234'); self.assertEqual(g['nhl_game_id'], str(GAME['id']))
        self.assertFalse(g['home_goalie']['confirmed']); self.assertNotEqual(g['quotes'], old['quotes'])
        espn = {'game_id': 'newESPN', 'home': 'TOR', 'away': 'MTL', 'date': GAME['startTimeUTC']}
        self.assertEqual(official.stabilize(espn, [g])['game_id'], '401234')

    def test_postponed_games_and_final_ot_scores(self):
        postponed = official.normalize({**GAME, 'gameScheduleState': 'PPD'}, PARTNERS, STAMP, IDENTITIES)
        self.assertEqual(postponed['state'], 'unknown'); self.assertFalse(postponed['completed'])
        final = copy.deepcopy(GAME); final['gameState'] = 'OFF'
        final['homeTeam']['score'] = 4; final['awayTeam']['score'] = 3
        g = official.normalize(final, [], STAMP, IDENTITIES)
        self.assertTrue(g['completed']); self.assertEqual(g['home_score'], 4)

    def test_standings_aliases_season_and_accented_summary(self):
        raw = {'standings': [{'seasonId': 20262027, 'teamAbbrev': {'default': 'NJD'}, 'teamName': {'default': 'New Jersey Devils'}, 'gamesPlayed': 2, 'goalFor': 7, 'goalAgainst': 4, 'points': 4, 'conferenceName': 'Eastern'}]}
        rows = official.standings(raw, {'11': {'id': '11', 'abbr': 'NJ'}}, 2027)
        self.assertEqual(rows['11']['gf_pg'], 3.5); self.assertEqual(rows['11']['conference'], 'Eastern Conference')
        self.assertEqual(official.standings(raw, {}, 2026), {})
        summary = official.summary_teams({'data': [{'teamFullName': 'Montreal Canadiens', 'gamesPlayed': 82}]}, IDENTITIES)
        self.assertEqual(summary['MTL']['gp'], 82)

    def test_full_refresh_survives_espn_403_and_holds_unconfirmed_goalies(self):
        standings = {'standings': [{'seasonId': 20262027, 'teamAbbrev': {'default': code}, 'teamName': {'default': t['name']}, 'gamesPlayed': 2, 'goalFor': 6, 'goalAgainst': 6, 'points': 2} for code, t in IDENTITIES.items()]}
        summary = {'data': [{'teamFullName': t['name'], 'gamesPlayed': 82, 'goalsForPerGame': 3.1, 'goalsAgainstPerGame': 3, 'shotsForPerGame': 30, 'powerPlayPct': .22, 'penaltyKillPct': .8} for t in IDENTITIES.values()]}
        def fetch(url):
            if 'espn.com' in url: raise HTTPError(url, 403, 'Forbidden', None, None)
            if '/schedule/' in url: return {'gameWeek': [{'games': [copy.deepcopy(GAME)]}], 'oddsPartners': PARTNERS}
            if '/standings/' in url: return standings
            if '/team/summary' in url: return summary
            if '/goalie/summary' in url: return {'data':[]}
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as temp:
            state, out = Path(temp)/'state', Path(temp)/'data'; out.mkdir()
            (out/'games.json').write_text(json.dumps([{'game_id': '401234', 'home': 'TOR', 'away': 'MTL', 'date': GAME['startTimeUTC']}]))
            with patch.object(build, 'STATE', state), patch.object(build, 'OUT', out), patch.object(build, 'fetch', fetch), patch.object(build, 'datetime', FrozenDateTime): build.main()
            meta = json.loads((out/'meta.json').read_text()); games = json.loads((out/'games.json').read_text()); board = json.loads((out/'board.json').read_text())
            self.assertEqual(meta['schedule_source'], 'NHL fallback'); self.assertEqual(meta['generated_at'], STAMP)
            self.assertEqual(meta['sources']['scoreboard']['status'], 'unavailable')
            self.assertEqual(len(games), 1); self.assertEqual(games[0]['game_id'], '401234')
            self.assertTrue(games[0]['projection']['ratings_known']); self.assertFalse(games[0]['stats_stale'])
            self.assertEqual(len(board), 2); self.assertTrue(all(r['held'] for r in board))
            self.assertTrue(all('Starting goalies not both confirmed' in r['reasons'] for r in board))
            records = json.loads((state/'model_accuracy.json').read_text())
            self.assertEqual(records['401234']['nhl_game_id'], str(GAME['id']))
            self.assertEqual(meta['challenger']['mode'],'shadow-only')
            self.assertIsNotNone(records['401234']['challenger'])
            self.assertFalse(any(k.startswith('nhl-schedule-') for k in json.loads((state/'sources.json').read_text())))

    def test_both_current_schedule_failures_retain_original_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            state, out = Path(temp)/'state', Path(temp)/'data'; out.mkdir()
            original = '{"generated_at":"old"}'; (out/'meta.json').write_text(original)
            with patch.object(build, 'STATE', state), patch.object(build, 'OUT', out), patch.object(build, 'fetch', side_effect=OSError('unavailable')), patch.object(build, 'datetime', FrozenDateTime):
                with self.assertRaisesRegex(RuntimeError, 'Both independent'): build.main()
            self.assertEqual((out/'meta.json').read_text(), original)

if __name__ == '__main__': unittest.main()
