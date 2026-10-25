"""Mocked tests for weather module."""

from decimal import Decimal
from datetime import datetime, timezone
from backend.tools.weather import (
    WeatherObservation,
    WeatherForecast,
    AgriculturalRiskAssessment,
    AgriculturalRiskEngine,
    CROP_TEMP_THRESHOLDS,
    CROP_HUMIDITY_THRESHOLDS,
    PERISHABILITY_RATES,
    HttpTransport,
    OpenMeteoClient,
)


def test_weather_observation():
    obs = WeatherObservation(
        timestamp="2024-01-15T12:00:00Z",
        temperature_c=28.5,
        humidity_pct=65.0,
        precipitation_mm=0.0,
        wind_speed_kmh=15.0,
        wind_direction_deg=180.0,
        pressure_hpa=1013.0,
        cloud_cover_pct=30.0,
        is_forecast=True,
    )
    d = obs.to_dict()
    assert d["temperature_c"] == 28.5
    assert d["humidity_pct"] == 65.0
    assert d["is_forecast"] is True


def test_weather_forecast():
    obs = WeatherObservation(
        timestamp="2024-01-15T12:00:00Z",
        temperature_c=28.5,
        humidity_pct=65.0,
        precipitation_mm=0.0,
        wind_speed_kmh=15.0,
        is_forecast=True,
    )
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=[obs],
        daily=[{"date": "2024-01-15", "temp_max_c": 32.0, "temp_min_c": 20.0}],
    )
    d = forecast.to_dict()
    assert d["location"] == "Pune"
    assert len(d["hourly"]) == 1
    assert d["daily"][0]["temp_max_c"] == 32.0


def test_crop_temp_thresholds():
    assert "Tomato" in CROP_TEMP_THRESHOLDS
    assert "Onion" in CROP_TEMP_THRESHOLDS
    assert "Potato" in CROP_TEMP_THRESHOLDS
    assert "default" in CROP_TEMP_THRESHOLDS
    
    tomato = CROP_TEMP_THRESHOLDS["Tomato"]
    assert tomato["optimal_min"] == 18
    assert tomato["optimal_max"] == 30
    assert tomato["critical_max"] == 38
    assert tomato["critical_min"] == 5
    
    default = CROP_TEMP_THRESHOLDS["default"]
    assert default["optimal_min"] == 15
    assert default["optimal_max"] == 30


def test_crop_humidity_thresholds():
    assert "Tomato" in CROP_HUMIDITY_THRESHOLDS
    assert "Onion" in CROP_HUMIDITY_THRESHOLDS
    assert "default" in CROP_HUMIDITY_THRESHOLDS
    
    tomato = CROP_HUMIDITY_THRESHOLDS["Tomato"]
    assert tomato["high_risk_above"] == 85
    assert tomato["moderate_above"] == 70
    
    onion = CROP_HUMIDITY_THRESHOLDS["Onion"]
    assert onion["high_risk_above"] == 80
    assert onion["moderate_above"] == 65


def test_perishability_rates():
    assert "high" in PERISHABILITY_RATES
    assert "medium" in PERISHABILITY_RATES
    assert "low" in PERISHABILITY_RATES
    
    high = PERISHABILITY_RATES["high"]
    assert high["base_spoilage_per_day"] == 0.08
    assert high["temp_factor"] == 1.5
    assert high["humidity_factor"] == 1.3
    
    low = PERISHABILITY_RATES["low"]
    assert low["base_spoilage_per_day"] == 0.015


def test_agricultural_risk_engine():
    engine = AgriculturalRiskEngine()
    
    # Create a mock forecast with some risk conditions
    hourly = [
        WeatherObservation(
            timestamp="2024-01-15T12:00:00Z",
            temperature_c=35.0,
            humidity_pct=80.0,
            precipitation_mm=0.0,
            wind_speed_kmh=20.0,
            is_forecast=True,
        ),
        WeatherObservation(
            timestamp="2024-01-16T12:00:00Z",
            temperature_c=38.0,
            humidity_pct=85.0,
            precipitation_mm=10.0,
            wind_speed_kmh=25.0,
            is_forecast=True,
        ),
    ]
    daily = [
        {"date": "2024-01-15", "temp_max_c": 35.0, "temp_min_c": 22.0, "precipitation_mm": 0.0, "wind_max_kmh": 20.0},
        {"date": "2024-01-16", "temp_max_c": 38.0, "temp_min_c": 23.0, "precipitation_mm": 10.0, "wind_max_kmh": 25.0},
    ]
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=hourly,
        daily=daily,
    )
    
    assessment = engine.assess(
        forecast, "Tomato", "medium",
        transport_duration_hours=6,
        storage_duration_days=3,
    )
    
    assert assessment.crop == "Tomato"
    assert assessment.location == "Pune"
    assert assessment.heat_stress_days >= 1  # 38°C > 30°C critical
    assert assessment.max_temp_c == 38.0
    assert assessment.min_temp_c == 22.0
    assert assessment.total_precipitation_mm == 10.0
    assert assessment.max_daily_precipitation_mm == 10.0
    assert assessment.avg_humidity_pct > 0
    assert assessment.max_wind_kmh == 25.0
    assert assessment.spoilage_acceleration_factor > 1.0
    assert assessment.transport_risk_level in ["low", "moderate", "high", "severe"]
    assert assessment.storage_risk_level in ["low", "moderate", "high", "severe"]
    assert assessment.harvest_risk_level in ["low", "moderate", "high", "severe"]
    assert len(assessment.recommendations) > 0


