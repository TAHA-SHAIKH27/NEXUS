-- Migration 002: Analytical Views and Additional Indexes
-- Created: 2026-10-24
-- Description: Creates materialized views and additional indexes for common analytical queries.

-- ============================================================
-- View: v_batch_inventory_summary
-- Aggregated view of batch inventory across warehouses
-- ============================================================
CREATE VIEW v_batch_inventory_summary AS
SELECT
    hb.batch_id,
    hb.batch_code,
    hb.harvest_date,
    hb.crop_id,
    c.crop_name,
    c.variety,
    c.perishability_category,
    c.typical_storage_days,
    hb.harvested_quantity_kg,
    hb.initial_quality_grade,
    hb.estimated_quality_window_end,
    hb.status AS batch_status,
    f.farm_id,
    f.farmer_id,
    fr.district AS farm_district,
    fr.state AS farm_state,
    fr.fpo_id,
    COALESCE(SUM(i.quantity_available_kg), 0) AS total_available_kg,
    COALESCE(SUM(i.quantity_reserved_kg), 0) AS total_reserved_kg,
    COALESCE(SUM(i.quantity_available_kg), 0) - COALESCE(SUM(i.quantity_reserved_kg), 0) AS net_available_kg,
    COUNT(DISTINCT i.warehouse_id) AS warehouse_count,
    MAX(i.last_updated) AS last_inventory_update
FROM harvest_batches hb
JOIN crops c ON hb.crop_id = c.crop_id
JOIN farms f ON hb.farm_id = f.farm_id
JOIN farmers fr ON f.farmer_id = fr.farmer_id
LEFT JOIN inventory i ON hb.batch_id = i.batch_id
GROUP BY
    hb.batch_id, hb.batch_code, hb.harvest_date, hb.crop_id,
    c.crop_name, c.variety, c.perishability_category, c.typical_storage_days,
    hb.harvested_quantity_kg, hb.initial_quality_grade,
    hb.estimated_quality_window_end, hb.status,
    f.farm_id, f.farmer_id, fr.district, fr.state, fr.fpo_id;

COMMENT ON VIEW v_batch_inventory_summary IS 'Aggregated inventory view per harvest batch with farm/FPO context';

-- ============================================================
-- View: v_warehouse_capacity_utilization
-- Current capacity utilization per warehouse
-- ============================================================
CREATE VIEW v_warehouse_capacity_utilization AS
SELECT
    w.warehouse_id,
    w.warehouse_name,
    w.fpo_id,
    w.district,
    w.state,
    w.capacity_kg,
    w.storage_type,
    w.temperature_controlled,
    COALESCE(SUM(i.quantity_available_kg), 0) AS current_stock_kg,
    ROUND(
        CASE WHEN w.capacity_kg > 0
        THEN (COALESCE(SUM(i.quantity_available_kg), 0) / w.capacity_kg) * 100
        ELSE 0 END, 2
    ) AS utilization_pct,
    w.capacity_kg - COALESCE(SUM(i.quantity_available_kg), 0) AS remaining_capacity_kg,
    COUNT(DISTINCT i.batch_id) AS distinct_batches,
    COUNT(DISTINCT hb.crop_id) AS distinct_crops
FROM warehouses w
LEFT JOIN inventory i ON w.warehouse_id = i.warehouse_id
LEFT JOIN harvest_batches hb ON i.batch_id = hb.batch_id
WHERE w.active_status = TRUE
GROUP BY
    w.warehouse_id, w.warehouse_name, w.fpo_id, w.district, w.state,
    w.capacity_kg, w.storage_type, w.temperature_controlled;

COMMENT ON VIEW v_warehouse_capacity_utilization IS 'Real-time warehouse capacity utilization';

-- ============================================================
-- View: v_crop_market_price_trends
-- Recent market price trends per crop and market
-- ============================================================
CREATE VIEW v_crop_market_price_trends AS
SELECT
    mp.crop_id,
    c.crop_name,
    c.variety,
    mp.market_name,
    mp.district,
    mp.state,
    mp.observation_date,
    mp.modal_price_inr_per_quintal,
    mp.minimum_price_inr_per_quintal,
    mp.maximum_price_inr_per_quintal,
    mp.source_type,
    LAG(mp.modal_price_inr_per_quintal) OVER (
        PARTITION BY mp.crop_id, mp.market_name
        ORDER BY mp.observation_date
    ) AS prev_modal_price,
    ROUND(
        CASE
            WHEN LAG(mp.modal_price_inr_per_quintal) OVER (
                PARTITION BY mp.crop_id, mp.market_name
                ORDER BY mp.observation_date
            ) > 0
            THEN (
                (mp.modal_price_inr_per_quintal - LAG(mp.modal_price_inr_per_quintal) OVER (
                    PARTITION BY mp.crop_id, mp.market_name
                    ORDER BY mp.observation_date
                )) / LAG(mp.modal_price_inr_per_quintal) OVER (
                    PARTITION BY mp.crop_id, mp.market_name
                    ORDER BY mp.observation_date
                )
            ) * 100
        ELSE NULL
        END, 2
    ) AS price_change_pct
