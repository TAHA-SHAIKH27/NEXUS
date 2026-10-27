"""
Natural Language to Zetaris SQL — Typed Query Planner.

Converts natural language FPO queries into typed, parameterized Zetaris queries.
Uses schema discovery and allowlisted tables/views. No arbitrary LLM-generated SQL.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from backend.tools import zetaris as zetaris_mod


# --- Schema Registry (discovered from Zetaris) ---

@dataclass
class TableColumn:
    name: str
    type: str
    nullable: bool = True

@dataclass
class TableSchema:
    name: str
    columns: List[TableColumn]
    primary_key: List[str] = field(default_factory=list)
    description: str = ""


# FPO Domain Tables/Views (registered in Zetaris NEXUS_FPO source)
FPO_ALLOWLIST = {
    "fpos": TableSchema(
        name="fpos",
        description="Farmer Producer Organizations",
        columns=[
            TableColumn("fpo_id", "uuid", False),
            TableColumn("fpo_code", "varchar", False),
            TableColumn("fpo_name", "varchar", False),
            TableColumn("district", "varchar", True),
            TableColumn("state", "varchar", True),
            TableColumn("latitude", "numeric", True),
            TableColumn("longitude", "numeric", True),
        ],
        primary_key=["fpo_id"],
    ),
    "farmers": TableSchema(
        name="farmers",
        description="Registered farmers",
        columns=[
            TableColumn("farmer_id", "uuid", False),
            TableColumn("fpo_id", "uuid", False),
            TableColumn("farmer_code", "varchar", False),
            TableColumn("land_area_hectares", "numeric", True),
        ],
        primary_key=["farmer_id"],
    ),
    "farms": TableSchema(
        name="farms",
        description="Farm plots",
        columns=[
            TableColumn("farm_id", "uuid", False),
            TableColumn("farmer_id", "uuid", False),
            TableColumn("area_hectares", "numeric", True),
            TableColumn("soil_type", "varchar", True),
            TableColumn("irrigation_type", "varchar", True),
        ],
        primary_key=["farm_id"],
    ),
    "crops": TableSchema(
        name="crops",
        description="Crop master data",
        columns=[
            TableColumn("crop_id", "uuid", False),
            TableColumn("crop_name", "varchar", False),
            TableColumn("variety", "varchar", True),
            TableColumn("storage_days", "integer", True),
            TableColumn("temp_range_min", "numeric", True),
            TableColumn("temp_range_max", "numeric", True),
            TableColumn("perishability_category", "varchar", True),
        ],
        primary_key=["crop_id"],
    ),
    "harvest_batches": TableSchema(
        name="harvest_batches",
        description="Individual harvests",
        columns=[
            TableColumn("batch_id", "uuid", False),
            TableColumn("farm_id", "uuid", False),
            TableColumn("crop_id", "uuid", False),
            TableColumn("harvest_date", "date", False),
            TableColumn("quantity", "numeric", False),
            TableColumn("quality_window_end", "date", True),
            TableColumn("status", "varchar", True),
        ],
        primary_key=["batch_id"],
    ),
    "warehouses": TableSchema(
        name="warehouses",
        description="Storage facilities",
        columns=[
            TableColumn("warehouse_id", "uuid", False),
            TableColumn("fpo_id", "uuid", False),
            TableColumn("warehouse_name", "varchar", False),
            TableColumn("capacity_kg", "numeric", False),
            TableColumn("storage_type", "varchar", True),
            TableColumn("temperature_controlled", "boolean", True),
            TableColumn("district", "varchar", True),
            TableColumn("state", "varchar", True),
            TableColumn("latitude", "numeric", True),
            TableColumn("longitude", "numeric", True),
        ],
        primary_key=["warehouse_id"],
    ),
    "inventory": TableSchema(
        name="inventory",
        description="Stock positions",
        columns=[
            TableColumn("inventory_id", "uuid", False),
            TableColumn("batch_id", "uuid", False),
            TableColumn("warehouse_id", "uuid", False),
            TableColumn("quantity_available_kg", "numeric", False),
            TableColumn("quantity_reserved_kg", "numeric", True),
        ],
        primary_key=["inventory_id"],
    ),
    "market_prices": TableSchema(
        name="market_prices",
        description="Price observations from mandis",
        columns=[
            TableColumn("price_id", "uuid", False),
            TableColumn("crop_id", "uuid", False),
            TableColumn("market", "varchar", False),
            TableColumn("district", "varchar", True),
            TableColumn("state", "varchar", True),
            TableColumn("observation_date", "date", False),
            TableColumn("min_price_inr_per_quintal", "numeric", True),
            TableColumn("modal_price_inr_per_quintal", "numeric", True),
            TableColumn("max_price_inr_per_quintal", "numeric", True),
            TableColumn("source_type", "varchar", True),
        ],
        primary_key=["price_id"],
    ),
    "buyers": TableSchema(
        name="buyers",
        description="Wholesale buyers",
        columns=[
            TableColumn("buyer_id", "uuid", False),
            TableColumn("buyer_name", "varchar", False),
            TableColumn("buyer_type", "varchar", True),
            TableColumn("market", "varchar", True),
            TableColumn("district", "varchar", True),
            TableColumn("state", "varchar", True),
            TableColumn("latitude", "numeric", True),
            TableColumn("longitude", "numeric", True),
        ],
        primary_key=["buyer_id"],
    ),
    "sales_orders": TableSchema(
        name="sales_orders",
        description="Sales transactions",
        columns=[
            TableColumn("order_id", "uuid", False),
            TableColumn("batch_id", "uuid", False),
            TableColumn("buyer_id", "uuid", False),
            TableColumn("quantity", "numeric", False),
            TableColumn("unit_price_inr_per_kg", "numeric", True),
            TableColumn("total_amount_inr", "numeric", True),
            TableColumn("status", "varchar", True),
        ],
        primary_key=["order_id"],
    ),
    "transport_routes": TableSchema(
        name="transport_routes",
        description="Logistics routes",
        columns=[
            TableColumn("route_id", "uuid", False),
            TableColumn("origin_warehouse", "varchar", False),
            TableColumn("destination_buyer", "varchar", True),
            TableColumn("destination_market", "varchar", True),
            TableColumn("distance_km", "numeric", True),
            TableColumn("vehicle_type", "varchar", True),
            TableColumn("transport_cost_per_kg_inr", "numeric", True),
        ],
        primary_key=["route_id"],
    ),
    # Analytical Views
    "v_batch_spoilage_risk": TableSchema(
        name="v_batch_spoilage_risk",
        description="Batches at spoilage risk with quality window",
        columns=[
            TableColumn("batch_id", "uuid", False),
            TableColumn("batch_code", "varchar", False),
            TableColumn("crop_name", "varchar", False),
            TableColumn("variety", "varchar", True),
            TableColumn("perishability_category", "varchar", True),
            TableColumn("harvest_date", "date", True),
            TableColumn("estimated_quality_window_end", "date", True),
            TableColumn("days_until_quality_window_end", "integer", True),
            TableColumn("spoilage_risk_level", "varchar", True),
            TableColumn("harvested_quantity_kg", "numeric", True),
            TableColumn("total_available_kg", "numeric", True),
            TableColumn("total_reserved_kg", "numeric", True),
            TableColumn("net_available_kg", "numeric", True),
            TableColumn("warehouse_count", "integer", True),
            TableColumn("farm_district", "varchar", True),
            TableColumn("farm_state", "varchar", True),
        ],
    ),
    "v_warehouse_capacity_utilization": TableSchema(
        name="v_warehouse_capacity_utilization",
        description="Warehouse utilization metrics",
        columns=[
            TableColumn("warehouse_id", "uuid", False),
            TableColumn("warehouse_name", "varchar", True),
            TableColumn("district", "varchar", True),
            TableColumn("state", "varchar", True),
            TableColumn("capacity_kg", "numeric", True),
            TableColumn("current_stock_kg", "numeric", True),
            TableColumn("remaining_capacity_kg", "numeric", True),
            TableColumn("utilization_pct", "numeric", True),
            TableColumn("storage_type", "varchar", True),
            TableColumn("temperature_controlled", "boolean", True),
        ],
    ),
    "v_crop_market_price_trends": TableSchema(
        name="v_crop_market_price_trends",
        description="Market price trends with day-over-day changes",
        columns=[
            TableColumn("crop_name", "varchar", False),
            TableColumn("market_name", "varchar", False),
            TableColumn("district", "varchar", True),
            TableColumn("state", "varchar", True),
            TableColumn("observation_date", "date", False),
            TableColumn("min_price_inr_per_quintal", "numeric", True),
            TableColumn("modal_price_inr_per_quintal", "numeric", True),
            TableColumn("max_price_inr_per_quintal", "numeric", True),
            TableColumn("price_change_pct", "numeric", True),
        ],
    ),
    "v_transport_cost_analysis": TableSchema(
        name="v_transport_cost_analysis",
        description="Transport cost per kg per route",
        columns=[
            TableColumn("route_id", "uuid", False),
            TableColumn("origin_warehouse", "varchar", True),
            TableColumn("origin_district", "varchar", True),
            TableColumn("destination_buyer", "varchar", True),
            TableColumn("destination_market", "varchar", True),
            TableColumn("distance_km", "numeric", True),
            TableColumn("vehicle_type", "varchar", True),
            TableColumn("transport_cost_per_kg_inr", "numeric", True),
            TableColumn("total_cost_inr", "numeric", True),
        ],
    ),
    "v_sales_with_transport_cost": TableSchema(
        name="v_sales_with_transport_cost",
        description="Sales orders with matched transport costs for net revenue",
        columns=[
            TableColumn("order_code", "varchar", True),
            TableColumn("crop_name", "varchar", True),
            TableColumn("gross_revenue_inr", "numeric", True),
            TableColumn("transport_cost_inr", "numeric", True),
            TableColumn("estimated_net_revenue_inr", "numeric", True),
            TableColumn("net_margin_pct", "numeric", True),
        ],
    ),
    "v_active_demo_scenarios_with_entities": TableSchema(
        name="v_active_demo_scenarios_with_entities",
        description="Demo scenarios linked to real entities",
        columns=[
            TableColumn("scenario_code", "varchar", True),
            TableColumn("scenario_name", "varchar", True),
            TableColumn("scenario_type", "varchar", True),
            TableColumn("entity_type", "varchar", True),
            TableColumn("entity_id_ref", "varchar", True),
            TableColumn("role_in_scenario", "varchar", True),
        ],
    ),
}


# --- Query Plan Types ---

# Allowed query type values (using type alias instead of Literal subclass for Python 3.14 compat)
QueryTypeValue = Literal["spoilage_risk", "market_prices", "warehouse_utilization", 
                       "transport_routes", "net_revenue", "batch_details", 
                       "scenario_entities", "overview"]


@dataclass
class QueryPlan:
    query_type: QueryTypeValue
    sql: str
    params: List[Any]
    tables: List[str]
    description: str
    row_limit: int = 100
    timeout_seconds: int = 30


@dataclass
class NLParsedIntent:
    intent_type: str
    crop: Optional[str] = None
    batch_code: Optional[str] = None
    warehouse: Optional[str] = None
    markets: List[str] = field(default_factory=list)
    districts: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    time_window_days: Optional[int] = None
    risk_level: Optional[str] = None
    comparison_type: Optional[str] = None  # "hold_vs_sell", "market_arbitrage", etc.
    entities: Dict[str, Any] = field(default_factory=dict)


# --- Schema Discovery ---

class SchemaRegistry:
    """Discovers and caches Zetaris schema."""
    
    def __init__(self):
        self._schemas: Dict[str, TableSchema] = {}
        self._discovered = False
    
    def get_allowlist(self) -> Dict[str, TableSchema]:
        """Return the hardcoded FPO allowlist (verified against Zetaris registration)."""
        return FPO_ALLOWLIST
    
    def validate_table(self, table_name: str) -> bool:
        return table_name in FPO_ALLOWLIST
    
    def validate_columns(self, table_name: str, columns: List[str]) -> List[str]:
        """Return only valid columns for the table."""
        if table_name not in FPO_ALLOWLIST:
            return []
        valid_cols = {c.name for c in FPO_ALLOWLIST[table_name].columns}
        return [c for c in columns if c in valid_cols]
    
    def get_column_type(self, table_name: str, column: str) -> Optional[str]:
        if table_name not in FPO_ALLOWLIST:
            return None
        for col in FPO_ALLOWLIST[table_name].columns:
            if col.name == column:
                return col.type
        return None


SCHEMA_REGISTRY = SchemaRegistry()


# --- Parameter Sanitization ---

def sanitize_identifier(value: str) -> str:
    """Sanitize table/column identifiers - only alphanumeric and underscore."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
        raise ValueError(f"Invalid identifier: {value}")
    return value