def test_assess_low_risk():
    engine = AgriculturalRiskEngine()
    
    hourly = [
        WeatherObservation(
            timestamp="2024-01-15T12:00:00Z",
            temperature_c=25.0,
            humidity_pct=60.0,
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
            is_forecast=True,
        ),
    ]
    daily = [
        {"date": "2024-01-15", "temp_max_c": 26.0, "temp_min_c": 18.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0},
    ]
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=hourly,
        daily=daily,
    )
    
    assessment = engine.assess(forecast, "Tomato", "low")
    
    assert assessment.heat_stress_days == 0
    assert assessment.cold_stress_days == 0
    assert assessment.heavy_rain_days == 0
    assert assessment.high_humidity_days == 0
    assert assessment.transport_risk_level == "low"
    assert assessment.storage_risk_level == "low"
    assert assessment.spoilage_acceleration_factor >= 1.0
    assert assessment.spoilage_acceleration_factor < 2.0


def test_assess_high_humidity():
    engine = AgriculturalRiskEngine()
    
    hourly = [
        WeatherObservation(
            timestamp="2024-01-15T12:00:00Z",
            temperature_c=25.0,
            humidity_pct=90.0,  # Above high risk threshold for Tomato (85)
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
            is_forecast=True,
        ),
    ]
    daily = [
        {"date": "2024-01-15", "temp_max_c": 26.0, "temp_min_c": 18.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0},
    ]
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=hourly,
        daily=daily,
    )
    
    assessment = engine.assess(forecast, "Tomato", "medium")
    
    assert assessment.high_humidity_days == 1
    assert assessment.storage_risk_level in ["moderate", "high", "severe"]


def test_assess_heavy_rain():
    engine = AgriculturalRiskEngine()
    
    hourly = []
    daily = [
        {"date": "2024-01-15", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 80.0, "wind_max_kmh": 30.0},
    ]
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=hourly,
        daily=daily,
    )
    
    assessment = engine.assess(forecast, "Tomato", "medium")
    
    assert assessment.heavy_rain_days == 1
    assert assessment.transport_risk_level in ["high", "severe"]
    assert assessment.harvest_risk_level in ["high", "severe"]


def test_assess_freeze_risk():
    engine = AgriculturalRiskEngine()
    
    hourly = []
    daily = [
        {"date": "2024-01-15", "temp_max_c": 20.0, "temp_min_c": 0.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0},
    ]
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=hourly,
        daily=daily,
    )
    
    assessment = engine.assess(forecast, "Tomato", "medium")
    
    assert assessment.cold_stress_days == 1  # 0°C < 5°C critical for Tomato
    assert assessment.warnings is not None


def test_risk_recommendations():
    engine = AgriculturalRiskEngine()
    
    hourly = []
    daily = [
        {"date": "2024-01-15", "temp_max_c": 38.0, "temp_min_c": 25.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0},
    ]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    assessment = engine.assess(forecast, "Tomato", "medium")
    
    assert len(assessment.recommendations) > 0
    # Should have some recommendation
    assert any(len(r) > 0 for r in assessment.recommendations)


def test_spoilage_factor_calculation():
    engine = AgriculturalRiskEngine()
    
    # High temp, high humidity, heavy rain
    hourly = [
        WeatherObservation(
            timestamp="2024-01-15T12:00:00Z",
            temperature_c=40.0,
            humidity_pct=90.0,
            precipitation_mm=50.0,
            wind_speed_kmh=20.0,
            is_forecast=True,
        ),
    ]
    daily = [
        {"date": "2024-01-15", "temp_max_c": 40.0, "temp_min_c": 28.0, "precipitation_mm": 50.0, "wind_max_kmh": 20.0},
    ]
    forecast = WeatherForecast(
        location="Pune",
        lat=18.52,
        lon=73.85,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hourly=hourly,
        daily=daily,
    )
    
    assessment = engine.assess(forecast, "Tomato", "high")
    
    # High perishability + extreme conditions = elevated factor (capped at 5.0)
    assert assessment.spoilage_acceleration_factor > 1.0
    assert assessment.spoilage_acceleration_factor <= 5.0  # capped


