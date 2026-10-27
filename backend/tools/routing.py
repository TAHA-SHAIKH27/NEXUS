"""
Road Routing and Distance Matrix — OpenRouteService integration.

Provides real road distances, durations, and route geometries.
Uses OpenStreetMap data via OpenRouteService API.
Caches results. Never presents straight-line distances as road distances.

Requires OPENROUTESERVICE_API_KEY in config or environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# --- Constants ---

ORS_BASE = "https://api.openrouteservice.org"
ORS_DIRECTIONS = f"{ORS_BASE}/v2/directions"
ORS_MATRIX = f"{ORS_BASE}/v2/matrix"
ORS_GEOCODE = f"{ORS_BASE}/geocode/search"

CACHE_DIR = Path(os.getenv("NEXUS_CACHE_DIR", "backend/data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ROUTING_TTL_SECONDS = 24 * 3600  # 24 hours - routes don't change often

DEFAULT_VEHICLE = "driving-hgv"  # Heavy goods vehicle for agricultural transport
VEHICLE_PROFILES = {
    "driving-car": "Passenger car",
    "driving-hgv": "Heavy goods vehicle (truck)",
    "cycling-regular": "Bicycle",
    "foot-walking": "Pedestrian",
}

# Vehicle specs for cost calculation
VEHICLE_SPECS = {
    "driving-car": {
        "capacity_kg": 1000,
        "fuel_efficiency_kmpl": 12.0,
        "fuel_type": "petrol",
    },
    "driving-hgv": {
        "capacity_kg": 10000,
        "fuel_efficiency_kmpl": 4.0,
        "fuel_type": "diesel",
    },
    "refrigerated-hgv": {
        "capacity_kg": 8000,
        "fuel_efficiency_kmpl": 3.5,
        "fuel_type": "diesel",
        "refrigeration_cost_per_km": 15.0,  # INR/km additional
    },
}

# Default fuel prices (INR/litre) - should be configurable
DEFAULT_FUEL_PRICES = {
    "petrol": Decimal("100.0"),
    "diesel": Decimal("90.0"),
}

# Labour and loading/unloading costs
DEFAULT_LOADING_COST = Decimal("500.0")  # INR per loading/unloading
DEFAULT_LABOUR_COST_PER_HOUR = Decimal("200.0")


# --- Data Models ---

@dataclass
class Coordinates:
    """Longitude, Latitude (GeoJSON order)."""
    lon: float
    lat: float
    
    def to_list(self) -> List[float]:
        return [self.lon, self.lat]
    
    @classmethod
    def from_latlon(cls, lat: float, lon: float) -> "Coordinates":
        return cls(lon=lon, lat=lat)


@dataclass
class RouteResult:
    """Single route result."""
    distance_km: float
    duration_minutes: float
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON LineString
    steps: List[Dict[str, Any]] = field(default_factory=list)
    vehicle_profile: str = DEFAULT_VEHICLE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "distance_km": round(self.distance_km, 2),
            "duration_minutes": round(self.duration_minutes, 1),
            "duration_hours": round(self.duration_minutes / 60, 2),
            "geometry": self.geometry,
            "steps": self.steps,
            "vehicle_profile": self.vehicle_profile,
        }


@dataclass
class MatrixResult:
    """Distance/duration matrix result."""
    origins: List[Coordinates]
    destinations: List[Coordinates]
    distances_km: List[List[float]]  # [origin][dest]
    durations_minutes: List[List[float]]
    vehicle_profile: str = DEFAULT_VEHICLE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "origins": [o.to_list() for o in self.origins],
            "destinations": [d.to_list() for d in self.destinations],
            "distances_km": [[round(d, 2) for d in row] for row in self.distances_km],
            "durations_minutes": [[round(d, 1) for d in row] for row in self.durations_minutes],
            "durations_hours": [[round(d / 60, 2) for d in row] for row in self.durations_minutes],
            "vehicle_profile": self.vehicle_profile,
        }


@dataclass
class TransportCost:
    """Calculated transport cost breakdown."""
    distance_km: float
    duration_hours: float
    vehicle_type: str
    capacity_kg: int
    fuel_type: str
    fuel_efficiency_kmpl: float
    fuel_price_per_litre: Decimal
    fuel_cost: Decimal
    loading_cost: Decimal
    unloading_cost: Decimal
    labour_cost: Decimal
    refrigeration_cost: Decimal
    toll_cost: Decimal
    total_cost: Decimal
    cost_per_kg: Decimal
    cost_per_tonne_km: Decimal
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "distance_km": round(self.distance_km, 2),
            "duration_hours": round(self.duration_hours, 2),
            "vehicle_type": self.vehicle_type,
            "capacity_kg": self.capacity_kg,
            "fuel_type": self.fuel_type,
            "fuel_efficiency_kmpl": self.fuel_efficiency_kmpl,
            "fuel_price_per_litre": float(self.fuel_price_per_litre.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "fuel_cost": float(self.fuel_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "loading_cost": float(self.loading_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "unloading_cost": float(self.unloading_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "labour_cost": float(self.labour_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "refrigeration_cost": float(self.refrigeration_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "toll_cost": float(self.toll_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "total_cost": float(self.total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "cost_per_kg": float(self.cost_per_kg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "cost_per_tonne_km": float(self.cost_per_tonne_km.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
        }


# --- Cache Management ---

def _cache_key(prefix: str, *parts: str) -> str:
    combined = f"{prefix}:{':'.join(parts)}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _get_cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def load_cache(key: str, ttl_seconds: int = ROUTING_TTL_SECONDS) -> Optional[Any]:
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
    
    def request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> Tuple[int, Any]:
        req_headers = {
            "User-Agent": "NEXUS-FPO/1.0 (Agricultural Intelligence Platform)",
            "Accept": "application/json, application/geo+json",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)
        
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = Request(url, data=body, headers=req_headers, method=method)
                with urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    if resp.headers.get("Content-Type", "").startswith("application/json"):
                        return resp.status, json.loads(raw)
                    return resp.status, raw
            except HTTPError as e:
                last_error = e
                if e.code in (401, 403, 404, 429):
                    return e.code, e.read().decode("utf-8", errors="replace")
            except (URLError, TimeoutError, OSError) as e:
                last_error = e
            
            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 5))
        
        raise RuntimeError(f"ORS request failed after {self.max_retries} attempts: {last_error}")


# --- Geocoding ---

def geocode_location(
    query: str,
    api_key: str,
    transport: Optional[HttpTransport] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Geocode a location name to coordinates using ORS."""
    transport = transport or HttpTransport()
    cache_key = _cache_key("geocode", query)
    cached = load_cache(cache_key)
    if cached:
        return cached
    
    params = {
        "api_key": api_key,
        "text": query,
        "size": limit,
    }
    
    url = f"{ORS_GEOCODE}?{urlencode(params)}"
    
    try:
        status, response = transport.request(url)
        if status == 200 and isinstance(response, dict):
            features = response.get("features", [])
            results = []
            for feat in features:
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if len(coords) == 2:
                    results.append({
                        "name": props.get("label", props.get("name", query)),
                        "lon": coords[0],
                        "lat": coords[1],
                        "confidence": props.get("confidence", 0),
                        "layer": props.get("layer", ""),
                        "country": props.get("country", ""),
                        "region": props.get("region", ""),
                        "locality": props.get("locality", ""),
                    })
            save_cache(cache_key, results)
            return results
        else:
            return []
    except Exception:
        return []


