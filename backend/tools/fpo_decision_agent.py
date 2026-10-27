"""
FPO decision intelligence pipeline.

User question -> intent -> evidence retrieval -> deterministic finance ->
optional AI explanation -> validation -> recommendation.

Numeric values come only from retrieved records and Python arithmetic.
Language models may explain; they must not invent rupees, kg, or percents.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional

from backend.tools import fpo_analytics
from backend.tools import meterless as meterless_mod
from backend.tools import nvidia_nemotron as nvidia_mod
from backend.tools import zetaris as zetaris_mod
from backend.tools.agri_context import (
    AgriConversation,
    AgriContextStore,
    AgriTurn,
    build_turn_from_pipeline,
    create_conversation_id,
    extract_batch_info_from_evidence,
    get_context_for_prompt,
    get_context_store,
    resolve_followup_entities,
)

INR_Q = Decimal("0.01")
KG_Q = Decimal("0.001")

INTENT_HOLD_VS_SELL = "hold_vs_sell"
INTENT_MARKET_SELECTION = "market_selection"
INTENT_NET_PROFIT = "net_profit"
INTENT_SPOILAGE = "spoilage"
INTENT_STORAGE_TRANSPORT = "storage_transport"
INTENT_BATCH = "batch_recommendation"
INTENT_INVENTORY = "inventory"
INTENT_GENERAL = "general"

REASONING_SYSTEM = (
    "You are NEXUS, an FPO agricultural decision intelligence analyst. "
    "You receive structured JSON containing: verified evidence (inventory batches, market prices, transport routes, weather), "
    "and a KEY_NUMBERS_TO_QUOTE section with pre-computed financial figures. "
    "Your task: produce a comprehensive, professional agricultural decision report. "
    "\n\n"
    "⚠️ CRITICAL: YOU ARE AN EXPLAINER, NOT A CALCULATOR. ⚠️\n"
    "ALL FINANCIAL CALCULATIONS HAVE ALREADY BEEN DONE BY A DETERMINISTIC ENGINE. "
    "DO NOT PERFORM ANY CALCULATIONS. DO NOT COMPUTE NEW NUMBERS. DO NOT ESTIMATE. "
    "YOUR ONLY JOB: EXPLAIN THE NUMBERS ALREADY PROVIDED IN THE 'KEY_NUMBERS_TO_QUOTE' SECTION. "
    "IF A NUMBER IS NOT IN THE 'KEY_NUMBERS_TO_QUOTE' SECTION, STATE 'Data not available' — DO NOT ESTIMATE. "
    "\n\n"
    "MANDATORY STRUCTURE - Use exactly these section headers:\n"
    "## EXECUTIVE SUMMARY\n"
    "Direct answer to the user's question in 2-3 sentences. Use ONLY numbers from the 'KEY_NUMBERS_TO_QUOTE' section.\n"
    "\n"
    "## CURRENT SITUATION\n"
    "Crop, batch details, quantities, harvest dates, storage locations, quality window, spoilage risk level. "
    "Cite specific batch IDs from evidence. Use ONLY numbers from KEY_NUMBERS_TO_QUOTE.\n"
    "\n"
    "## MARKET ANALYSIS\n"
    "Compare destination markets using actual price observations. "
    "Table format: Market | Variety | Modal Price (₹/quintal) | Observation Date | Source. "
    "Use ONLY prices from the 'market_summary' or KEY_NUMBERS_TO_QUOTE. If prices missing, state which markets lack data.\n"
    "\n"
    "## TRANSPORT & LOGISTICS\n"
    "Road routes from storage to each market. "
    "Table: Destination | Distance (km) | Duration (hrs) | Vehicle | Cost (₹/kg) | Total Cost (₹) | Trips Needed. "
    "Use ONLY numbers from 'transport_summary' and KEY_NUMBERS_TO_QUOTE. Account for vehicle capacity vs quantity.\n"
    "\n"
    "## WEATHER & SPOILAGE RISK\n"
    "Forecast at origin, destination, and en route. "
    "Temperature, humidity, precipitation, heat stress days. "
    "Estimated quality deterioration during transit + storage. "
    "Use ONLY 'weather_summary'. If weather data missing, state so. DO NOT ESTIMATE.\n"
    "\n"
    "## FINANCIAL COMPARISON\n"
    "For each feasible destination, reference ONLY the pre-computed values in KEY_NUMBERS_TO_QUOTE:\n"
    "- Expected saleable quantity (kg): use KEY_NUMBERS_TO_QUOTE.quantity_kg_at_risk\n"
    "- Gross revenue (₹): use KEY_NUMBERS_TO_QUOTE.sell_now_estimated_net_inr (already computed)\n"
    "- Transport cost (₹): use KEY_NUMBERS_TO_QUOTE.sell_now_transport_per_kg_inr (per kg rate)\n"
    "- Storage cost (₹): use KEY_NUMBERS_TO_QUOTE.hold_proxy_storage_cost_per_kg_day_inr if available\n"
    "- Net proceeds (₹): use KEY_NUMBERS_TO_QUOTE.sell_now_estimated_net_inr or KEY_NUMBERS_TO_QUOTE.hold_proxy_estimated_net_inr\n"
    "- Profit/loss vs historical procurement cost: state if data unavailable\n"
    "If data missing for a market, mark as 'Insufficient data - cannot rank'. DO NOT ESTIMATE.\n"
    "\n"
    "## FEASIBILITY & UNCERTAINTY\n"
    "Quality window vs total transit+market time (use KEY_NUMBERS_TO_QUOTE.days_until_quality_window_end). "
    "Truck availability assumptions. "
    "Market acceptance risk. "
    "Worst-case loss exposure (only if in KEY_NUMBERS_TO_QUOTE).\n"
    "\n"
    "## RECOMMENDATION\n"
    "Primary: [Destination] - [key reason with numbers from KEY_NUMBERS_TO_QUOTE]\n"
    "Alternative: [Destination] - [key reason with numbers from KEY_NUMBERS_TO_QUOTE]\n"
    "If all options lose money: recommend least-loss option with rationale from KEY_NUMBERS_TO_QUOTE.\n"
    "\n"
    "## PRACTICAL NEXT STEPS\n"
    "1. [Immediate dispatch action]\n"
    "2. [Booking/coordination needed]\n"
    "3. [Monitoring during transit]\n"
    "\n"
    "## MISSING EVIDENCE & ASSUMPTIONS\n"
    "List every data gap that affects confidence. "
    "Distinguish: observed (from APIs), calculated (deterministic), assumed (operator input).\n"
    "\n"
    "CRITICAL RULES:\n"
    "- NEVER invent numbers. Only use values from the provided JSON, especially the 'KEY_NUMBERS_TO_QUOTE' section.\n"
    "- If a figure is missing from 'KEY_NUMBERS_TO_QUOTE', explicitly state 'Data not available for [X]' — DO NOT ESTIMATE.\n"
    "- Quote exact numbers from 'KEY_NUMBERS_TO_QUOTE' section. Do not round unless the source does.\n"
    "- For inventory queries (listing batches), return a clean table only - skip financial sections.\n"
    "- For simple questions, be concise. For 'analyze/compare/recommend' questions, use full structure.\n"
    "- Tone: professional, decisive, farmer-facing."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _d(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _money(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value.quantize(INR_Q, rounding=ROUND_HALF_UP))


def _kg(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value.quantize(KG_Q, rounding=ROUND_HALF_UP))


def classify_intent(prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
    p = (prompt or "").lower()

    # First, check for explicit data listing patterns (show/list N batches/items)
    # These are data retrieval queries, not decision queries
    if any(k in p for k in ("show the", "list the", "show top", "list top", "show bottom", "list bottom")) and any(k in p for k in ("batch", "batches", "item", "items", "record", "records")):
        return INTENT_INVENTORY

    # First, check for explicit intent keywords (these override context)
    if any(k in p for k in ("hold vs sell", "hold versus sell", "hold or sell", "should we sell", "should we hold")):
        return INTENT_HOLD_VS_SELL
    if any(k in p for k in ("net profit", "net margin", "net revenue", "compare profit", "profit comparison")):
        return INTENT_NET_PROFIT
    if any(k in p for k in ("which market", "which mandi", "market selection", "best market", "arbitrage")):
        return INTENT_MARKET_SELECTION
    if any(k in p for k in ("spoilage", "quality window", "perish", "shelf life", "expire", "risk", "critical", "high risk")):
        return INTENT_SPOILAGE
    # Inventory/quantity queries
    if any(k in p for k in ("show", "list", "inventory", "quantity", "available", "stock", "how many", "tons", "tonnes", "available stock", "available quantity", "quantity available", "batch", "batches")):
        return INTENT_INVENTORY
    if any(k in p for k in ("storage", "warehouse", "transport", "logistics", "freight")):
        return INTENT_STORAGE_TRANSPORT
    if any(k in p for k in ("batch", "recommend", "recommendation", "scn-a", "scn-b", "scn-c", "scn-d", "scn-e", "simulate")):
        return INTENT_BATCH
    if any(k in p for k in ("overview", "summary", "stats", "kpi", "how many", "total")):
        return "overview"

    # Only check for follow-up context if no explicit intent was found
    if context and context.get("is_followup"):
        prev_intent = context.get("previous_intent")
        # Follow-ups about selling/dispatching inherit the previous intent
        if any(k in p for k in ("where should i sell", "where to sell", "sell them", "dispatch them")):
            if prev_intent in (INTENT_HOLD_VS_SELL, INTENT_MARKET_SELECTION, INTENT_NET_PROFIT, INTENT_SPOILAGE):
                return prev_intent
        # Follow-ups about comparing inherit the comparison intent
        if "compare" in p or "what about" in p:
            if prev_intent in (INTENT_HOLD_VS_SELL, INTENT_MARKET_SELECTION, INTENT_NET_PROFIT, INTENT_SPOILAGE):
                return prev_intent
        # Follow-ups asking "which market" with context
        if "which market" in p and prev_intent in (INTENT_HOLD_VS_SELL, INTENT_MARKET_SELECTION, INTENT_NET_PROFIT, INTENT_SPOILAGE):
            return prev_intent

    return INTENT_GENERAL


def extract_crop(prompt: str) -> Optional[str]:
    crops = [
        "Tomato", "Onion", "Potato", "Grapes", "Banana", "Turmeric",
        "Pomegranate", "Wheat", "Soybean", "Chilli", "Cotton",
    ]
    p = (prompt or "").lower()
    for crop in crops:
        if crop.lower() in p:
            return crop
    return None


def extract_batch_code(prompt: str) -> Optional[str]:
    m = re.search(r"\b(BAT[-_][A-Z0-9]+|HB[-_][A-Z0-9]+)\b", prompt or "", re.I)
    return m.group(1) if m else None


def _source(name: str, identifier: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    item = {
        "source": name,
        "identifier": identifier,
        "retrieved_at": _now_iso(),
    }
    if extra:
        item.update(extra)
    return item


def retrieve_evidence(
    prompt: str,
    *,
    intent: Optional[str] = None,
    analytics: Any = fpo_analytics,
    zetaris_client: Any = None,
    config: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    intent = intent or classify_intent(prompt, context)
    crop = extract_crop(prompt)
    batch_code = extract_batch_code(prompt)
    warnings: List[str] = []
    sources: List[Dict[str, Any]] = []
    payload: Dict[str, Any] = {
        "crop": crop,
        "batch_code": batch_code,
        "intent": intent,
    }

    # Apply follow-up context resolution
    if context and context.get("is_followup"):
        payload = resolve_followup_entities(prompt, context, payload)
        crop = payload.get("crop") or crop

    # Use NL-to-SQL planner for Zetaris queries when client is available
    zetaris_results = []
    if zetaris_client is not None:
        try:
            from backend.tools import nl_to_sql
            # Parse intent and create query plan
            nl_intent = nl_to_sql.parse_natural_language(prompt)
            # Override with context-resolved crop
            if crop:
                nl_intent.crop = crop
            if batch_code:
                nl_intent.batch_code = batch_code
            plan = nl_to_sql.create_query_plan(nl_intent)
            executor = nl_to_sql.QueryExecutor(config)
            executor._client = zetaris_client  # Use the provided client
            zetaris_result = executor.execute(plan)
            if zetaris_result.get("status") == "success":
                zetaris_results.append(zetaris_result)
                sources.append(_source("zetaris", plan.tables[0] if plan.tables else "query", {"sql": plan.sql, "params": plan.params}))
                # Add rows to payload for finance calculations
                if zetaris_result.get("rows"):
                    payload["zetaris_data"] = zetaris_result["rows"]
                    # If we got inventory data, use it for finance calculations
                    if plan.query_type in ("batch_details", "spoilage_risk", "overview", "inventory"):
                        payload["zetaris_inventory"] = zetaris_result["rows"]
        except Exception as exc:
            warnings.append(f"Zetaris query failed: {exc}")

    # Fallback to PostgreSQL analytics if no Zetaris data
    if not zetaris_results:
        market = analytics.get_market_intelligence(crop_name=crop)
        if market.get("status") == "success":
            payload["market"] = market
            sources.append(_source("postgresql", "v_crop_market_price_trends", {"crop": crop}))
        else:
            warnings.append(f"Market prices unavailable: {market.get('message') or 'error'}")
            payload["market"] = {"status": "missing", "crop": crop}

        risks = analytics.get_risk_centre()
        if risks.get("status") == "success":
            payload["risks"] = risks
            sources.append(_source("postgresql", "v_batch_spoilage_risk"))
            sources.append(_source("postgresql", "v_warehouse_capacity_utilization"))
        else:
            warnings.append(f"Risk views unavailable: {risks.get('message') or 'error'}")
            payload["risks"] = {"status": "missing"}

        logistics = analytics.get_logistics_intelligence()
        if logistics.get("status") == "success":
            payload["logistics"] = logistics
            sources.append(_source("postgresql", "v_transport_cost_analysis"))
        else:
            warnings.append(f"Logistics views unavailable: {logistics.get('message') or 'error'}")
            payload["logistics"] = {"status": "missing"}

        decisions = analytics.get_decisions_scenarios()
        if decisions.get("status") == "success":
            payload["scenarios"] = decisions
            sources.append(_source("postgresql", "v_sales_with_transport_cost"))
            sources.append(_source("postgresql", "demo_scenarios"))
        else:
            warnings.append(f"Scenario/sales views unavailable: {decisions.get('message') or 'error'}")
            payload["scenarios"] = {"status": "missing"}

    if batch_code:
        inventory = analytics.get_inventory_batches(page=1, page_size=5, search=batch_code, crop_name=crop)
        if inventory.get("status") == "success":
            payload["inventory"] = inventory
            sources.append(_source("postgresql", "inventory", {"search": batch_code}))
        else:
            warnings.append("Batch inventory lookup failed")

    if not sources and not zetaris_results:
        warnings.append("No evidence sources returned data")

    return {
        "intent": intent,
        "crop": crop,
        "batch_code": batch_code,
        "retrieved_at": _now_iso(),
        "sources": sources,
        "warnings": warnings,
        "data": payload,
        "zetaris_results": zetaris_results,
    }


def _best_markets(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = market.get("market_comparison") or []
    ranked = []
    for row in rows:
        price = _d(row.get("avg_price"))
        if price is None:
            continue
        ranked.append({
            "market_name": row.get("market_name"),
            "district": row.get("district"),
            "avg_price_inr_per_quintal": _money(price),
            "price_inr_per_kg": _money(price / Decimal("100")),
            "observations_count": row.get("observations_count"),
        })
    ranked.sort(key=lambda r: r["avg_price_inr_per_quintal"] or 0, reverse=True)
    return ranked


def _cheapest_route(logistics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    routes = logistics.get("routes") or []
    priced = []
    for route in routes:
        cost = _d(route.get("transport_cost_per_kg_inr"))
        if cost is None:
            continue
        priced.append({
            "origin_warehouse": route.get("origin_warehouse"),
            "origin_district": route.get("origin_district"),
            "destination_market": route.get("destination_market"),
            "distance_km": float(_d(route.get("distance_km")) or 0),
            "transport_cost_per_kg_inr": _money(cost),
            "vehicle_type": route.get("vehicle_type"),
        })
    if not priced:
        return None
    priced.sort(key=lambda r: r["transport_cost_per_kg_inr"] or 0)
    return priced[0]


def calculate_finance(evidence: Dict[str, Any]) -> Dict[str, Any]:
    data = evidence.get("data") or {}
    crop = evidence.get("crop")
    warnings = list(evidence.get("warnings") or [])

    # Check for Zetaris inventory data first
    zetaris_inventory = data.get("zetaris_inventory") or []
    zetaris_data = data.get("zetaris_data") or []

    market = data.get("market") or {}
    logistics = data.get("logistics") or {}
    risks = data.get("risks") or {}
    scenarios = data.get("scenarios") or {}

    markets = _best_markets(market) if market.get("status") == "success" else []
    if not markets:
        warnings.append("No mandi price observations available for net-profit math")

    route = _cheapest_route(logistics) if logistics.get("status") == "success" else None
    if route is None:
        warnings.append("No transport cost per kg available; net-of-freight figures omitted")

    # Use Zetaris inventory data if available, otherwise fall back to PostgreSQL risks
    qty = Decimal("0")
    critical = []

    if zetaris_inventory:
        # Use Zetaris inventory data
        for batch in zetaris_inventory:
            if str(batch.get("crop_name") or "").lower() == str(crop or "").lower():
                critical.append(batch)
                kg = _d(batch.get("net_available_kg")) or Decimal("0")
                qty += kg
        if qty <= 0:
            warnings.append("No at-risk quantity for this crop; profit totals use 0 kg")
    elif risks.get("status") == "success":
        # Fallback to PostgreSQL risks
        for batch in (risks.get("critical_batches") or []):
            if str(batch.get("crop_name") or "").lower() == str(crop or "").lower():
                critical.append(batch)
                kg = _d(batch.get("net_available_kg")) or Decimal("0")
                qty += kg
        if qty <= 0:
            warnings.append("No at-risk quantity for this crop; profit totals use 0 kg")
    else:
        warnings.append("No inventory data available for quantity calculation")

    local = markets[-1] if len(markets) > 1 else (markets[0] if markets else None)
    best = markets[0] if markets else None

    transport_per_kg = _d(route["transport_cost_per_kg_inr"]) if route else None
    best_per_kg = _d(best["price_inr_per_kg"]) if best else None
    local_per_kg = _d(local["price_inr_per_kg"]) if local else None

    sell_now = None
    hold_proxy = None
    spread = None
    if best_per_kg is not None and transport_per_kg is not None:
        net_per_kg = best_per_kg - transport_per_kg
        sell_now = {
            "quantity_kg": _kg(qty),
            "best_market": best.get("market_name") if best else None,
            "gross_per_kg_inr": _money(best_per_kg),
            "transport_per_kg_inr": _money(transport_per_kg),
            "net_per_kg_inr": _money(net_per_kg),
            "estimated_net_inr": _money(net_per_kg * qty),
        }
        if local_per_kg is not None:
            spread = _money(best_per_kg - local_per_kg)
            hold_net_per_kg = local_per_kg
            hold_proxy = {
                "quantity_kg": _kg(qty),
                "local_market": local.get("market_name") if local else None,
                "gross_per_kg_inr": _money(local_per_kg),
                "storage_cost_per_kg_day_inr": None,
                "estimated_net_inr": _money(hold_net_per_kg * qty),
                "note": "Hold path omits storage cost: cost_per_kg_day was not in the retrieved evidence.",
            }
            warnings.append("Storage INR/kg/day not retrieved; hold vs sell compares farm-gate vs best mandi net of freight only")

    days_left = None
    spoilage_level = None
    if critical:
        days = [_d(b.get("days_until_quality_window_end")) for b in critical]
        days = [d for d in days if d is not None]
        if days:
            days_left = int(min(days))
        spoilage_level = critical[0].get("spoilage_risk_level")

    sales_rows = []
    if scenarios.get("status") == "success":
        for row in (scenarios.get("sales_analysis") or [])[:8]:
            sales_rows.append({
                "order_code": row.get("order_code"),
                "crop_name": row.get("crop_name"),
                "gross_revenue_inr": _money(_d(row.get("gross_revenue_inr"))),
                "transport_cost_inr": _money(_d(row.get("transport_cost_inr"))),
                "estimated_net_revenue_inr": _money(_d(row.get("estimated_net_revenue_inr"))),
                "net_margin_pct": _money(_d(row.get("net_margin_pct"))),
            })

    action = "insufficient_data"
    rationale_bits = []
    if days_left is not None and days_left <= 3:
        action = "sell_now"
        rationale_bits.append(f"Quality window has {days_left} day(s) remaining")
    elif sell_now and hold_proxy and (sell_now["estimated_net_inr"] or 0) > (hold_proxy["estimated_net_inr"] or 0):
        action = "sell_now"
        rationale_bits.append("Best mandi net of freight exceeds local/hold proxy")
    elif sell_now and hold_proxy:
        action = "hold_local"
        rationale_bits.append("Local/hold proxy exceeds best-mandi net of freight")
    elif sell_now:
        action = "sell_now"
        rationale_bits.append("Best mandi net-of-freight figure is available")

    return {
        "crop": crop,
        "quantity_kg_at_risk": _kg(qty),
        "markets_ranked": markets[:5],
        "cheapest_route": route,
        "sell_now": sell_now,
        "hold_proxy": hold_proxy,
        "price_spread_per_kg_inr": spread,
        "days_until_quality_window_end": days_left,
        "spoilage_risk_level": spoilage_level,
        "sales_comparables": sales_rows,
        "recommended_action": action,
        "calculation_notes": rationale_bits,
        "warnings": warnings,
        "calculated_at": _now_iso(),
    }


def _extract_numbers(text: str) -> List[str]:
    """Extract numbers from text, handling comma-separated thousands (e.g., 1,000, 63,352.32)
    and plain numbers without commas. Avoids splitting numbers like 63352.32 into 633 and 52.32."""
    # Match either:
    # - Comma-formatted: 1-3 digits, then REQUIRED groups of comma+3 digits, optional decimal
    # - Plain numbers without commas: digits, optional decimal
    return re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", text or "")


def _is_key_financial_number(token: str) -> bool:
    """Heuristic: is this a key financial figure worth validating? Ignore dates, IDs, counts."""
    normalized = token.replace(",", "")
    try:
        val = float(normalized)
        # Ignore small integers (likely counts, years, IDs)
        if val == int(val) and val < 1000:
            return False
        # Ignore years (2020-2030)
        if 2020 <= val <= 2030 and val == int(val):
            return False
        # Ignore small decimals that are likely percentages or rates < 1
        if 0 < val < 1:
            return False
        return True
    except ValueError:
        return False


def _float_value(token: str) -> float:
    """Extract float value from token, handling commas."""
    return float(token.replace(",", ""))


def _normalize_number(token: str) -> str:
    """Normalize a number token for comparison: remove commas, leading zeros, ensure consistent decimal."""
    # Remove commas
    token = token.replace(",", "")
    # Remove leading zeros from integer part (but keep at least one digit)
    if "." in token:
        int_part, dec_part = token.split(".", 1)
        int_part = int_part.lstrip("0") or "0"
        # Remove trailing zeros from decimal part
        dec_part = dec_part.rstrip("0")
        if dec_part:
            return f"{int_part}.{dec_part}"
        else:
            return int_part
    else:
        return token.lstrip("0") or "0"


def _allowed_number_tokens(evidence_package: Dict[str, Any]) -> set:
    """Extract all numeric tokens from the full evidence package for validation, normalized."""
    blob = json.dumps(evidence_package, default=str)
    raw_numbers = _extract_numbers(blob)
    return set(_normalize_number(n) for n in raw_numbers)


def _numbers_equivalent(a: str, b: str, rel_tol: float = 0.02) -> bool:
    """Check if two number strings represent the same value within 2% tolerance.
    Handles comma-formatted numbers and ignores minor precision differences."""
    try:
        a_clean = a.replace(",", "")
        b_clean = b.replace(",", "")
        fa = float(a_clean)
        fb = float(b_clean)
        # Use 2% relative tolerance for financial numbers
        if max(abs(fa), abs(fb)) > 1000:
            return abs(fa - fb) <= rel_tol * max(abs(fa), abs(fb))
        else:
            # For smaller numbers, use absolute tolerance of 0.01
            return abs(fa - fb) <= 0.01
    except (ValueError, ZeroDivisionError):
        return a == b


def _is_simple_arithmetic_combination(token_val: float, allowed_floats: set, rel_tol: float = 0.02) -> bool:
    """Check if token_val is a simple arithmetic combination of two allowed numbers.
    Checks: a * b, a + b, a - b (within 2% relative tolerance)."""
    for a in allowed_floats:
        for b in allowed_floats:
            if a == 0 or b == 0:
                continue
            # Check multiplication: a * b
            if abs(token_val - a * b) <= 0.02 * max(abs(token_val), abs(a * b)):
                return True
            # Check addition: a + b
            if abs(token_val - (a + b)) <= 0.02 * max(abs(token_val), abs(a + b)):
                return True
            # Check subtraction: a - b
            if abs(token_val - abs(a - b)) <= 0.02 * max(abs(token_val), abs(a - b)):
                return True
            # Check division: a / b
            if b != 0:
                if abs(token_val - a / b) <= 0.02 * max(abs(token_val), abs(a / b)):
                    return True
    return False


def validate_reasoning(text: str, evidence_package: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that model response doesn't invent KEY FINANCIAL numbers not in evidence.
    Lenient validation: ignores dates, counts, IDs, small integers; only validates key financial figures."""
    # Extract all numeric values from evidence as float (normalized)
    evidence_text = json.dumps(evidence_package, default=str)
    allowed_floats = set()
    for token in _extract_numbers(evidence_text):
        try:
            val = float(token.replace(",", ""))
            if _is_key_financial_number(token):
                allowed_floats.add(round(val, 2))
        except ValueError:
            pass
    
    invented = []
    for token in _extract_numbers(text):
        if not _is_key_financial_number(token):
            continue
        try:
            token_val = round(float(token.replace(",", "")), 2)
            # Check if close to any allowed value (within 2% or 0.5 absolute)
            matches = any(abs(token_val - allowed) <= max(0.5, allowed * 0.02) for allowed in allowed_floats)
            if not matches:
                invented.append(token)
        except ValueError:
            invented.append(token)
    
    if invented:
        return {
            "ok": False,
            "invented_tokens": invented,
            "text": (
                "Model explanation discarded because it introduced key financial numbers "
                f"not present in evidence: {', '.join(invented[:8])}."
            ),
        }
    return {"ok": True, "invented_tokens": [], "text": text}


