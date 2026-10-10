import copy
from datetime import datetime,timedelta,timezone
import unittest
from tools.validation import report
from tools.research import calibration,market
from tools.research.build import attach_market_benchmarks

NOW=datetime(2026,10,10,15,tzinfo=timezone.utc)

def rows(p=.9, market=.6, games=220, outcome=None):
    result=[]
    for i in range(games):
        start=NOW-timedelta(days=40-i%35)
        result.append(dict(sport='nfl',event_id=str(i),market='ATS',baseline_version='v1',version=calibration.VERSION,
          book='A',price=-110,captured_at=(start-timedelta(hours=1)).isoformat(),observed_at=(start-timedelta(hours=2)).isoformat(),generated_at=(start-timedelta(hours=1)).isoformat(),start=start.isoformat(),
          raw_no_push=p,market_no_push=market,calibrated_no_push=.5,calibrator={'enabled':True,'contracts':200,'games':100,'trained_at':(start-timedelta(hours=1)).isoformat(),'last_result_at':(start-timedelta(days=1)).isoformat()},result={'outcome':outcome or ('win' if i%2 else 'loss'),'observed_at':(start+timedelta(hours=4)).isoformat()}))
    return result

class Validation(unittest.TestCase):
    def test_pauses_only_with_sufficient_forward_evidence(self):
        m=report(rows(),NOW)['markets'][0]
        self.assertTrue(m['recommendations_paused']);self.assertEqual(m['status'],'paused');self.assertTrue(m['research_available'])
        self.assertEqual(m['market_pairs'],220);self.assertEqual(m['shadow_status'],'review-candidate');self.assertFalse(m['promotion_enabled'])
        for data in [rows(games=20),[{**r,'start':rows()[0]['start']} for r in rows()]]:
            self.assertFalse(report(data,NOW)['markets'][0]['recommendations_paused'])
    def test_does_not_inflate_samples_or_pool_versions_and_markets(self):
        data=rows(games=120)
        data.extend([{**r,'line':-4,'book':'Other'} for r in data])
        data.extend([{**r,'baseline_version':'other'} for r in rows(games=90)])
        data.extend([{**r,'market':'TOTAL'} for r in rows(games=90)])
        groups=report(data,NOW)['markets'];self.assertEqual(sorted(m['contracts'] for m in groups),[90,90,120]);self.assertTrue(all(not m['recommendations_paused'] for m in groups))
    def test_legacy_future_and_invalid_outcomes_do_not_vote(self):
        for change in [{'version':'market-calibration-v1'},{'captured_at':(NOW+timedelta(days=1)).isoformat()},{'observed_at':(NOW+timedelta(days=1)).isoformat()},{'quote_status':'retained'},{'reference_only':True},{'price_source':'model'},{'raw_no_push':True},{'result':{'outcome':'push','observed_at':NOW.isoformat()}},{'result':{'outcome':'win','observed_at':(NOW+timedelta(days=1)).isoformat()}},{'result':{'outcome':'win','observed_at':(NOW-timedelta(days=90)).isoformat()}}]:
            data=[{**r,**change} for r in rows()];m=report(data,NOW)
            self.assertTrue(all(x['contracts']==0 for x in m['markets']),change)
    def test_missing_benchmarks_stay_missing_and_control_can_recover(self):
        data=rows(p=.5)
        for r in data:r.pop('market_no_push')
        m=report(data,NOW)['markets'][0];self.assertEqual(m['market_pairs'],0);self.assertIsNone(m['vs_market']['brier']['interval']);self.assertFalse(m['recommendations_paused']);self.assertEqual(m['shadow_status'],'shadow-only')
    def test_low_probability_side_is_also_checked_for_overconfidence(self):
        m=report(rows(p=.1),NOW)['markets'][0];self.assertTrue(m['recommendations_paused'])
    def test_benchmark_requires_exact_book_time_line_and_quoted_price(self):
        q=dict(sport='nfl',event_id='future',market='ATS',baseline_version='v1',start=(NOW+timedelta(days=1)).isoformat(),observed_at=NOW.isoformat(),book='A',side='home',line=-3,price=-110)
        audited,_=market.audit([q,{**q,'side':'away','price':-120}],[],NOW);by={('nfl','future'):audited['groups']}
        enriched=attach_market_benchmarks([q],by,NOW)[0];self.assertAlmostEqual(enriched['market_no_push'],(1/market.normalize(q,NOW)['decimal'])/(1/market.normalize(q,NOW)['decimal']+1/market.normalize({**q,'price':-120},NOW)['decimal']))
        self.assertNotIn('market_no_push',q)
        for change in [{'book':'Other'},{'line':-3.5},{'observed_at':(NOW-timedelta(minutes=1)).isoformat()},{'price':-115},{'quote_status':'retained'},{'reference_only':True}]:self.assertNotIn('market_no_push',attach_market_benchmarks([{**q,**change}],by,NOW)[0])

    def test_freeze_corrects_conditional_push_basis_and_retains_captures(self):
        q=dict(sport='nfl',event_id='future',market='ATS',baseline_version='v1',start=(NOW+timedelta(days=1)).isoformat(),generated_at=NOW.isoformat(),observed_at=NOW.isoformat(),book='A',side='home',line=-3,p_win=.6,p_push=.1,price=-110,probability_basis='conditional',market_no_push=.52)
        saved=calibration.freeze([], [q], NOW);self.assertAlmostEqual(saved[0]['raw_no_push'],.6);self.assertAlmostEqual(saved[0]['calibrated_win'],.54)
        self.assertEqual(calibration.freeze(saved,[{**q,'market_no_push':.7}],NOW),saved)
        for change in [{'quote_status':'retained'},{'reference_only':True},{'observed_at':(NOW-timedelta(hours=5)).isoformat()}]:self.assertEqual(calibration.freeze([],[{**q,**change}],NOW),[])

if __name__=='__main__':unittest.main()
