"""Mocked tests for routing module."""

from decimal import Decimal
from backend.tools.routing import (
    Coordinates,
    RouteResult,
    MatrixResult,
    TransportCost,
    calculate_transport_cost,
    haversine_distance,
    VEHICLE_SPECS,
    DEFAULT_FUEL_PRICES,
    DEFAULT_LOADING_COST,
    DEFAULT_LABOUR_COST_PER_HOUR,
    HttpTransport,
)


def test_coordinates():
    c = Coordinates(lon=73.85, lat=18.52)
    assert c.to_list() == [73.85, 18.52]
    
    c2 = Coordinates.from_latlon(18.52, 73.85)
    assert c2.lon == 73.85
    assert c2.lat == 18.52


def test_route_result_to_dict():
    result = RouteResult(
        distance_km=180.5,
        duration_minutes=240.0,
        geometry={"type": "LineString", "coordinates": [[73.85, 18.52], [72.87, 19.07]]},
        steps=[{"instruction": "Head north", "distance": 100}],
        vehicle_profile="driving-hgv",
    )
    d = result.to_dict()
    assert d["distance_km"] == 180.5
    assert d["duration_minutes"] == 240.0
    assert d["duration_hours"] == 4.0
    assert d["geometry"]["type"] == "LineString"
    assert d["vehicle_profile"] == "driving-hgv"


def test_matrix_result_to_dict():
    origins = [Coordinates(lon=73.85, lat=18.52)]
    destinations = [Coordinates(lon=72.87, lat=19.07)]
    result = MatrixResult(
        origins=origins,
        destinations=destinations,
        distances_km=[[180.5]],
        durations_minutes=[[240.0]],
        vehicle_profile="driving-hgv",
    )
    d = result.to_dict()
    assert d["distances_km"] == [[180.5]]
    assert d["durations_minutes"] == [[240.0]]
    assert d["durations_hours"] == [[4.0]]
    assert d["vehicle_profile"] == "driving-hgv"


def test_transport_cost_calculation():
    cost = calculate_transport_cost(
        distance_km=180.0,
        duration_minutes=240.0,
        quantity_kg=5000.0,
        vehicle_type="driving-hgv",
        fuel_prices={"diesel": Decimal("90.0")},
        loading_cost=Decimal("500.0"),
        unloading_cost=Decimal("500.0"),
        labour_cost_per_hour=Decimal("200.0"),
        refrigerated=False,
        tolls=Decimal("0.0"),
    )
    
    assert cost.distance_km == 180.0
    assert cost.duration_hours == 4.0
    assert cost.vehicle_type == "driving-hgv"
    assert cost.capacity_kg == 10000
    assert cost.fuel_type == "diesel"
    assert cost.fuel_efficiency_kmpl == 4.0
    assert cost.fuel_price_per_litre == Decimal("90.0")
    # Fuel: 180/4 = 45 litres * 90 = 4050
    assert cost.fuel_cost == Decimal("4050.00")
    assert cost.loading_cost == Decimal("500.00")
    assert cost.unloading_cost == Decimal("500.00")
    assert cost.labour_cost == Decimal("800.00")
    assert cost.refrigeration_cost == Decimal("0.00")
    assert cost.total_cost == Decimal("5850.00")
    assert cost.cost_per_kg == Decimal("1.17")
    # cost_per_tonne_km = total_cost / (quantity_tonnes * distance_km) = 5850 / (5 * 180) = 6.5
    assert cost.cost_per_tonne_km == Decimal("6.50")


def test_transport_cost_refrigerated():
    cost = calculate_transport_cost(
        distance_km=180.0,
        duration_minutes=240.0,
        quantity_kg=5000.0,
        vehicle_type="driving-hgv",
        fuel_prices={"diesel": Decimal("90.0")},
        loading_cost=Decimal("500.0"),
        unloading_cost=Decimal("500.0"),
        labour_cost_per_hour=Decimal("200.0"),
        refrigerated=True,
    )
    
    assert cost.vehicle_type == "driving-hgv"
    assert cost.refrigeration_cost > Decimal("0")
    # Refrigerated cost: 180 km * 15 INR/km = 2700
    assert cost.refrigeration_cost == Decimal("2700.00")