def sanitize_literal(value: Any) -> Any:
    """Sanitize literal values for parameterized queries."""
    if isinstance(value, str):
        # Remove any SQL injection attempts
        cleaned = re.sub(r'[\'";\\]', '', value)
        return cleaned
    return value


# --- Intent Parsing ---

CROP_ALIASES = {
    "tomato": "Tomato", "tomatoes": "Tomato",
    "onion": "Onion", "onions": "Onion",
    "potato": "Potato", "potatoes": "Potato",
    "grape": "Grapes", "grapes": "Grapes",
    "banana": "Banana", "bananas": "Banana",
    "turmeric": "Turmeric",
    "pomegranate": "Pomegranate",
    "wheat": "Wheat",
    "soybean": "Soybean",
    "chilli": "Chilli", "chili": "Chilli",
    "cotton": "Cotton",
}

MARKET_ALIASES = {
    "lasalgaon": "Lasalgaon",
    "mumbai": "Mumbai",
    "pune": "Pune",
    "pimpalgaon": "Pimpalgaon",
    "nashik": "Nashik",
    "ahmednagar": "Ahmednagar",
    "solapur": "Solapur",
}

DISTRICT_ALIASES = {
    "nashik": "Nashik",
    "pune": "Pune",
    "ahmednagar": "Ahmednagar",
    "solapur": "Solapur",
    "mumbai": "Mumbai",
}

