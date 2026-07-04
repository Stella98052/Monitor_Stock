import pytest
from unittest.mock import patch
from stock_analysis import PriceFetcher

@patch("requests.get")
def test_quote_tw(mock_get):
    mock_get.return_value.json.return_value = {
        "closePrice": 100,
        "previousClose": 95,
        "changePercent": 5,
        "name": "台積電"
    }
    mock_get.return_value.raise_for_status = lambda: None

    pf = PriceFetcher(fugle_key="FAKE")
    result = pf.quote_tw("2330")
    assert result["price"] == 100
    assert result["change_pct"] == 5
