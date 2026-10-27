import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional

DEFAULT_PG_URL = os.getenv("FPO_DATABASE_URL", "postgresql://nexus_admin:nexus_local_dev@127.0.0.1:5433/nexus_fpo")

def get_connection():
    """Create a scoped PostgreSQL connection."""
    return psycopg2.connect(DEFAULT_PG_URL)

def get_overview_stats(fpo_id: Optional[str] = None, crop_name: Optional[str] = None) -> Dict[str, Any]:
    """Fetch core operational KPIs for the FPO network."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM fpos) as total_fpos,
                        (SELECT COUNT(*) FROM farmers) as total_farmers,
                        (SELECT COUNT(*) FROM crops) as total_crops,
                        (SELECT COUNT(*) FROM harvest_batches WHERE status = 'harvested') as active_batches,
                        (SELECT COALESCE(SUM(quantity_available_kg), 0) FROM inventory) as total_available_kg,
                        (SELECT COALESCE(SUM(quantity_reserved_kg), 0) FROM inventory) as total_reserved_kg,
                        (SELECT ROUND(AVG(utilization_pct)::numeric, 1) FROM v_warehouse_capacity_utilization) as avg_warehouse_utilization,
                        (SELECT COUNT(*) FROM v_warehouse_capacity_utilization WHERE utilization_pct >= 80) as warehouses_near_capacity
                """)
                overview = dict(cur.fetchone())

                cur.execute("""
                    SELECT spoilage_risk_level, COUNT(*) as count, COALESCE(SUM(net_available_kg), 0) as total_kg
                    FROM v_batch_spoilage_risk
                    GROUP BY spoilage_risk_level
                    ORDER BY 
                        CASE spoilage_risk_level
                            WHEN 'critical_today' THEN 1
                            WHEN 'high_risk' THEN 2
                            WHEN 'medium_risk' THEN 3
                            WHEN 'low_risk' THEN 4
                            ELSE 5
                        END
                """)
                spoilage = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT c.crop_name, c.perishability_category, 
                           SUM(i.quantity_available_kg) as available_kg,
                           COUNT(DISTINCT hb.batch_id) as batch_count
                    FROM inventory i
                    JOIN harvest_batches hb ON i.batch_id = hb.batch_id
                    JOIN crops c ON hb.crop_id = c.crop_id
                    GROUP BY c.crop_name, c.perishability_category
                    ORDER BY available_kg DESC
                    LIMIT 8
                """)
                top_crops = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT storage_type, COUNT(*) as total_warehouses,
                           ROUND(AVG(utilization_pct)::numeric, 1) as avg_utilization_pct,
                           SUM(capacity_kg) as total_capacity_kg,
                           SUM(current_stock_kg) as total_stock_kg
                    FROM v_warehouse_capacity_utilization
                    GROUP BY storage_type
                    ORDER BY total_capacity_kg DESC
                """)
                warehouse_summary = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT DISTINCT ON (crop_name)
                        crop_name, market_name, observation_date, modal_price_inr_per_quintal, price_change_pct
                    FROM v_crop_market_price_trends
                    ORDER BY crop_name, observation_date DESC
                    LIMIT 8
                """)
                market_trends = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "overview": overview,
                    "spoilage": spoilage,
                    "top_crops": top_crops,
                    "warehouse_summary": warehouse_summary,
                    "market_trends": market_trends
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_inventory_batches(page: int = 1, page_size: int = 25, 
                          crop_name: Optional[str] = None, 
                          district: Optional[str] = None,
                          risk_level: Optional[str] = None,
                          search: Optional[str] = None) -> Dict[str, Any]:
    """Server-side paginated inventory batch list."""
    try:
        offset = max(0, (page - 1) * page_size)
        conditions = ["1=1"]
        params = []

        if crop_name and crop_name != 'All':
            conditions.append("crop_name = %s")
            params.append(crop_name)
        if district and district != 'All':
            conditions.append("farm_district = %s")
            params.append(district)
        if risk_level and risk_level != 'All':
            conditions.append("spoilage_risk_level = %s")
            params.append(risk_level)
        if search:
            conditions.append("(batch_code ILIKE %s OR crop_name ILIKE %s OR farm_district ILIKE %s)")
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard, wildcard])

        where_clause = " AND ".join(conditions)

        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                count_query = f"SELECT COUNT(*) as total FROM v_batch_spoilage_risk WHERE {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()['total']

                data_query = f"""
                    SELECT 
                        batch_id, batch_code, crop_name, variety, perishability_category,
                        harvest_date, initial_quality_grade, estimated_quality_window_end,
                        days_until_quality_window_end, spoilage_risk_level,
                        harvested_quantity_kg, total_available_kg, total_reserved_kg,
                        net_available_kg, warehouse_count, farm_district, farm_state
                    FROM v_batch_spoilage_risk
                    WHERE {where_clause}
                    ORDER BY 
                        CASE spoilage_risk_level
                            WHEN 'critical_today' THEN 1
                            WHEN 'high_risk' THEN 2
                            WHEN 'medium_risk' THEN 3
                            WHEN 'low_risk' THEN 4
                            ELSE 5
                        END,
                        days_until_quality_window_end ASC
                    LIMIT %s OFFSET %s
                """
                cur.execute(data_query, params + [page_size, offset])
                rows = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
                    "batches": rows
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_market_intelligence(crop_name: Optional[str] = None, market_name: Optional[str] = None) -> Dict[str, Any]:
    """Historical market prices, market comparisons, and trends."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                target_crop = crop_name or 'Tomato'
                
                cur.execute("""
                    SELECT observation_date, market_name, 
                           ROUND(AVG(modal_price_inr_per_quintal)::numeric, 2) as avg_modal_price,
                           ROUND(MIN(min_price_inr_per_quintal)::numeric, 2) as min_price,
                           ROUND(MAX(max_price_inr_per_quintal)::numeric, 2) as max_price
                    FROM v_crop_market_price_trends
                    WHERE crop_name = %s
                    GROUP BY observation_date, market_name
                    ORDER BY observation_date DESC
                    LIMIT 60
                """, (target_crop,))
                trends = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT market_name, district, state,
                           ROUND(AVG(modal_price_inr_per_quintal)::numeric, 2) as avg_price,
                           ROUND(MIN(min_price_inr_per_quintal)::numeric, 2) as min_price,
                           ROUND(MAX(max_price_inr_per_quintal)::numeric, 2) as max_price,
                           COUNT(*) as observations_count
                    FROM v_crop_market_price_trends
                    WHERE crop_name = %s
                    GROUP BY market_name, district, state
                    ORDER BY avg_price DESC
                    LIMIT 15
                """, (target_crop,))
                market_comparison = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT b.buyer_name, b.buyer_type, b.market, 
                           COUNT(so.order_id) as total_orders,
                           ROUND(SUM(so.total_amount_inr)::numeric, 2) as total_purchase_inr,
                           ROUND(AVG(so.unit_price_inr_per_kg)::numeric, 2) as avg_unit_price_inr
                    FROM buyers b
                    JOIN sales_orders so ON b.buyer_id = so.buyer_id
                    JOIN harvest_batches hb ON so.batch_id = hb.batch_id
                    JOIN crops c ON hb.crop_id = c.crop_id
                    WHERE c.crop_name = %s
                    GROUP BY b.buyer_name, b.buyer_type, b.market
                    ORDER BY total_purchase_inr DESC
                    LIMIT 10
                """, (target_crop,))
                top_buyers = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "crop": target_crop,
                    "trends": trends,
                    "market_comparison": market_comparison,
                    "top_buyers": top_buyers
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_logistics_intelligence() -> Dict[str, Any]:
    """Warehouse locations, utilization, and top transport routes."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT warehouse_id, warehouse_name, district, state,
                           capacity_kg, current_stock_kg, remaining_capacity_kg,
                           utilization_pct, storage_type, temperature_controlled,
                           distinct_batches, distinct_crops
                    FROM v_warehouse_capacity_utilization
                    ORDER BY utilization_pct DESC
                    LIMIT 25
                """)
                warehouses = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT route_id, origin_warehouse, origin_district,
                           destination_buyer, destination_market,
                           distance_km, vehicle_type,
                           transport_cost_per_kg_inr, total_cost_inr
                    FROM v_transport_cost_analysis
                    ORDER BY transport_cost_per_kg_inr ASC
                    LIMIT 25
                """)
                routes = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "warehouses": warehouses,
                    "routes": routes
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_risk_centre(risk_level: Optional[str] = None) -> Dict[str, Any]:
    """Risk alerts: high spoilage risks and warehouse capacity bottlenecks."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        batch_id, batch_code, crop_name, variety, perishability_category,
                        harvest_date, estimated_quality_window_end, days_until_quality_window_end,
                        spoilage_risk_level, net_available_kg, farm_district, farm_state
                    FROM v_batch_spoilage_risk
                    WHERE spoilage_risk_level IN ('critical_today', 'high_risk')
                    ORDER BY days_until_quality_window_end ASC
                    LIMIT 30
                """)
                critical_batches = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT warehouse_id, warehouse_name, district, state,
                           capacity_kg, current_stock_kg, remaining_capacity_kg,
                           utilization_pct, storage_type, temperature_controlled
                    FROM v_warehouse_capacity_utilization
                    WHERE utilization_pct >= 90
                    ORDER BY utilization_pct DESC
                    LIMIT 20
                """)
                congested_warehouses = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT crop_name, 
                           COUNT(*) as total_batches,
                           SUM(CASE WHEN spoilage_risk_level = 'critical_today' THEN 1 ELSE 0 END) as critical_count,
                           SUM(CASE WHEN spoilage_risk_level = 'high_risk' THEN 1 ELSE 0 END) as high_risk_count,
                           ROUND(SUM(net_available_kg)::numeric, 0) as at_risk_quantity_kg
                    FROM v_batch_spoilage_risk
                    WHERE spoilage_risk_level IN ('critical_today', 'high_risk')
                    GROUP BY crop_name
                    ORDER BY at_risk_quantity_kg DESC
                """)
                crop_risk_summary = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "critical_batches": critical_batches,
                    "congested_warehouses": congested_warehouses,
                    "crop_risk_summary": crop_risk_summary
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_decisions_scenarios() -> Dict[str, Any]:
    """Predefined demo scenarios and net revenue analysis."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT s.scenario_id, s.scenario_code, s.scenario_name, s.crop_name,
                           s.risk_category, s.description, s.created_at
                    FROM demo_scenarios s
                    ORDER BY s.scenario_code
                """)
                scenarios = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT scenario_code, scenario_name, scenario_type, 
                           entity_type, entity_id_ref, role_in_scenario, notes
                    FROM v_active_demo_scenarios_with_entities
                    ORDER BY scenario_code
                """)
                linked_entities = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT order_code, crop_name, 
                           gross_revenue_inr, transport_cost_inr,
                           estimated_net_revenue_inr, net_margin_pct
                    FROM v_sales_with_transport_cost
                    ORDER BY estimated_net_revenue_inr DESC
                    LIMIT 15
                """)
                sales_analysis = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "scenarios": scenarios,
                    "linked_entities": linked_entities,
                    "sales_analysis": sales_analysis
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_datasources_status() -> Dict[str, Any]:
    """Check PostgreSQL, Zetaris and FastAPI connectivity status safely."""
    pg_ok = False
    table_counts = {}
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """)
                tables = [r['table_name'] for r in cur.fetchall()]
                for t in tables:
                    cur.execute(f"SELECT COUNT(*) as cnt FROM {t}")
                    table_counts[t] = cur.fetchone()['cnt']
                pg_ok = True
    except Exception as e:
        table_counts["error"] = str(e)

    zetaris_status = {"connected": False, "message": "Not checked"}
    try:
        from backend.tools import zetaris
        cfg = {
            'zetaris_rest_url': 'http://localhost:8888/api/v1.0',
            'zetaris_auth_url': 'http://localhost:8889',
            'zetaris_username': 'admin@zetaris.com',
            'zetaris_password': 'Zetaris1@',
            'zetaris_org_id': '',
        }
        client, err = zetaris.get_zetaris_client(cfg)
        if client:
            res = client.test_connection()
            zetaris_status = {
                "connected": bool(res.success),
                "message": res.message or "Connected",
                "base_url": "http://localhost:8888/api/v1.0",
                "source_registered": "NEXUS_FPO"
            }
        else:
            zetaris_status["message"] = err or "Client configuration failed"
    except Exception as e:
        zetaris_status = {"connected": False, "message": str(e)}

    return {
        "status": "success",
        "postgresql": {
            "connected": pg_ok,
            "database": "nexus_fpo",
            "host": "127.0.0.1:5433 (docker: nexus-fpo-db)",
            "table_counts": table_counts
        },
        "zetaris": zetaris_status,
        "fastapi": {
            "connected": True,
            "version": "2.4.3"
        }
    }