FROM market_prices mp
JOIN crops c ON mp.crop_id = c.crop_id
WHERE mp.observation_date >= CURRENT_DATE - INTERVAL '90 days'
  AND mp.data_quality_flag IN ('verified', 'estimated');

COMMENT ON VIEW v_crop_market_price_trends IS '90-day market price trends with day-over-day change percentage';

-- ============================================================
-- View: v_batch_spoilage_risk
-- Batches approaching quality window end with current inventory
-- ============================================================
CREATE VIEW v_batch_spoilage_risk AS
SELECT
    bis.*,
    CASE
        WHEN bis.estimated_quality_window_end IS NULL THEN 'unknown'
        WHEN bis.estimated_quality_window_end < CURRENT_DATE THEN 'expired'
        WHEN bis.estimated_quality_window_end = CURRENT_DATE THEN 'critical_today'
        WHEN bis.estimated_quality_window_end <= CURRENT_DATE + INTERVAL '3 days' THEN 'high_risk'
        WHEN bis.estimated_quality_window_end <= CURRENT_DATE + INTERVAL '7 days' THEN 'medium_risk'
        ELSE 'low_risk'
    END AS spoilage_risk_level,
    bis.estimated_quality_window_end - CURRENT_DATE AS days_until_quality_window_end
FROM v_batch_inventory_summary bis
WHERE bis.net_available_kg > 0
  AND bis.batch_status NOT IN ('fully_sold', 'spoiled', 'discarded');

COMMENT ON VIEW v_batch_spoilage_risk IS 'Batches at risk of quality degradation with days remaining';

-- ============================================================
-- View: v_fpo_revenue_summary
-- Revenue and sales summary per FPO
-- ============================================================
CREATE VIEW v_fpo_revenue_summary AS
SELECT
    fpo.fpo_id,
    fpo.fpo_code,
    fpo.fpo_name,
    COUNT(DISTINCT so.order_id) AS total_orders,
    COUNT(DISTINCT so.batch_id) AS batches_sold,
    COALESCE(SUM(so.quantity_kg), 0) AS total_qty_sold_kg,
    COALESCE(SUM(so.transaction_value_inr), 0) AS total_revenue_inr,
    COUNT(DISTINCT so.buyer_id) AS distinct_buyers,
    MIN(so.order_date) AS first_sale_date,
    MAX(so.order_date) AS last_sale_date
FROM fpos fpo
JOIN farmers fr ON fpo.fpo_id = fr.fpo_id
JOIN farms f ON fr.farmer_id = f.farmer_id
JOIN harvest_batches hb ON f.farm_id = hb.farm_id
JOIN sales_orders so ON hb.batch_id = so.batch_id
WHERE so.order_status IN ('delivered', 'partial_delivered')
GROUP BY fpo.fpo_id, fpo.fpo_code, fpo.fpo_name;

COMMENT ON VIEW v_fpo_revenue_summary IS 'Aggregated sales revenue per FPO';

-- ============================================================
-- View: v_transport_cost_analysis
-- Transport cost per kg for each route
-- ============================================================
CREATE VIEW v_transport_cost_analysis AS
SELECT
    tr.route_id,
    tr.origin_warehouse_id,
    w.warehouse_name AS origin_warehouse,
    w.district AS origin_district,
    w.state AS origin_state,
    tr.destination_buyer_id,
    b.buyer_name,
    b.market_name AS destination_market,
    b.district AS dest_district,
    b.state AS dest_state,
    tr.distance_km,
    tr.vehicle_type,
    tr.capacity_kg,
    tr.estimated_total_cost_inr,
    ROUND(tr.estimated_total_cost_inr / NULLIF(tr.capacity_kg, 0), 4) AS cost_per_kg,
    ROUND(tr.estimated_total_cost_inr / NULLIF(tr.distance_km, 0), 2) AS cost_per_km_distance,
    tr.route_status
FROM transport_routes tr
JOIN warehouses w ON tr.origin_warehouse_id = w.warehouse_id
JOIN buyers b ON tr.destination_buyer_id = b.buyer_id
WHERE tr.route_status = 'active';

COMMENT ON VIEW v_transport_cost_analysis IS 'Per-kg transport cost analysis for active routes';

