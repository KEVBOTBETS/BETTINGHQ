import datetime as dt
import unittest
from unittest.mock import patch
from pipeline.weather import nws_hourly, at_kickoff, fetch_nws, adjustment

class NWSWeatherTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,1,12,tzinfo=dt.timezone.utc)
        self.data={'generatedAt':'2026-10-01T11:00:00Z','periods':[{'startTime':'2026-10-01T09:00:00-04:00','endTime':'2026-10-01T10:00:00-04:00','temperature':20,'temperatureUnit':'C','windSpeed':'5 to 10 mph','probabilityOfPrecipitation':{'value':30},'shortForecast':'Cloudy'}]}
    def test_units_alignment_and_unknown_values(self):
        series=nws_hourly(self.data,self.now)
        forecast=at_kickoff(series,'2026-10-01T13:15:00Z')
        self.assertEqual(forecast['temp_f'],68)
        self.assertEqual(forecast['wind_mph'],10)
        self.assertEqual(forecast['precip_prob'],30)
        self.assertEqual(forecast['source'],'National Weather Service')
        self.assertEqual(forecast['condition'],'Cloudy')
        self.assertIsNone(forecast['gust_mph'])
        self.assertIsNone(forecast['snow_in'])
        self.assertIsNone(at_kickoff(series,'2026-10-01T15:00:00Z'))
        self.assertFalse(adjustment(forecast,'dome',{})['applied'])
    def test_stale_and_nonhourly_rejected(self):
        self.assertIsNone(nws_hourly(self.data,self.now+dt.timedelta(hours=7)))
        self.data['periods'][0]['endTime']='2026-10-01T21:00:00-04:00'
        self.assertIsNone(nws_hourly(self.data,self.now))
    @patch('pipeline.weather.requests.get')
    def test_international_and_external_forecast_not_fetched(self,get):
        self.assertIsNone(fetch_nws((51.5,-0.1)))
        get.assert_not_called()
        get.return_value.json.return_value={'properties':{'forecastHourly':'https://example.com/forecast'}}
        self.assertIsNone(fetch_nws((40,-75)))
        self.assertEqual(get.call_count,1)

    @patch('pipeline.weather.fetch_nws')
    @patch('pipeline.weather.fetch_forecasts',return_value={})
    @patch('pipeline.weather.load_venues')
    def test_missing_primary_uses_nws_with_provenance(self,venues,primary,nws):
        from pipeline.weather import build_for_games
        now=dt.datetime.now(dt.timezone.utc).replace(minute=0,second=0,microsecond=0)+dt.timedelta(hours=2)
        venues.return_value={'venues':{'test':{'lat':40,'lon':-75,'roof':'open'}}}
        nws.return_value={'time':[now.replace(tzinfo=None).isoformat()],'temperature_2m':[60], 'wind_speed_10m':[15], '_source':'National Weather Service'}
        game={'game_id':'g','venue':'Test','home':{'abbr':'H'},'date_utc':now.isoformat()}
        result=build_for_games([game],{}, {})['g']
        self.assertEqual(result['forecast']['source'],'National Weather Service')
        nws.assert_called_once_with((40.0,-75.0))
