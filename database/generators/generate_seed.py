#!/usr/bin/env python3
"""
FPO Synthetic Data Generator - Stage A: Small Validation Seed (~1,000 records)

Generates a small, consistent dataset for schema validation and constraint testing.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch

from config import db_config, gen_config


class SeedGenerator:
    """Generates a small validation seed dataset."""
    
    def __init__(self, conn, seed: int = 42):
        self.conn = conn
        self.cur = conn.cursor(cursor_factory=RealDictCursor)
        self.rng = random.Random(seed)
        self.gen_config = gen_config
        self._cache = {}
    
    def _insert_batch(self, table: str, columns: List[str], rows: List[List[Any]]):
        """Insert rows in batches using execute_batch."""
        if not rows:
            return
        # Convert UUID objects to strings for psycopg2
        converted_rows = []
        for row in rows:
            converted_row = []
            for val in row:
                if isinstance(val, uuid.UUID):
                    converted_row.append(str(val))
                else:
                    converted_row.append(val)
            converted_rows.append(converted_row)
        
        placeholders = ", ".join(["%s"] * len(columns))
        cols = ", ".join(columns)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        execute_batch(self.cur, sql, converted_rows, page_size=1000)
        self.conn.commit()
    
    def generate_fpos(self, count: int = 5) -> List[Dict]:
        """Generate FPOs."""
        print(f"Generating {count} FPOs...")
        
        fpo_names = [
            ("MAH-NAS", "Nashik FPO", "Nashik", "Maharashtra", 19.9975, 73.7898),
            ("MAH-AHM", "Ahmednagar FPO", "Ahmednagar", "Maharashtra", 19.0948, 74.7380),
            ("MAH-PUN", "Pune FPO", "Pune", "Maharashtra", 18.5204, 73.8567),
            ("MAH-SOL", "Solapur FPO", "Solapur", "Maharashtra", 17.6599, 75.9064),
            ("MAH-SNG", "Sangli FPO", "Sangli", "Maharashtra", 16.8524, 74.5815),
            ("TEL-HYD", "Hyderabad FPO", "Hyderabad", "Telangana", 17.3850, 78.4867),
            ("TEL-WAR", "Warangal FPO", "Warangal", "Telangana", 17.9784, 79.5941),
            ("TEL-NZB", "Nizamabad FPO", "Nizamabad", "Telangana", 18.6725, 78.0941),
            ("TEL-KMM", "Khammam FPO", "Khammam", "Telangana", 17.2473, 80.1514),
            ("TEL-ADB", "Adilabad FPO", "Adilabad", "Telangana", 19.6643, 78.5300),
        ]
        
        rows = []
        fpos = []
        for i in range(min(count, len(fpo_names))):
            code, name, district, state, lat, lon = fpo_names[i]
            fpo_id = uuid.uuid4()
            reg_date = date(2020, self.rng.randint(1, 12), self.rng.randint(1, 28))
            rows.append([fpo_id, f"{code}-{i+1:03d}", name, district, state, lat, lon, reg_date, True, datetime.now(), datetime.now()])
            fpos.append({"fpo_id": fpo_id, "fpo_code": f"{code}-{i+1:03d}", "district": district, "state": state})
        
        self._insert_batch("fpos", [
            "fpo_id", "fpo_code", "fpo_name", "district", "state",
            "latitude", "longitude", "registration_date", "active_status",
            "created_at", "updated_at"
        ], rows)
        
        self._cache['fpos'] = fpos
        return fpos
    
    def generate_crops(self, count: int = 20) -> List[Dict]:
        """Generate crop master data."""
        print(f"Generating {count} crops...")
        
        crop_data = self.gen_config.crop_data[:count]
        rows = []
        crops = []
        for cd in crop_data:
            crop_id = uuid.uuid4()
            name, variety, category, storage_days, temp_min, temp_max, unit, perishability = cd
            rows.append([crop_id, name, variety, category, storage_days, temp_min, temp_max, unit, perishability, datetime.now(), datetime.now()])
            crops.append({"crop_id": crop_id, "crop_name": name, "variety": variety, "category": category})
        
        self._insert_batch("crops", [
            "crop_id", "crop_name", "variety", "crop_category",
            "typical_storage_days", "storage_temperature_min", "storage_temperature_max",
            "measurement_unit", "perishability_category", "created_at", "updated_at"
        ], rows)
        
        self._cache['crops'] = crops
        return crops
    
    def generate_farmers(self, fpos: List[Dict], count: int = 100) -> List[Dict]:
        """Generate farmers."""
        print(f"Generating {count} farmers...")
        
        first_names = ["Rajesh", "Suresh", "Mahesh", "Ganesh", "Ramesh", "Dinesh", "Naresh", "Umesh", "Lokesh", "Hitesh",
                       "Priya", "Sunita", "Anita", "Kavita", "Geeta", "Seeta", "Neeta", "Reeta", "Meeta", "Beena",
                       "Venkatesh", "Srinivas", "Raghavendra", "Madhav", "Govind", "Harish", "Krish", "Vishnu", "Shiva", "Rama"]
        last_names = ["Patil", "Deshmukh", "Kulkarni", "Jadhav", "More", "Shinde", "Pawar", "Salunkhe", "Chavan", "Gaikwad",
                      "Reddy", "Rao", "Naidu", "Goud", "Yadav", "Singh", "Kumar", "Gupta", "Sharma", "Verma"]
        villages = ["Khed", "Sinnar", "Yeola", "Niphad", "Dindori", "Surgana", "Kalwan", "Baglan", "Malegaon", "Chandwad",
                    "Rahuri", "Shrirampur", "Newasa", "Shevgaon", "Pathardi", "Karjat", "Jamkhed", "Ashti", "Parner", "Akole",
                    "Junnar", "Ambegaon", "Khed", "Maval", "Mulshi", "Velhe", "Bhor", "Purandar", "Baramati", "Indapur"]
        
        rows = []
        farmers = []
        for i in range(count):
            fpo = self.rng.choice(fpos)
            farmer_id = uuid.uuid4()
            fn = self.rng.choice(first_names)
            ln = self.rng.choice(last_names)
            village = self.rng.choice(villages)
            reg_date = date(2021, self.rng.randint(1, 12), self.rng.randint(1, 28))
            rows.append([
                farmer_id, fpo["fpo_id"],
                f"{fpo['fpo_code']}-FRM-{i+1:05d}",
                f"{fn} {ln}", village, fpo["district"], fpo["state"],
                round(self.rng.uniform(0.5, 10.0), 2), reg_date, True,
                datetime.now(), datetime.now()
            ])
            farmers.append({"farmer_id": farmer_id, "fpo_id": fpo["fpo_id"], "district": fpo["district"]})
        
        self._insert_batch("farmers", [
            "farmer_id", "fpo_id", "farmer_code", "full_name", "village",
            "district", "state", "land_area_hectares", "membership_date",
            "active_status", "created_at", "updated_at"
        ], rows)
        
        self._cache['farmers'] = farmers
        return farmers
    
    def generate_farms(self, farmers: List[Dict], count: int = 150) -> List[Dict]:
        """Generate farms."""
        print(f"Generating {count} farms...")
        
        soil_types = ["black_cotton", "red_lateritic", "alluvial", "sandy_loam", "clay_loam", "lateritic"]
        irrigation_types = ["rainfed", "drip", "sprinkler", "canal", "borewell"]
        
        rows = []
        farms = []
        for i in range(count):
            farmer = self.rng.choice(farmers)
            farm_id = uuid.uuid4()
            lat = round(self.rng.uniform(self.gen_config.lat_min, self.gen_config.lat_max), 6)
            lon = round(self.rng.uniform(self.gen_config.lon_min, self.gen_config.lon_max), 6)
            rows.append([
                farm_id, farmer["farmer_id"], farmer["district"],
                f"Village-{i+1}", lat, lon,
                round(self.rng.uniform(0.2, 5.0), 2),
                self.rng.choice(soil_types), self.rng.choice(irrigation_types), True,
                datetime.now(), datetime.now()
            ])
            farms.append({"farm_id": farm_id, "farmer_id": farmer["farmer_id"], "district": farmer["district"]})
        
        self._insert_batch("farms", [
            "farm_id", "farmer_id", "district", "village", "latitude", "longitude",
            "area_hectares", "soil_type", "irrigation_type", "active_status",
            "created_at", "updated_at"
        ], rows)
        
        self._cache['farms'] = farms
        return farms
    
    def generate_warehouses(self, fpos: List[Dict], count: int = 20) -> List[Dict]:
        """Generate warehouses."""
        print(f"Generating {count} warehouses...")
        
        storage_types = ["cold_storage", "ambient_warehouse", "ventilated_godown", "silo"]
        
        rows = []
        warehouses = []
        for i in range(count):
            fpo = self.rng.choice(fpos)
            wh_id = uuid.uuid4()
            lat = round(self.rng.uniform(self.gen_config.lat_min, self.gen_config.lat_max), 6)
            lon = round(self.rng.uniform(self.gen_config.lon_min, self.gen_config.lon_max), 6)
            rows.append([
                wh_id, fpo["fpo_id"], f"{fpo['fpo_code']}-WH-{i+1:03d}",
                fpo["district"], fpo["state"], lat, lon,
                self.rng.randint(50000, 500000), self.rng.choice(storage_types),
                self.rng.choice([True, False]), True, datetime.now(), datetime.now()
            ])
            warehouses.append({"warehouse_id": wh_id, "fpo_id": fpo["fpo_id"], "capacity_kg": rows[-1][8]})
        
        self._insert_batch("warehouses", [
            "warehouse_id", "fpo_id", "warehouse_name", "district", "state",
            "latitude", "longitude", "capacity_kg", "storage_type",
            "temperature_controlled", "active_status", "created_at", "updated_at"
        ], rows)
        
        self._cache['warehouses'] = warehouses
        return warehouses
    
    def generate_harvest_batches(self, farms: List[Dict], crops: List[Dict], count: int = 200) -> List[Dict]:
        """Generate harvest batches."""
        print(f"Generating {count} harvest batches...")
        
        quality_grades = ["premium", "A", "B", "C", "standard", "substandard"]
        statuses = ["harvested", "stored", "partial_sold", "fully_sold"]
        
        rows = []
        batches = []
        start_date = date(2023, 1, 1)
        end_date = date(2026, 10, 1)
        days_range = (end_date - start_date).days
        
        for i in range(count):
            farm = self.rng.choice(farms)
            crop = self.rng.choice(crops)
            batch_id = uuid.uuid4()
            harvest_date = start_date + timedelta(days=self.rng.randint(0, days_range))
            qty = round(self.rng.uniform(500, 50000), 2)
            quality = self.rng.choice(quality_grades)
            storage_days = crop.get("typical_storage_days", 30) if isinstance(crop, dict) else 30
            quality_end = harvest_date + timedelta(days=self.rng.randint(storage_days // 2, storage_days))
            cost = round(qty * self.rng.uniform(5, 25), 2)
            status = self.rng.choice(statuses)
            
            rows.append([
                batch_id, f"HB-{harvest_date.year}-{crop['crop_name'][:3].upper()}-{i+1:06d}",
                farm["farm_id"], crop["crop_id"], harvest_date, qty, quality,
                quality_end, cost, status, datetime.now(), datetime.now()
            ])
            batches.append({"batch_id": batch_id, "farm_id": farm["farm_id"], "crop_id": crop["crop_id"],
                          "harvest_date": harvest_date, "quantity": qty, "quality_end": quality_end})
        
        self._insert_batch("harvest_batches", [
            "batch_id", "batch_code", "farm_id", "crop_id", "harvest_date",
            "harvested_quantity_kg", "initial_quality_grade", "estimated_quality_window_end",
            "estimated_harvest_cost_inr", "status", "created_at", "updated_at"
        ], rows)
        
        self._cache['harvest_batches'] = batches
        return batches
    
    def generate_inventory(self, batches: List[Dict], warehouses: List[Dict], count: int = 200) -> List[Dict]:
        """Generate inventory records."""
        print(f"Generating {count} inventory records...")
        
        stock_statuses = ["available", "reserved", "quality_hold"]
        
        rows = []
        for i in range(count):
            batch = self.rng.choice(batches)
            warehouse = self.rng.choice(warehouses)
            inv_id = uuid.uuid4()
            qty_avail = round(self.rng.uniform(100, batch["quantity"]), 2)
            qty_reserved = round(self.rng.uniform(0, qty_avail * 0.5), 2)
            
            rows.append([
                inv_id, batch["batch_id"], warehouse["warehouse_id"],
                qty_avail, qty_reserved, datetime.now(),
                self.rng.choice(stock_statuses), datetime.now(), datetime.now()
            ])
        
        self._insert_batch("inventory", [
            "inventory_id", "batch_id", "warehouse_id", "quantity_available_kg",
            "quantity_reserved_kg", "last_updated", "stock_status",
            "created_at", "updated_at"
        ], rows)
    
    def generate_market_prices(self, crops: List[Dict], count: int = 500) -> List[Dict]:
        """Generate market price observations."""
        print(f"Generating {count} market prices...")
        
        markets = [
            ("Lasalgaon", "Nashik", "Maharashtra"), ("Pimpalgaon", "Nashik", "Maharashtra"),
            ("Nashik", "Nashik", "Maharashtra"), ("Ahmednagar", "Ahmednagar", "Maharashtra"),
            ("Pune", "Pune", "Maharashtra"), ("Solapur", "Solapur", "Maharashtra"),
            ("Sangli", "Sangli", "Maharashtra"), ("Kolhapur", "Kolhapur", "Maharashtra"),
            ("Hyderabad", "Hyderabad", "Telangana"), ("Warangal", "Warangal", "Telangana"),
            ("Nizamabad", "Nizamabad", "Telangana"), ("Khammam", "Khammam", "Telangana"),
            ("Bengaluru", "Bengaluru Urban", "Karnataka"), ("Mysuru", "Mysuru", "Karnataka"),
        ]
        
        source_types = ["synthetic"]
        quality_flags = ["verified", "estimated"]
        
        rows = []
        start_date = date(2023, 1, 1)
        end_date = date(2026, 10, 24)
        days_range = (end_date - start_date).days
        
        # Base prices per quintal for different crops
        base_prices = {
            "Tomato": (800, 1500), "Onion": (1000, 2500), "Potato": (800, 1800),
            "Banana": (1200, 2500), "Grapes": (3000, 6000), "Pomegranate": (4000, 8000),
            "Chilli": (8000, 15000), "Turmeric": (6000, 12000), "Cotton": (5000, 7000),
            "Soybean": (4000, 6000), "Wheat": (2000, 2800), "Rice": (2500, 4000),
            "Mango": (3000, 8000), "Orange": (2000, 4000),
        }
        
        for i in range(count):
            crop = self.rng.choice(crops)
            market_name, district, state = self.rng.choice(markets)
            price_id = uuid.uuid4()
            obs_date = start_date + timedelta(days=self.rng.randint(0, days_range))
            
            base_min, base_max = base_prices.get(crop["crop_name"], (1000, 3000))
            modal = round(self.rng.uniform(base_min, base_max), 2)
            min_p = round(modal * self.rng.uniform(0.85, 0.98), 2)
            max_p = round(modal * self.rng.uniform(1.02, 1.15), 2)
            
            rows.append([
                price_id, crop["crop_id"], market_name, district, state, obs_date,
                min_p, modal, max_p, self.rng.choice(source_types),
                self.rng.choice(quality_flags), datetime.now(), datetime.now()
            ])
        
        self._insert_batch("market_prices", [
            "price_id", "crop_id", "market_name", "district", "state",
            "observation_date", "minimum_price_inr_per_quintal",
            "modal_price_inr_per_quintal", "maximum_price_inr_per_quintal",
            "source_type", "data_quality_flag", "created_at", "updated_at"
        ], rows)
    
    def generate_buyers(self, count: int = 100) -> List[Dict]:
        """Generate buyers."""
        print(f"Generating {count} buyers...")
        
        buyer_names = ["AgriTrade", "FreshMart", "GreenFields", "HarvestHub", "CropConnect",
                       "FarmFresh", "AgroMart", "NatureBasket", "FieldToFork", "CropKing"]
        buyer_types = ["wholesaler", "processor", "retailer", "exporter", "institutional", "commission_agent"]
        markets = ["Lasalgaon", "Pimpalgaon", "Nashik", "Ahmednagar", "Pune", "Solapur",
                   "Hyderabad", "Warangal", "Nizamabad", "Bengaluru", "Mysuru"]
        
        rows = []
        buyers = []
        for i in range(count):
            buyer_id = uuid.uuid4()
            market = self.rng.choice(markets)
            lat = round(self.rng.uniform(self.gen_config.lat_min, self.gen_config.lat_max), 6)
            lon = round(self.rng.uniform(self.gen_config.lon_min, self.gen_config.lon_max), 6)
            rows.append([
                buyer_id, f"BUY-{i+1:05d}", f"{self.rng.choice(buyer_names)} {i+1}",
                self.rng.choice(buyer_types), market, "District", "State", lat, lon, True,
                datetime.now(), datetime.now()
            ])
            buyers.append({"buyer_id": buyer_id, "buyer_type": rows[-1][3]})
        
        self._insert_batch("buyers", [
            "buyer_id", "buyer_code", "buyer_name", "buyer_type", "market_name",
            "district", "state", "latitude", "longitude", "active_status",
            "created_at", "updated_at"
        ], rows)
        
        self._cache['buyers'] = buyers
        return buyers
    
    def generate_sales_orders(self, batches: List[Dict], buyers: List[Dict], count: int = 100) -> List[Dict]:
        """Generate sales orders."""
        print(f"Generating {count} sales orders...")
        
        statuses = ["delivered", "partial_delivered", "confirmed", "in_transit"]
        
        rows = []
        start_date = date(2023, 1, 1)
        end_date = date(2026, 10, 24)
        days_range = (end_date - start_date).days
        
        for i in range(count):
            batch = self.rng.choice(batches)
            buyer = self.rng.choice(buyers)
            order_id = uuid.uuid4()
            order_date = start_date + timedelta(days=self.rng.randint(0, days_range))
            qty = round(self.rng.uniform(500, min(batch["quantity"], 10000)), 2)
            price = round(self.rng.uniform(1000, 8000), 2)
            delivery_date = order_date + timedelta(days=self.rng.randint(1, 14))
            status = self.rng.choice(statuses)
            
            rows.append([
                order_id, f"SO-{order_date.year}-{i+1:06d}", batch["batch_id"],
                buyer["buyer_id"], qty, price, order_date, delivery_date, status,
                datetime.now(), datetime.now()
            ])
        
        self._insert_batch("sales_orders", [
            "order_id", "order_code", "batch_id", "buyer_id", "quantity_kg",
            "agreed_price_inr_per_quintal", "order_date", "delivery_date",
            "order_status", "created_at", "updated_at"
        ], rows)
    
    def generate_transport_routes(self, warehouses: List[Dict], buyers: List[Dict], count: int = 200) -> List[Dict]:
        """Generate transport routes."""
        print(f"Generating {count} transport routes...")
        
        vehicle_types = ["mini_truck_1t", "truck_5t", "truck_9t", "truck_16t",
                         "container_20ft", "container_40ft", "refrigerated_5t", "refrigerated_9t"]
        route_statuses = ["active", "inactive", "seasonal"]
        
        rows = []
        for i in range(count):
            wh = self.rng.choice(warehouses)
            buyer = self.rng.choice(buyers)
            route_id = uuid.uuid4()
            distance = round(self.rng.uniform(10, 800), 2)
            vehicle = self.rng.choice(vehicle_types)
            capacity = {"mini_truck_1t": 1000, "truck_5t": 5000, "truck_9t": 9000,
                       "truck_16t": 16000, "container_20ft": 20000, "container_40ft": 28000,
                       "refrigerated_5t": 5000, "refrigerated_9t": 9000}[vehicle]
            fixed = round(self.rng.uniform(500, 5000), 2)
            var_cost = round(self.rng.uniform(8, 25), 2)
            
            rows.append([
                route_id, wh["warehouse_id"], buyer["buyer_id"], distance,
                round(distance / 40, 1), vehicle, capacity, fixed, var_cost,
                self.rng.choice(route_statuses), datetime.now(), datetime.now()
            ])
        
        self._insert_batch("transport_routes", [
            "route_id", "origin_warehouse_id", "destination_buyer_id",
            "distance_km", "expected_transit_hours", "vehicle_type", "capacity_kg",
            "fixed_cost_inr", "variable_cost_inr_per_km", "route_status",
            "created_at", "updated_at"
        ], rows)
    
    def generate_storage_costs(self, warehouses: List[Dict], crops: List[Dict], count: int = 200) -> List[Dict]:
        """Generate storage costs."""
        print(f"Generating {count} storage costs...")
        
        cost_sources = ["synthetic"]
        
        rows = []
        for i in range(count):
            wh = self.rng.choice(warehouses)
            crop = self.rng.choice(crops)
            sc_id = uuid.uuid4()
            eff_from = date(2023, 1, 1)
            eff_to = date(2026, 12, 31)
            
            rows.append([
                sc_id, wh["warehouse_id"], crop["crop_id"], eff_from, eff_to,
                round(self.rng.uniform(0.01, 0.50), 4),  # storage_cost_per_kg_day
                round(self.rng.uniform(0.50, 3.00), 4),  # handling_cost_per_kg
                round(self.rng.uniform(0.02, 0.30), 4) if wh.get("temperature_controlled") else None,
                self.rng.choice(cost_sources), datetime.now(), datetime.now()
            ])
        
        self._insert_batch("storage_costs", [
            "storage_cost_id", "warehouse_id", "crop_id", "effective_from",
            "effective_to", "storage_cost_inr_per_kg_day", "handling_cost_inr_per_kg",
            "refrigeration_cost_inr_per_kg_day", "cost_source", "created_at", "updated_at"
        ], rows)


def run_seed_generation():
    """Run the seed generation."""
    print("=" * 60)
    print("FPO Synthetic Data Generation - Stage A (Validation Seed)")
    print("=" * 60)
    
    conn = psycopg2.connect(db_config.connection_string())
    conn.autocommit = False
    print(f"Connected to {db_config.database} on {db_config.host}:{db_config.port}")
    
    try:
        generator = SeedGenerator(conn, seed=gen_config.seed)
        
        # Generate in dependency order
        fpos = generator.generate_fpos(5)
        crops = generator.generate_crops(20)
        farmers = generator.generate_farmers(fpos, 100)
        farms = generator.generate_farms(farmers, 150)
        warehouses = generator.generate_warehouses(fpos, 20)
        batches = generator.generate_harvest_batches(farms, crops, 200)
        generator.generate_inventory(batches, warehouses, 200)
        generator.generate_market_prices(crops, 500)
        buyers = generator.generate_buyers(100)
        generator.generate_sales_orders(batches, buyers, 100)
        generator.generate_transport_routes(warehouses, buyers, 200)
        generator.generate_storage_costs(warehouses, crops, 200)
        
        # Log generation run
        run_id = uuid.uuid4()
        log_rows = [
            [run_id, "seed", "fpos", 5, 5, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "crops", 20, 20, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "farmers", 100, 100, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "farms", 150, 150, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "warehouses", 20, 20, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "harvest_batches", 200, 200, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "inventory", 200, 200, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "market_prices", 500, 500, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "buyers", 100, 100, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "sales_orders", 100, 100, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "transport_routes", 200, 200, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
            [run_id, "seed", "storage_costs", 200, 200, 0, "completed", None, gen_config.seed, datetime.now(), datetime.now()],
        ]
        generator._insert_batch("data_generation_log", [
            "generation_run_id", "stage", "table_name", "records_target",
            "records_generated", "duration_seconds", "status", "error_message",
            "seed_used", "started_at", "completed_at"
        ], log_rows)
        
        print("\n" + "=" * 60)
        print("Stage A (Validation Seed) completed successfully!")
        print("=" * 60)
        
        # Print summary
        for table in ["fpos", "farmers", "farms", "crops", "harvest_batches", 
                      "warehouses", "inventory", "market_prices", "buyers",
                      "sales_orders", "transport_routes", "storage_costs"]:
            generator.cur.execute(f"SELECT COUNT(*) FROM {table}")
            cnt = generator.cur.fetchone()['count']
            print(f"  {table}: {cnt} records")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_seed_generation()