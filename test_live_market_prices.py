"""Mocked tests for live_market_prices module."""

from decimal import Decimal
from backend.tools.live_market_prices import (
    MarketPrice,
    MarketPriceCollection,
    normalize_commodity,
    parse_agmarknet_date,
    AgmarknetFetcher,
    DatagovFetcher,
    MarketPriceService,
    CROP_NORMALIZATION,
    HttpTransport,
)


def test_normalize_commodity():
    assert normalize_commodity("tomato") == "Tomato"
    assert normalize_commodity("TOMATO") == "Tomato"
    assert normalize_commodity("tomatoes") == "Tomato"
    assert normalize_commodity("pyaz") == "Onion"
    assert normalize_commodity("aloo") == "Potato"
    assert normalize_commodity("unknown_crop") == "Unknown_Crop"


def test_parse_agmarknet_date():
    assert parse_agmarknet_date("15/01/2024") == "2024-01-15"
    assert parse_agmarknet_date("15-01-2024") == "2024-01-15"
    assert parse_agmarknet_date("15-Jan-2024") == "2024-01-15"
    assert parse_agmarknet_date("2024-01-15") == "2024-01-15"
    # Invalid falls back to today
    today = parse_agmarknet_date("invalid")
    from datetime import datetime, timezone
    assert today == datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_market_price_to_dict():
    price = MarketPrice(
        commodity="Tomato",
        variety="Hybrid",
        market="Lasalgaon",
        district="Nashik",
        state="Maharashtra",
        arrival_date="2024-01-15",
        min_price=Decimal("1800"),
        max_price=Decimal("2400"),
        modal_price=Decimal("2100"),
        source="agmarknet",
        source_url="https://agmarknet.gov.in/test",
        fetched_at="2024-01-15T10:00:00Z",
    )
    d = price.to_dict()
    assert d["commodity"] == "Tomato"
    assert d["min_price_inr_per_quintal"] == 1800.0
    assert d["max_price_inr_per_quintal"] == 2400.0
    assert d["modal_price_inr_per_quintal"] == 2100.0
    assert d["min_price_inr_per_tonne"] == 18000.0
    assert d["max_price_inr_per_tonne"] == 24000.0
    assert d["modal_price_inr_per_tonne"] == 21000.0


def test_market_price_collection_filter():
    p1 = MarketPrice(
        commodity="Tomato", variety="", market="Lasalgaon", district="Nashik", state="Maharashtra",
        arrival_date="2024-01-15", min_price=Decimal("1800"), max_price=Decimal("2400"),
        modal_price=Decimal("2100"), source="agmarknet", source_url="", fetched_at="",
    )
    p2 = MarketPrice(
        commodity="Onion", variety="", market="Mumbai", district="Mumbai", state="Maharashtra",
        arrival_date="2024-01-15", min_price=Decimal("2000"), max_price=Decimal("2500"),
        modal_price=Decimal("2200"), source="agmarknet", source_url="", fetched_at="",
    )
    p3 = MarketPrice(
        commodity="Tomato", variety="", market="Pune", district="Pune", state="Maharashtra",
        arrival_date="2024-01-16", min_price=Decimal("1900"), max_price=Decimal("2300"),
        modal_price=Decimal("2100"), source="agmarknet", source_url="", fetched_at="",
    )
    
    collection = MarketPriceCollection(prices=[p1, p2, p3])
    
    # Filter by commodity
    tomatoes = collection.filter(commodity="Tomato")
    assert len(tomatoes.prices) == 2
    assert all(p.commodity == "Tomato" for p in tomatoes.prices)
    
    # Filter by market
    lasalgaon = collection.filter(market="Lasalgaon")
    assert len(lasalgaon.prices) == 1
    assert lasalgaon.prices[0].market == "Lasalgaon"
    
    # Filter by state
    mh = collection.filter(state="Maharashtra")
    assert len(mh.prices) == 3
    
    # Filter by date
    recent = collection.filter(date_from="2024-01-16")
    assert len(recent.prices) == 1
    assert recent.prices[0].arrival_date == "2024-01-16"


def test_crop_normalization_coverage():
    # Ensure major crops are covered
    assert "tomato" in CROP_NORMALIZATION
    assert "onion" in CROP_NORMALIZATION
    assert "potato" in CROP_NORMALIZATION
    assert "wheat" in CROP_NORMALIZATION
    assert "rice" in CROP_NORMALIZATION
    assert "cotton" in CROP_NORMALIZATION
    assert "chilli" in CROP_NORMALIZATION
    assert "turmeric" in CROP_NORMALIZATION
    assert "grape" in CROP_NORMALIZATION
    assert "banana" in CROP_NORMALIZATION


def test_http_transport():
    class MockTransport(HttpTransport):
        def __init__(self):
            pass
        
        def request(self, url, method="GET", headers=None, body=None, timeout=30):
            return 200, {"test": "data"}
    
    transport = MockTransport()
    status, data = transport.request("http://test.com")
    assert status == 200
    assert data == {"test": "data"}


def test_agmarknet_fetcher_initialization():
    fetcher = AgmarknetFetcher()
    assert fetcher.transport is not None


def test_datagov_fetcher_without_key():
    fetcher = DatagovFetcher(api_key=None)
    result = fetcher.fetch_prices()
    assert result.prices == []
    assert "data.gov.in API key not configured" in result.warnings[0]


def test_market_price_service_initialization():
    service = MarketPriceService()
    assert service.agmarknet is not None
    assert service.datagov is not None
    assert service.enam is not None


def test_market_price_service_get_live_prices_mocked():
    """Test the service with mocked transport."""
    from unittest.mock import MagicMock
    
    service = MarketPriceService()
    
    # Mock the agmarknet fetcher
    mock_price = MarketPrice(
        commodity="Tomato", variety="", market="Test", district="Test", state="Test",
        arrival_date="2024-01-15", min_price=Decimal("1800"), max_price=Decimal("2400"),
        modal_price=Decimal("2100"), source="agmarknet", source_url="", fetched_at="",
    )
    
    service.agmarknet.fetch_daily_prices = MagicMock(return_value=MarketPriceCollection(prices=[mock_price]))
    
    result = service.get_live_prices(commodity="Tomato", state="Maharashtra")
    
    assert result.prices == [mock_price]
    assert "agmarknet" in result.sources_used


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])