def test_transport_risk_levels():
    engine = AgriculturalRiskEngine()
    
    # Low risk
    daily = [{"date": "2024-01-15", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0}]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    assessment = engine.assess(forecast, "Tomato", "low", transport_duration_hours=2)
    assert assessment.transport_risk_level == "low"
    
    # Moderate risk - heavy rain
    daily = [{"date": "2024-01-15", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 60.0, "wind_max_kmh": 10.0}]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    assessment = engine.assess(forecast, "Tomato", "medium", transport_duration_hours=12)
    assert assessment.transport_risk_level in ["moderate", "high", "severe"]


def test_storage_risk_levels():
    engine = AgriculturalRiskEngine()
    
    # Low risk
    daily = [{"date": "2024-01-15", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0}]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    assessment = engine.assess(forecast, "Tomato", "low", storage_duration_days=2)
    assert assessment.storage_risk_level == "low"
    
    # Moderate risk - heat + humidity
    daily = [{"date": "2024-01-15", "temp_max_c": 35.0, "temp_min_c": 25.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0}]
    hourly = [WeatherObservation(timestamp="2024-01-15T12:00:00Z", temperature_c=35.0, humidity_pct=85.0, precipitation_mm=0.0, wind_speed_kmh=10.0, is_forecast=True)]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=hourly, daily=daily)
    assessment = engine.assess(forecast, "Tomato", "medium", storage_duration_days=10)
    assert assessment.storage_risk_level in ["moderate", "high", "severe"]


def test_harvest_risk_levels():
    engine = AgriculturalRiskEngine()
    
    # Low risk
    daily = [{"date": "2024-01-15", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0}]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    assessment = engine.assess(forecast, "Tomato", "low")
    assert assessment.harvest_risk_level == "low"
    
    # Severe risk - heavy rain during harvest
    daily = [{"date": "2024-01-15", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 80.0, "wind_max_kmh": 30.0}]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    assessment = engine.assess(forecast, "Tomato", "medium")
    assert assessment.harvest_risk_level in ["high", "severe"]


def test_weather_alerts():
    daily = [
        {"date": "2024-01-15", "temp_max_c": 42.0, "temp_min_c": 28.0, "precipitation_mm": 0.0, "precipitation_probability_pct": 0, "wind_max_kmh": 10.0, "wind_gusts_10m_max": 10.0},
        {"date": "2024-01-16", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 80.0, "precipitation_probability_pct": 90, "wind_max_kmh": 10.0, "wind_gusts_10m_max": 10.0},
        {"date": "2024-01-17", "temp_max_c": 25.0, "temp_min_c": 1.0, "precipitation_mm": 0.0, "precipitation_probability_pct": 0, "wind_max_kmh": 70.0, "wind_gusts_10m_max": 80.0},
    ]
    
    client = OpenMeteoClient()
    alerts = client._generate_alerts(daily)
    
    assert len(alerts) >= 3
    assert any("Extreme heat" in a for a in alerts)
    assert any("Heavy rainfall" in a for a in alerts)
    assert any("Frost risk" in a for a in alerts)
    assert any("High winds" in a for a in alerts)
    assert any("High precipitation probability" in a for a in alerts) or any("Heavy rainfall" in a for a in alerts)


def test_http_transport():
    class MockTransport(HttpTransport):
        def request(self, url, method="GET", headers=None, body=None, timeout=30):
            return 200, {"test": "data"}
    
    transport = MockTransport()
    status, data = transport.request("http://test.com")
    assert status == 200
    assert data == {"test": "data"}


def test_assessment_to_dict():
    hourly = []
    daily = [{"date": "2024-01-15", "temp_max_c": 30.0, "temp_min_c": 20.0, "precipitation_mm": 0.0, "wind_max_kmh": 10.0}]
    forecast = WeatherForecast(location="P", lat=0, lon=0, generated_at="", hourly=[], daily=daily)
    engine = AgriculturalRiskEngine()
    assessment = engine.assess(forecast, "Tomato", "medium")
    
    d = assessment.to_dict()
    
    assert "location" in d
    assert "crop" in d
    assert "assessed_at" in d
    assert "temperature" in d
    assert "precipitation" in d
    assert "humidity" in d
    assert "wind" in d
    assert "composite_risks" in d
    assert "recommendations" in d
    assert "warnings" in d
    
    assert d["composite_risks"]["transport_risk_level"] in ["low", "moderate", "high", "severe"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])