def get_filter_options() -> Dict[str, Any]:
    """Dropdown options for filtering across pages."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT DISTINCT crop_name FROM crops ORDER BY crop_name")
                crops = [r['crop_name'] for r in cur.fetchall()]

                cur.execute("SELECT DISTINCT district FROM fpos WHERE district IS NOT NULL ORDER BY district")
                districts = [r['district'] for r in cur.fetchall()]

                cur.execute("SELECT DISTINCT fpo_id, fpo_name, district FROM fpos ORDER BY fpo_name LIMIT 30")
                fpos = [dict(r) for r in cur.fetchall()]

                return {
                    "status": "success",
                    "crops": crops,
                    "districts": districts,
                    "fpos": fpos,
                    "risk_levels": ["critical_today", "high_risk", "medium_risk", "low_risk"]
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_fpo_agent_command(prompt: str) -> Optional[Dict[str, Any]]:
    """Handle natural language agricultural commands with real data from nexus_fpo."""
    p = prompt.lower().strip()
    
    # 1. Spoilage risk queries
    if any(k in p for k in ["spoilage", "risk", "critical batch", "batches at risk", "shelf life"]):
        res = get_risk_centre()
        if res.get("status") == "success":
            critical = res.get("critical_batches", [])[:5]
            summary = res.get("crop_risk_summary", [])[:4]
            lines = [f"Found {len(res.get('critical_batches', []))} harvest batches with active spoilage risk."]
            for b in critical:
                lines.append(f"• Batch {b['batch_code']} ({b['crop_name']} - {b['variety']}): {b['net_available_kg']} kg in {b['farm_district']} - {b['days_until_quality_window_end']} days left ({b['spoilage_risk_level']})")
            
            speak = f"Identified {len(critical)} batches requiring priority dispatch due to quality window expiration."
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": [f"INPUT: \"{prompt}\"", "QUERY: v_batch_spoilage_risk", f"RESULT: {len(critical)} priority batches"],
                "file_data": {"type": "risk_report", "batches": critical, "crops": summary},
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": ["Analyzing crop perishability", "Checking storage time limits", "Formulating dispatch advice"]
            }

    # 2. Warehouse capacity queries
    if any(k in p for k in ["warehouse", "capacity", "storage utilization", "godown", "storage facility"]):
        res = get_logistics_intelligence()
        if res.get("status") == "success":
            whs = res.get("warehouses", [])[:5]
            lines = ["Current Warehouse Utilization:"]
            for w in whs:
                lines.append(f"• {w['warehouse_name']} ({w['district']}): {w['utilization_pct']}% full ({w['current_stock_kg']} / {w['capacity_kg']} kg)")
            speak = f"Top warehouse is {whs[0]['warehouse_name']} at {whs[0]['utilization_pct']}% capacity." if whs else "Warehouses checked."
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": [f"INPUT: \"{prompt}\"", "QUERY: v_warehouse_capacity_utilization", f"RESULT: {len(whs)} warehouses checked"],
                "file_data": {"type": "warehouse_report", "warehouses": whs},
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": ["Scanning storage nodes", "Aggregating utilization metric"]
            }

    # 3. Crop quantity/availability queries
    if any(k in p for k in ["quantity", "available", "stock", "how much", "tons", "tonnes", "in tons", "in tonnes", "total quantity", "total available"]):
        crop = "Tomato"
        for c in ["Tomato", "Onion", "Potato", "Grapes", "Banana", "Turmeric", "Pomegranate", "Wheat", "Soybean", "Chilli", "Cotton"]:
            if c.lower() in p:
                crop = c
                break
        res = get_inventory_batches(page=1, page_size=20, crop_name=crop)
        if res.get("status") == "success":
            total_kg = sum(b.get("net_available_kg", 0) for b in res.get("batches", []))
            total_tons = total_kg / 1000
            batch_count = res.get("total", 0)
            lines = [f"{crop} Inventory Summary:"]
            lines.append(f"• Total Available: {total_kg:,.0f} kg ({total_tons:.2f} tons)")
            lines.append(f"• Active Batches: {batch_count}")
            speak = f"Total available {crop.lower()}: {total_kg:,.0f} kilograms ({total_tons:.2f} tons) across {batch_count} batches."
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": [f"INPUT: \"{prompt}\"", "QUERY: v_batch_spoilage_risk (inventory)", f"RESULT: {total_kg:,.0f} kg {crop}"],
                "file_data": {"type": "inventory_report", "crop": crop, "total_kg": total_kg, "total_tons": total_tons, "batch_count": batch_count, "batches": res.get("batches", [])},
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": ["Querying inventory by crop", "Aggregating net available quantities", "Converting to tons"]
            }

    # 4. Market price queries
    if any(k in p for k in ["market", "price", "mandi", "rate", "bhav"]):
        crop = "Tomato"
        for c in ["Onion", "Potato", "Tomato", "Grapes", "Banana", "Turmeric", "Pomegranate", "Wheat", "Soybean"]:
            if c.lower() in p:
                crop = c
                break
        res = get_market_intelligence(crop_name=crop)
        if res.get("status") == "success":
            comps = res.get("market_comparison", [])[:4]
            lines = [f"{crop} Price Observations:"]
            for m in comps:
                lines.append(f"• {m['market_name']} ({m['district']}): Modal ₹{m['avg_price']}/quintal (Range: ₹{m['min_price']} - ₹{m['max_price']})")
            speak = f"{crop} modal price ranges up to ₹{comps[0]['avg_price']}/quintal in {comps[0]['market_name']}." if comps else "Prices fetched."
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": [f"INPUT: \"{prompt}\"", f"QUERY: v_crop_market_price_trends ({crop})", f"RESULT: {len(comps)} markets compared"],
                "file_data": {"type": "market_report", "crop": crop, "markets": comps},
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": ["Querying mandi price trends", "Evaluating regional arbitrage"]
            }

    # 4. Overview / KPI query
    if any(k in p for k in ["fpo", "overview", "kpi", "summary", "dashboard stats", "how many"]):
        res = get_overview_stats()
        if res.get("status") == "success":
            ov = res["overview"]
            speak = f"NEXUS manages {ov['total_fpos']} FPOs, {ov['total_farmers']:,} registered farmers, and {ov['active_batches']} active harvest batches across Maharashtra and Telangana."
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": [f"INPUT: \"{prompt}\"", "QUERY: FPO Network Statistics", f"RESULT: {ov['total_fpos']} FPOs, {ov['total_farmers']} farmers"],
                "file_data": {"type": "overview_report", "stats": ov},
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": ["Aggregating federated FPO metrics", "Verifying live database telemetry"]
            }

    return None