def test_transport_cost_multiple_trips():
    # 15000 kg with 10000 kg capacity = 2 trips
    cost = calculate_transport_cost(
        distance_km=100.0,
        duration_minutes=120.0,
        quantity_kg=15000.0,
        vehicle_type="driving-hgv",
        fuel_prices={"diesel": Decimal("90.0")},
    )
    
    # 2 trips * 100 km = 200 km total
    assert cost.distance_km == 100.0  # base distance
    # Fuel for 200 km: 200/4 = 50 litres * 90 = 4500
    assert cost.fuel_cost == Decimal("4500.00")
    # Loading/unloading for 2 trips
    assert cost.loading_cost == Decimal("1000.00")
    assert cost.unloading_cost == Decimal("1000.00")
    # Labour for 2 trips * 2 hours = 4 hours * 200 = 800
    assert cost.labour_cost == Decimal("800.00")


def test_haversine_distance():
    # Pune to Mumbai ~120 km (straight-line)
    pune = Coordinates.from_latlon(18.52, 73.85)
    mumbai = Coordinates.from_latlon(19.07, 72.87)
    dist = haversine_distance(pune, mumbai)
    assert 110 < dist < 130  # straight-line distance
    
    # Same point = 0
    dist_same = haversine_distance(pune, pune)
    assert dist_same == 0.0


def test_vehicle_specs():
    assert "driving-car" in VEHICLE_SPECS
    assert "driving-hgv" in VEHICLE_SPECS
    assert "refrigerated-hgv" in VEHICLE_SPECS
    
    hgv = VEHICLE_SPECS["driving-hgv"]
    assert hgv["capacity_kg"] == 10000
    assert hgv["fuel_efficiency_kmpl"] == 4.0
    assert hgv["fuel_type"] == "diesel"
    
    ref_hgv = VEHICLE_SPECS["refrigerated-hgv"]
    assert "refrigeration_cost_per_km" in ref_hgv


def test_default_fuel_prices():
    assert "petrol" in DEFAULT_FUEL_PRICES
    assert "diesel" in DEFAULT_FUEL_PRICES
    assert DEFAULT_FUEL_PRICES["diesel"] == Decimal("90.0")
    assert DEFAULT_FUEL_PRICES["petrol"] == Decimal("100.0")


def test_default_costs():
    assert DEFAULT_LOADING_COST == Decimal("500.0")
    assert DEFAULT_LABOUR_COST_PER_HOUR == Decimal("200.0")


def test_http_transport():
    class MockTransport(HttpTransport):
        def request(self, url, method="GET", headers=None, body=None, timeout=30):
            return 200, {"test": "data"}
    
    transport = MockTransport()
    status, data = transport.request("http://test.com")
    assert status == 200
    assert data == {"test": "data"}


def test_transport_cost_to_dict():
    cost = calculate_transport_cost(
        distance_km=100.0,
        duration_minutes=120.0,
        quantity_kg=1000.0,
    )
    d = cost.to_dict()
    
    assert "distance_km" in d
    assert "duration_hours" in d
    assert "vehicle_type" in d
    assert "capacity_kg" in d
    assert "fuel_type" in d
    assert "fuel_efficiency_kmpl" in d
    assert "fuel_price_per_litre" in d
    assert "fuel_cost" in d
    assert "loading_cost" in d
    assert "unloading_cost" in d
    assert "labour_cost" in d
    assert "refrigeration_cost" in d
    assert "toll_cost" in d
    assert "total_cost" in d
    assert "cost_per_kg" in d
    assert "cost_per_tonne_km" in d
    
    assert d["distance_km"] == 100.0
    assert d["duration_hours"] == 2.0
    assert d["vehicle_type"] == "driving-hgv"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])