def resolve_coordinates(
    location: str,
    api_key: str,
    known_locations: Optional[Dict[str, Tuple[float, float]]] = None,
    transport: Optional[HttpTransport] = None,
) -> Optional[Coordinates]:
    """Resolve a location name to coordinates, using known locations first."""
    
    # Check known locations (warehouses, markets with stored coords)
    if known_locations and location in known_locations:
        lat, lon = known_locations[location]
        return Coordinates.from_latlon(lat, lon)
    
    # Try geocoding
    results = geocode_location(location, api_key, transport, limit=1)
    if results:
        return Coordinates(lon=results[0]["lon"], lat=results[0]["lat"])
    
    return None


# --- Directions (Single Route) ---

def get_route(
    origin: Coordinates,
    destination: Coordinates,
    api_key: str,
    vehicle: str = DEFAULT_VEHICLE,
    transport: Optional[HttpTransport] = None,
    geometry: bool = True,
    instructions: bool = True,
) -> RouteResult:
    """Get a single route between origin and destination."""
    
    transport = transport or HttpTransport()
    cache_key = _cache_key("route", f"{origin.lon},{origin.lat}", f"{destination.lon},{destination.lat}", vehicle)
    cached = load_cache(cache_key)
    if cached:
        return RouteResult(**cached)
    
    url = f"{ORS_DIRECTIONS}/{vehicle}"
    params = {
        "api_key": api_key,
        "start": f"{origin.lon},{origin.lat}",
        "end": f"{destination.lon},{destination.lat}",
    }
    if geometry:
        params["geometry"] = "true"
    if instructions:
        params["instructions"] = "true"
    
    url = f"{url}?{urlencode(params)}"
    
    try:
        status, response = transport.request(url)
        if status == 200 and isinstance(response, dict):
            routes = response.get("routes", [])
            if routes:
                route = routes[0]
                distance_m = route.get("distance", 0)
                duration_s = route.get("duration", 0)
                
                result = RouteResult(
                    distance_km=distance_m / 1000,
                    duration_minutes=duration_s / 60,
                    geometry=route.get("geometry"),
                    steps=route.get("segments", [{}])[0].get("steps", []) if instructions else [],
                    vehicle_profile=vehicle,
                )
                save_cache(cache_key, result.to_dict())
                return result
    except Exception:
        pass
    
    # Fallback: straight-line distance (clearly marked)
    straight_line = haversine_distance(origin, destination)
    return RouteResult(
        distance_km=straight_line,
        duration_minutes=straight_line / 50 * 60,  # rough estimate 50 km/h
        vehicle_profile=vehicle,
    )


