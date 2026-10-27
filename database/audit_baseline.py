#!/usr/bin/env python3
"""
Comprehensive baseline audit of the FPO database.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date

def main():
    conn = psycopg2.connect('postgresql://nexus_admin:nexus_local_dev@127.0.0.1:5433/nexus_fpo')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("FPO DATABASE BASELINE AUDIT - 2026-10-24")
    print("=" * 80)
    
    # 1. Table counts
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [r['table_name'] for r in cur.fetchall()]
    
    print("\n=== TABLE RECORD COUNTS ===")
    total_records = 0
    for table in tables:
        cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        cnt = cur.fetchone()['cnt']
        total_records += cnt
        print(f"  {table}: {cnt:,}")
    print(f"  TOTAL: {total_records:,}")
    
    # 2. Harvest batch analysis
    print("\n=== HARVEST BATCH ANALYSIS ===")
    cur.execute("""
        SELECT 
            COUNT(*) as total_batches,
            SUM(harvested_quantity_kg) as total_harvested_kg,
            MIN(harvest_date) as earliest_harvest,
            MAX(harvest_date) as latest_harvest,
            COUNT(CASE WHEN harvest_date < CURRENT_DATE THEN 1 END) as historical_batches,
            COUNT(CASE WHEN harvest_date = CURRENT_DATE THEN 1 END) as today_batches,
            COUNT(CASE WHEN harvest_date > CURRENT_DATE THEN 1 END) as future_batches
        FROM harvest_batches
    """)
    hb = cur.fetchone()
    print(f"  Total batches: {hb['total_batches']:,}")
    print(f"  Total harvested: {hb['total_harvested_kg']:,.2f} kg")
    print(f"  Date range: {hb['earliest_harvest']} to {hb['latest_harvest']}")
    print(f"  Historical: {hb['historical_batches']:,}, Today: {hb['today_batches']:,}, Future: {hb['future_batches']:,}")
    
    # 3. Inventory analysis
    print("\n=== INVENTORY ANALYSIS ===")
    cur.execute("""
        SELECT 
            COUNT(*) as inventory_records,
            SUM(quantity_available_kg) as total_available_kg,
            SUM(quantity_reserved_kg) as total_reserved_kg,
            SUM(quantity_available_kg) - SUM(quantity_reserved_kg) as net_available_kg,
            COUNT(DISTINCT batch_id) as batches_with_inventory,
            COUNT(DISTINCT warehouse_id) as warehouses_used
        FROM inventory
    """)
    inv = cur.fetchone()
    print(f"  Inventory records: {inv['inventory_records']:,}")
    print(f"  Total available: {inv['total_available_kg']:,.2f} kg")
    print(f"  Total reserved: {inv['total_reserved_kg']:,.2f} kg")
    print(f"  Net available: {inv['net_available_kg']:,.2f} kg")
    print(f"  Batches with inventory: {inv['batches_with_inventory']:,}")
    print(f"  Warehouses used: {inv['warehouses_used']:,}")
    
    # 4. Inventory by harvest date category
    print("\n=== INVENTORY BY HARVEST DATE CATEGORY ===")
    cur.execute("""
        SELECT 
            CASE 
                WHEN hb.harvest_date < CURRENT_DATE THEN 'historical'
                WHEN hb.harvest_date = CURRENT_DATE THEN 'today'
                WHEN hb.harvest_date > CURRENT_DATE THEN 'future'
            END as harvest_category,
            COUNT(DISTINCT i.batch_id) as batches,
            SUM(i.quantity_available_kg) as available_kg,
            SUM(i.quantity_reserved_kg) as reserved_kg
        FROM inventory i
        JOIN harvest_batches hb ON i.batch_id = hb.batch_id
        GROUP BY harvest_category
        ORDER BY harvest_category
    """)
    for row in cur.fetchall():
        print(f"  {row['harvest_category']}: {row['batches']:,} batches, {row['available_kg']:,.2f} kg available, {row['reserved_kg']:,.2f} kg reserved")
    
    # 5. Quality window risk analysis
    print("\n=== QUALITY WINDOW RISK DISTRIBUTION ===")
    cur.execute("""
        SELECT 
            spoilage_risk_level as risk_level,
            COUNT(*) as batches,
            SUM(total_available_kg) as available_kg
        FROM v_batch_spoilage_risk
        GROUP BY spoilage_risk_level
        ORDER BY 
            CASE spoilage_risk_level 
                WHEN 'expired' THEN 1 
                WHEN 'critical_today' THEN 2 
                WHEN 'high_risk' THEN 3 
                WHEN 'medium_risk' THEN 4 
                WHEN 'low_risk' THEN 5 
                ELSE 6 END
    """)
    for row in cur.fetchall():
        print(f"  {row['risk_level']}: {row['batches']:,} batches, {row['available_kg']:,.2f} kg")
    
    # 6. Sales analysis
    print("\n=== SALES ANALYSIS ===")
    cur.execute("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(quantity_kg) as total_sold_kg,
            SUM(transaction_value_inr) as total_revenue_inr,
            COUNT(CASE WHEN order_status IN ('delivered', 'partial_delivered') THEN 1 END) as completed_orders,
            SUM(CASE WHEN order_status IN ('delivered', 'partial_delivered') THEN quantity_kg ELSE 0 END) as completed_kg
        FROM sales_orders
    """)
    so = cur.fetchone()
    print(f"  Total orders: {so['total_orders']:,}")
    print(f"  Total sold: {so['total_sold_kg']:,.2f} kg")
    print(f"  Total revenue: INR {so['total_revenue_inr']:,.2f}")
    print(f"  Completed orders: {so['completed_orders']:,} ({so['completed_kg']:,.2f} kg)")
    
    # 7. Warehouse capacity
    print("\n=== WAREHOUSE CAPACITY ===")
    cur.execute("""
        SELECT 
            COUNT(*) as total_warehouses,
            SUM(capacity_kg) as total_capacity_kg,
            SUM(current_stock_kg) as total_stock_kg,
            ROUND(AVG(utilization_pct), 2) as avg_utilization_pct,
            COUNT(CASE WHEN utilization_pct > 100 THEN 1 END) as over_capacity,
            COUNT(CASE WHEN utilization_pct > 80 THEN 1 END) as high_utilization
        FROM v_warehouse_capacity_utilization
    """)
    wh = cur.fetchone()
    print(f"  Warehouses: {wh['total_warehouses']:,}")
    print(f"  Total capacity: {wh['total_capacity_kg']:,.2f} kg")
    print(f"  Current stock: {wh['total_stock_kg']:,.2f} kg")
    print(f"  Avg utilization: {wh['avg_utilization_pct']:.2f}%")
    print(f"  Over capacity: {wh['over_capacity']:,}")
    print(f"  High utilization (>80%): {wh['high_utilization']:,}")
    
    # 8. Crop distribution
    print("\n=== CROP DISTRIBUTION ===")
    cur.execute("""
        SELECT c.crop_name, c.variety, 
               COUNT(hb.batch_id) as batches,
               SUM(hb.harvested_quantity_kg) as total_kg
        FROM harvest_batches hb
        JOIN crops c ON hb.crop_id = c.crop_id
        GROUP BY c.crop_name, c.variety
        ORDER BY total_kg DESC
        LIMIT 15
    """)
    for row in cur.fetchall():
        print(f"  {row['crop_name']} ({row['variety']}): {row['batches']:,} batches, {row['total_kg']:,.2f} kg")
    
    # 9. FPO distribution
    print("\n=== FPO DISTRIBUTION ===")
    cur.execute("""
        SELECT f.fpo_code, f.fpo_name,
               COUNT(DISTINCT hb.batch_id) as batches,
               SUM(hb.harvested_quantity_kg) as harvested_kg,
               COALESCE(SUM(i.quantity_available_kg), 0) as available_kg
        FROM fpos f
        LEFT JOIN farmers fr ON f.fpo_id = fr.fpo_id
        LEFT JOIN farms fm ON fr.farmer_id = fm.farmer_id
        LEFT JOIN harvest_batches hb ON fm.farm_id = hb.farm_id
        LEFT JOIN inventory i ON hb.batch_id = i.batch_id
        GROUP BY f.fpo_id, f.fpo_code, f.fpo_name
        ORDER BY harvested_kg DESC NULLS LAST
        LIMIT 15
    """)
    for row in cur.fetchall():
        print(f"  {row['fpo_code']} ({row['fpo_name']}): {row['batches'] or 0} batches, harvested: {row['harvested_kg'] or 0:,.2f} kg, available: {row['available_kg']:,.2f} kg")
    
    # 10. Geographical audit
    print("\n=== GEOGRAPHICAL AUDIT ===")
    cur.execute("""
        SELECT DISTINCT district, state 
        FROM buyers 
        WHERE district = 'District' OR state = 'State'
        ORDER BY district, state
    """)
    placeholders = cur.fetchall()
    print(f"  Buyer placeholder locations: {len(placeholders)}")
    for p in placeholders[:10]:
        print(f"    District: '{p['district']}', State: '{p['state']}'")
    
    cur.execute("""
        SELECT DISTINCT district, state 
        FROM buyers 
        WHERE latitude IS NULL OR longitude IS NULL
        ORDER BY district, state
    """)
    missing_coords = cur.fetchall()
    print(f"  Buyers missing coordinates: {len(missing_coords)}")
    
    cur.execute("""
        SELECT market_name, district, state, COUNT(*) as observations
        FROM market_prices
        GROUP BY market_name, district, state
        ORDER BY observations DESC
    """)
    print("  Market price locations:")
    for row in cur.fetchall():
        print(f"    {row['market_name']}, {row['district']}, {row['state']}: {row['observations']} obs")
    
    # 11. Batch status distribution
    print("\n=== BATCH STATUS DISTRIBUTION ===")
    cur.execute("""
        SELECT status, COUNT(*) as count, SUM(harvested_quantity_kg) as total_kg
        FROM harvest_batches
        GROUP BY status
        ORDER BY count DESC
    """)
    for row in cur.fetchall():
        print(f"  {row['status']}: {row['count']:,} batches, {row['total_kg']:,.2f} kg")
    
    # 12. Inventory status
    print("\n=== INVENTORY STATUS DISTRIBUTION ===")
    cur.execute("""
        SELECT stock_status, COUNT(*) as count, SUM(quantity_available_kg) as total_kg
        FROM inventory
        GROUP BY stock_status
        ORDER BY count DESC
    """)
    for row in cur.fetchall():
        print(f"  {row['stock_status']}: {row['count']:,} records, {row['total_kg']:,.2f} kg")
    
    # 13. Price consistency
    print("\n=== PRICE CONSISTENCY CHECK ===")
    cur.execute("""
        SELECT COUNT(*) as violations
        FROM market_prices
        WHERE minimum_price_inr_per_quintal > modal_price_inr_per_quintal
           OR modal_price_inr_per_quintal > maximum_price_inr_per_quintal
    """)
    price_violations = cur.fetchone()
    print(f"  Price ordering violations: {price_violations['violations']}")
    
    cur.execute("""
        SELECT source_type, COUNT(*) as count
        FROM market_prices
        GROUP BY source_type
    """)
    for row in cur.fetchall():
        print(f"  {row['source_type']}: {row['count']:,} records")
    
    # 13. Data quality flags
    cur.execute("""
        SELECT data_quality_flag, COUNT(*) as count
        FROM market_prices
        GROUP BY data_quality_flag
    """)
    for row in cur.fetchall():
        print(f"  {row['data_quality_flag']}: {row['count']:,} records")
    
    # 14. Demo scenario linkage
    print("\n=== DEMO SCENARIO LINKAGE ===")
    cur.execute("""
        SELECT ds.scenario_code, ds.scenario_name, COUNT(de.entity_id) as linked_entities
        FROM demo_scenarios ds
        LEFT JOIN demo_scenario_entities de ON ds.scenario_id = de.scenario_id
        GROUP BY ds.scenario_id, ds.scenario_code, ds.scenario_name
        ORDER BY ds.scenario_code
    """)
    for row in cur.fetchall():
        print(f"  {row['scenario_code']}: {row['linked_entities']} linked entities")
    
    # 15. Generation log
    print("\n=== DATA GENERATION LOG ===")
    cur.execute("""
        SELECT generation_run_id, stage, table_name, records_target, records_generated, 
               status, started_at, completed_at
        FROM data_generation_log
        ORDER BY started_at DESC
    """)
    for row in cur.fetchall():
        print(f"  {row['stage']} - {row['table_name']}: target={row['records_target']:,}, generated={row['records_generated']:,}, status={row['status']}")
    
    conn.close()
    print("\n" + "=" * 80)
    print("BASELINE AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()