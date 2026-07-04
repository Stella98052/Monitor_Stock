from stock_analysis import NewsRiskScanner

def test_news_risk_detection():
    news = [
        {"headline": "Company faces lawsuit", "datetime": 1700000000},
        {"headline": "Strong earnings report", "datetime": 1700000000},
    ]
    result = NewsRiskScanner().scan(news)
    assert result["risk_count"] == 1
    assert "暫緩進場" in result["verdict"]