-- ============================================================
-- View: v_sales_with_transport_cost
-- Sales orders joined with transport costs for net revenue calculation
-- ============================================================
CREATE VIEW v_sales_with_transport_cost AS
SELECT
    so.order_id,
    so.order_code,
    so.batch_id,
    hb.batch_code,
    hb.crop_id,
    c.crop_name,
    so.buyer_id,
    b.buyer_name,
    so.quantity_kg,
    so.agreed_price_inr_per_quintal,
    so.transaction_value_inr AS gross_revenue_inr,
    so.order_date,
    so.delivery_date,
    so.order_status,
    w.warehouse_id,
    w.warehouse_name,
    tr.route_id,
    tr.estimated_total_cost_inr AS transport_cost_inr,
    tr.distance_km,
    tr.vehicle_type,
    (so.transaction_value_inr - COALESCE(tr.estimated_total_cost_inr, 0)) AS estimated_net_revenue_inr,
    ROUND(
        CASE WHEN so.transaction_value_inr > 0
        THEN ((so.transaction_value_inr - COALESCE(tr.estimated_total_cost_inr, 0)) / so.transaction_value_inr) * 100
        ELSE NULL END, 2
    ) AS net_margin_pct
FROM sales_orders so
JOIN harvest_batches hb ON so.batch_id = hb.batch_id
JOIN crops c ON hb.crop_id = c.crop_id
JOIN buyers b ON so.buyer_id = b.buyer_id
LEFT JOIN inventory i ON hb.batch_id = i.batch_id
LEFT JOIN warehouses w ON i.warehouse_id = w.warehouse_id
LEFT JOIN transport_routes tr ON w.warehouse_id = tr.origin_warehouse_id AND b.buyer_id = tr.destination_buyer_id
WHERE so.order_status IN ('delivered', 'partial_delivered', 'in_transit', 'confirmed')
  AND tr.route_status = 'active';

COMMENT ON VIEW v_sales_with_transport_cost IS 'Sales orders with matched transport costs for net revenue analysis';

-- ============================================================
-- Additional indexes for analytical query performance
-- ============================================================

-- Composite index for batch spoilage queries
-- Note: Partial index with status check uses non-immutable CURRENT_DATE alternative
CREATE INDEX IF NOT EXISTS idx_harvest_batches_spoilage_check
ON harvest_batches(estimated_quality_window_end, status)
WHERE estimated_quality_window_end IS NOT NULL;

-- Composite index for inventory availability checks
CREATE INDEX IF NOT EXISTS idx_inventory_availability
ON inventory(warehouse_id, quantity_available_kg);

-- Composite index for recent market prices
CREATE INDEX IF NOT EXISTS idx_market_prices_recent_crop_market
ON market_prices(crop_id, market_name, observation_date DESC);

-- Composite index for FPO-level sales queries
CREATE INDEX IF NOT EXISTS idx_sales_orders_fpo_date
ON sales_orders(order_date DESC);

-- Partial index for active transport routes
CREATE INDEX IF NOT EXISTS idx_transport_routes_active_lookup
ON transport_routes(origin_warehouse_id, destination_buyer_id);

-- ============================================================
-- Materialized view for expensive aggregations (refresh on schedule)
-- ============================================================
CREATE MATERIALIZED VIEW mv_daily_crop_market_summary AS
SELECT
    mp.crop_id,
    c.crop_name,
    c.variety,
    mp.market_name,
    mp.district,
    mp.state,
    mp.observation_date,
    AVG(mp.modal_price_inr_per_quintal) AS avg_modal_price,
    MIN(mp.minimum_price_inr_per_quintal) AS min_price,
    MAX(mp.maximum_price_inr_per_quintal) AS max_price,
    COUNT(*) AS price_observations
FROM market_prices mp
JOIN crops c ON mp.crop_id = c.crop_id
WHERE mp.data_quality_flag IN ('verified', 'estimated')
GROUP BY
    mp.crop_id, c.crop_name, c.variety,
    mp.market_name, mp.district, mp.state, mp.observation_date;

CREATE UNIQUE INDEX idx_mv_daily_crop_market_summary_pk
ON mv_daily_crop_market_summary(crop_id, market_name, observation_date);

CREATE INDEX idx_mv_daily_crop_market_summary_date
ON mv_daily_crop_market_summary(observation_date DESC);

COMMENT ON MATERIALIZED VIEW mv_daily_crop_market_summary IS 'Daily aggregated market prices per crop per market. Refresh via REFRESH MATERIALIZED VIEW CONCURRENTLY.';

-- ============================================================
-- Function to refresh materialized views
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_analytical_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_crop_market_summary;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_analytical_views() IS 'Refreshes all analytical materialized views. Run daily via pg_cron or external scheduler.';