from stock_analysis import CrossValidator

def test_cross_validator_score():
    cv = CrossValidator()
    result = cv.score(
        up_yoy=10, peer_yoy=5, down_yoy=8, self_yoy=12,
        theme=5, foreign_pct=50, inst=4, lead=4,
        mv_signal=6, wave_score=6, imtm_score=5, trial=3
    )
    assert result["overall"] >= 80
    assert "可積極布局" in result["verdict"]
