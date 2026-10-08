from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
import requests
from tools import night_news

NOW=datetime(2026,10,8,19,tzinfo=timezone.utc)
GAME={'game_id':'g','date':'2026-10-09T00:15Z','home':{'id':'6'},'away':{'id':'27'}}

class NightNews(unittest.TestCase):
    def test_actual_evening_schedule_in_eastern(self):
        self.assertTrue(night_news.eligible(GAME,NOW))
        for change in [{'date':'2026-10-08T17:00Z'},{'date':'2026-10-11T17:00Z'},{'canceled':True},{'postponed':True}]:self.assertFalse(night_news.eligible({**GAME,**change},NOW))

    def test_failure_retains_original_news_receipt_and_other_team_succeeds(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);feed=root/'projects/nfl-edge-lab/site/data/games_detail.json';feed.parent.mkdir(parents=True);feed.write_text(json.dumps([GAME]))
            dest=root/'projects/bet-ledger-hq/data/newsletters/nights.json';dest.parent.mkdir(parents=True)
            article={'headline':'Cowboys news','published':'2026-10-08T12:00Z','observed_at':'2026-10-08T13:00Z','url':'https://www.espn.com/old'}
            dest.write_text(json.dumps({'teams':{'6':{'articles':[article],'observed_at':'2026-10-08T13:00Z'}},'events':{}}))
            def fetch(team_id,now):
                if team_id=='6':raise requests.ConnectionError('offline')
                return {'articles':[],'observed_at':now.isoformat()}
            with patch.object(night_news,'articles_for',side_effect=fetch):result=night_news.collect(root,NOW)
            self.assertEqual(result['events']['g']['articles'][0],article)
            self.assertEqual(result['teams']['6']['observed_at'],'2026-10-08T13:00Z')
            self.assertEqual(len(result['errors']),1)

    def test_future_and_old_articles_are_rejected(self):
        response=unittest.mock.Mock();response.json.return_value={'articles':[{'headline':'Future','published':'2026-10-09T12:00Z','links':{'web':{'href':'https://www.espn.com/future'}}},{'headline':'Today','published':'2026-10-08T12:00Z','links':{'web':{'href':'https://www.espn.com/today'}}}]}
        with patch('requests.get',return_value=response):result=night_news.articles_for('6',NOW)
        self.assertEqual([a['headline'] for a in result['articles']],['Today'])

if __name__=='__main__':unittest.main()