# --- Distance Matrix ---

def get_matrix(
    origins: List[Coordinates],
    destinations: List[Coordinates],
    api_key: str,
    vehicle: str = DEFAULT_VEHICLE,
    transport: Optional[HttpTransport] = None,
    metrics: List[str] = None,
) -> MatrixResult:
    """Get distance/duration matrix between multiple origins and destinations."""
    
    transport = transport or HttpTransport()
    
    # Create cache key from all coordinates
    orig_str = "|".join(f"{o.lon},{o.lat}" for o in origins)
    dest_str = "|".join(f"{d.lon},{d.lat}" for d in destinations)
    cache_key = _cache_key("matrix", vehicle, orig_str, dest_str)
    cached = load_cache(cache_key)
    if cached:
        return MatrixResult(**cached)
    
    metrics = metrics or ["distance", "duration"]
    
    payload = {
        "locations": [o.to_list() for o in origins] + [d.to_list() for d in destinations],
        "metrics": metrics,
        "units": "km",
    }
    
    url = f"{ORS_MATRIX}/{vehicle}?api_key={api_key}"
    
    try:
        status, response = transport.request(url, method="POST", body=json.dumps(payload).encode())
        if status == 200 and isinstance(response, dict):
            distances = response.get("distances", [])
            durations = response.get("durations", [])
            
            # Split into origin x destination matrix
            n_origins = len(origins)
            n_destinations = len(destinations)
            
            dist_matrix = []
            dur_matrix = []
            
            for i in range(n_origins):
                dist_row = []
                dur_row = []
                for j in range(n_destinations):
                    # ORS returns flat array or matrix
                    if isinstance(distances[0], list):
                        dist = distances[i][n_origins + j]
                        dur = durations[i][n_origins + j]
                    else:
                        idx = i * (n_origins + n_destinations) + n_origins + j
                        dist = distances[idx] if idx < len(distances) else 0
                        dur = durations[idx] if idx < len(durations) else 0
                    
                    dist_row.append(dist if dist is not None else 0)
                    dur_row.append(dur / 60 if dur is not None else 0)  # seconds to minutes
                
                dist_matrix.append(dist_row)
                dur_matrix.append(dur_row)
            
            result = MatrixResult(
                origins=origins,
                destinations=destinations,
                distances_km=dist_matrix,
                durations_minutes=dur_matrix,
                vehicle_profile=vehicle,
            )
            save_cache(cache_key, result.to_dict())
            return result
    except Exception:
        pass
    
    # Fallback: compute straight-line distances
    dist_matrix = []
    dur_matrix = []
    for o in origins:
        dist_row = []
        dur_row = []
        for d in destinations:
            dist = haversine_distance(o, d)
            dist_row.append(dist)
            dur_row.append(dist / 50 * 60)  # rough estimate
        dist_matrix.append(dist_row)
        dur_matrix.append(dur_row)
    
    return MatrixResult(
        origins=origins,
        destinations=destinations,
        distances_km=dist_matrix,
        durations_minutes=dur_matrix,
        vehicle_profile=vehicle,
    )