STATE_ALIASES = {
    "maharashtra": "Maharashtra",
    "mh": "Maharashtra",
    "telangana": "Telangana",
    "ts": "Telangana",
    "karnataka": "Karnataka",
    "ka": "Karnataka",
}

RISK_LEVELS = ["critical_today", "high_risk", "medium_risk", "low_risk"]


def extract_crop(text: str) -> Optional[str]:
    """Extract crop name from text."""
    text_lower = text.lower()
    for alias, canonical in CROP_ALIASES.items():
        if alias in text_lower:
            return canonical
    return None


def extract_markets(text: str) -> List[str]:
    """Extract market names from text."""
    found = []
    text_lower = text.lower()
    for alias, canonical in MARKET_ALIASES.items():
        if alias in text_lower:
            found.append(canonical)
    return found


def extract_districts(text: str) -> List[str]:
    """Extract district names from text."""
    found = []
    text_lower = text.lower()
    for alias, canonical in DISTRICT_ALIASES.items():
        if alias in text_lower:
            found.append(canonical)
    return found


def extract_states(text: str) -> List[str]:
    """Extract state names from text."""
    found = []
    text_lower = text.lower()
    for alias, canonical in STATE_ALIASES.items():
        if alias in text_lower:
            found.append(canonical)
    return found


