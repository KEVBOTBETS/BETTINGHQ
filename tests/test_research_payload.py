import copy
import unittest
from tools.research.build import publication_report

class ResearchPayloadTests(unittest.TestCase):
    def test_browser_preview_preserves_full_count_and_original_records(self):
        report={'closing_prices':[{'decimal_ratio':i/1000} for i in range(1000)],'lab':{'records':40}}
        before=copy.deepcopy(report)
        compact=publication_report(report)
        self.assertEqual(compact['closing_price_count'],1000)
        self.assertEqual(compact['closing_prices'],report['closing_prices'][-200:])
        self.assertEqual(compact['lab'],report['lab'])
        self.assertEqual(report,before)

    def test_empty_closes_have_an_exact_zero_total(self):
        compact=publication_report({'closing_prices':[]})
        self.assertEqual(compact['closing_price_count'],0)
        self.assertEqual(compact['closing_prices'],[])

if __name__ == '__main__':unittest.main()
