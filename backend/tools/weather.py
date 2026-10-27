"""
Weather and Agricultural Risk — Open-Meteo integration.

Fetches weather forecasts and evaluates agricultural risks:
- Temperature extremes
- Rainfall probability and precipitation
- Severe weather indicators
- Transport exposure risk
- Crop-specific spoilage vulnerability
- Estimated safe transport/storage windows

Uses documented scientific/configurable business rules.
Clearly distinguishes forecasts from observations.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# --- Constants ---

OPENMETEO_BASE = "https://api.open-meteo.com/v1"
OPENMETEO_FORECAST = f"{OPENMETEO_BASE}/forecast"
OPENMETEO_ARCHIVE = f"{OPENMETEO_BASE}/archive"

CACHE_DIR = Path(os.getenv("NEXUS_CACHE_DIR", "backend/data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
WEATHER_TTL_SECONDS = 3 * 3600  # 3 hours for forecasts
ARCHIVE_TTL_SECONDS = 24 * 3600  # 24 hours for historical

# Crop-specific temperature thresholds (°C)
CROP_TEMP_THRESHOLDS = {
    "Tomato": {"optimal_min": 18, "optimal_max": 30, "critical_max": 38, "critical_min": 5},
    "Onion": {"optimal_min": 15, "optimal_max": 28, "critical_max": 35, "critical_min": 2},
    "Potato": {"optimal_min": 10, "optimal_max": 25, "critical_max": 30, "critical_min": 0},
    "Grapes": {"optimal_min": 15, "optimal_max": 32, "critical_max": 40, "critical_min": 0},
    "Banana": {"optimal_min": 20, "optimal_max": 35, "critical_max": 42, "critical_min": 10},
    "Wheat": {"optimal_min": 12, "optimal_max": 25, "critical_max": 35, "critical_min": -5},
    "Rice": {"optimal_min": 20, "optimal_max": 35, "critical_max": 40, "critical_min": 15},
    "Maize": {"optimal_min": 18, "optimal_max": 32, "critical_max": 38, "critical_min": 8},
    "Soybean": {"optimal_min": 20, "optimal_max": 30, "critical_max": 38, "critical_min": 10},
    "Cotton": {"optimal_min": 20, "optimal_max": 35, "critical_max": 42, "critical_min": 12},
    "Chilli": {"optimal_min": 20, "optimal_max": 32, "critical_max": 38, "critical_min": 10},
    "Turmeric": {"optimal_min": 20, "optimal_max": 35, "critical_max": 40, "critical_min": 15},
    "default": {"optimal_min": 15, "optimal_max": 30, "critical_max": 38, "critical_min": 5},
}

# Crop-specific humidity sensitivity
CROP_HUMIDITY_THRESHOLDS = {
    "Tomato": {"high_risk_above": 85, "moderate_above": 70},
    "Onion": {"high_risk_above": 80, "moderate_above": 65},  # Curing needs low humidity
    "Potato": {"high_risk_above": 90, "moderate_above": 75},
    "Grapes": {"high_risk_above": 80, "moderate_above": 70},
    "Banana": {"high_risk_above": 85, "moderate_above": 75},
    "Wheat": {"high_risk_above": 75, "moderate_above": 60},  # Harvest time
    "Rice": {"high_risk_above": 85, "moderate_above": 75},
    "default": {"high_risk_above": 80, "moderate_above": 70},
}

# Perishability categories and spoilage rates
PERISHABILITY_RATES = {
    "high": {"base_spoilage_per_day": 0.08, "temp_factor": 1.5, "humidity_factor": 1.3},
    "medium": {"base_spoilage_per_day": 0.04, "temp_factor": 1.2, "humidity_factor": 1.1},
    "low": {"base_spoilage_per_day": 0.015, "temp_factor": 1.0, "humidity_factor": 1.0},
}


# --- Data Models ---

@dataclass
class WeatherObservation:
    """Single weather observation (current or historical)."""
    timestamp: str  # ISO format
    temperature_c: float
    humidity_pct: float
    precipitation_mm: float
    wind_speed_kmh: float
    wind_direction_deg: Optional[float] = None
    pressure_hpa: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    is_forecast: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "precipitation_mm": self.precipitation_mm,
            "wind_speed_kmh": self.wind_speed_kmh,
            "wind_direction_deg": self.wind_direction_deg,
            "pressure_hpa": self.pressure_hpa,
            "cloud_cover_pct": self.cloud_cover_pct,
            "is_forecast": self.is_forecast,
        }


@dataclass
class WeatherForecast:
    """Weather forecast for a location."""
    location: str
    lat: float
    lon: float
    generated_at: str
    hourly: List[WeatherObservation]
    daily: List[Dict[str, Any]]
    alerts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "lat": self.lat,
            "lon": self.lon,
            "generated_at": self.generated_at,
            "hourly": [h.to_dict() for h in self.hourly],
            "daily": self.daily,
            "alerts": self.alerts,
        }


@dataclass
class AgriculturalRiskAssessment:
    """Agricultural risk assessment based on weather."""
    location: str
    crop: str
    assessed_at: str
    forecast_period_days: int
    
    # Temperature risks
    heat_stress_days: int = 0
    cold_stress_days: int = 0
    max_temp_c: float = 0
    min_temp_c: float = 0
    
    # Precipitation risks
    heavy_rain_days: int = 0
    total_precipitation_mm: float = 0
    max_daily_precipitation_mm: float = 0
    
    # Humidity risks
    high_humidity_days: int = 0
    avg_humidity_pct: float = 0
    
    # Wind risks
    high_wind_days: int = 0
    max_wind_kmh: float = 0
    
    # Composite risks
    spoilage_acceleration_factor: float = 1.0
    transport_risk_level: str = "low"  # low, moderate, high, severe
    storage_risk_level: str = "low"
    harvest_risk_level: str = "low"
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "crop": self.crop,
            "assessed_at": self.assessed_at,
            "forecast_period_days": self.forecast_period_days,
            "temperature": {
                "heat_stress_days": self.heat_stress_days,
                "cold_stress_days": self.cold_stress_days,
                "max_temp_c": self.max_temp_c,
                "min_temp_c": self.min_temp_c,
            },
            "precipitation": {
                "heavy_rain_days": self.heavy_rain_days,
                "total_precipitation_mm": self.total_precipitation_mm,
                "max_daily_precipitation_mm": self.max_daily_precipitation_mm,
            },
            "humidity": {
                "high_humidity_days": self.high_humidity_days,
                "avg_humidity_pct": self.avg_humidity_pct,
            },
            "wind": {
                "high_wind_days": self.high_wind_days,
                "max_wind_kmh": self.max_wind_kmh,
            },
            "composite_risks": {
                "spoilage_acceleration_factor": round(self.spoilage_acceleration_factor, 2),
                "transport_risk_level": self.transport_risk_level,
                "storage_risk_level": self.storage_risk_level,
                "harvest_risk_level": self.harvest_risk_level,
            },
            "recommendations": self.recommendations,
            "warnings": self.warnings,
        }


# --- Cache Management ---

def _cache_key(prefix: str, *parts: str) -> str:
    combined = f"{prefix}:{':'.join(parts)}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _get_cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def load_cache(key: str, ttl_seconds: int = WEATHER_TTL_SECONDS) -> Optional[Any]:
    path = _get_cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            cached = json.load(f)
        cached_at = datetime.fromisoformat(cached["cached_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age > ttl_seconds:
            return None
        return cached["data"]
    except Exception:
        return None


def save_cache(key: str, data: Any) -> None:
    path = _get_cache_path(key)
    try:
        with open(path, "w") as f:
            json.dump({
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }, f)
    except Exception:
        pass


# --- HTTP Transport ---

class HttpTransport:
    def __init__(self, timeout: int = 30, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Any]:
        req_headers = {
            "User-Agent": "NEXUS-FPO/1.0 (Agricultural Intelligence Platform)",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)
        
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = Request(url, headers=req_headers)
                with urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return resp.status, json.loads(raw)
            except HTTPError as e:
                last_error = e
                if e.code in (401, 403, 404, 429):
                    return e.code, e.read().decode("utf-8", errors="replace")
            except (URLError, TimeoutError, OSError) as e:
                last_error = e
            
            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 5))
        
        raise RuntimeError(f"Open-Meteo request failed after {self.max_retries} attempts: {last_error}")


# --- Open-Meteo Client ---

class OpenMeteoClient:
    """Client for Open-Meteo weather API."""
    
    def __init__(self, transport: Optional[HttpTransport] = None):
        self.transport = transport or HttpTransport()
    
    def get_forecast(
        self,
        lat: float,
        lon: float,
        location_name: str = "",
        days: int = 7,
        hourly_vars: List[str] = None,
        daily_vars: List[str] = None,
    ) -> WeatherForecast:
        """Get weather forecast for coordinates."""
        
        cache_key = _cache_key("forecast", f"{lat:.4f},{lon:.4f}", str(days))
        cached = load_cache(cache_key)
        if cached:
            return WeatherForecast(**cached)
        
        hourly_vars = hourly_vars or [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "showers",
            "snowfall",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "surface_pressure",
            "cloud_cover",
            "visibility",
        ]
        
        daily_vars = daily_vars or [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "rain_sum",
            "showers_sum",
            "snowfall_sum",
            "precipitation_hours",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "uv_index_max",
            "weather_code",
        ]
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_vars),
            "daily": ",".join(daily_vars),
            "forecast_days": days,
            "timezone": "UTC",
            "models": "best_match",
        }
        
        url = f"{OPENMETEO_FORECAST}?{urlencode(params)}"
        
        try:
            status, response = self.transport.get(url)
            if status != 200 or not isinstance(response, dict):
                raise RuntimeError(f"Open-Meteo returned HTTP {status}")
            
            hourly_data = response.get("hourly", {})
            daily_data = response.get("daily", {})
            
            # Parse hourly
            hourly_obs = []
            times = hourly_data.get("time", [])
            for i, t in enumerate(times):
                obs = WeatherObservation(
                    timestamp=t,
                    temperature_c=hourly_data.get("temperature_2m", [None])[i] if i < len(hourly_data.get("temperature_2m", [])) else None,
                    humidity_pct=hourly_data.get("relative_humidity_2m", [None])[i] if i < len(hourly_data.get("relative_humidity_2m", [])) else None,
                    precipitation_mm=hourly_data.get("precipitation", [None])[i] if i < len(hourly_data.get("precipitation", [])) else None,
                    wind_speed_kmh=hourly_data.get("wind_speed_10m", [None])[i] if i < len(hourly_data.get("wind_speed_10m", [])) else None,
                    wind_direction_deg=hourly_data.get("wind_direction_10m", [None])[i] if i < len(hourly_data.get("wind_direction_10m", [])) else None,
                    pressure_hpa=hourly_data.get("surface_pressure", [None])[i] if i < len(hourly_data.get("surface_pressure", [])) else None,
                    cloud_cover_pct=hourly_data.get("cloud_cover", [None])[i] if i < len(hourly_data.get("cloud_cover", [])) else None,
                    is_forecast=True,
                )
                # Filter None values
                if obs.temperature_c is not None:
                    hourly_obs.append(obs)
            
            # Parse daily
            daily_summaries = []
            daily_times = daily_data.get("time", [])
            for i, day in enumerate(daily_times):
                daily_summaries.append({
                    "date": day,
                    "temp_max_c": daily_data.get("temperature_2m_max", [None])[i] if i < len(daily_data.get("temperature_2m_max", [])) else None,
                    "temp_min_c": daily_data.get("temperature_2m_min", [None])[i] if i < len(daily_data.get("temperature_2m_min", [])) else None,
                    "precipitation_mm": daily_data.get("precipitation_sum", [None])[i] if i < len(daily_data.get("precipitation_sum", [])) else None,
                    "rain_mm": daily_data.get("rain_sum", [None])[i] if i < len(daily_data.get("rain_sum", [])) else None,
                    "precipitation_hours": daily_data.get("precipitation_hours", [None])[i] if i < len(daily_data.get("precipitation_hours", [])) else None,
                    "precipitation_probability_pct": daily_data.get("precipitation_probability_max", [None])[i] if i < len(daily_data.get("precipitation_probability_max", [])) else None,
                    "wind_max_kmh": daily_data.get("wind_speed_10m_max", [None])[i] if i < len(daily_data.get("wind_speed_10m_max", [])) else None,
                    "wind_gust_max_kmh": daily_data.get("wind_gusts_10m_max", [None])[i] if i < len(daily_data.get("wind_gusts_10m_max", [])) else None,
                    "uv_index_max": daily_data.get("uv_index_max", [None])[i] if i < len(daily_data.get("uv_index_max", [])) else None,
                    "weather_code": daily_data.get("weather_code", [None])[i] if i < len(daily_data.get("weather_code", [])) else None,
                })
            
            forecast = WeatherForecast(
                location=location_name or f"{lat:.4f},{lon:.4f}",
                lat=lat,
                lon=lon,
                generated_at=datetime.now(timezone.utc).isoformat(),
                hourly=hourly_obs,
                daily=daily_summaries,
                alerts=self._generate_alerts(daily_summaries),
            )
            
            save_cache(cache_key, forecast.to_dict())
            return forecast
            
        except Exception as e:
            raise RuntimeError(f"Open-Meteo forecast failed: {e}")
    
    def _generate_alerts(self, daily: List[Dict[str, Any]]) -> List[str]:
        """Generate weather alerts from daily forecast."""
        alerts = []
        for day in daily:
            date = day.get("date", "")
            temp_max = day.get("temp_max_c")
            temp_min = day.get("temp_min_c")
            precip = day.get("precipitation_mm")
            precip_prob = day.get("precipitation_probability_pct")
            wind = day.get("wind_max_kmh")
            
            if temp_max is not None and temp_max > 40:
                alerts.append(f"{date}: Extreme heat warning (>40°C)")
            elif temp_max is not None and temp_max > 38:
                alerts.append(f"{date}: Heat stress risk ({temp_max}°C)")
            
            if temp_min is not None and temp_min < 2:
                alerts.append(f"{date}: Frost risk ({temp_min}°C)")
            
            if precip is not None and precip > 50:
                alerts.append(f"{date}: Heavy rainfall expected ({precip}mm)")
            elif precip_prob is not None and precip_prob > 80:
                alerts.append(f"{date}: High precipitation probability ({precip_prob}%)")
            
            if wind is not None and wind > 60:
                alerts.append(f"{date}: High winds ({wind} km/h)")
        
        return alerts


# --- Agricultural Risk Engine ---

class AgriculturalRiskEngine:
    """Evaluates agricultural risks from weather forecasts."""
    
    def __init__(self):
        self.temp_thresholds = CROP_TEMP_THRESHOLDS
        self.humidity_thresholds = CROP_HUMIDITY_THRESHOLDS
        self.perishability_rates = PERISHABILITY_RATES
    
    def assess(
        self,
        forecast: WeatherForecast,
        crop: str,
        perishability: str = "medium",
        transport_duration_hours: Optional[float] = None,
        storage_duration_days: Optional[float] = None,
    ) -> AgriculturalRiskAssessment:
        """Assess agricultural risks for a crop at a location."""
        
        thresholds = self.temp_thresholds.get(crop, self.temp_thresholds["default"])
        humidity_thresholds = self.humidity_thresholds.get(crop, self.humidity_thresholds["default"])
        perish_rate = self.perishability_rates.get(perishability, self.perishability_rates["medium"])
        
        assessment = AgriculturalRiskAssessment(
            location=forecast.location,
            crop=crop,
            assessed_at=datetime.now(timezone.utc).isoformat(),
            forecast_period_days=len(forecast.daily),
        )
        
        # Analyze daily forecasts
        temps_max = []
        temps_min = []
        precip_daily = []
        humidity_daily = []
        wind_max = []
        
        for day in forecast.daily:
            # Temperature
            if day.get("temp_max_c") is not None:
                temps_max.append(day["temp_max_c"])
                if day["temp_max_c"] >= thresholds["critical_max"]:
                    assessment.heat_stress_days += 1
                elif day["temp_max_c"] > thresholds["optimal_max"]:
                    assessment.warnings.append(f"{day['date']}: Temperature {day['temp_max_c']}°C exceeds optimal for {crop}")
            
            if day.get("temp_min_c") is not None:
                temps_min.append(day["temp_min_c"])
                if day["temp_min_c"] < thresholds["critical_min"]:
                    assessment.cold_stress_days += 1
                elif day["temp_min_c"] < thresholds["optimal_min"]:
                    assessment.warnings.append(f"{day['date']}: Temperature {day['temp_min_c']}°C below optimal for {crop}")
            
            # Precipitation
            if day.get("precipitation_mm") is not None:
                p = day["precipitation_mm"]
                precip_daily.append(p)
                if p >= 50:
                    assessment.heavy_rain_days += 1
                    assessment.warnings.append(f"{day['date']}: Heavy rain {p}mm - transport/storage risk")
                elif p > 20:
                    assessment.warnings.append(f"{day['date']}: Moderate rain {p}mm - monitor conditions")
            
            # Humidity (from hourly data near midday)
            midday_humidity = self._get_midday_humidity(forecast, day.get("date", ""))
            if midday_humidity is not None:
                humidity_daily.append(midday_humidity)
                if midday_humidity > humidity_thresholds["high_risk_above"]:
                    assessment.high_humidity_days += 1
                    assessment.warnings.append(f"{day['date']}: High humidity {midday_humidity}% - spoilage risk")
                elif midday_humidity > humidity_thresholds["moderate_above"]:
                    assessment.warnings.append(f"{day['date']}: Elevated humidity {midday_humidity}%")
            
            # Wind
            if day.get("wind_max_kmh") is not None:
                w = day["wind_max_kmh"]
                wind_max.append(w)
                if w > 60:
                    assessment.high_wind_days += 1
                    assessment.warnings.append(f"{day['date']}: High winds {w} km/h - transport risk")
        
        # Set aggregates
        if temps_max:
            assessment.max_temp_c = max(temps_max)
        if temps_min:
            assessment.min_temp_c = min(temps_min)
        
        assessment.total_precipitation_mm = sum(precip_daily)
        if precip_daily:
            assessment.max_daily_precipitation_mm = max(precip_daily)
        
        if humidity_daily:
            assessment.avg_humidity_pct = sum(humidity_daily) / len(humidity_daily)
        
        if wind_max:
            assessment.max_wind_kmh = max(wind_max)
        
        # Calculate spoilage acceleration
        assessment.spoilage_acceleration_factor = self._calculate_spoilage_factor(
            assessment, perish_rate, thresholds, crop
        )
        
        # Determine risk levels
        assessment.transport_risk_level = self._assess_transport_risk(assessment, transport_duration_hours)
        assessment.storage_risk_level = self._assess_storage_risk(assessment, storage_duration_days)
        assessment.harvest_risk_level = self._assess_harvest_risk(assessment)
        
        # Generate recommendations
        assessment.recommendations = self._generate_recommendations(assessment, crop)
        
        return assessment
    
    def _get_midday_humidity(self, forecast: WeatherForecast, date: str) -> Optional[float]:
        """Get average humidity around midday for a given date."""
        if not date:
            return None
        
        humidities = []
        for obs in forecast.hourly:
            if obs.timestamp.startswith(date) and 10 <= int(obs.timestamp[11:13]) <= 14:
                if obs.humidity_pct is not None:
                    humidities.append(obs.humidity_pct)
        
        return sum(humidities) / len(humidities) if humidities else None
    
    def _calculate_spoilage_factor(
        self,
        assessment: AgriculturalRiskAssessment,
        perish_rate: Dict[str, float],
        thresholds: Dict[str, int],
        crop: str,
    ) -> float:
        """Calculate spoilage acceleration factor based on weather."""
        factor = 1.0
        
        # Temperature effect
        if assessment.max_temp_c > thresholds["optimal_max"]:
            temp_excess = assessment.max_temp_c - thresholds["optimal_max"]
            factor *= 1 + (temp_excess * perish_rate["temp_factor"] / 100)
        
        if assessment.min_temp_c < thresholds["optimal_min"]:
            temp_deficit = thresholds["optimal_min"] - assessment.min_temp_c
            factor *= 1 + (temp_deficit * perish_rate["temp_factor"] / 200)
        
        # Humidity effect
        hum_thresh = self.humidity_thresholds.get(crop, self.humidity_thresholds["default"])
        if assessment.avg_humidity_pct > hum_thresh.get("moderate_above", 70):
            hum_excess = assessment.avg_humidity_pct - 70
            factor *= 1 + (hum_excess * perish_rate["humidity_factor"] / 200)
        
        # Rain effect
        if assessment.heavy_rain_days > 0:
            factor *= 1 + (assessment.heavy_rain_days * 0.15)
        
        return min(factor, 5.0)  # Cap at 5x
    
    def _assess_transport_risk(
        self,
        assessment: AgriculturalRiskAssessment,
        duration_hours: Optional[float],
    ) -> str:
        """Assess transport risk level."""
        risk_score = 0
        
        if assessment.heavy_rain_days > 0:
            risk_score += 3
        elif assessment.total_precipitation_mm > 20:
            risk_score += 1
        
        if assessment.high_wind_days > 0:
            risk_score += 2
        elif assessment.max_wind_kmh > 40:
            risk_score += 1
        
        if assessment.heat_stress_days > 0:
            risk_score += 1
        
        if assessment.high_humidity_days > 2:
            risk_score += 1
        
        if duration_hours and duration_hours > 12:
            risk_score += 1
        elif duration_hours and duration_hours > 6:
            risk_score += 0.5
        
        if risk_score >= 4:
            return "severe"
        elif risk_score >= 3:
            return "high"
        elif risk_score >= 2:
            return "moderate"
        else:
            return "low"
    
    def _assess_storage_risk(
        self,
        assessment: AgriculturalRiskAssessment,
        duration_days: Optional[float],
    ) -> str:
        """Assess storage risk level."""
        risk_score = 0
        
        if assessment.heat_stress_days > 0:
            risk_score += 2
        elif assessment.max_temp_c > 30:
            risk_score += 1
        
        if assessment.high_humidity_days > 1:
            risk_score += 3
        elif assessment.high_humidity_days > 0:
            risk_score += 2
        
        if assessment.heavy_rain_days > 0:
            risk_score += 2
        
        if duration_days and duration_days > 7:
            risk_score += 1
        elif duration_days and duration_days > 3:
            risk_score += 0.5
        
        if risk_score >= 4:
            return "severe"
        elif risk_score >= 3:
            return "high"
        elif risk_score >= 2:
            return "moderate"
        else:
            return "low"
    
    def _assess_harvest_risk(self, assessment: AgriculturalRiskAssessment) -> str:
        """Assess harvest timing risk."""
        risk_score = 0
        
        if assessment.heavy_rain_days > 0:
            risk_score += 3  # Rain during harvest is critical
        elif assessment.total_precipitation_mm > 10:
            risk_score += 1
        
        if assessment.high_wind_days > 0:
            risk_score += 1  # Wind can cause shattering
        
        if assessment.max_temp_c > 35:
            risk_score += 1  # Heat affects quality
        
        if risk_score >= 3:
            return "severe"
        elif risk_score >= 2:
            return "high"
        elif risk_score >= 1:
            return "moderate"
        else:
            return "low"
    
    def _generate_recommendations(
        self,
        assessment: AgriculturalRiskAssessment,
        crop: str,
    ) -> List[str]:
        """Generate actionable recommendations."""
        recs = []
        
        if assessment.transport_risk_level in ("high", "severe"):
            recs.append("Delay transport if possible; use covered/refrigerated vehicles")
            recs.append("Monitor weather hourly during transport window")
        
        if assessment.storage_risk_level in ("high", "severe"):
            recs.append("Ensure cold storage is operational; reduce storage duration")
            recs.append("Monitor temperature/humidity in storage facilities continuously")
        
        if assessment.harvest_risk_level in ("high", "severe"):
            recs.append("Harvest before predicted heavy rainfall if crop is mature")
            recs.append("Have tarps/covers ready for field protection")
        
        if assessment.heat_stress_days > 0:
            recs.append(f"Heat stress expected for {crop} - irrigate if possible, harvest early morning")
        
        if assessment.heavy_rain_days > 0:
            recs.append("Ensure drainage in fields and storage areas")
        
        if assessment.high_humidity_days > 1:
            recs.append("Ventilate storage; consider dehumidification for high-value crops")
        
        if assessment.spoilage_acceleration_factor > 2.0:
            recs.append(f"Spoilage rate may accelerate {assessment.spoilage_acceleration_factor:.1f}x - prioritize sales")
        
        if not recs:
            recs.append("Conditions favorable for normal operations")
        
        return recs


# --- High-level Service ---

class WeatherService:
    """Unified weather service for FPO operations."""
    
    def __init__(self, transport: Optional[HttpTransport] = None):
        self.transport = transport or HttpTransport()
        self.client = OpenMeteoClient(self.transport)
        self.risk_engine = AgriculturalRiskEngine()
    
    def get_forecast(
        self,
        lat: float,
        lon: float,
        location_name: str = "",
        days: int = 7,
    ) -> WeatherForecast:
        """Get weather forecast for coordinates."""
        return self.client.get_forecast(lat, lon, location_name, days)
    
    def assess_risks(
        self,
        lat: float,
        lon: float,
        location_name: str,
        crop: str,
        perishability: str = "medium",
        transport_duration_hours: Optional[float] = None,
        storage_duration_days: Optional[float] = None,
        days: int = 7,
    ) -> AgriculturalRiskAssessment:
        """Get forecast and assess agricultural risks."""
        forecast = self.get_forecast(lat, lon, location_name, days)
        return self.risk_engine.assess(
            forecast, crop, perishability, transport_duration_hours, storage_duration_days
        )
    
    def assess_route_risks(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        crop: str,
        perishability: str = "medium",
        transport_duration_hours: float = 6,
    ) -> Dict[str, AgriculturalRiskAssessment]:
        """Assess risks along a transport route (origin, destination, and midpoint)."""
        
        # Assess at origin, destination, and midpoint
        mid_lat = (origin[0] + destination[0]) / 2
        mid_lon = (origin[1] + destination[1]) / 2
        
        results = {}
        for name, coords in [
            ("origin", origin),
            ("midpoint", (mid_lat, mid_lon)),
            ("destination", destination),
        ]:
            forecast = self.get_forecast(coords[0], coords[1], name, days=3)
            assessment = self.risk_engine.assess(
                forecast, crop, perishability, transport_duration_hours, None
            )
            results[name] = assessment
        
        return results


# --- Factory ---

def create_weather_service(timeout: int = 30) -> WeatherService:
    """Create a configured WeatherService."""
    transport = HttpTransport(timeout=timeout)
    return WeatherService(transport)


def get_weather_forecast(
    lat: float,
    lon: float,
    location_name: str = "",
    days: int = 7,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Convenience function to get forecast."""
    service = create_weather_service(timeout)
    forecast = service.get_forecast(lat, lon, location_name, days)
    return forecast.to_dict()


def assess_agricultural_risk(
    lat: float,
    lon: float,
    location_name: str,
    crop: str,
    perishability: str = "medium",
    transport_duration_hours: Optional[float] = None,
    storage_duration_days: Optional[float] = None,
    days: int = 7,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Convenience function for agricultural risk assessment."""
    service = create_weather_service(timeout)
    assessment = service.assess_risks(
        lat, lon, location_name, crop, perishability,
        transport_duration_hours, storage_duration_days, days
    )
    return assessment.to_dict()


def assess_transport_weather_risk(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    crop: str,
    transport_duration_hours: float = 6,
    perishability: str = "medium",
    timeout: int = 30,
) -> Dict[str, Any]:
    """Assess weather risk for a transport route."""
    service = create_weather_service(timeout)
    results = service.assess_route_risks(
        (origin_lat, origin_lon),
        (dest_lat, dest_lon),
        crop, perishability, transport_duration_hours
    )
    return {k: v.to_dict() for k, v in results.items()}