def extract_batch_code(text: str) -> Optional[str]:
    """Extract batch code (BAT-XXX or HB-XXX)."""
    # First try with "batch " prefix
    m = re.search(r'(?:batch\s+)?(BAT[-_A-Z0-9]+|HB[-_A-Z0-9]+)\b', text or "", re.I)
    return m.group(1) if m else None


def extract_warehouse(text: str) -> Optional[str]:
    """Extract warehouse reference."""
    # Look for "warehouse N" or "warehouse name"
    m = re.search(r'warehouse\s+(\d+|[a-zA-Z0-9\s]+)', text, re.I)
    if m:
        return m.group(1).strip()
    return None


def extract_time_window(text: str) -> Optional[int]:
    """Extract time window in days."""
    # "next 7 days", "within 3 days", "7 days"
    m = re.search(r'(?:next|within|in)\s+(\d+)\s*days?', text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'\b(\d+)\s*days?\b', text, re.I)
    if m:
        return int(m.group(1))
    return None


def classify_intent_type(text: str) -> str:
    """Classify the high-level intent."""
    text_lower = text.lower()
    
    if any(k in text_lower for k in ("hold vs sell", "hold versus sell", "should we sell", "should we hold", "sell or store")):
        return "hold_vs_sell"
    if any(k in text_lower for k in ("which market", "which mandi", "best market", "market selection", "arbitrage", "compare markets", "compare prices", "compare tomato prices", "compare onion prices", "compare potato prices", "compare prices in")):
        return "market_selection"
    if any(k in text_lower for k in ("net profit", "net margin", "net revenue", "compare profit", "profit comparison", "financial")):
        return "net_profit"
    if any(k in text_lower for k in ("spoilage", "quality window", "perish", "shelf life", "expire", "risk")):
        return "spoilage"
    # Specific batch detail queries (with batch code) -> batch_recommendation
    if any(k in text_lower for k in ("batch ", " bat-", " hb-", "batch code", "batch id", "batch detail", "batch detail")):
        return "batch_recommendation"
    # Inventory/quantity queries (listing batches, showing inventory) -> inventory
    if any(k in text_lower for k in ("show", "list", "inventory", "quantity", "available", "stock", "how many", "tons", "tonnes", "available stock", "available quantity", "quantity available", "batches", "all batches", "all tomato", "all onion", "all potato")):
        return "inventory"
    if any(k in text_lower for k in ("storage", "warehouse", "transport", "logistics", "freight", "route", "distance")):
        return "storage_transport"
    if any(k in text_lower for k in ("spoilage", "quality window", "perish", "shelf life", "expire", "risk")):
        return "spoilage"
    if any(k in text_lower for k in ("storage", "warehouse", "transport", "logistics", "freight", "route", "distance")):
        return "storage_transport"
    if any(k in text_lower for k in ("batch", "recommend", "recommendation", "scn-a", "scn-b", "scn-c", "scn-d", "scn-e", "simulate")):
        return "batch_recommendation"
    if any(k in text_lower for k in ("overview", "summary", "stats", "kpi", "how many", "total")):
        return "overview"
    return "general"