def _deterministic_explanation(finance: Dict[str, Any], evidence: Dict[str, Any]) -> str:
    crop = finance.get("crop")
    action = finance.get("recommended_action")
    sell = finance.get("sell_now") or {}
    hold = finance.get("hold_proxy") or {}
    days = finance.get("days_until_quality_window_end")
    lines = [
        f"Deterministic recommendation for {crop}: {action.replace('_', ' ')}.",
    ]
    if days is not None:
        lines.append(f"Earliest quality-window remaining among retrieved batches: {days} day(s).")
    if sell:
        lines.append(
            f"Sell-now net uses {sell.get('best_market')} at {sell.get('gross_per_kg_inr')} INR/kg "
            f"minus {sell.get('transport_per_kg_inr')} INR/kg freight on {sell.get('quantity_kg')} kg "
            f"= {sell.get('estimated_net_inr')} INR."
        )
    if hold:
        lines.append(
            f"Hold/local proxy uses {hold.get('local_market')} at {hold.get('gross_per_kg_inr')} INR/kg "
            f"on {hold.get('quantity_kg')} kg = {hold.get('estimated_net_inr')} INR "
            "(storage cost not in evidence)."
        )
    if evidence.get("warnings") or finance.get("warnings"):
        lines.append("Missing-data warnings are listed in the evidence pack.")
    lines.append("No live language-model explanation was used.")
    return " ".join(lines)


