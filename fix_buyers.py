import re

with open('database/generators/generate_corrected.py', 'r') as f:
    content = f.read()

# Find and replace the generate_buyers function
old = '''    def generate_buyers(self, count: int) -> List[Dict]:
        print(f"Generating {count} buyers...")
        
        buyer_prefixes = ["AgriTrade", "FreshMart", "GreenFields", "HarvestHub", "CropConnect",
                         "FarmFresh", "AgroMart", "NatureBasket", "FieldToFork", "CropKing",
                         "WholesaleCo", "ProduceHub", "MarketLink", "FarmDirect", "AgriLink",
                         "GlobalExports", "DomesticTrade", "RetailChain", "ProcessorCorp", "InstitutionalBuyer"]
        buyer_types = ["wholesaler", "processor", "retailer", "exporter", "institutional", "commission_agent"]
        type_weights = [0.30, 0.20, 0.15, 0.10, 0.15, 0.10]
        markets = ["Lasalgaon", "Pimpalgaon", "Nashik", "Ahmednagar", "Pune", "Solapur",
                   "Hyderabad", "Warangal", "Nizamabad", "Bengaluru", "Mysuru", "Davanagere",
                   "Sangli", "Kolhapur", "Satara", "Jalgaon", "Dhule", "Aurangabad"]
        
        rows = []
        buyers = []
        for i in range(count):
            buyer_id = uuid.uuid4()
            market = self.rng.choice(markets)
            lat = round(self.rng.uniform(15.0, 22.0), 6)
            lon = round(self.rng.uniform(72.0, 81.0), 6)
            
            rows.append([
                buyer_id, f"BUY-{i+1:06d}", f"{self.rng.choice(buyer_prefixes)} {i+1}",
                self.rng.choices(buyer_types, weights=type_weights)[0], market,
                district, state, lat, lon, True
            ])'''

new = '''    def generate_buyers(self, count: int) -> List[Dict]:
        print(f"Generating {count} buyers...")
        
        buyer_prefixes = ["AgriTrade", "FreshMart", "GreenFields", "HarvestHub", "CropConnect",
                         "FarmFresh", "AgroMart", "NatureBasket", "FieldToFork", "CropKing",
                         "WholesaleCo", "ProduceHub", "MarketLink", "FarmDirect", "AgriLink",
                         "GlobalExports", "DomesticTrade", "RetailChain", "ProcessorCorp", "InstitutionalBuyer"]
        buyer_types = ["wholesaler", "processor", "retailer", "exporter", "institutional", "commission_agent"]
        type_weights = [0.30, 0.20, 0.15, 0.10, 0.15, 0.10]
        markets = [
            ("Lasalgaon", "Nashik", "Maharashtra"), ("Pimpalgaon", "Nashik", "Maharashtra"),
            ("Nashik", "Nashik", "Maharashtra"), ("Ahmednagar", "Ahmednagar", "Maharashtra"),
            ("Pune", "Pune", "Maharashtra"), ("Solapur", "Solapur", "Maharashtra"),
            ("Sangli", "Sangli", "Maharashtra"), ("Kolhapur", "Kolhapur", "Maharashtra"),
            ("Hyderabad", "Hyderabad", "Telangana"), ("Warangal", "Warangal", "Telangana"),
            ("Nizamabad", "Nizamabad", "Telangana"), ("Khammam", "Khammam", "Telangana"),
            ("Bengaluru", "Bengaluru Urban", "Karnataka"), ("Mysuru", "Mysuru", "Karnataka"),
            ("Davanagere", "Davanagere", "Karnataka"), ("Ballari", "Ballari", "Karnataka"),
            ("Satara", "Satara", "Maharashtra"), ("Jalgaon", "Jalgaon", "Maharashtra"),
            ("Dhule", "Dhule", "Maharashtra"), ("Aurangabad", "Aurangabad", "Maharashtra"),
        ]
        
        rows = []
        buyers = []
        for i in range(count):
            buyer_id = uuid.uuid4()
            market, district, state = self.rng.choice(markets)
            lat = round(self.rng.uniform(15.0, 22.0), 6)
            lon = round(self.rng.uniform(72.0, 81.0), 6)
            
            rows.append([
                buyer_id, f"BUY-{i+1:06d}", f"{self.rng.choice(buyer_prefixes)} {i+1}",
                self.rng.choices(buyer_types, weights=type_weights)[0], market,
                district, state, lat, lon, True
            ])'''

if old in content:
    content = content.replace(old, new)
    with open('database/generators/generate_corrected.py', 'w') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Old text not found')
    # Print the actual content around that area
    idx = content.find('def generate_buyers')
    if idx >= 0:
        print(content[idx:idx+1500])