import pytest
from stock_analysis import IMTMAnalyzer

def test_mtm_basic():
    closes = [10, 11, 12, 13]
    assert IMTMAnalyzer.mtm(closes, 2) == pytest.approx((13 - 11) / 11 * 100)

def test_mtm_insufficient():
    assert IMTMAnalyzer.mtm([10], 5) is None

def test_imtm_average():
    imtm = IMTMAnalyzer().imtm([10, None, 20])
    assert imtm == pytest.approx(15)

def test_verdict_dual_positive():
    verdict = IMTMAnalyzer().verdict(5, 10)
    assert "雙週期動量同揚" in verdict

def test_verdict_negative():
    verdict = IMTMAnalyzer().verdict(-5, -10)
    assert "雙週期動量同弱" in verdict