def reason_with_models(
    evidence: Dict[str, Any],
    finance: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    *,
    meterless_client: Any = None,
    nvidia_client: Any = None,
) -> Dict[str, Any]:
    """Prefer Meterless when a real runtime is injected/available; else NVIDIA FPO adapter; else deterministic text."""
    # Build focused evidence package for the model - only essential data to avoid token bloat and validation issues
    data = evidence.get("data") or {}
    
    # Extract only essential data for the model - avoid token bloat from raw data
    # The finance section already contains computed values with all needed numbers
    # Provide only summaries of raw data to avoid token bloat and validation issues
    def _summarize_inventory(batches):
        if not batches:
            return "No inventory data available"
        # Return summary: count, total kg, crops represented
        total_kg = sum(float(b.get("net_available_kg") or 0) for b in batches)
        crops = set(b.get("crop_name") for b in batches if b.get("crop_name"))
        return f"{len(batches)} batches, {total_kg:,.1f} kg total, crops: {', '.join(sorted(crops))}"
    
    def _summarize_market(market_data):
        if not market_data or market_data.get("status") != "success":
            return "No market data available"
        comps = market_data.get("market_comparison", [])
        if not comps:
            return "No market comparisons available"
        # Return top 3 markets summary
        top = comps[:3]
        return "; ".join(f"{m['market_name']}: {m.get('avg_price', 'N/A')} INR/quintal" for m in top)
    
    def _summarize_transport(transport_data):
        if not transport_data or transport_data.get("status") != "success":
            return "No transport data available"
        routes = transport_data.get("routes", [])
        if not routes:
            return "No routes available"
        # Return cheapest 3 routes
        cheapest = sorted(routes, key=lambda r: float(r.get("transport_cost_per_kg_inr") or 999))[:3]
        return "; ".join(f"{r['origin_warehouse']}->{r['destination_market']}: {r.get('transport_cost_per_kg_inr', 'N/A')} INR/kg" for r in cheapest)
    
    # Build focused evidence package - ONLY provide summarized data and key numbers
    # DO NOT include the full finance object - model should only use KEY_NUMBERS_TO_QUOTE
    key_numbers = {}
    f = finance
    # Only provide FINAL computed values - NO intermediate numbers that could be used for calculations
    key_numbers["quantity_kg_at_risk"] = f.get("quantity_kg_at_risk")
    key_numbers["days_until_quality_window_end"] = f.get("days_until_quality_window_end")
    key_numbers["spoilage_risk_level"] = f.get("spoilage_risk_level")
    key_numbers["recommended_action"] = f.get("recommended_action")
    if f.get("sell_now"):
        key_numbers["sell_now_best_market"] = f["sell_now"].get("best_market")
        # Only provide FINAL net values, NOT intermediate rates that could be multiplied
        key_numbers["sell_now_estimated_net_inr"] = f["sell_now"].get("estimated_net_inr")
        key_numbers["sell_now_net_per_kg_inr"] = f["sell_now"].get("net_per_kg_inr")
        key_numbers["sell_now_transport_per_kg_inr"] = f["sell_now"].get("transport_per_kg_inr")
    if f.get("hold_proxy"):
        key_numbers["hold_proxy_local_market"] = f["hold_proxy"].get("local_market")
        key_numbers["hold_proxy_estimated_net_inr"] = f["hold_proxy"].get("estimated_net_inr")
        key_numbers["hold_proxy_gross_per_kg_inr"] = f["hold_proxy"].get("gross_per_kg_inr")
    if f.get("price_spread_per_kg_inr") is not None:
        key_numbers["price_spread_per_kg_inr"] = f.get("price_spread_per_kg_inr")
    if f.get("cheapest_route"):
        key_numbers["cheapest_route_origin"] = f["cheapest_route"].get("origin_warehouse")
        key_numbers["cheapest_route_destination"] = f["cheapest_route"].get("destination_market")
        key_numbers["cheapest_route_distance_km"] = f["cheapest_route"].get("distance_km")
        key_numbers["cheapest_route_transport_cost_per_kg_inr"] = f["cheapest_route"].get("transport_cost_per_kg_inr")
    
    # Build focused evidence package - ONLY provide summarized data and key numbers
    # DO NOT include the full finance object - model should only use KEY_NUMBERS_TO_QUOTE
    evidence_package = {
        "intent": evidence.get("intent"),
        "crop": evidence.get("crop"),
        "batch_code": evidence.get("batch_code"),
        "warnings": evidence.get("warnings"),
        "sources": evidence.get("sources"),
        # Summarized data only - no raw bulk data
        "inventory_summary": _summarize_inventory(
            data.get("zetaris_inventory") or data.get("inventory", {}).get("items") or data.get("risks", {}).get("critical_batches")
        ),
        "market_summary": _summarize_market(data.get("market")),
        "transport_summary": _summarize_transport(data.get("logistics")),
        "weather_summary": "Weather data not available" if not data.get("weather") else "Weather data available",
        "warehouse_summary": "Warehouse data not available" if not data.get("warehouse") else "Warehouse data available",
        "KEY_NUMBERS_TO_QUOTE": key_numbers,
    }
    
    # Add commonly needed derived numbers to prevent model from inventing them
    # Build prompt with KEY_NUMBERS_TO_QUOTE at the top for model to see first
    prompt = (
        "KEY NUMBERS TO QUOTE DIRECTLY (do not calculate, just quote these exact values):\r\n"
        + json.dumps(key_numbers, default=str)
        + "\r\n\r\nFORBIDDEN: Do NOT perform any arithmetic, multiplication, division, addition, or subtraction on these numbers. "
        "Do NOT compute totals, percentages, differences, or any derived values. "
        "Quote ONLY the exact numbers from KEY_NUMBERS_TO_QUOTE below.\r\n\r\n"
        "EVIDENCE PACKAGE:\r\n"
        + json.dumps(evidence_package, default=str)
    )
    attempts: List[Dict[str, Any]] = []

    def _try(name: str, fn: Callable[[], str], live: bool) -> Optional[Dict[str, Any]]:
        try:
            raw = fn()
        except Exception as exc:
            attempts.append({"provider": name, "status": "error", "message": str(exc), "live": False})
            return None
        checked = validate_reasoning(raw, evidence_package)
        attempts.append({
            "provider": name,
            "status": "ok" if checked["ok"] else "rejected_invented_numbers",
            "live": live,
        })
        if not checked["ok"]:
            return {
                "provider": name,
                "live": False,
                "text": checked["text"],
                "validation": checked,
            }
        return {
            "provider": name,
            "live": live,
            "text": checked["text"],
            "validation": checked,
        }

    if meterless_client is not None:
        result = _try("meterless", lambda: meterless_client.chat(prompt, system_prompt=REASONING_SYSTEM, model="meterless/deep"), True)
        if result and result.get("validation", {}).get("ok"):
            result["attempts"] = attempts
            return result

    if nvidia_client is not None:
        result = _try("nvidia_nim", lambda: nvidia_client.chat(prompt, system_prompt=REASONING_SYSTEM), True)
        if result and result.get("validation", {}).get("ok"):
            result["attempts"] = attempts
            return result

    cfg = config or {}
    # Only attempt live HTTP if callers did not inject clients AND a token/key exists.
    # Default unit tests pass neither, so this stays deterministic / not "live".
    if meterless_client is None and (cfg.get("meterless_runtime_token") or "").strip() not in ("", "rt-local"):
        try:
            text = meterless_mod.chat_completion(prompt, cfg, system_prompt=REASONING_SYSTEM, model="meterless/deep")
            checked = validate_reasoning(text, evidence_package)
            attempts.append({"provider": "meterless", "status": "ok" if checked["ok"] else "rejected", "live": True})
            if checked["ok"]:
                return {"provider": "meterless", "live": True, "text": checked["text"], "validation": checked, "attempts": attempts}
        except Exception as exc:
            attempts.append({"provider": "meterless", "status": "error", "message": str(exc), "live": False})

    if nvidia_client is None and (cfg.get("nvidia_api_key") or "").strip():
        try:
            text = nvidia_mod.chat_completion(prompt, cfg, system_prompt=REASONING_SYSTEM)
            checked = validate_reasoning(text, evidence_package)
            attempts.append({"provider": "nvidia_nim", "status": "ok" if checked["ok"] else "rejected", "live": True})
            if checked["ok"]:
                return {"provider": "nvidia_nim", "live": True, "text": checked["text"], "validation": checked, "attempts": attempts}
        except Exception as exc:
            attempts.append({"provider": "nvidia_nim", "status": "error", "message": str(exc), "live": False})

    text = _deterministic_explanation(finance, evidence)
    return {
        "provider": "deterministic",
        "live": False,
        "text": text,
        "validation": {"ok": True, "invented_tokens": []},
        "attempts": attempts,
        "message": "No live Meterless or NVIDIA FPO model was used.",
    }


