import unittest,json
from pipeline.parlay_history import encode_archive,decode_archive
class Compression(unittest.TestCase):
 def test_legacy_and_lossless_envelope(self):
  value={'schema':1,'records':{'frozen':{'captured_at':'2026-01-01','line':2.5,'name':'Jokić','result':'Win'}}}
  self.assertEqual(decode_archive(value),value)
  self.assertEqual(decode_archive(json.loads(encode_archive(value,threshold=1))),value)
 def test_corrupt_checksum_fails_closed(self):
  value=json.loads(encode_archive({'records':{}},threshold=1));value['sha256']='invalid'
  with self.assertRaises(ValueError):decode_archive(value)