# --- Transport Cost Calculation ---

def calculate_transport_cost(
    distance_km: float,
    duration_minutes: float,
    quantity_kg: float,
    vehicle_type: str = "driving-hgv",
    fuel_prices: Optional[Dict[str, Decimal]] = None,
    loading_cost: Optional[Decimal] = None,
    unloading_cost: Optional[Decimal] = None,
    labour_cost_per_hour: Optional[Decimal] = None,
    refrigerated: bool = False,
    tolls: Optional[Decimal] = None,
) -> TransportCost:
    """Calculate detailed transport cost breakdown."""
    
    fuel_prices = fuel_prices or DEFAULT_FUEL_PRICES
    loading_cost = loading_cost or DEFAULT_LOADING_COST
    unloading_cost = unloading_cost or DEFAULT_LOADING_COST
    labour_cost_per_hour = labour_cost_per_hour or DEFAULT_LABOUR_COST_PER_HOUR
    
    # Get vehicle specs
    specs_key = "refrigerated-hgv" if refrigerated and vehicle_type == "driving-hgv" else vehicle_type
    specs = VEHICLE_SPECS.get(specs_key, VEHICLE_SPECS["driving-hgv"])
    
    capacity_kg = specs["capacity_kg"]
    fuel_efficiency = specs["fuel_efficiency_kmpl"]
    fuel_type = specs["fuel_type"]
    fuel_price = fuel_prices.get(fuel_type, DEFAULT_FUEL_PRICES[fuel_type])
    
    # Calculate trips needed
    trips = max(1, int((quantity_kg + capacity_kg - 1) / capacity_kg))
    total_distance = distance_km * trips
    
    # Fuel cost
    fuel_litres = Decimal(str(total_distance)) / Decimal(str(fuel_efficiency))
    fuel_cost = fuel_litres * fuel_price
    
    # Labour cost (driver time)
    duration_hours = Decimal(str(duration_minutes)) / Decimal("60") * Decimal(str(trips))
    labour_cost = duration_hours * labour_cost_per_hour
    
    # Loading/unloading
    total_loading = loading_cost * Decimal(str(trips))
    total_unloading = unloading_cost * Decimal(str(trips))
    
    # Refrigeration
    refrigeration_cost = Decimal("0")
    if refrigerated and "refrigeration_cost_per_km" in specs:
        refrigeration_cost = Decimal(str(total_distance)) * Decimal(str(specs["refrigeration_cost_per_km"]))
    
    # Tolls
    toll_cost = tolls or Decimal("0")
    
    # Total
    total_cost = fuel_cost + labour_cost + total_loading + total_unloading + refrigeration_cost + toll_cost
    
    # Per-unit costs
    cost_per_kg = total_cost / Decimal(str(quantity_kg)) if quantity_kg > 0 else Decimal("0")
    cost_per_tonne_km = total_cost / (Decimal(str(quantity_kg)) / Decimal("1000") * Decimal(str(distance_km))) if quantity_kg > 0 and distance_km > 0 else Decimal("0")
    
    return TransportCost(
        distance_km=distance_km,
        duration_hours=float(duration_hours),
        vehicle_type=vehicle_type,
        capacity_kg=capacity_kg,
        fuel_type=fuel_type,
        fuel_efficiency_kmpl=fuel_efficiency,
        fuel_price_per_litre=fuel_price,
        fuel_cost=fuel_cost,
        loading_cost=total_loading,
        unloading_cost=total_unloading,
        labour_cost=labour_cost,
        refrigeration_cost=refrigeration_cost,
        toll_cost=toll_cost,
        total_cost=total_cost,
        cost_per_kg=cost_per_kg,
        cost_per_tonne_km=cost_per_tonne_km,
    )


