import pytest
from stock_analysis import MVTidalAnalyzer, EXTREME_VOLUME_MULTIPLIER

def test_moving_volume_basic():
    mv = MVTidalAnalyzer.moving_volume([1,2,3,4,5], 5)
    assert mv == pytest.approx(3.0)

def test_moving_volume_insufficient():
    assert MVTidalAnalyzer.moving_volume([1,2], 5) is None

def test_mv_direction_up():
    volumes = [1,2,3,4,5, 10]  # last 5 avg > previous 5 avg
    assert MVTidalAnalyzer.mv_direction(volumes, 5) == "up"

def test_mv_direction_down():
    volumes = [10,9,8,7,6, 1]
    assert MVTidalAnalyzer.mv_direction(volumes, 5) == "down"

def test_analyze_extreme_volume():
    volumes = [10]*5 + [100]  # today volume extremely high
    result = MVTidalAnalyzer().analyze(volumes)
    assert result["extreme_volume"] is True
    assert result["signal"] in ["WARNING", "SELL_NOW", "SHORT_TERM", "BUY_HOLD", "STRONG_BUY"]

def test_analyze_minimum_requirement():
    result = MVTidalAnalyzer().analyze([1,2,3,4])
    assert "error" in result
