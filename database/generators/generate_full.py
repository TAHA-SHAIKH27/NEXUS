#!/usr/bin/env python3
"""
FPO Synthetic Data Generator - Stage B/C: Integration (50K) and Full (500K) Dataset

Uses COPY for high-performance bulk loading.
Deterministic with seed 42.
"""
import sys
import os
import csv
import uuid
import random
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Generator
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import db_config, gen_config


class FullDatasetGenerator:
    """Generates large-scale synthetic FPO dataset using COPY."""
    
    def __init__(self, conn: psycopg2.extensions.connection, seed: int = 42):
        self.conn = conn
        self.cur = conn.cursor(cursor_factory=RealDictCursor)
        self.copy_cur = conn.cursor()  # Regular cursor for COPY operations
        self.rng = random.Random(seed)
        self.gen_config = gen_config
        self._id_maps = {}  # Track generated IDs for FK references
        
    def _copy_from_buffer(self, table: str, columns: List[str], data_generator: Generator) -> int:
        """Use COPY FROM STDIN for high-performance bulk insert."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        count = 0
        for row in data_generator:
            # Convert UUIDs to strings, handle None
            converted = []
            for val in row:
                if isinstance(val, uuid.UUID):
                    converted.append(str(val))
                elif isinstance(val, (date, datetime)):
                    converted.append(val.isoformat())
                elif isinstance(val, Decimal):
                    converted.append(str(val))
                elif val is None:
                    converted.append('\\N')
                else:
                    converted.append(str(val))
            writer.writerow(converted)
            count += 1
            
            if count % 50000 == 0:
                self._flush_buffer(table, columns, buffer)
                buffer = io.StringIO()
                writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        if count % 50000 != 0 or count < 50000:
            self._flush_buffer(table, columns, buffer)
        
        return count
    
    def _flush_buffer(self, table: str, columns: List[str], buffer: io.StringIO):
        """Flush buffer to database using COPY."""
        if buffer.tell() == 0:
            return
        buffer.seek(0)
        cols = ", ".join(columns)
        sql = f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')"
        self.copy_cur.copy_expert(sql, buffer)
        self.conn.commit()
    
    def generate_fpos(self, count: int) -> List[Dict]:
        print(f"Generating {count} FPOs...")
        
        states_districts = {
            "Maharashtra": ["Nashik", "Ahmednagar", "Pune", "Solapur", "Sangli", "Kolhapur",
                           "Satara", "Jalgaon", "Dhule", "Nandurbar", "Aurangabad", "Jalna",
                           "Beed", "Latur", "Osmanabad", "Nanded", "Parbhani", "Hingoli",
                           "Buldhana", "Akola", "Washim", "Amravati", "Yavatmal", "Wardha",
                           "Nagpur", "Bhandara", "Gondia", "Chandrapur", "Gadchiroli"],
            "Telangana": ["Hyderabad", "Rangareddy", "Medchal", "Vikarabad", "Sangareddy",
                         "Medak", "Siddipet", "Kamareddy", "Nizamabad", "Jagtial",
                         "Peddapalli", "Karimnagar", "Rajanna Sircilla", "Jayashankar",
                         "Mahabubabad", "Warangal", "Warangal Rural", "Mulugu",
                         "Bhadradri Kothagudem", "Khammam", "Mahabubnagar", "Jogulamba",
                         "Nagarkurnool", "Wanaparthy", "Narayanpet", "Adilabad",
                         "Kumuram Bheem", "Mancherial", "Nirmal"],
            "Karnataka": ["Bengaluru Urban", "Bengaluru Rural", "Ramanagara", "Kolar",
                         "Chikkaballapura", "Tumakuru", "Chitradurga", "Davanagere",
                         "Ballari", "Vijayanagara", "Koppal", "Raichur", "Yadgir",
                         "Kalaburagi", "Bidar", "Belagavi", "Bagalkote", "Vijayapura",
                         "Dharwad", "Gadag", "Haveri", "Uttara Kannada", "Shivamogga",
                         "Chikkamagaluru", "Hassan", "Kodagu", "Mysuru", "Mandya",
                         "Chamarajanagara"]
        }
        
        fpo_names_by_state = {
            "Maharashtra": ["FPO", "Krishi", "Shetkari", "Gramin", "Kranti"],
            "Telangana": ["Rythu", "Kisan", "Krishi", "Samakhya", "FPO"],
            "Karnataka": ["Raitha", "Krishi", "FPO", "Sangha", "Samruddhi"]
        }
        
        rows = []
        fpos = []
        for i in range(count):
            state = self.rng.choice(list(states_districts.keys()))
            district = self.rng.choice(states_districts[state])
            fpo_id = uuid.uuid4()
            name_prefix = self.rng.choice(fpo_names_by_state[state])
            reg_date = date(2018, self.rng.randint(1, 12), self.rng.randint(1, 28))
            lat = round(self.rng.uniform(15.0, 22.0), 6)
            lon = round(self.rng.uniform(72.0, 81.0), 6)
            
            code = f"{state[:3].upper()}-{district[:3].upper()}-{i+1:03d}"
            rows.append((fpo_id, code, f"{name_prefix} {district}", district, state, lat, lon, reg_date, True))
            fpos.append({"fpo_id": fpo_id, "fpo_code": code, "district": district, "state": state})
        
        self._copy_from_buffer("fpos", [
            "fpo_id", "fpo_code", "fpo_name", "district", "state",
            "latitude", "longitude", "registration_date", "active_status"
        ], iter(rows))
        
        self._id_maps['fpos'] = fpos
        return fpos
    
    def generate_crops(self, count: int) -> List[Dict]:
        print(f"Generating {count} crops...")
        
        # Use all crop data from config
        crop_data = self.gen_config.crop_data[:count]
        
        rows = []
        crops = []
        for cd in crop_data:
            crop_id = uuid.uuid4()
            name, variety, category, storage_days, temp_min, temp_max, unit, perishability = cd
            rows.append((crop_id, name, variety, category, storage_days, temp_min, temp_max, unit, perishability))
            crops.append({"crop_id": crop_id, "crop_name": name, "variety": variety, "category": category,
                         "storage_days": storage_days, "temp_min": temp_min, "temp_max": temp_max,
                         "perishability": perishability})
        
        self._copy_from_buffer("crops", [
            "crop_id", "crop_name", "variety", "crop_category",
            "typical_storage_days", "storage_temperature_min", "storage_temperature_max",
            "measurement_unit", "perishability_category"
        ], iter(rows))
        
        self._id_maps['crops'] = crops
        return crops
    
    def generate_farmers(self, fpos: List[Dict], count: int) -> List[Dict]:
        print(f"Generating {count} farmers...")
        
        first_names = ["Rajesh", "Suresh", "Mahesh", "Ganesh", "Ramesh", "Dinesh", "Naresh", "Umesh", "Lokesh", "Hitesh",
                       "Priya", "Sunita", "Anita", "Kavita", "Geeta", "Seeta", "Neeta", "Reeta", "Meeta", "Beena",
                       "Venkatesh", "Srinivas", "Raghavendra", "Madhav", "Govind", "Harish", "Krish", "Vishnu", "Shiva", "Rama",
                       "Anil", "Sunil", "Mohan", "Rohan", "Sohan", "Gopal", "Kamal", "Vimal", "Bimal", "Jimal"]
        last_names = ["Patil", "Deshmukh", "Kulkarni", "Jadhav", "More", "Shinde", "Pawar", "Salunkhe", "Chavan", "Gaikwad",
                      "Reddy", "Rao", "Naidu", "Goud", "Yadav", "Singh", "Kumar", "Gupta", "Sharma", "Verma",
                      "Nair", "Menon", "Iyer", "Shetty", "Hegde", "Bhat", "Kulkarni", "Joshi", "Desai", "Mehta"]
        villages = [f"Village-{i}" for i in range(1, 501)]
        
        rows = []
        farmers = []
        for i in range(count):
            fpo = self.rng.choice(fpos)
            farmer_id = uuid.uuid4()
            fn = self.rng.choice(first_names)
            ln = self.rng.choice(last_names)
            village = self.rng.choice(villages)
            reg_date = date(2020, self.rng.randint(1, 12), self.rng.randint(1, 28))
            
            rows.append((
                farmer_id, fpo["fpo_id"],
                f"{fpo['fpo_code']}-FRM-{i+1:05d}",
                f"{fn} {ln}", village, fpo["district"], fpo["state"],
                round(self.rng.uniform(0.5, 15.0), 2), reg_date, True
            ))
            farmers.append({"farmer_id": farmer_id, "fpo_id": fpo["fpo_id"], "district": fpo["district"]})
        
        self._copy_from_buffer("farmers", [
            "farmer_id", "fpo_id", "farmer_code", "full_name", "village",
            "district", "state", "land_area_hectares", "membership_date", "active_status"
        ], iter(rows))
        
        self._id_maps['farmers'] = farmers
        return farmers
    
    def generate_farms(self, farmers: List[Dict], count: int) -> List[Dict]:
        print(f"Generating {count} farms...")
        
        soil_types = ["black_cotton", "red_lateritic", "alluvial", "sandy_loam", "clay_loam", "lateritic"]
        irrigation_types = ["rainfed", "drip", "sprinkler", "canal", "borewell"]
        
        rows = []
        farms = []
        for i in range(count):
            farmer = self.rng.choice(farmers)
            farm_id = uuid.uuid4()
            lat = round(self.rng.uniform(15.0, 22.0), 6)
            lon = round(self.rng.uniform(72.0, 81.0), 6)
            
            rows.append((
                farm_id, farmer["farmer_id"], farmer["district"], f"Village-{i+1}",
                lat, lon, round(self.rng.uniform(0.2, 8.0), 2),
                self.rng.choice(soil_types), self.rng.choice(irrigation_types), True
            ))
            farms.append({"farm_id": farm_id, "farmer_id": farmer["farmer_id"], "district": farmer["district"]})
        
        self._copy_from_buffer("farms", [
            "farm_id", "farmer_id", "district", "village", "latitude", "longitude",
            "area_hectares", "soil_type", "irrigation_type", "active_status"
        ], iter(rows))
        
        self._id_maps['farms'] = farms
        return farms
    
    def generate_warehouses(self, fpos: List[Dict], count: int) -> List[Dict]:
        print(f"Generating {count} warehouses...")
        
        storage_types = ["cold_storage", "ambient_warehouse", "ventilated_godown", "silo"]
        
        rows = []
        warehouses = []
        for i in range(count):
            fpo = self.rng.choice(fpos)
            wh_id = uuid.uuid4()
            lat = round(self.rng.uniform(15.0, 22.0), 6)
            lon = round(self.rng.uniform(72.0, 81.0), 6)
            capacity = self.rng.randint(50000, 1000000)
            temp_controlled = self.rng.choice([True, False])
            
            rows.append((
                wh_id, fpo["fpo_id"], f"{fpo['fpo_code']}-WH-{i+1:04d}",
                fpo["district"], fpo["state"], lat, lon, capacity,
                self.rng.choice(storage_types), temp_controlled, True
            ))
            warehouses.append({"warehouse_id": wh_id, "fpo_id": fpo["fpo_id"],
                              "capacity_kg": capacity, "temp_controlled": temp_controlled,
                              "district": fpo["district"], "state": fpo["state"]})
        
        self._copy_from_buffer("warehouses", [
            "warehouse_id", "fpo_id", "warehouse_name", "district", "state",
            "latitude", "longitude", "capacity_kg", "storage_type",
            "temperature_controlled", "active_status"
        ], iter(rows))
        
        self._id_maps['warehouses'] = warehouses
        return warehouses
    
    def generate_harvest_batches(self, farms: List[Dict], crops: List[Dict], count: int) -> List[Dict]:
        print(f"Generating {count} harvest batches...")
        
        quality_grades = ["premium", "A", "B", "C", "standard", "substandard"]
        statuses = ["harvested", "stored", "partial_sold", "fully_sold", "spoiled"]
        status_weights = [0.1, 0.5, 0.25, 0.1, 0.05]
        
        crop_lookup = {c["crop_id"]: c for c in crops}
        
        rows = []
        batches = []
        start_date = date(2023, 1, 1)
        end_date = date(2026, 10, 24)
        days_range = (end_date - start_date).days
        
        # Crop seasonality: higher probability in harvest months
        harvest_months = {
            "Tomato": [1,2,3,10,11,12], "Onion": [3,4,5,10,11], "Potato": [1,2,3,11,12],
            "Banana": list(range(1,13)), "Grapes": [2,3,4], "Pomegranate": [8,9,10],
            "Chilli": [2,3,4,9,10], "Mango": [4,5,6], "Orange": [11,12,1,2],
            "Wheat": [3,4], "Rice": [10,11], "Cotton": [10,11,12], "Soybean": [10,11],
        }
        
        for i in range(count):
            farm = self.rng.choice(farms)
            crop = self.rng.choice(crops)
            crop_info = crop_lookup[crop["crop_id"]]
            batch_id = uuid.uuid4()
            
            # Seasonal harvest date
            crop_name = crop_info["crop_name"]
            preferred_months = harvest_months.get(crop_name, list(range(1,13)))
            year = self.rng.randint(2023, 2026)
            month = self.rng.choice(preferred_months)
            day = self.rng.randint(1, 28)
            harvest_date = date(year, month, day)
            
            qty = round(self.rng.uniform(500, 100000), 2)
            quality = self.rng.choice(quality_grades)
            storage_days = crop_info.get("storage_days", 30)
            quality_end = harvest_date + timedelta(days=self.rng.randint(storage_days // 2, storage_days + 30))
            cost = round(qty * self.rng.uniform(5, 30), 2)
            status = self.rng.choices(statuses, weights=status_weights)[0]
            
            rows.append((
                batch_id, f"HB-{year}-{crop_name[:3].upper()}-{i+1:06d}",
                farm["farm_id"], crop["crop_id"], harvest_date, qty, quality,
                quality_end, cost, status
            ))
            batches.append({"batch_id": batch_id, "farm_id": farm["farm_id"],
                          "crop_id": crop["crop_id"], "harvest_date": harvest_date,
                          "quantity": qty, "quality_end": quality_end,
                          "crop_name": crop_name, "status": status})
        
        self._copy_from_buffer("harvest_batches", [
            "batch_id", "batch_code", "farm_id", "crop_id", "harvest_date",
            "harvested_quantity_kg", "initial_quality_grade", "estimated_quality_window_end",
            "estimated_harvest_cost_inr", "status"
        ], iter(rows))
        
        self._id_maps['harvest_batches'] = batches
        return batches
    
    def generate_inventory(self, batches: List[Dict], warehouses: List[Dict], count: int) -> int:
        print(f"Generating {count} inventory records...")
        
        stock_statuses = ["available", "reserved", "quality_hold", "in_transit"]
        
        rows = []
        generated = 0
        batch_warehouse_pairs = set()
        
        # Pre-assign each batch to 1-3 warehouses
        batch_wh_map = {}
        for batch in batches:
            num_wh = self.rng.randint(1, 3)
            whs = self.rng.sample(warehouses, min(num_wh, len(warehouses)))
            batch_wh_map[batch["batch_id"]] = whs
        
        for batch in batches:
            whs = batch_wh_map.get(batch["batch_id"], [self.rng.choice(warehouses)])
            remaining = batch["quantity"]
            for wh in whs:
                if remaining <= 0:
                    break
                inv_id = uuid.uuid4()
                qty_avail = round(min(remaining, self.rng.uniform(100, remaining)), 2)
                qty_reserved = round(self.rng.uniform(0, qty_avail * 0.6), 2)
                remaining -= qty_avail
                
                rows.append((
                    inv_id, batch["batch_id"], wh["warehouse_id"],
                    qty_avail, qty_reserved, datetime.now(),
                    self.rng.choice(stock_statuses)
                ))
                generated += 1
                batch_warehouse_pairs.add((batch["batch_id"], wh["warehouse_id"]))
        
        self._copy_from_buffer("inventory", [
            "inventory_id", "batch_id", "warehouse_id", "quantity_available_kg",
            "quantity_reserved_kg", "last_updated", "stock_status"
        ], iter(rows))
        
        self._id_maps['inventory'] = batch_warehouse_pairs
        return generated
    
    def generate_market_prices(self, crops: List[Dict], count: int) -> int:
        print(f"Generating {count} market prices...")
        
        markets = [
            ("Lasalgaon", "Nashik", "Maharashtra"), ("Pimpalgaon", "Nashik", "Maharashtra"),
            ("Nashik", "Nashik", "Maharashtra"), ("Ahmednagar", "Ahmednagar", "Maharashtra"),
            ("Pune", "Pune", "Maharashtra"), ("Solapur", "Solapur", "Maharashtra"),
            ("Sangli", "Sangli", "Maharashtra"), ("Kolhapur", "Kolhapur", "Maharashtra"),
            ("Hyderabad", "Hyderabad", "Telangana"), ("Warangal", "Warangal", "Telangana"),
            ("Nizamabad", "Nizamabad", "Telangana"), ("Khammam", "Khammam", "Telangana"),
            ("Bengaluru", "Bengaluru Urban", "Karnataka"), ("Mysuru", "Mysuru", "Karnataka"),
            ("Davanagere", "Davanagere", "Karnataka"), ("Ballari", "Ballari", "Karnataka"),
        ]
        
        source_types = ["synthetic"] * 90 + ["agmarknet"] * 10
        quality_flags = ["verified"] * 70 + ["estimated"] * 25 + ["stale"] * 5
        
        crop_lookup = {c["crop_id"]: c for c in crops}
        base_prices = {
            "Tomato": (600, 2000), "Onion": (800, 3000), "Potato": (700, 2200),
            "Banana": (1000, 3000), "Grapes": (2500, 7000), "Pomegranate": (3500, 9000),
            "Chilli": (7000, 18000), "Turmeric": (5000, 14000), "Cotton": (4500, 8000),
            "Soybean": (3500, 7000), "Wheat": (1800, 3000), "Rice": (2000, 4500),
            "Mango": (2500, 10000), "Orange": (1800, 5000), "Papaya": (1500, 3500),
            "Cabbage": (500, 1500), "Cauliflower": (800, 2000), "Brinjal": (800, 2000),
            "Okra": (1000, 3000), "Cucumber": (800, 2200), "Groundnut": (4000, 7000),
            "Ginger": (4000, 8000),
        }
        
        rows = []
        start_date = date(2023, 1, 1)
        end_date = date(2026, 10, 24)
        days_range = (end_date - start_date).days
        
        # Generate more prices for high-volume crops
        for i in range(count):
            crop = self.rng.choice(crops)
            crop_info = crop_lookup[crop["crop_id"]]
            market_name, district, state = self.rng.choice(markets)
            price_id = uuid.uuid4()
            obs_date = start_date + timedelta(days=self.rng.randint(0, days_range))
            
            base_min, base_max = base_prices.get(crop_info["crop_name"], (1000, 3000))
            modal = round(self.rng.uniform(base_min, base_max), 2)
            min_p = round(modal * self.rng.uniform(0.82, 0.98), 2)
            max_p = round(modal * self.rng.uniform(1.02, 1.20), 2)
            
            rows.append((
                price_id, crop["crop_id"], market_name, district, state, obs_date,
                min_p, modal, max_p, self.rng.choice(source_types),
                self.rng.choice(quality_flags)
            ))
        
        self._copy_from_buffer("market_prices", [
            "price_id", "crop_id", "market_name", "district", "state",
            "observation_date", "minimum_price_inr_per_quintal",
            "modal_price_inr_per_quintal", "maximum_price_inr_per_quintal",
            "source_type", "data_quality_flag"
        ], iter(rows))
        
        return count
    
    def generate_buyers(self, count: int) -> List[Dict]:
        print(f"Generating {count} buyers...")
        
        buyer_prefixes = ["AgriTrade", "FreshMart", "GreenFields", "HarvestHub", "CropConnect",
                         "FarmFresh", "AgroMart", "NatureBasket", "FieldToFork", "CropKing",
                         "WholesaleCo", "ProduceHub", "MarketLink", "FarmDirect", "AgriLink"]
        buyer_types = ["wholesaler", "processor", "retailer", "exporter", "institutional", "commission_agent"]
        type_weights = [0.3, 0.2, 0.15, 0.1, 0.15, 0.1]
        markets = ["Lasalgaon", "Pimpalgaon", "Nashik", "Ahmednagar", "Pune", "Solapur",
                   "Hyderabad", "Warangal", "Nizamabad", "Bengaluru", "Mysuru", "Davanagere"]
        
        rows = []
        buyers = []
        for i in range(count):
            buyer_id = uuid.uuid4()
            market = self.rng.choice(markets)
            lat = round(self.rng.uniform(15.0, 22.0), 6)
            lon = round(self.rng.uniform(72.0, 81.0), 6)
            
            rows.append((
                buyer_id, f"BUY-{i+1:06d}", f"{self.rng.choice(buyer_prefixes)} {i+1}",
                self.rng.choices(buyer_types, weights=type_weights)[0], market,
                "District", "State", lat, lon, True
            ))
            buyers.append({"buyer_id": buyer_id, "buyer_type": rows[-1][3]})
        
        self._copy_from_buffer("buyers", [
            "buyer_id", "buyer_code", "buyer_name", "buyer_type", "market_name",
            "district", "state", "latitude", "longitude", "active_status"
        ], iter(rows))
        
        self._id_maps['buyers'] = buyers
        return buyers
    
    def generate_sales_orders(self, batches: List[Dict], buyers: List[Dict], count: int) -> int:
        print(f"Generating {count} sales orders...")
        
        statuses = ["delivered", "partial_delivered", "confirmed", "in_transit", "pending", "cancelled"]
        status_weights = [0.4, 0.1, 0.15, 0.1, 0.15, 0.1]
        
        # Only use batches that are not spoiled/discarded
        valid_batches = [b for b in batches if b["status"] not in ("spoiled", "discarded", "fully_sold")]
        if not valid_batches:
            print("  No valid batches for orders")
            return 0
        
        rows = []
        start_date = date(2023, 1, 1)
        end_date = date(2026, 10, 24)
        days_range = (end_date - start_date).days
        generated = 0
        
        for i in range(count):
            batch = self.rng.choice(valid_batches)
            buyer = self.rng.choice(buyers)
            order_id = uuid.uuid4()
            order_date = start_date + timedelta(days=self.rng.randint(0, days_range))
            max_qty = min(batch["quantity"], 50000)
            qty = round(self.rng.uniform(500, max_qty), 2)
            price = round(self.rng.uniform(800, 12000), 2)
            delivery_date = order_date + timedelta(days=self.rng.randint(1, 30))
            status = self.rng.choices(statuses, weights=status_weights)[0]
            
            rows.append((
                order_id, f"SO-{order_date.year}-{i+1:07d}", batch["batch_id"],
                buyer["buyer_id"], qty, price, order_date, delivery_date, status
            ))
            generated += 1
        
        self._copy_from_buffer("sales_orders", [
            "order_id", "order_code", "batch_id", "buyer_id", "quantity_kg",
            "agreed_price_inr_per_quintal", "order_date", "delivery_date", "order_status"
        ], iter(rows))
        
        return generated
    
    def generate_transport_routes(self, warehouses: List[Dict], buyers: List[Dict], count: int) -> int:
        print(f"Generating {count} transport routes...")
        
        vehicle_types = ["mini_truck_1t", "truck_5t", "truck_9t", "truck_16t",
                        "container_20ft", "container_40ft", "refrigerated_5t", "refrigerated_9t"]
        vehicle_caps = {"mini_truck_1t": 1000, "truck_5t": 5000, "truck_9t": 9000,
                       "truck_16t": 16000, "container_20ft": 20000, "container_40ft": 28000,
                       "refrigerated_5t": 5000, "refrigerated_9t": 9000}
        route_statuses = ["active", "inactive", "seasonal"]
        status_weights = [0.7, 0.2, 0.1]
        
        # Pre-compute all possible unique pairs
        all_pairs = [(w["warehouse_id"], b["buyer_id"]) for w in warehouses for b in buyers]
        max_unique = len(all_pairs)
        actual_count = min(count, max_unique)
        
        if actual_count < count:
            print(f"  Warning: Only {actual_count} unique warehouse-buyer pairs possible (requested {count})")
        
        self.rng.shuffle(all_pairs)
        selected_pairs = all_pairs[:actual_count]
        
        rows = []
        generated = 0
        
        for wh_id, buyer_id in selected_pairs:
            route_id = uuid.uuid4()
            distance = round(self.rng.uniform(10, 1200), 2)
            vehicle = self.rng.choice(vehicle_types)
            capacity = vehicle_caps[vehicle]
            fixed = round(self.rng.uniform(500, 10000), 2)
            var_cost = round(self.rng.uniform(6, 35), 2)
            
            rows.append((
                route_id, wh_id, buyer_id, distance,
                round(distance / 40, 1), vehicle, capacity, fixed, var_cost,
                self.rng.choices(route_statuses, weights=status_weights)[0]
            ))
            generated += 1
        
        self._copy_from_buffer("transport_routes", [
            "route_id", "origin_warehouse_id", "destination_buyer_id",
            "distance_km", "expected_transit_hours", "vehicle_type", "capacity_kg",
            "fixed_cost_inr", "variable_cost_inr_per_km", "route_status"
        ], iter(rows))
        
        return generated
    
    def generate_storage_costs(self, warehouses: List[Dict], crops: List[Dict], count: int) -> int:
        print(f"Generating {count} storage costs...")
        
        cost_sources = ["synthetic"]
        
        # Pre-compute all possible unique pairs
        all_pairs = [(w["warehouse_id"], c["crop_id"]) for w in warehouses for c in crops]
        max_unique = len(all_pairs)
        actual_count = min(count, max_unique)
        
        if actual_count < count:
            print(f"  Warning: Only {actual_count} unique warehouse-crop pairs possible (requested {count})")
        
        self.rng.shuffle(all_pairs)
        selected_pairs = all_pairs[:actual_count]
        
        rows = []
        generated = 0
        
        for wh_id, crop_id in selected_pairs:
            sc_id = uuid.uuid4()
            eff_from = date(2023, 1, 1)
            eff_to = date(2026, 12, 31)
            
            rows.append((
                sc_id, wh_id, crop_id, eff_from, eff_to,
                round(self.rng.uniform(0.005, 0.80), 4),
                round(self.rng.uniform(0.30, 5.00), 4),
                round(self.rng.uniform(0.01, 0.50), 4) if self.rng.random() > 0.5 else None,
                self.rng.choice(cost_sources)
            ))
            generated += 1
        
        self._copy_from_buffer("storage_costs", [
            "storage_cost_id", "warehouse_id", "crop_id", "effective_from",
            "effective_to", "storage_cost_inr_per_kg_day", "handling_cost_inr_per_kg",
            "refrigeration_cost_inr_per_kg_day", "cost_source"
        ], iter(rows))
        
        return generated
    
    def log_generation(self, stage: str, results: Dict[str, int]):
        """Log generation run to data_generation_log."""
        print(f"Logging generation run...")
        run_id = uuid.uuid4()
        now = datetime.now()
        rows = []
        for table, cnt in results.items():
            rows.append((
                run_id, stage, table,
                self.gen_config.target_counts.get(table, cnt),
                cnt, 0, "completed", None, self.gen_config.seed, now, now
            ))
        
        self._copy_from_buffer("data_generation_log", [
            "generation_run_id", "stage", "table_name", "records_target",
            "records_generated", "duration_seconds", "status", "error_message",
            "seed_used", "started_at", "completed_at"
        ], iter(rows))


def run_full_generation(target: str = "full"):
    """Run full dataset generation."""
    target_counts = {
        "integration": {
            "fpos": 20, "farmers": 5000, "farms": 8000, "crops": 40,
            "harvest_batches": 20000, "warehouses": 150, "inventory": 20000,
            "market_prices": 50000, "buyers": 800, "sales_orders": 25000,
            "transport_routes": 15000, "storage_costs": 5000,
        },
        "full": gen_config.target_counts
    }
    
    counts = target_counts.get(target, target_counts["full"])
    total = sum(counts.values())
    
    print("=" * 60)
    print(f"FPO Synthetic Data Generation - Stage {target.upper()} ({total:,} records)")
    print("=" * 60)
    
    conn = psycopg2.connect(db_config.connection_string())
    conn.autocommit = False
    print(f"Connected to {db_config.database} on {db_config.host}:{db_config.port}")
    
    try:
        # Clear existing data for both integration and full stages
        clear_tables = [
            "data_generation_log", "sales_orders", "transport_routes", "storage_costs",
            "inventory", "market_prices", "harvest_batches", "farms", "farmers",
            "warehouses", "crops", "buyers", "fpos"
        ]
        cur = conn.cursor()
        for t in clear_tables:
            cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
        conn.commit()
        cur.close()
        print("Cleared existing data for generation run")
        
        generator = FullDatasetGenerator(conn, seed=gen_config.seed)
        
        # Generate in dependency order
        fpos = generator.generate_fpos(counts["fpos"])
        crops = generator.generate_crops(counts["crops"])
        farmers = generator.generate_farmers(fpos, counts["farmers"])
        farms = generator.generate_farms(farmers, counts["farms"])
        warehouses = generator.generate_warehouses(fpos, counts["warehouses"])
        batches = generator.generate_harvest_batches(farms, crops, counts["harvest_batches"])
        inv_count = generator.generate_inventory(batches, warehouses, counts["inventory"])
        mp_count = generator.generate_market_prices(crops, counts["market_prices"])
        buyers = generator.generate_buyers(counts["buyers"])
        so_count = generator.generate_sales_orders(batches, buyers, counts["sales_orders"])
        tr_count = generator.generate_transport_routes(warehouses, buyers, counts["transport_routes"])
        sc_count = generator.generate_storage_costs(warehouses, crops, counts["storage_costs"])
        
        results = {
            "fpos": counts["fpos"], "farmers": counts["farmers"], "farms": counts["farms"],
            "crops": counts["crops"], "harvest_batches": counts["harvest_batches"],
            "warehouses": counts["warehouses"], "inventory": inv_count,
            "market_prices": mp_count, "buyers": counts["buyers"],
            "sales_orders": so_count, "transport_routes": tr_count,
            "storage_costs": sc_count,
        }
        
        generator.log_generation(target, results)
        
        print("\n" + "=" * 60)
        print(f"Stage {target.upper()} completed successfully!")
        print("=" * 60)
        for table, cnt in results.items():
            print(f"  {table}: {cnt:,} records")
        print(f"  TOTAL: {sum(results.values()):,} records")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["integration", "full"], default="integration")
    args = parser.parse_args()
    run_full_generation(args.stage)