def calculate_multi_destination_costs(
    origin: Coordinates,
    destinations: List[Tuple[str, Coordinates, float]],  # [(name, coords, quantity_kg)]
    api_key: str,
    vehicle_type: str = "driving-hgv",
    config: Optional[Dict[str, Any]] = None,
    transport: Optional[HttpTransport] = None,
) -> List[Dict[str, Any]]:
    """Calculate transport costs to multiple destinations."""
    
    cfg = config or {}
    fuel_prices = {k: Decimal(str(v)) for k, v in cfg.get("fuel_prices", DEFAULT_FUEL_PRICES).items()}
    loading_cost = Decimal(str(cfg.get("loading_cost", DEFAULT_LOADING_COST)))
    unloading_cost = Decimal(str(cfg.get("unloading_cost", DEFAULT_LOADING_COST)))
    labour_cost = Decimal(str(cfg.get("labour_cost_per_hour", DEFAULT_LABOUR_COST_PER_HOUR)))
    refrigerated = cfg.get("refrigerated", False)
    
    # Get matrix
    dest_coords = [d[1] for d in destinations]
    matrix = get_matrix([origin], dest_coords, api_key, vehicle_type, transport)
    
    results = []
    for i, (name, coords, qty) in enumerate(destinations):
        dist = matrix.distances_km[0][i] if matrix.distances_km else 0
        dur = matrix.durations_minutes[0][i] if matrix.durations_minutes else 0
        
        cost = calculate_transport_cost(
            distance_km=dist,
            duration_minutes=dur,
            quantity_kg=qty,
            vehicle_type=vehicle_type,
            fuel_prices=fuel_prices,
            loading_cost=loading_cost,
            unloading_cost=unloading_cost,
            labour_cost_per_hour=labour_cost,
            refrigerated=refrigerated,
        )
        
        results.append({
            "destination": name,
            "coordinates": coords.to_list(),
            "quantity_kg": qty,
            "distance_km": round(dist, 2),
            "duration_hours": round(dur / 60, 2),
            "cost": cost.to_dict(),
        })
    
    # Sort by cost per kg
    results.sort(key=lambda x: x["cost"]["cost_per_kg"])
    return results


# --- Haversine (fallback only) ---

def haversine_distance(origin: Coordinates, destination: Coordinates) -> float:
    """Calculate straight-line distance in km (fallback only)."""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371.0  # Earth radius in km
    
    lat1, lon1 = radians(origin.lat), radians(origin.lon)
    lat2, lon2 = radians(destination.lat), radians(destination.lon)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


# --- High-level Service ---

