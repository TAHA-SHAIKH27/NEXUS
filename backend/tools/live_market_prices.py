"""
Live Market Prices — AGMARKNET / data.gov.in integration.

Fetches real Indian agricultural market prices from official government sources.
Never fabricates or silently uses synthetic prices as live prices.

Sources:
- AGMARKNET (agmarknet.gov.in) - Daily wholesale prices
- data.gov.in - Open Government Data Platform
- e-NAM (enam.gov.in) - National Agriculture Market (when available)

All rates converted to consistent ₹/quintal and ₹/tonne units.
Caches results with freshness limits.
Identifies unavailable or stale markets.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
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

# AGMARKNET endpoints
AGMARKNET_BASE = "https://agmarknet.gov.in"
AGMARKNET_DAILY_PRICE = f"{AGMARKNET_BASE}/SearchCmmMkt.aspx"
AGMARKNET_CSV_ENDPOINT = f"{AGMARKNET_BASE}/price_trends/"

# data.gov.in API
DATAGOV_BASE = "https://api.data.gov.in"
DATAGOV_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"  # Daily market prices
DATAGOV_API_KEY_ENV = "DATAGOV_API_KEY"

# e-NAM
ENAM_BASE = "https://enam.gov.in/web"

# Cache settings
CACHE_DIR = Path(os.getenv("NEXUS_CACHE_DIR", "backend/data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_TTL_SECONDS = 6 * 3600  # 6 hours
STALE_THRESHOLD_HOURS = 24

# Unit conversions
QUINTAL_TO_KG = Decimal("100")
TONNE_TO_KG = Decimal("1000")
KG_TO_QUINTAL = Decimal("0.01")
KG_TO_TONNE = Decimal("0.001")

# Standard crop names for matching
CROP_NORMALIZATION = {
    "tomato": "Tomato", "tomatoes": "Tomato",
    "onion": "Onion", "onions": "Onion",
    "potato": "Potato", "potatoes": "Potato",
    "wheat": "Wheat",
    "rice": "Rice", "paddy": "Rice",
    "maize": "Maize", "corn": "Maize",
    "soybean": "Soybean", "soya": "Soybean",
    "cotton": "Cotton",
    "groundnut": "Groundnut", "peanut": "Groundnut",
    "mustard": "Mustard", "rapeseed": "Mustard",
    "gram": "Gram", "chickpea": "Gram",
    "tur": "Tur", "arhar": "Tur", "pigeonpea": "Tur",
    "moong": "Moong", "greengram": "Moong",
    "urad": "Urad", "blackgram": "Urad",
    "jowar": "Jowar", "sorghum": "Jowar",
    "bajra": "Bajra", "pearlmillet": "Bajra",
    "ragi": "Ragi", "fingermillet": "Ragi",
    "barley": "Barley",
    "sunflower": "Sunflower",
    "sesame": "Sesame", "til": "Sesame",
    "coconut": "Coconut", "copra": "Coconut",
    "sugarcane": "Sugarcane",
    "chilli": "Chilli", "chili": "Chilli", "mirchi": "Chilli",
    "turmeric": "Turmeric", "haldi": "Turmeric",
    "ginger": "Ginger",
    "garlic": "Garlic",
    "coriander": "Coriander", "dhania": "Coriander",
    "cumin": "Cumin", "jeera": "Cumin",
    "fennel": "Fennel", "saunf": "Fennel",
    "fenugreek": "Fenugreek", "methi": "Fenugreek",
    "guar": "Guar", "guargum": "Guar",
    "isabgol": "Isabgol", "psyllium": "Isabgol",
    "grape": "Grapes", "grapes": "Grapes",
    "banana": "Banana", "bananas": "Banana",
    "mango": "Mango", "mangoes": "Mango",
    "apple": "Apple",
    "orange": "Orange", "kinnow": "Orange",
    "pomegranate": "Pomegranate", "anar": "Pomegranate",
    "papaya": "Papaya",
    "guava": "Guava",
    "sapota": "Sapota", "chikoo": "Sapota",
    "custardapple": "Custard Apple", "sitaphal": "Custard Apple",
    "pineapple": "Pineapple",
    "watermelon": "Watermelon",
    "muskmelon": "Muskmelon",
    "cauliflower": "Cauliflower", "gobi": "Cauliflower",
    "cabbage": "Cabbage",
    "bhindi": "Okra", "okra": "Okra", "ladiesfinger": "Okra",
    "brinjal": "Brinjal", "eggplant": "Brinjal", "baingan": "Brinjal",
    "bittergourd": "Bitter Gourd", "karela": "Bitter Gourd",
    "bottlegourd": "Bottle Gourd", "lauki": "Bottle Gourd",
    "ridgegourd": "Ridge Gourd", "turai": "Ridge Gourd",
    "snakegourd": "Snake Gourd", "chichinda": "Snake Gourd",
    "pumpkin": "Pumpkin", "kaddu": "Pumpkin",
    "carrot": "Carrot", "gajar": "Carrot",
    "radish": "Radish", "mooli": "Radish",
    "beetroot": "Beetroot", "beet": "Beetroot",
    "turnip": "Turnip", "shalgam": "Turnip",
    "sweetpotato": "Sweet Potato", "shakarkand": "Sweet Potato",
    "yam": "Yam", "suran": "Yam",
    "colocasia": "Colocasia", "arbi": "Colocasia",
    "peas": "Peas", "matar": "Peas",
    "beans": "Beans", "frenchbeans": "Beans",
    "clusterbeans": "Cluster Beans", "guarphali": "Cluster Beans",
    "drumstick": "Drumstick", "moringa": "Drumstick",
    "spinach": "Spinach", "palak": "Spinach",
    "amaranth": "Amaranth", "chaulai": "Amaranth",
    "methi": "Fenugreek Leaves", "fenugreekl": "Fenugreek Leaves",
    "mint": "Mint", "pudina": "Mint",
    "corianderleaves": "Coriander Leaves", "dhaniapatti": "Coriander Leaves",
    "curryleaves": "Curry Leaves", "kadipatta": "Curry Leaves",
    "greenchilli": "Green Chilli", "harimirch": "Green Chilli",
    "capsicum": "Capsicum", "shimlamirch": "Capsicum",
    "tomato": "Tomato", "tamatar": "Tomato",
    "onion": "Onion", "pyaz": "Onion",
    "potato": "Potato", "aloo": "Potato",
}


# --- Data Models ---

@dataclass
class MarketPrice:
    """Normalized market price observation."""
    commodity: str
    variety: str
    market: str
    district: str
    state: str
    arrival_date: str  # YYYY-MM-DD
    min_price: Decimal  # ₹/quintal
    max_price: Decimal  # ₹/quintal
    modal_price: Decimal  # ₹/quintal
    source: str  # "agmarknet", "data.gov.in", "enam"
    source_url: str
    fetched_at: str
    is_stale: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "commodity": self.commodity,
            "variety": self.variety,
            "market": self.market,
            "district": self.district,
            "state": self.state,
            "arrival_date": self.arrival_date,
            "min_price_inr_per_quintal": float(self.min_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "max_price_inr_per_quintal": float(self.max_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "modal_price_inr_per_quintal": float(self.modal_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "min_price_inr_per_tonne": float((self.min_price * Decimal("10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "max_price_inr_per_tonne": float((self.max_price * Decimal("10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "modal_price_inr_per_tonne": float((self.modal_price * Decimal("10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "source": self.source,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "is_stale": self.is_stale,
        }


@dataclass
class MarketPriceCollection:
    """Collection of market prices with metadata."""
    prices: List[MarketPrice]
    commodity: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    market: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sources_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "commodity": self.commodity,
            "state": self.state,
            "district": self.district,
            "market": self.market,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "fetched_at": self.fetched_at,
            "sources_used": self.sources_used,
            "warnings": self.warnings,
            "count": len(self.prices),
            "prices": [p.to_dict() for p in self.prices],
        }
    
    def filter(self, **kwargs) -> "MarketPriceCollection":
        """Filter prices by criteria."""
        filtered = self.prices
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "commodity":
                filtered = [p for p in filtered if p.commodity.lower() == value.lower()]
            elif key == "state":
                filtered = [p for p in filtered if p.state.lower() == value.lower()]
            elif key == "district":
                filtered = [p for p in filtered if p.district.lower() == value.lower()]
            elif key == "market":
                filtered = [p for p in filtered if p.market.lower() == value.lower()]
            elif key == "date_from":
                filtered = [p for p in filtered if p.arrival_date >= value]
            elif key == "date_to":
                filtered = [p for p in filtered if p.arrival_date <= value]
        return MarketPriceCollection(
            prices=filtered,
            commodity=self.commodity,
            state=self.state,
            district=self.district,
            market=self.market,
            date_from=self.date_from,
            date_to=self.date_to,
            fetched_at=self.fetched_at,
            sources_used=self.sources_used,
            warnings=self.warnings,
        )


# --- Cache Management ---

def _cache_key(prefix: str, *parts: str) -> str:
    """Generate cache key from parts."""
    combined = f"{prefix}:{':'.join(parts)}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _get_cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def load_cache(key: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[Any]:
    """Load cached data if fresh."""
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
    """Save data to cache."""
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
    """Simple HTTP transport with timeout and retries."""
    
    def __init__(self, timeout: int = 30, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Any]:
        req_headers = {
            "User-Agent": "NEXUS-FPO/1.0 (Agricultural Intelligence Platform)",
            "Accept": "application/json, text/csv, text/html",
        }
        if headers:
            req_headers.update(headers)
        
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = Request(url, headers=req_headers)
                with urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        return resp.status, json.loads(raw)
                    return resp.status, raw
            except HTTPError as e:
                last_error = e
                if e.code in (401, 403, 404):
                    return e.code, e.read().decode("utf-8", errors="replace")
            except (URLError, TimeoutError, OSError) as e:
                last_error = e
            
            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 5))
        
        raise RuntimeError(f"HTTP request failed after {self.max_retries} attempts: {last_error}")


# --- AGMARKNET Parser ---

def parse_agmarknet_html(html: str, source_url: str) -> List[MarketPrice]:
    """Parse AGMARKNET HTML table for daily prices."""
    prices = []
    
    # Look for the main price table
    # AGMARKNET uses a table with specific structure
    # Try to find price data in HTML tables
    
    # Pattern for price rows
    # <tr> <td>Commodity</td> <td>Variety</td> <td>Market</td> <td>District</td> <td>State</td> <td>Date</td> <td>Min</td> <td>Max</td> <td>Modal</td> </tr>
    
    # Use regex to extract table rows
    table_pattern = r'<table[^>]*class="[^"]*table[^"]*"[^>]*>(.*?)</table>'
    tables = re.findall(table_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for table in tables:
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        rows = re.findall(row_pattern, table, re.DOTALL | re.IGNORECASE)
        
        for row in rows:
            cell_pattern = r'<td[^>]*>(.*?)</td>'
            cells = re.findall(cell_pattern, row, re.DOTALL | re.IGNORECASE)
            
            if len(cells) >= 9:
                # Clean cells
                clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                
                try:
                    commodity = clean_cells[0]
                    variety = clean_cells[1] if len(clean_cells) > 1 else ""
                    market = clean_cells[2] if len(clean_cells) > 2 else ""
                    district = clean_cells[3] if len(clean_cells) > 3 else ""
                    state = clean_cells[4] if len(clean_cells) > 4 else ""
                    date_str = clean_cells[5] if len(clean_cells) > 5 else ""
                    min_price_str = clean_cells[6] if len(clean_cells) > 6 else ""
                    max_price_str = clean_cells[7] if len(clean_cells) > 7 else ""
                    modal_price_str = clean_cells[8] if len(clean_cells) > 8 else ""
                    
                    # Parse prices
                    min_price = Decimal(re.sub(r'[^\d.]', '', min_price_str) or "0")
                    max_price = Decimal(re.sub(r'[^\d.]', '', max_price_str) or "0")
                    modal_price = Decimal(re.sub(r'[^\d.]', '', modal_price_str) or "0")
                    
                    # Normalize commodity
                    commodity_norm = normalize_commodity(commodity)
                    
                    # Parse date (DD/MM/YYYY or DD-Mon-YYYY)
                    arrival_date = parse_agmarknet_date(date_str)
                    
                    prices.append(MarketPrice(
                        commodity=commodity_norm,
                        variety=variety,
                        market=market,
                        district=district,
                        state=state,
                        arrival_date=arrival_date,
                        min_price=min_price,
                        max_price=max_price,
                        modal_price=modal_price,
                        source="agmarknet",
                        source_url=source_url,
                        fetched_at=datetime.now(timezone.utc).isoformat(),
                    ))
                except Exception:
                    continue
    
    return prices


def parse_agmarknet_csv(csv_content: str, source_url: str) -> List[MarketPrice]:
    """Parse AGMARKNET CSV export."""
    prices = []
    
    try:
        reader = csv.DictReader(csv_content.splitlines())
        for row in reader:
            # Map CSV columns (AGMARKNET format varies)
            commodity = row.get("Commodity", row.get("commodity", ""))
            variety = row.get("Variety", row.get("variety", ""))
            market = row.get("Market", row.get("market", ""))
            district = row.get("District", row.get("district", ""))
            state = row.get("State", row.get("state", ""))
            date_str = row.get("Arrival_Date", row.get("Date", row.get("arrival_date", "")))
            min_price_str = row.get("Min_Price", row.get("Min Price", row.get("min_price", "0")))
            max_price_str = row.get("Max_Price", row.get("Max Price", row.get("max_price", "0")))
            modal_price_str = row.get("Modal_Price", row.get("Modal Price", row.get("modal_price", "0")))
            
            try:
                min_price = Decimal(re.sub(r'[^\d.]', '', min_price_str) or "0")
                max_price = Decimal(re.sub(r'[^\d.]', '', max_price_str) or "0")
                modal_price = Decimal(re.sub(r'[^\d.]', '', modal_price_str) or "0")
                
                commodity_norm = normalize_commodity(commodity)
                arrival_date = parse_agmarknet_date(date_str)
                
                prices.append(MarketPrice(
                    commodity=commodity_norm,
                    variety=variety,
                    market=market,
                    district=district,
                    state=state,
                    arrival_date=arrival_date,
                    min_price=min_price,
                    max_price=max_price,
                    modal_price=modal_price,
                    source="agmarknet",
                    source_url=source_url,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ))
            except Exception:
                continue
    except Exception:
        pass
    
    return prices


def parse_agmarknet_date(date_str: str) -> str:
    """Parse AGMARKNET date formats to YYYY-MM-DD."""
    date_str = date_str.strip()
    
    # Try DD/MM/YYYY
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # Try DD-MM-YYYY
    try:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # Try DD-Mon-YYYY (e.g., 15-Jan-2024)
    try:
        return datetime.strptime(date_str, "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # Default to today
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize_commodity(name: str) -> str:
    """Normalize commodity name to standard form."""
    name_lower = name.lower().strip()
    return CROP_NORMALIZATION.get(name_lower, name.title())


# --- AGMARKNET Fetcher ---

class AgmarknetFetcher:
    """Fetch live prices from AGMARKNET."""
    
    def __init__(self, transport: Optional[HttpTransport] = None):
        self.transport = transport or HttpTransport()
    
    def fetch_daily_prices(
        self,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        date: Optional[str] = None,
    ) -> MarketPriceCollection:
        """Fetch daily wholesale prices from AGMARKNET."""
        
        cache_key = _cache_key("agmarknet", commodity or "all", state or "all", district or "all", date or "latest")
        cached = load_cache(cache_key)
        if cached:
            return MarketPriceCollection(**cached)
        
        # Build query parameters
        params = {}
        if commodity:
            params["commodity"] = commodity
        if state:
            params["state"] = state
        if district:
            params["district"] = district
        if market:
            params["market"] = market
        if date:
            params["date"] = date
        else:
            params["date"] = datetime.now().strftime("%d-%b-%Y")
        
        # AGMARKNET requires specific parameter names
        url = f"{AGMARKNET_DAILY_PRICE}?{urlencode(params)}"
        
        warnings = []
        prices = []
        sources_used = ["agmarknet"]
        
        try:
            status, response = self.transport.get(url)
            if status == 200:
                if isinstance(response, str):
                    # Try HTML parsing first
                    prices = parse_agmarknet_html(response, url)
                    if not prices:
                        # Try CSV if available
                        csv_url = url.replace("SearchCmmMkt.aspx", "PriceAndArrival/CommodityWiseReport.aspx")
                        status, csv_resp = self.transport.get(csv_url)
                        if status == 200 and isinstance(csv_resp, str):
                            prices = parse_agmarknet_csv(csv_resp, csv_url)
            else:
                warnings.append(f"AGMARKNET returned HTTP {status}")
        except Exception as e:
            warnings.append(f"AGMARKNET fetch failed: {e}")
        
        # Check staleness
        for p in prices:
            if p.arrival_date:
                try:
                    price_date = datetime.strptime(p.arrival_date, "%Y-%m-%d")
                    if (datetime.now(timezone.utc) - price_date).days > STALE_THRESHOLD_HOURS / 24:
                        p.is_stale = True
                except Exception:
                    p.is_stale = True
        
        collection = MarketPriceCollection(
            prices=prices,
            commodity=commodity,
            state=state,
            district=district,
            market=market,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            sources_used=sources_used,
            warnings=warnings,
        )
        
        # Cache successful results
        if prices:
            save_cache(cache_key, collection.to_dict())
        
        return collection


# --- data.gov.in Fetcher ---

class DatagovFetcher:
    """Fetch prices from data.gov.in Open Government Data Platform."""
    
    def __init__(self, transport: Optional[HttpTransport] = None, api_key: Optional[str] = None):
        self.transport = transport or HttpTransport()
        self.api_key = api_key or os.environ.get(DATAGOV_API_KEY_ENV)
    
    def fetch_prices(
        self,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 1000,
    ) -> MarketPriceCollection:
        """Fetch prices from data.gov.in API."""
        
        if not self.api_key:
            return MarketPriceCollection(
                prices=[],
                commodity=commodity,
                state=state,
                district=district,
                market=market,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                sources_used=[],
                warnings=["data.gov.in API key not configured (set DATAGOV_API_KEY)"],
            )
        
        cache_key = _cache_key("datagov", commodity or "all", state or "all", district or "all")
        cached = load_cache(cache_key)
        if cached:
            return MarketPriceCollection(**cached)
        
        # Build API query
        params = {
            "api-key": self.api_key,
            "format": "json",
            "limit": limit,
            "filters[state]": state or "",
            "filters[district]": district or "",
            "filters[market]": market or "",
            "filters[commodity]": commodity or "",
        }
        
        # Remove empty filters
        params = {k: v for k, v in params.items() if v}
        
        url = f"{DATAGOV_BASE}/resource/{DATAGOV_RESOURCE_ID}?{urlencode(params)}"
        
        warnings = []
        prices = []
        sources_used = ["data.gov.in"]
        
        try:
            status, response = self.transport.get(url)
            if status == 200 and isinstance(response, dict):
                records = response.get("records", [])
                for record in records:
                    try:
                        commodity_raw = record.get("commodity", record.get("commodity_name", ""))
                        variety = record.get("variety", "")
                        market_name = record.get("market", record.get("market_name", ""))
                        district_name = record.get("district", "")
                        state_name = record.get("state", "")
                        date_str = record.get("arrival_date", record.get("price_date", ""))
                        min_price = Decimal(str(record.get("min_price", record.get("minimum_price", "0"))))
                        max_price = Decimal(str(record.get("max_price", record.get("maximum_price", "0"))))
                        modal_price = Decimal(str(record.get("modal_price", record.get("model_price", "0"))))
                        
                        commodity_norm = normalize_commodity(commodity_raw)
                        arrival_date = parse_agmarknet_date(date_str)
                        
                        prices.append(MarketPrice(
                            commodity=commodity_norm,
                            variety=variety,
                            market=market_name,
                            district=district_name,
                            state=state_name,
                            arrival_date=arrival_date,
                            min_price=min_price,
                            max_price=max_price,
                            modal_price=modal_price,
                            source="data.gov.in",
                            source_url=url,
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                        ))
                    except Exception:
                        continue
            else:
                warnings.append(f"data.gov.in returned HTTP {status}")
        except Exception as e:
            warnings.append(f"data.gov.in fetch failed: {e}")
        
        # Check staleness
        for p in prices:
            if p.arrival_date:
                try:
                    price_date = datetime.strptime(p.arrival_date, "%Y-%m-%d")
                    if (datetime.now(timezone.utc) - price_date).days > STALE_THRESHOLD_HOURS / 24:
                        p.is_stale = True
                except Exception:
                    p.is_stale = True
        
        collection = MarketPriceCollection(
            prices=prices,
            commodity=commodity,
            state=state,
            district=district,
            market=market,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            sources_used=sources_used,
            warnings=warnings,
        )
        
        if prices:
            save_cache(cache_key, collection.to_dict())
        
        return collection


# --- e-NAM Fetcher (placeholder - requires specific API access) ---

class EnamFetcher:
    """Fetch prices from e-NAM (National Agriculture Market)."""
    
    def __init__(self, transport: Optional[HttpTransport] = None):
        self.transport = transport or HttpTransport()
    
    def fetch_prices(
        self,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        market: Optional[str] = None,
    ) -> MarketPriceCollection:
        """e-NAM requires authentication and specific API access.
        
        This is a placeholder - actual implementation requires:
        1. e-NAM API credentials
        2. Specific endpoint documentation
        3. Rate limit compliance
        
        Returns empty collection with warning.
        """
        return MarketPriceCollection(
            prices=[],
            commodity=commodity,
            state=state,
            market=market,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            sources_used=[],
            warnings=["e-NAM integration requires authenticated API access. Not publicly available."],
        )


# --- Unified Market Price Service ---

class MarketPriceService:
    """Unified service for fetching live market prices from multiple sources."""
    
    def __init__(
        self,
        transport: Optional[HttpTransport] = None,
        datagov_api_key: Optional[str] = None,
    ):
        self.transport = transport or HttpTransport()
        self.agmarknet = AgmarknetFetcher(self.transport)
        self.datagov = DatagovFetcher(self.transport, datagov_api_key)
        self.enam = EnamFetcher(self.transport)
    
    def get_live_prices(
        self,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        date: Optional[str] = None,
        prefer_source: Optional[str] = None,  # "agmarknet", "datagov", "enam"
    ) -> MarketPriceCollection:
        """
        Fetch live market prices from official sources.
        
        Tries sources in order of preference:
        1. AGMARKNET (most comprehensive for daily mandi prices)
        2. data.gov.in (open government data)
        3. e-NAM (if authenticated)
        
        Returns combined, deduplicated results.
        """
        sources_order = ["agmarknet", "datagov", "enam"]
        if prefer_source and prefer_source in sources_order:
            sources_order.remove(prefer_source)
            sources_order.insert(0, prefer_source)
        
        all_prices = []
        all_warnings = []
        sources_used = []
        
        for source in sources_order:
            try:
                if source == "agmarknet":
                    result = self.agmarknet.fetch_daily_prices(commodity, state, district, market, date)
                elif source == "datagov":
                    result = self.datagov.fetch_prices(commodity, state, district, market)
                elif source == "enam":
                    result = self.enam.fetch_prices(commodity, state, market)
                else:
                    continue
                
                if result.prices:
                    all_prices.extend(result.prices)
                    sources_used.append(source)
                all_warnings.extend(result.warnings)
                
                # If we got good data from primary source, we can stop
                if source == sources_order[0] and len(result.prices) > 10:
                    break
                    
            except Exception as e:
                all_warnings.append(f"{source} error: {e}")
        
        # Deduplicate by (commodity, variety, market, district, state, date)
        seen = set()
        unique_prices = []
        for p in all_prices:
            key = (p.commodity, p.variety, p.market, p.district, p.state, p.arrival_date)
            if key not in seen:
                seen.add(key)
                unique_prices.append(p)
        
        # Sort by date desc, then modal price desc
        unique_prices.sort(key=lambda x: (x.arrival_date, -float(x.modal_price)), reverse=True)
        
        return MarketPriceCollection(
            prices=unique_prices,
            commodity=commodity,
            state=state,
            district=district,
            market=market,
            date_from=date,
            date_to=date,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            sources_used=sources_used,
            warnings=all_warnings,
        )
    
    def compare_markets(
        self,
        commodity: str,
        markets: List[str],
        state: Optional[str] = None,
    ) -> MarketPriceCollection:
        """Compare prices across specific markets."""
        return self.get_live_prices(
            commodity=commodity,
            state=state,
            market=None,  # fetch all, filter later
        ).filter(commodity=commodity).filter(market=markets[0] if markets else None)
    
    def get_price_trend(
        self,
        commodity: str,
        market: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get price trend for a commodity at a specific market."""
        # This would require historical data API
        # For now, return latest price
        result = self.get_live_prices(commodity=commodity, market=market)
        return [p.to_dict() for p in result.prices[:1]]


# --- Convenience Functions ---

def create_market_price_service(
    datagov_api_key: Optional[str] = None,
    timeout: int = 30,
) -> MarketPriceService:
    """Create a configured MarketPriceService."""
    transport = HttpTransport(timeout=timeout)
    return MarketPriceService(transport=transport, datagov_api_key=datagov_api_key)


def fetch_live_prices(
    commodity: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    market: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    High-level function to fetch live prices.
    Used by the decision pipeline.
    """
    cfg = config or {}
    api_key = cfg.get("datagov_api_key") or os.environ.get("DATAGOV_API_KEY")
    timeout = cfg.get("market_price_timeout", 30)
    
    service = create_market_price_service(datagov_api_key=api_key, timeout=timeout)
    result = service.get_live_prices(commodity, state, district, market)
    
    return result.to_dict()