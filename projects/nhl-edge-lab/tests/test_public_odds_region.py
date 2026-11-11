import gzip
import http.client
import io
import unittest
from unittest.mock import patch
from tests.test_public_odds import NOW,GAME,page,cell,quote
from pipeline import public_odds as p

class RegionalOddsTests(unittest.TestCase):
    def test_fetch_uses_sportsbook_region_and_rejects_percentage_contracts(self):
        sports=page('moneyline',cell('bet365',quote('+115'),quote('-135')))
        contracts=page('moneyline',cell('Example exchange',quote('46%'),quote('61%')))
        def download(url):return sports if url.startswith('https://www.covers.com/') and 'countrycode=ca' in url else contracts
        with patch.object(p,'download',side_effect=download):rows=p.fetch([GAME],NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual({q['book'] for _,q in rows},{'bet365'})
        self.assertFalse(p.parse(contracts,[GAME],NOW))
        self.assertTrue(all('countrycode=ca' in q['source_url'] for _,q in rows))

    def test_gzip_and_incomplete_response_retry_without_using_partial_odds(self):
        html=page('moneyline',cell('bet365',quote('+115'),quote('-135')))
        class Response(io.BytesIO):
            headers={'Content-Encoding':'gzip'}
        broken=Response(b'');broken.read=lambda *a:(_ for _ in ()).throw(http.client.IncompleteRead(b'partial'))
        with patch('pipeline.public_odds.urllib.request.urlopen',side_effect=[broken,Response(gzip.compress(html.encode()))]) as fetch:
            self.assertEqual(p.download(p.URL),html)
            self.assertEqual(fetch.call_count,2)
        bad=lambda *a,**k:(_ for _ in ()).throw(http.client.IncompleteRead(b'partial'))
        with patch('pipeline.public_odds.urllib.request.urlopen',side_effect=bad):
            with self.assertRaises(OSError):p.download(p.URL)

if __name__=='__main__':unittest.main()