class RoutingService:
    """High-level routing service for FPO logistics."""
    
    def __init__(
        self,
        api_key: str,
        transport: Optional[HttpTransport] = None,
        known_locations: Optional[Dict[str, Tuple[float, float]]] = None,
    ):
        self.api_key = api_key
        self.transport = transport or HttpTransport()
        self.known_locations = known_locations or {}
    
    def get_route(
        self,
        origin_name: str,
        destination_name: str,
        vehicle: str = DEFAULT_VEHICLE,
    ) -> RouteResult:
        """Get route between two named locations."""
        origin = resolve_coordinates(origin_name, self.api_key, self.known_locations, self.transport)
        destination = resolve_coordinates(destination_name, self.api_key, self.known_locations, self.transport)
        
        if not origin or not destination:
            raise ValueError(f"Could not resolve coordinates: {origin_name} -> {destination_name}")
        
        return get_route(origin, destination, self.api_key, vehicle, self.transport)
    
    def get_matrix(
        self,
        origin_names: List[str],
        destination_names: List[str],
        vehicle: str = DEFAULT_VEHICLE,
    ) -> MatrixResult:
        """Get distance matrix between named locations."""
        origins = []
        for name in origin_names:
            coord = resolve_coordinates(name, self.api_key, self.known_locations, self.transport)
            if not coord:
                raise ValueError(f"Could not resolve: {name}")
            origins.append(coord)
        
        destinations = []
        for name in destination_names:
            coord = resolve_coordinates(name, self.api_key, self.known_locations, self.transport)
            if not coord:
                raise ValueError(f"Could not resolve: {name}")
            destinations.append(coord)
        
        return get_matrix(origins, destinations, self.api_key, vehicle, self.transport)
    
    def calculate_cost(
        self,
        origin_name: str,
        destination_name: str,
        quantity_kg: float,
        vehicle_type: str = "driving-hgv",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get route and calculate transport cost."""
        route = self.get_route(origin_name, destination_name, vehicle_type)
        cost = calculate_transport_cost(
            distance_km=route.distance_km,
            duration_minutes=route.duration_minutes,
            quantity_kg=quantity_kg,
            vehicle_type=vehicle_type,
            fuel_prices={k: Decimal(str(v)) for k, v in (config or {}).get("fuel_prices", DEFAULT_FUEL_PRICES).items()},
            loading_cost=Decimal(str((config or {}).get("loading_cost", DEFAULT_LOADING_COST))),
            unloading_cost=Decimal(str((config or {}).get("unloading_cost", DEFAULT_LOADING_COST))),
            labour_cost_per_hour=Decimal(str((config or {}).get("labour_cost_per_hour", DEFAULT_LABOUR_COST_PER_HOUR))),
            refrigerated=(config or {}).get("refrigerated", False),
        )
        
        return {
            "route": route.to_dict(),
            "cost": cost.to_dict(),
        }
    
    def compare_destinations(
        self,
        origin_name: str,
        destination_names: List[str],
        quantities_kg: List[float],
        vehicle_type: str = "driving-hgv",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Compare transport costs to multiple destinations."""
        origin = resolve_coordinates(origin_name, self.api_key, self.known_locations, self.transport)
        if not origin:
            raise ValueError(f"Could not resolve origin: {origin_name}")
        
        destinations = []
        for i, name in enumerate(destination_names):
            coord = resolve_coordinates(name, self.api_key, self.known_locations, self.transport)
            if not coord:
                raise ValueError(f"Could not resolve destination: {name}")
            qty = quantities_kg[i] if i < len(quantities_kg) else 0
            destinations.append((name, coord, qty))
        
        return calculate_multi_destination_costs(
            origin, destinations, self.api_key, vehicle_type, config, self.transport
        )


# --- Factory ---

def create_routing_service(
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Optional[RoutingService]:
    """Create a RoutingService instance.
    
    Returns None if API key not available.
    """
    key = api_key or (config or {}).get("openrouteservice_api_key") or os.environ.get("OPENROUTESERVICE_API_KEY")
    if not key:
        return None
    
    transport = HttpTransport(timeout=timeout)
    known = (config or {}).get("known_locations", {})
    return RoutingService(key, transport, known)


def calculate_route_cost(
    origin: Dict[str, float],  # {"lat": ..., "lon": ...}
    destination: Dict[str, float],
    quantity_kg: float,
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience function for single route cost calculation."""
    key = api_key or (config or {}).get("openrouteservice_api_key") or os.environ.get("OPENROUTESERVICE_API_KEY")
    if not key:
        return {"error": "OpenRouteService API key not configured"}
    
    service = create_routing_service(api_key=key, config=config)
    if not service:
        return {"error": "OpenRouteService API key not configured"}
    
    o = Coordinates.from_latlon(origin["lat"], origin["lon"])
    d = Coordinates.from_latlon(destination["lat"], destination["lon"])
    
    route = get_route(o, d, key)
    cost = calculate_transport_cost(
        distance_km=route.distance_km,
        duration_minutes=route.duration_minutes,
        quantity_kg=quantity_kg,
        fuel_prices={k: Decimal(str(v)) for k, v in (config or {}).get("fuel_prices", DEFAULT_FUEL_PRICES).items()},
        loading_cost=Decimal(str((config or {}).get("loading_cost", DEFAULT_LOADING_COST))),
        unloading_cost=Decimal(str((config or {}).get("unloading_cost", DEFAULT_LOADING_COST))),
        labour_cost_per_hour=Decimal(str((config or {}).get("labour_cost_per_hour", DEFAULT_LABOUR_COST_PER_HOUR))),
        refrigerated=(config or {}).get("refrigerated", False),
    )
    
    return {
        "route": route.to_dict(),
        "cost": cost.to_dict(),
    }