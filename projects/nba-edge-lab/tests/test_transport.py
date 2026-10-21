import unittest,json
from unittest.mock import patch,MagicMock
from pipeline.build import fetch
class Transport(unittest.TestCase):
 def response(self,status,data):
  value=MagicMock();value.status_code=status;value.iter_content.return_value=[json.dumps(data).encode()];value.__enter__.return_value=value;return value
 @patch('pipeline.build.time.sleep')
 @patch('pipeline.build.requests.get')
 def test_transient_status_retries_without_inventing_data(self,get,sleep):
  get.side_effect=[self.response(429,{}),self.response(200,{'events':[]})];self.assertEqual(fetch('https://example.test'),{'events':[]});self.assertEqual(get.call_count,2)
 @patch('pipeline.build.requests.get')
 def test_permission_error_is_not_bypassed(self,get):
  get.return_value=self.response(403,{});
  with self.assertRaisesRegex(OSError,'403'):fetch('https://example.test')
  self.assertEqual(get.call_count,1)
 @patch('pipeline.build.time.sleep')
 @patch('pipeline.build.requests.get')
 def test_bad_json_fails_closed(self,get,sleep):
  value=self.response(200,{});value.iter_content.return_value=[b'invalid json'];get.return_value=value
  with self.assertRaises(OSError):fetch('https://example.test')
