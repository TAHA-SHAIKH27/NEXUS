"""
Configuration for FPO synthetic data generation.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str = "127.0.0.1"
    port: int = 5433
    database: str = "nexus_fpo"
    user: str = "nexus_admin"
    password: str = "nexus_local_dev"

    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class GenerationConfig:
    """Data generation parameters."""
    # Target record counts per table
    target_counts: dict = None
    
    # Random seed for reproducibility
    seed: int = 42
    
    # Batch size for bulk inserts
    batch_size: int = 1000
    
    # Date range for historical data
    start_date: str = "2023-01-01"
    end_date: str = "2026-10-24"
    
    # Geographic bounds (Maharashtra & Telangana focus)
    lat_min: float = 15.0
    lat_max: float = 22.0
    lon_min: float = 72.0
    lon_max: float = 81.0
    
    # Crop categories and their properties
    crop_data: list = None
    
    # Districts by state
    districts_by_state: dict = None
    
    def __post_init__(self):
        if self.target_counts is None:
            self.target_counts = {
                "fpos": 50,
                "farmers": 16000,
                "farms": 22000,
                "crops": 50,
                "harvest_batches": 85000,
                "warehouses": 550,
                "inventory": 85000,
                "market_prices": 195000,
                "buyers": 2200,
                "sales_orders": 88000,
                "transport_routes": 44000,
                "storage_costs": 13500,
            }
        
        if self.crop_data is None:
            self.crop_data = [
                # (crop_name, variety, category, storage_days, temp_min, temp_max, unit, perishability)
                ("Tomato", "Hybrid", "vegetable", 14, 10.0, 15.0, "kg", "highly_perishable"),
                ("Tomato", "Desi", "vegetable", 10, 10.0, 15.0, "kg", "highly_perishable"),
                ("Onion", "Red", "vegetable", 180, 25.0, 30.0, "kg", "durable"),
                ("Onion", "White", "vegetable", 150, 25.0, 30.0, "kg", "durable"),
                ("Potato", "Kufri Jyoti", "vegetable", 240, 2.0, 4.0, "kg", "durable"),
                ("Potato", "Kufri Chipsona", "vegetable", 200, 2.0, 4.0, "kg", "durable"),
                ("Banana", "Grand Naine", "fruit", 14, 13.0, 15.0, "kg", "highly_perishable"),
                ("Banana", "Robusta", "fruit", 10, 13.0, 15.0, "kg", "highly_perishable"),
                ("Grapes", "Thompson Seedless", "fruit", 21, 0.0, 1.0, "kg", "highly_perishable"),
                ("Grapes", "Sharad Seedless", "fruit", 18, 0.0, 1.0, "kg", "highly_perishable"),
                ("Pomegranate", "Bhagwa", "fruit", 60, 5.0, 7.0, "kg", "moderately_perishable"),
                ("Pomegranate", "Ganesh", "fruit", 45, 5.0, 7.0, "kg", "moderately_perishable"),
                ("Chilli", "Teja", "spice", 30, 10.0, 15.0, "kg", "moderately_perishable"),
                ("Chilli", "Byadgi", "spice", 45, 10.0, 15.0, "kg", "moderately_perishable"),
                ("Turmeric", "Salem", "spice", 365, 20.0, 25.0, "kg", "durable"),
                ("Ginger", "Rio de Janeiro", "spice", 60, 12.0, 15.0, "kg", "moderately_perishable"),
                ("Cotton", "Bt Cotton", "fiber", 365, 20.0, 30.0, "kg", "durable"),
                ("Soybean", "JS 335", "oilseed", 365, 15.0, 25.0, "kg", "durable"),
                ("Groundnut", "Kadiri", "oilseed", 365, 15.0, 25.0, "kg", "durable"),
                ("Wheat", "HD 2967", "cereal", 365, 15.0, 25.0, "kg", "durable"),
                ("Maize", "Hybrid", "cereal", 365, 15.0, 25.0, "kg", "durable"),
                ("Rice", "Basmati", "cereal", 365, 15.0, 25.0, "kg", "durable"),
                ("Mango", "Alphonso", "fruit", 21, 12.0, 14.0, "kg", "highly_perishable"),
                ("Mango", "Kesar", "fruit", 18, 12.0, 14.0, "kg", "highly_perishable"),
                ("Orange", "Nagpur", "fruit", 60, 4.0, 7.0, "kg", "moderately_perishable"),
                ("Papaya", "Red Lady", "fruit", 14, 10.0, 13.0, "kg", "highly_perishable"),
                ("Cabbage", "Golden Acre", "vegetable", 60, 0.0, 2.0, "kg", "moderately_perishable"),
                ("Cauliflower", "Pusa Snowball", "vegetable", 21, 0.0, 2.0, "kg", "highly_perishable"),
                ("Brinjal", "Pusa Purple Long", "vegetable", 14, 10.0, 12.0, "kg", "highly_perishable"),
                ("Okra", "Arka Anamika", "vegetable", 10, 10.0, 12.0, "kg", "highly_perishable"),
                ("Cucumber", "Poinsett", "vegetable", 14, 10.0, 13.0, "kg", "highly_perishable"),
            ]
        
        if self.districts_by_state is None:
            self.districts_by_state = {
                "Maharashtra": [
                    "Nashik", "Ahmednagar", "Pune", "Solapur", "Sangli", "Kolhapur",
                    "Satara", "Jalgaon", "Dhule", "Nandurbar", "Aurangabad", "Jalna",
                    "Beed", "Latur", "Osmanabad", "Nanded", "Parbhani", "Hingoli",
                    "Buldhana", "Akola", "Washim", "Amravati", "Yavatmal", "Wardha",
                    "Nagpur", "Bhandara", "Gondia", "Chandrapur", "Gadchiroli",
                    "Mumbai", "Thane", "Raigad", "Ratnagiri", "Sindhudurg"
                ],
                "Telangana": [
                    "Hyderabad", "Rangareddy", "Medchal", "Vikarabad", "Sangareddy",
                    "Medak", "Siddipet", "Kamareddy", "Nizamabad", "Jagtial",
                    "Peddapalli", "Karimnagar", "Rajanna Sircilla", "Jayashankar",
                    "Mahabubabad", "Warangal", "Warangal Rural", "Mulugu",
                    "Bhadradri Kothagudem", "Khammam", "Mahabubnagar", "Jogulamba",
                    "Nagarkurnool", "Wanaparthy", "Narayanpet", "Adilabad",
                    "Kumuram Bheem", "Mancherial", "Nirmal"
                ],
                "Karnataka": [
                    "Bengaluru Urban", "Bengaluru Rural", "Ramanagara", "Kolar",
                    "Chikkaballapura", "Tumakuru", "Chitradurga", "Davanagere",
                    "Ballari", "Vijayanagara", "Koppal", "Raichur", "Yadgir",
                    "Kalaburagi", "Bidar", "Belagavi", "Bagalkote", "Vijayapura",
                    "Dharwad", "Gadag", "Haveri", "Uttara Kannada", "Shivamogga",
                    "Chikkamagaluru", "Hassan", "Kodagu", "Mysuru", "Mandya",
                    "Chamarajanagara"
                ]
            }

# Global config instances
db_config = DatabaseConfig()
gen_config = GenerationConfig()