def run_pipeline(
    prompt: str,
    config: Optional[Dict[str, Any]] = None,
    *,
    analytics: Any = fpo_analytics,
    zetaris_client: Any = None,
    meterless_client: Any = None,
    nvidia_client: Any = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    # Get or create conversation context
    store = get_context_store()
    if not conversation_id:
        conversation_id = create_conversation_id()
    context_summary = get_context_for_prompt(conversation_id, prompt)

    intent = classify_intent(prompt, context_summary)
    stages = ["intent", "evidence", "finance", "reasoning", "validation", "recommendation"]
    evidence = retrieve_evidence(
        prompt,
        intent=intent,
        analytics=analytics,
        zetaris_client=zetaris_client,
        config=config,
        context=context_summary,
    )
    finance = calculate_finance(evidence)
    # Ensure finance is always a valid dict with expected structure
    if not finance or not isinstance(finance, dict):
        finance = {
            "crop": evidence.get("crop"),
            "quantity_kg_at_risk": 0,
            "markets_ranked": [],
            "cheapest_route": None,
            "sell_now": None,
            "hold_proxy": None,
            "price_spread_per_kg_inr": None,
            "days_until_quality_window_end": None,
            "spoilage_risk_level": None,
            "sales_comparables": [],
            "recommended_action": "insufficient_data",
            "calculation_notes": [],
            "warnings": ["No financial data available"],
            "calculated_at": _now_iso(),
        }
    reasoning = reason_with_models(
        evidence,
        finance,
        config,
        meterless_client=meterless_client,
        nvidia_client=nvidia_client,
    )
    recommendation = {
        "action": finance.get("recommended_action"),
        "crop": finance.get("crop"),
        "sell_now": finance.get("sell_now"),
        "hold_proxy": finance.get("hold_proxy"),
        "best_market": (finance.get("markets_ranked") or [{}])[0] if finance.get("markets_ranked") else None,
        "spoilage": {
            "days_until_quality_window_end": finance.get("days_until_quality_window_end"),
            "spoilage_risk_level": finance.get("spoilage_risk_level"),
        },
        "cost_profit": {
            "quantity_kg_at_risk": finance.get("quantity_kg_at_risk"),
            "price_spread_per_kg_inr": finance.get("price_spread_per_kg_inr"),
            "cheapest_route": finance.get("cheapest_route"),
            "sales_comparables": finance.get("sales_comparables"),
        },
        "notes": finance.get("calculation_notes"),
    }
    live = bool(reasoning.get("live"))
    speak = reasoning.get("text") or "Decision computed from retrieved evidence."

    # Build turn and store in conversation context
    turn = build_turn_from_pipeline(prompt, {
        "intent": intent,
        "evidence": evidence,
        "finance": finance,
        "recommendation": recommendation,
    }, conversation_id)
    store.add_turn(conversation_id, turn)

    # Include actual data rows for inventory/spoilage queries
    data_rows = None
    if intent in ("inventory", "spoilage"):
        data = evidence.get("data") or {}
        # Prefer Zetaris data, fall back to PostgreSQL
        data_rows = data.get("zetaris_inventory") or data.get("zetaris_data") or data.get("inventory", {}).get("items") or data.get("risks", {}).get("critical_batches")

    return {
        "status": "success",
        "live_model": live,
        "provider": reasoning.get("provider"),
        "intent": intent,
        "conversation_id": conversation_id,
        "stages": stages,
        "evidence": {
            "sources": evidence.get("sources"),
            "warnings": list(dict.fromkeys((evidence.get("warnings") or []) + (finance.get("warnings") or []))),
            "retrieved_at": evidence.get("retrieved_at"),
            "crop": evidence.get("crop"),
            "batch_code": evidence.get("batch_code"),
            "data_rows": data_rows,  # Include actual records for data listing queries
        },
        "finance": finance,
        "reasoning": reasoning,
        "recommendation": recommendation,
        "speak": speak,
        "speak_lang": "en",
        "file_data": {
            "type": "fpo_decision",
            "live_model": live,
            "recommendation": recommendation,
            "finance": finance,
            "evidence": evidence.get("sources"),
            "warnings": list(dict.fromkeys((evidence.get("warnings") or []) + (finance.get("warnings") or []))),
            "data_rows": data_rows,  # Include in file_data for frontend
        },
        "logs": [
            f"INTENT: {intent}",
            f"CONVERSATION: {conversation_id[:8]}",
            f"SOURCES: {len(evidence.get('sources') or [])}",
            f"ACTION: {recommendation.get('action')}",
            f"REASONING_PROVIDER: {reasoning.get('provider')} live={live}",
        ],
        "narration_steps": [
            "Classified FPO intent",
            "Retrieved PostgreSQL/Zetaris evidence",
            "Computed deterministic finance",
            "Attached explanation (live model only if a provider answered)",
            "Validated that explanation numbers match finance",
        ],
        "refresh_files": False,
        "image_data": None,
        "timer_data": None,
        "clarification_needed": None,
    }


_DECISION_HINTS = (
    "hold vs sell", "hold or sell", "should we sell", "should we hold",
    "which market", "which mandi", "net profit", "net margin",
    "recommend", "recommendation", "simulate", "decision",
    "arbitrage", "best market", "scn-a", "scn-b", "scn-c", "scn-d", "scn-e",
    "show batches", "show inventory", "show batches", "available batches",
    "batch quantity", "how many batches", "list batches", "tomato batches",
    "onion batches", "potato batches", "crop quantity", "available stock",
    "inventory", "stock level", "quantity available", "tons of", "tonnes of",
    "compare prices", "compare tomato prices", "compare onion prices",
    "compare potato prices", "compare prices in",
    # Follow-up patterns
    "so where", "where should", "where to sell", "sell them", "dispatch them",
    "what about", "how about", "compare", "versus", "vs ", "best market",
    "recommend", "suggestion", "advice",
)


def handle_fpo_decision_command(prompt: str, config: Optional[Dict[str, Any]] = None, conversation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    p = (prompt or "").lower()
    if not any(h in p for h in _DECISION_HINTS):
        return None

    cfg = config or {}

    # Create Meterless client if token is configured
    meterless_client = None
    try:
        from backend.tools import meterless as meterless_mod
        meterless_cfg = meterless_mod.MeterlessConfig.from_config_dict(cfg)
        ok, _ = meterless_cfg.token_status()
        if ok:
            meterless_client = meterless_mod.MeterlessClient(meterless_cfg)
    except Exception:
        pass

    # Create NVIDIA client if API key is configured
    nvidia_client = None
    try:
        from backend.tools import nvidia_nemotron as nvidia_mod
        nvidia_cfg = nvidia_mod.NvidiaFpoConfig.from_config_dict(cfg)
        if nvidia_cfg.api_key:
            nvidia_client = nvidia_mod.NvidiaNemotronClient(nvidia_cfg)
    except Exception:
        pass

    # Create Zetaris client if configured
    zetaris_client = None
    try:
        from backend.tools import zetaris as zetaris_mod
        zclient, zerr = zetaris_mod.get_zetaris_client(cfg)
        if zclient:
            zetaris_client = zclient
    except Exception:
        pass

    result = run_pipeline(
        prompt,
        config=cfg,
        zetaris_client=zetaris_client,
        meterless_client=meterless_client,
        nvidia_client=nvidia_client,
        conversation_id=conversation_id,
    )
    return {
        "speak": result["speak"],
        "speak_lang": result["speak_lang"],
        "logs": result["logs"],
        "file_data": result["file_data"],
        "refresh_files": False,
        "image_data": None,
        "timer_data": None,
        "clarification_needed": None,
        "narration_steps": result["narration_steps"],
        "live_model": result["live_model"],
        "provider": result["provider"],
        "intent": result["intent"],
        "conversation_id": result.get("conversation_id"),
        "recommendation": result["recommendation"],
        "evidence": result["evidence"],
        "finance": result["finance"],
        "reasoning": result["reasoning"],
    }