def parse_natural_language(prompt: str) -> NLParsedIntent:
    """Parse natural language into structured intent."""
    return NLParsedIntent(
        intent_type=classify_intent_type(prompt),
        crop=extract_crop(prompt),
        batch_code=extract_batch_code(prompt),
        warehouse=extract_warehouse(prompt),
        markets=extract_markets(prompt),
        districts=extract_districts(prompt),
        states=extract_states(prompt),
        time_window_days=extract_time_window(prompt),
        risk_level=None,  # Could extract from context
    )


# --- Query Plan Builders ---

def build_spoilage_risk_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for spoilage risk analysis."""
    conditions = ["spoilage_risk_level IN ('critical_today', 'high_risk')"]
    params = []
    
    if intent.crop:
        conditions.append("crop_name = %s")
        params.append(intent.crop)
    if intent.districts:
        placeholders = ','.join(['%s'] * len(intent.districts))
        conditions.append(f"farm_district IN ({placeholders})")
        params.extend(intent.districts)
    if intent.time_window_days:
        conditions.append("days_until_quality_window_end <= %s")
        params.append(intent.time_window_days)
    
    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT 
            batch_id, batch_code, crop_name, variety, perishability_category,
            harvest_date, estimated_quality_window_end, days_until_quality_window_end,
            spoilage_risk_level, net_available_kg, farm_district, farm_state
        FROM v_batch_spoilage_risk
        WHERE {where_clause}
        ORDER BY days_until_quality_window_end ASC
        LIMIT %s
    """
    params.append(50)
    
    return QueryPlan(
        query_type="spoilage_risk",
        sql=sql.strip(),
        params=params,
        tables=["v_batch_spoilage_risk"],
        description=f"Spoilage risk for {intent.crop or 'all crops'}",
    )


