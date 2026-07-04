import pytest
from stock_analysis import ElliottWaveAnalyzer

def test_wave_info_valid():
    ew = ElliottWaveAnalyzer()
    info = ew.wave_info("3")
    assert info["nature"] == "推動浪（主升段）⭐"

def test_wave_info_invalid():
    ew = ElliottWaveAnalyzer()
    assert ew.wave_info("Z") is None

def test_dynamic_targets_wave3():
    ew = ElliottWaveAnalyzer()
    result = ew.dynamic_targets("3", 100)
    assert result["target_low"] == 120
    assert result["target_high"] == 140
    assert result["stop_loss"] == 92

def test_dynamic_targets_B_wave():
    ew = ElliottWaveAnalyzer()
    result = ew.dynamic_targets("B", 100)
    assert result["target_low"] == 103
    assert result["target_high"] == 108
    assert result["stop_loss"] == "出場為主"

def test_cross_check_mv():
    ew = ElliottWaveAnalyzer()
    mv = {"dir5": "down", "dir13": "up"}
    msg = ew.cross_check_with_mv("B", mv)
    assert "B波陷阱" in msg