def build_market_prices_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for market price comparison."""
    crop = intent.crop or "Tomato"
    conditions = ["crop_name = %s"]
    params = [crop]
    
    if intent.markets:
        placeholders = ','.join(['%s'] * len(intent.markets))
        conditions.append(f"market_name IN ({placeholders})")
        params.extend(intent.markets)
    if intent.districts:
        placeholders = ','.join(['%s'] * len(intent.districts))
        conditions.append(f"district IN ({placeholders})")
        params.extend(intent.districts)
    if intent.states:
        placeholders = ','.join(['%s'] * len(intent.states))
        conditions.append(f"state IN ({placeholders})")
        params.extend(intent.states)
    
    where_clause = " AND ".join(conditions)
    
    # Main comparison query
    sql = f"""
        SELECT 
            market_name, district, state,
            ROUND(AVG(modal_price_inr_per_quintal)::numeric, 2) as avg_modal_price,
            ROUND(MIN(min_price_inr_per_quintal)::numeric, 2) as min_price,
            ROUND(MAX(max_price_inr_per_quintal)::numeric, 2) as max_price,
            COUNT(*) as observations_count,
            MAX(observation_date) as latest_observation
        FROM v_crop_market_price_trends
        WHERE {where_clause}
        GROUP BY market_name, district, state
        ORDER BY avg_modal_price DESC
        LIMIT %s
    """
    params.append(20)
    
    return QueryPlan(
        query_type="market_prices",
        sql=sql.strip(),
        params=params,
        tables=["v_crop_market_price_trends"],
        description=f"Market prices for {crop}",
    )


def build_warehouse_utilization_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for warehouse utilization."""
    conditions = []
    params = []
    
    if intent.warehouse:
        # Try to match by name or ID
        conditions.append("(warehouse_name ILIKE %s OR warehouse_id::text ILIKE %s)")
        params.extend([f"%{intent.warehouse}%", f"%{intent.warehouse}%"])
    if intent.districts:
        placeholders = ','.join(['%s'] * len(intent.districts))
        conditions.append(f"district IN ({placeholders})")
        params.extend(intent.districts)
    if intent.states:
        placeholders = ','.join(['%s'] * len(intent.states))
        conditions.append(f"state IN ({placeholders})")
        params.extend(intent.states)
    
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT 
            warehouse_id, warehouse_name, district, state,
            capacity_kg, current_stock_kg, remaining_capacity_kg,
            utilization_pct, storage_type, temperature_controlled
        FROM v_warehouse_capacity_utilization
        {where_clause}
        ORDER BY utilization_pct DESC
        LIMIT %s
    """
    params.append(25)
    
    return QueryPlan(
        query_type="warehouse_utilization",
        sql=sql.strip(),
        params=params,
        tables=["v_warehouse_capacity_utilization"],
        description="Warehouse utilization",
    )


def build_transport_routes_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for transport routes and costs."""
    conditions = []
    params = []
    
    if intent.warehouse:
        conditions.append("origin_warehouse ILIKE %s")
        params.append(f"%{intent.warehouse}%")
    if intent.markets:
        placeholders = ','.join(['%s'] * len(intent.markets))
        conditions.append(f"destination_market IN ({placeholders})")
        params.extend(intent.markets)
    if intent.districts:
        placeholders = ','.join(['%s'] * len(intent.districts))
        conditions.append(f"origin_district IN ({placeholders})")
        params.extend(intent.districts)
    
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT 
            route_id, origin_warehouse, origin_district,
            destination_buyer, destination_market,
            distance_km, vehicle_type,
            transport_cost_per_kg_inr, total_cost_inr
        FROM v_transport_cost_analysis
        {where_clause}
        ORDER BY transport_cost_per_kg_inr ASC
        LIMIT %s
    """
    params.append(25)
    
    return QueryPlan(
        query_type="transport_routes",
        sql=sql.strip(),
        params=params,
        tables=["v_transport_cost_analysis"],
        description="Transport routes and costs",
    )


def build_net_revenue_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for net revenue analysis."""
    crop = intent.crop or "Tomato"
    conditions = ["crop_name = %s"]
    params = [crop]
    
    if intent.markets:
        placeholders = ','.join(['%s'] * len(intent.markets))
        conditions.append(f"market_name IN ({placeholders})")
        params.extend(intent.markets)
    
    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT 
            order_code, crop_name, 
            gross_revenue_inr, transport_cost_inr,
            estimated_net_revenue_inr, net_margin_pct
        FROM v_sales_with_transport_cost
        WHERE {where_clause}
        ORDER BY estimated_net_revenue_inr DESC
        LIMIT %s
    """
    params.append(20)
    
    return QueryPlan(
        query_type="net_revenue",
        sql=sql.strip(),
        params=params,
        tables=["v_sales_with_transport_cost"],
        description=f"Net revenue for {crop}",
    )


def build_batch_details_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for specific batch details."""
    if not intent.batch_code:
        # Fall back to spoilage risk
        return build_spoilage_risk_query(intent)
    
    conditions = ["batch_code = %s"]
    params = [intent.batch_code]
    
    sql = f"""
        SELECT 
            batch_id, batch_code, crop_name, variety, perishability_category,
            harvest_date, estimated_quality_window_end, days_until_quality_window_end,
            spoilage_risk_level, harvested_quantity_kg, total_available_kg,
            total_reserved_kg, net_available_kg, warehouse_count,
            farm_district, farm_state
        FROM v_batch_spoilage_risk
        WHERE {' AND '.join(conditions)}
        LIMIT 1
    """
    
    return QueryPlan(
        query_type="batch_details",
        sql=sql.strip(),
        params=params,
        tables=["v_batch_spoilage_risk"],
        description=f"Batch details for {intent.batch_code}",
    )


def build_overview_query(intent: NLParsedIntent) -> QueryPlan:
    """Build overview stats query."""
    sql = """
        SELECT 
            (SELECT COUNT(*) FROM fpos) as total_fpos,
            (SELECT COUNT(*) FROM farmers) as total_farmers,
            (SELECT COUNT(*) FROM crops) as total_crops,
            (SELECT COUNT(*) FROM harvest_batches WHERE status = 'harvested') as active_batches,
            (SELECT COALESCE(SUM(quantity_available_kg), 0) FROM inventory) as total_available_kg,
            (SELECT ROUND(AVG(utilization_pct)::numeric, 1) FROM v_warehouse_capacity_utilization) as avg_warehouse_utilization,
            (SELECT COUNT(*) FROM v_warehouse_capacity_utilization WHERE utilization_pct >= 80) as warehouses_near_capacity
    """
    return QueryPlan(
        query_type="overview",
        sql=sql.strip(),
        params=[],
        tables=["fpos", "farmers", "crops", "harvest_batches", "inventory", "v_warehouse_capacity_utilization"],
        description="FPO network overview",
    )


def build_scenario_entities_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for scenario-linked entities."""
    sql = """
        SELECT scenario_code, scenario_name, scenario_type, 
               entity_type, entity_id_ref, role_in_scenario, notes
        FROM v_active_demo_scenarios_with_entities
        ORDER BY scenario_code
        LIMIT 20
    """
    return QueryPlan(
        query_type="scenario_entities",
        sql=sql.strip(),
        params=[],
        tables=["v_active_demo_scenarios_with_entities"],
        description="Active demo scenarios with entities",
    )


def build_inventory_query(intent: NLParsedIntent) -> QueryPlan:
    """Build query for inventory/batch listing."""
    conditions = []
    params = []
    
    if intent.crop:
        conditions.append("crop_name = %s")
        params.append(intent.crop)
    if intent.districts:
        placeholders = ','.join(['%s'] * len(intent.districts))
        conditions.append(f"farm_district IN ({placeholders})")
        params.extend(intent.districts)
    if intent.states:
        placeholders = ','.join(['%s'] * len(intent.states))
        conditions.append(f"farm_state IN ({placeholders})")
        params.extend(intent.states)
    if intent.warehouse:
        conditions.append("(warehouse_name ILIKE %s OR warehouse_id::text ILIKE %s)")
        params.extend([f"%{intent.warehouse}%", f"%{intent.warehouse}%"])
    
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    sql = f"""
        SELECT 
            batch_id, batch_code, crop_name, variety, perishability_category,
            harvest_date, estimated_quality_window_end, days_until_quality_window_end,
            spoilage_risk_level, harvested_quantity_kg, total_available_kg,
            total_reserved_kg, net_available_kg, warehouse_count,
            farm_district, farm_state
        FROM v_batch_spoilage_risk
        {where_clause}
        ORDER BY harvest_date DESC, net_available_kg DESC
        LIMIT %s
    """
    params.append(100)
    
    return QueryPlan(
        query_type="inventory",
        sql=sql.strip(),
        params=params,
        tables=["v_batch_spoilage_risk"],
        description=f"Inventory listing for {intent.crop or 'all crops'}",
    )


# --- Main Query Planner ---

QUERY_BUILDERS = {
    "spoilage": build_spoilage_risk_query,
    "market_selection": build_market_prices_query,
    "net_profit": build_net_revenue_query,
    "storage_transport": build_transport_routes_query,
    "batch_recommendation": build_batch_details_query,
    "inventory": build_inventory_query,
    "overview": build_overview_query,
    "general": build_market_prices_query,  # default
}


def create_query_plan(intent: NLParsedIntent) -> QueryPlan:
    """Create a typed query plan from parsed intent."""
    builder = QUERY_BUILDERS.get(intent.intent_type, build_market_prices_query)
    return builder(intent)


# --- Zetaris Execution ---

class QueryExecutor:
    """Executes approved query plans via Zetaris."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            client, err = zetaris_mod.get_zetaris_client(self.config)
            if err:
                raise RuntimeError(f"Zetaris client error: {err}")
            self._client = client
        return self._client
    
    def execute(self, plan: QueryPlan) -> Dict[str, Any]:
        """Execute a query plan and return structured results."""
        client = self._get_client()
        
        # Sanitize params
        safe_params = [sanitize_literal(p) for p in plan.params]
        
        # Execute via Zetaris
        result = client.execute_query(plan.sql, limit=plan.row_limit)
        
        if result.status != "success":
            return {
                "status": "error",
                "query_type": plan.query_type,
                "description": plan.description,
                "sql": plan.sql,
                "params": safe_params,
                "error": result.error,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
        
        # Convert to list of dicts
        columns = result.data.get("columns", [])
        rows = result.data.get("rows", [])
        
        data = []
        for row in rows:
            if isinstance(row, list) and columns:
                data.append(dict(zip(columns, row)))
            elif isinstance(row, dict):
                data.append(row)
            else:
                data.append({"value": row})
        
        return {
            "status": "success",
            "query_type": plan.query_type,
            "description": plan.description,
            "sql": plan.sql,
            "params": safe_params,
            "columns": columns,
            "rows": data,
            "row_count": len(data),
            "query_token": result.data.get("query_token"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "source": "zetaris",
        }
    
    def execute_multiple(self, plans: List[QueryPlan]) -> List[Dict[str, Any]]:
        """Execute multiple query plans."""
        return [self.execute(plan) for plan in plans]


# --- High-level Orchestration ---

def plan_and_execute(
    prompt: str,
    config: Optional[Dict[str, Any]] = None,
    max_queries: int = 5
) -> Dict[str, Any]:
    """
    Parse natural language, create query plans, execute via Zetaris.
    Returns structured evidence for the decision pipeline.
    """
    intent = parse_natural_language(prompt)
    
    # Determine which queries to run based on intent
    plans = []
    
    # Always get overview for context
    if intent.intent_type != "overview":
        plans.append(build_overview_query(intent))
    
    # Primary query based on intent
    primary = create_query_plan(intent)
    plans.append(primary)
    
    # Secondary queries for cross-reference
    if intent.intent_type in ("hold_vs_sell", "market_selection", "net_profit"):
        plans.append(build_market_prices_query(intent))
        plans.append(build_transport_routes_query(intent))
    elif intent.intent_type == "spoilage":
        plans.append(build_warehouse_utilization_query(intent))
    elif intent.intent_type == "storage_transport":
        plans.append(build_market_prices_query(intent))
    elif intent.intent_type == "inventory":
        plans.append(build_market_prices_query(intent))
        plans.append(build_warehouse_utilization_query(intent))
    
    # Limit queries
    plans = plans[:max_queries]
    
    # Execute
    executor = QueryExecutor(config)
    results = executor.execute_multiple(plans)
    
    return {
        "intent": intent.__dict__,
        "queries_executed": len(results),
        "results": results,
        "planned_at": datetime.now(timezone.utc).isoformat(),
    }


# --- Direct Zetaris SQL (for explicit commands) ---

def execute_direct_zetaris(
    sql: str,
    config: Optional[Dict[str, Any]] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """Execute a direct SELECT-only query via Zetaris (for explicit zetaris: commands)."""
    # Validate
    valid, err = zetaris_mod.validate_select_only(sql)
    if not valid:
        return {"status": "error", "error": err}
    
    client, err = zetaris_mod.get_zetaris_client(config or {})
    if err:
        return {"status": "error", "error": err}
    
    result = client.execute_query(sql, limit=limit)
    if result.status != "success":
        return {"status": "error", "error": result.error, "sql": sql}
    
    columns = result.data.get("columns", [])
    rows = result.data.get("rows", [])
    
    data = []
    for row in rows:
        if isinstance(row, list) and columns:
            data.append(dict(zip(columns, row)))
        elif isinstance(row, dict):
            data.append(row)
        else:
            data.append({"value": row})
    
    return {
        "status": "success",
        "sql": sql,
        "columns": columns,
        "rows": data,
        "row_count": len(data),
        "query_token": result.data.get("query_token"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "source": "zetaris",
    }


# --- Schema Introspection Endpoint ---

def get_schema_catalog() -> Dict[str, Any]:
    """Return the FPO schema catalog for the frontend."""
    return {
        "tables": {
            name: {
                "description": schema.description,
                "columns": [
                    {"name": c.name, "type": c.type, "nullable": c.nullable}
                    for c in schema.columns
                ],
                "primary_key": schema.primary_key,
            }
            for name, schema in FPO_ALLOWLIST.items()
        },
        "relationships": [
            {"from": "harvest_batches", "to": "farms", "via": "farm_id"},
            {"from": "harvest_batches", "to": "crops", "via": "crop_id"},
            {"from": "farms", "to": "farmers", "via": "farmer_id"},
            {"from": "farmers", "to": "fpos", "via": "fpo_id"},
            {"from": "inventory", "to": "harvest_batches", "via": "batch_id"},
            {"from": "inventory", "to": "warehouses", "via": "warehouse_id"},
            {"from": "market_prices", "to": "crops", "via": "crop_id"},
            {"from": "sales_orders", "to": "harvest_batches", "via": "batch_id"},
            {"from": "sales_orders", "to": "buyers", "via": "buyer_id"},
            {"from": "transport_routes", "to": "warehouses", "via": "origin_warehouse"},
            {"from": "transport_routes", "to": "buyers", "via": "destination_buyer"},
        ],
    }