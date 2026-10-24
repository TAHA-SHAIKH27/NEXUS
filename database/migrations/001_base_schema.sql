-- Migration 001: Base FPO Schema
-- Created: 2026-10-24
-- Description: Creates the 12 core FPO business tables with primary keys, foreign keys, and basic constraints.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Table 1: fpos - Farmer Producer Organizations
-- ============================================================
CREATE TABLE fpos (
    fpo_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fpo_code            VARCHAR(20) NOT NULL UNIQUE,
    fpo_name            VARCHAR(200) NOT NULL,
    district            VARCHAR(100) NOT NULL,
    state               VARCHAR(50) NOT NULL,
    latitude            NUMERIC(10, 7),
    longitude           NUMERIC(10, 7),
    registration_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    active_status       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fpos IS 'Farmer Producer Organizations - apex cooperative entities';
COMMENT ON COLUMN fpos.fpo_code IS 'Human-readable code like MAH-NAS-001';
COMMENT ON COLUMN fpos.latitude IS 'Decimal degrees, WGS84';
COMMENT ON COLUMN fpos.longitude IS 'Decimal degrees, WGS84';

-- ============================================================
-- Table 2: farmers - Registered farmers belonging to FPOs
-- ============================================================
CREATE TABLE farmers (
    farmer_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fpo_id              UUID NOT NULL REFERENCES fpos(fpo_id) ON DELETE RESTRICT,
    farmer_code         VARCHAR(30) NOT NULL UNIQUE,
    full_name           VARCHAR(200) NOT NULL,
    village             VARCHAR(150) NOT NULL,
    district            VARCHAR(100) NOT NULL,
    state               VARCHAR(50) NOT NULL,
    land_area_hectares  NUMERIC(10, 3) NOT NULL CHECK (land_area_hectares > 0),
    membership_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    active_status       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE farmers IS 'Individual farmers registered with an FPO';
COMMENT ON COLUMN farmers.farmer_code IS 'Human-readable code like FPO-001-FRM-0042';
COMMENT ON COLUMN farmers.land_area_hectares IS 'Total cultivable land owned/leased in hectares';

CREATE INDEX idx_farmers_fpo_id ON farmers(fpo_id);
CREATE INDEX idx_farmers_district_state ON farmers(district, state);
CREATE INDEX idx_farmers_active ON farmers(active_status) WHERE active_status = TRUE;

-- ============================================================
-- Table 3: farms - Agricultural land managed by farmers
-- ============================================================
CREATE TABLE farms (
    farm_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farmer_id           UUID NOT NULL REFERENCES farmers(farmer_id) ON DELETE RESTRICT,
    district            VARCHAR(100) NOT NULL,
    village             VARCHAR(150) NOT NULL,
    latitude            NUMERIC(10, 7),
    longitude           NUMERIC(10, 7),
    area_hectares       NUMERIC(10, 3) NOT NULL CHECK (area_hectares > 0),
    soil_type           VARCHAR(50),
    irrigation_type     VARCHAR(30),
    active_status       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE farms IS 'Individual farm plots managed by farmers';
COMMENT ON COLUMN farms.soil_type IS 'e.g., black cotton, red lateritic, alluvial, sandy loam';
COMMENT ON COLUMN farms.irrigation_type IS 'e.g., rainfed, drip, sprinkler, canal, borewell';

CREATE INDEX idx_farms_farmer_id ON farms(farmer_id);
CREATE INDEX idx_farms_district_village ON farms(district, village);
CREATE INDEX idx_farms_active ON farms(active_status) WHERE active_status = TRUE;

-- ============================================================
-- Table 4: crops - Crop master data with storage characteristics
-- ============================================================
CREATE TABLE crops (
    crop_id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_name                   VARCHAR(100) NOT NULL,
    variety                     VARCHAR(100),
    crop_category               VARCHAR(50) NOT NULL,
    typical_storage_days        INTEGER CHECK (typical_storage_days >= 0),
    storage_temperature_min     NUMERIC(5, 2),
    storage_temperature_max     NUMERIC(5, 2),
    measurement_unit            VARCHAR(20) NOT NULL DEFAULT 'kg',
    perishability_category      VARCHAR(30) NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_crop_name_variety UNIQUE (crop_name, variety)
);

COMMENT ON TABLE crops IS 'Crop master data with post-harvest storage characteristics';
COMMENT ON COLUMN crops.perishability_category IS 'e.g., highly_perishable, moderately_perishable, durable';
COMMENT ON COLUMN crops.typical_storage_days IS 'Typical shelf life under optimal conditions (days)';

CREATE INDEX idx_crops_category ON crops(crop_category);
CREATE INDEX idx_crops_perishability ON crops(perishability_category);

-- ============================================================
-- Table 5: harvest_batches - Individual harvest events
-- ============================================================
CREATE TABLE harvest_batches (
    batch_id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_code                  VARCHAR(50) NOT NULL UNIQUE,
    farm_id                     UUID NOT NULL REFERENCES farms(farm_id) ON DELETE RESTRICT,
    crop_id                     UUID NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT,
    harvest_date                DATE NOT NULL,
    harvested_quantity_kg       NUMERIC(14, 3) NOT NULL CHECK (harvested_quantity_kg > 0),
    initial_quality_grade       VARCHAR(20) NOT NULL,
    estimated_quality_window_end DATE,
    estimated_harvest_cost_inr  NUMERIC(14, 2) CHECK (estimated_harvest_cost_inr >= 0),
    status                      VARCHAR(30) NOT NULL DEFAULT 'harvested',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_quality_grade CHECK (initial_quality_grade IN ('A', 'B', 'C', 'premium', 'standard', 'substandard')),
    CONSTRAINT chk_batch_status CHECK (status IN ('harvested', 'stored', 'partial_sold', 'fully_sold', 'spoiled', 'discarded'))
);

COMMENT ON TABLE harvest_batches IS 'Individual harvest events from specific farms and crops';
COMMENT ON COLUMN harvest_batches.batch_code IS 'Human-readable code like HB-2026-000123';
COMMENT ON COLUMN harvest_batches.initial_quality_grade IS 'Grade at harvest: premium/A/B/C/standard/substandard';
COMMENT ON COLUMN harvest_batches.estimated_quality_window_end IS 'Estimated date by which quality degrades significantly';
COMMENT ON COLUMN harvest_batches.status IS 'Current lifecycle status of the batch';

CREATE INDEX idx_harvest_batches_farm_id ON harvest_batches(farm_id);
CREATE INDEX idx_harvest_batches_crop_id ON harvest_batches(crop_id);
CREATE INDEX idx_harvest_batches_harvest_date ON harvest_batches(harvest_date);
CREATE INDEX idx_harvest_batches_status ON harvest_batches(status);
CREATE INDEX idx_harvest_batches_quality_window ON harvest_batches(estimated_quality_window_end) WHERE estimated_quality_window_end IS NOT NULL;

-- ============================================================
-- Table 6: warehouses - Storage facilities
-- ============================================================
CREATE TABLE warehouses (
    warehouse_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fpo_id                  UUID NOT NULL REFERENCES fpos(fpo_id) ON DELETE RESTRICT,
    warehouse_name          VARCHAR(200) NOT NULL,
    district                VARCHAR(100) NOT NULL,
    state                   VARCHAR(50) NOT NULL,
    latitude                NUMERIC(10, 7),
    longitude               NUMERIC(10, 7),
    capacity_kg             NUMERIC(14, 3) NOT NULL CHECK (capacity_kg > 0),
    storage_type            VARCHAR(50) NOT NULL,
    temperature_controlled  BOOLEAN NOT NULL DEFAULT FALSE,
    active_status           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE warehouses IS 'Storage facilities owned/managed by FPOs';
COMMENT ON COLUMN warehouses.storage_type IS 'e.g., cold_storage, ambient_warehouse, ventilated_godown, silo';
COMMENT ON COLUMN warehouses.temperature_controlled IS 'Whether facility has active temperature control';

CREATE INDEX idx_warehouses_fpo_id ON warehouses(fpo_id);
CREATE INDEX idx_warehouses_district_state ON warehouses(district, state);
CREATE INDEX idx_warehouses_active ON warehouses(active_status) WHERE active_status = TRUE;
CREATE INDEX idx_warehouses_temp_controlled ON warehouses(temperature_controlled);

-- ============================================================
-- Table 7: inventory - Current stock positions
-- ============================================================
CREATE TABLE inventory (
    inventory_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id                UUID NOT NULL REFERENCES harvest_batches(batch_id) ON DELETE RESTRICT,
    warehouse_id            UUID NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    quantity_available_kg   NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (quantity_available_kg >= 0),
    quantity_reserved_kg    NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (quantity_reserved_kg >= 0),
    last_updated            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stock_status            VARCHAR(30) NOT NULL DEFAULT 'available',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_inventory_batch_warehouse UNIQUE (batch_id, warehouse_id),
    CONSTRAINT chk_reserved_not_exceed_available CHECK (quantity_reserved_kg <= quantity_available_kg),
    CONSTRAINT chk_stock_status CHECK (stock_status IN ('available', 'reserved', 'in_transit', 'quality_hold', 'spoiled'))
);

COMMENT ON TABLE inventory IS 'Current stock positions linking harvest batches to warehouses';
COMMENT ON COLUMN inventory.quantity_available_kg IS 'Physically present and available for sale (includes reserved)';
COMMENT ON COLUMN inventory.quantity_reserved_kg IS 'Portion committed to orders but not yet shipped';
COMMENT ON COLUMN inventory.stock_status IS 'Operational status of this stock lot';

CREATE INDEX idx_inventory_batch_id ON inventory(batch_id);
CREATE INDEX idx_inventory_warehouse_id ON inventory(warehouse_id);
CREATE INDEX idx_inventory_stock_status ON inventory(stock_status);
CREATE INDEX idx_inventory_available_qty ON inventory(quantity_available_kg) WHERE quantity_available_kg > 0;

-- ============================================================
-- Table 8: market_prices - Market price observations
-- ============================================================
CREATE TABLE market_prices (
    price_id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_id                     UUID NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT,
    market_name                 VARCHAR(200) NOT NULL,
    district                    VARCHAR(100) NOT NULL,
    state                       VARCHAR(50) NOT NULL,
    observation_date            DATE NOT NULL,
    minimum_price_inr_per_quintal NUMERIC(10, 2) NOT NULL CHECK (minimum_price_inr_per_quintal >= 0),
    modal_price_inr_per_quintal   NUMERIC(10, 2) NOT NULL CHECK (modal_price_inr_per_quintal >= 0),
    maximum_price_inr_per_quintal NUMERIC(10, 2) NOT NULL CHECK (maximum_price_inr_per_quintal >= 0),
    source_type                 VARCHAR(30) NOT NULL DEFAULT 'synthetic',
    data_quality_flag           VARCHAR(20) NOT NULL DEFAULT 'verified',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_price_order CHECK (
        minimum_price_inr_per_quintal <= modal_price_inr_per_quintal
        AND modal_price_inr_per_quintal <= maximum_price_inr_per_quintal
    ),
    CONSTRAINT chk_source_type CHECK (source_type IN ('synthetic', 'agmarknet', 'manual', 'api', 'survey')),
    CONSTRAINT chk_data_quality CHECK (data_quality_flag IN ('verified', 'estimated', 'stale', 'suspect'))
);

COMMENT ON TABLE market_prices IS 'Daily market price observations for crops at specific markets';
COMMENT ON COLUMN market_prices.source_type IS 'Provenance of price data: synthetic=generated, agmarknet=govt, manual=entered, api=feed, survey=field';
COMMENT ON COLUMN market_prices.data_quality_flag IS 'Quality assessment of the price observation';

CREATE INDEX idx_market_prices_crop_id ON market_prices(crop_id);
CREATE INDEX idx_market_prices_market_date ON market_prices(market_name, observation_date DESC);
CREATE INDEX idx_market_prices_crop_market_date ON market_prices(crop_id, market_name, observation_date DESC);
CREATE INDEX idx_market_prices_source ON market_prices(source_type);
CREATE INDEX idx_market_prices_observation_date ON market_prices(observation_date DESC);

-- ============================================================
-- Table 9: buyers - Wholesale buyers
-- ============================================================
CREATE TABLE buyers (
    buyer_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_code          VARCHAR(30) NOT NULL UNIQUE,
    buyer_name          VARCHAR(200) NOT NULL,
    buyer_type          VARCHAR(50) NOT NULL,
    market_name         VARCHAR(200),
    district            VARCHAR(100),
    state               VARCHAR(50),
    latitude            NUMERIC(10, 7),
    longitude           NUMERIC(10, 7),
    active_status       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_buyer_type CHECK (buyer_type IN ('wholesaler', 'processor', 'retailer', 'exporter', 'institutional', 'commission_agent'))
);

COMMENT ON TABLE buyers IS 'Wholesale buyers and market intermediaries';
COMMENT ON COLUMN buyers.buyer_type IS 'Category of buyer in the value chain';
COMMENT ON COLUMN buyers.buyer_code IS 'Human-readable code like BUY-MAH-NAS-001';

CREATE INDEX idx_buyers_market_name ON buyers(market_name);
CREATE INDEX idx_buyers_district_state ON buyers(district, state);
CREATE INDEX idx_buyers_active ON buyers(active_status) WHERE active_status = TRUE;
CREATE INDEX idx_buyers_type ON buyers(buyer_type);

-- ============================================================
-- Table 10: sales_orders - Sales transactions
-- ============================================================
CREATE TABLE sales_orders (
    order_id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_code                  VARCHAR(50) NOT NULL UNIQUE,
    batch_id                    UUID NOT NULL REFERENCES harvest_batches(batch_id) ON DELETE RESTRICT,
    buyer_id                    UUID NOT NULL REFERENCES buyers(buyer_id) ON DELETE RESTRICT,
    quantity_kg                 NUMERIC(14, 3) NOT NULL CHECK (quantity_kg > 0),
    agreed_price_inr_per_quintal NUMERIC(10, 2) NOT NULL CHECK (agreed_price_inr_per_quintal > 0),
    order_date                  DATE NOT NULL DEFAULT CURRENT_DATE,
    delivery_date               DATE,
    order_status                VARCHAR(30) NOT NULL DEFAULT 'pending',
    transaction_value_inr       NUMERIC(16, 2) GENERATED ALWAYS AS ((quantity_kg / 100.0) * agreed_price_inr_per_quintal) STORED,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_order_status CHECK (order_status IN ('pending', 'confirmed', 'in_transit', 'delivered', 'partial_delivered', 'cancelled', 'disputed')),
    CONSTRAINT chk_delivery_after_order CHECK (delivery_date IS NULL OR delivery_date >= order_date)
);

COMMENT ON TABLE sales_orders IS 'Sales transactions linking harvest batches to buyers';
COMMENT ON COLUMN sales_orders.order_code IS 'Human-readable code like SO-2026-000456';
COMMENT ON COLUMN sales_orders.transaction_value_inr IS 'Auto-calculated: (quantity_kg / 100) * agreed_price_inr_per_quintal';
COMMENT ON COLUMN sales_orders.agreed_price_inr_per_quintal IS 'Price per 100 kg (quintal) as agreed with buyer';

CREATE INDEX idx_sales_orders_batch_id ON sales_orders(batch_id);
CREATE INDEX idx_sales_orders_buyer_id ON sales_orders(buyer_id);
CREATE INDEX idx_sales_orders_order_date ON sales_orders(order_date DESC);
CREATE INDEX idx_sales_orders_status ON sales_orders(order_status);
CREATE INDEX idx_sales_orders_delivery_date ON sales_orders(delivery_date) WHERE delivery_date IS NOT NULL;

-- ============================================================
-- Table 11: transport_routes - Logistics options
-- ============================================================
CREATE TABLE transport_routes (
    route_id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    origin_warehouse_id         UUID NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    destination_buyer_id        UUID NOT NULL REFERENCES buyers(buyer_id) ON DELETE RESTRICT,
    distance_km                 NUMERIC(8, 2) NOT NULL CHECK (distance_km > 0),
    expected_transit_hours      NUMERIC(6, 2) CHECK (expected_transit_hours > 0),
    vehicle_type                VARCHAR(30) NOT NULL,
    capacity_kg                 NUMERIC(10, 3) NOT NULL CHECK (capacity_kg > 0),
    fixed_cost_inr              NUMERIC(12, 2) NOT NULL CHECK (fixed_cost_inr >= 0),
    variable_cost_inr_per_km    NUMERIC(8, 2) NOT NULL CHECK (variable_cost_inr_per_km >= 0),
    estimated_total_cost_inr    NUMERIC(12, 2) GENERATED ALWAYS AS (fixed_cost_inr + (distance_km * variable_cost_inr_per_km)) STORED,
    route_status                VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_route_origin_dest UNIQUE (origin_warehouse_id, destination_buyer_id),
    CONSTRAINT chk_vehicle_type CHECK (vehicle_type IN ('mini_truck_1t', 'truck_5t', 'truck_9t', 'truck_16t', 'container_20ft', 'container_40ft', 'refrigerated_5t', 'refrigerated_9t')),
    CONSTRAINT chk_route_status CHECK (route_status IN ('active', 'inactive', 'seasonal', 'under_maintenance'))
);

COMMENT ON TABLE transport_routes IS 'Logistics routes from warehouses to buyer locations';
COMMENT ON COLUMN transport_routes.vehicle_type IS 'Vehicle class affecting capacity and cost structure';
COMMENT ON COLUMN transport_routes.estimated_total_cost_inr IS 'Auto-calculated: fixed_cost + (distance_km * variable_cost_per_km)';

CREATE INDEX idx_transport_routes_origin ON transport_routes(origin_warehouse_id);
CREATE INDEX idx_transport_routes_destination ON transport_routes(destination_buyer_id);
CREATE INDEX idx_transport_routes_status ON transport_routes(route_status) WHERE route_status = 'active';

-- ============================================================
-- Table 12: storage_costs - Warehouse holding costs per crop
-- ============================================================
CREATE TABLE storage_costs (
    storage_cost_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id                UUID NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    crop_id                     UUID NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT,
    effective_from              DATE NOT NULL,
    effective_to                DATE,
    storage_cost_inr_per_kg_day NUMERIC(8, 4) NOT NULL CHECK (storage_cost_inr_per_kg_day >= 0),
    handling_cost_inr_per_kg    NUMERIC(8, 4) NOT NULL CHECK (handling_cost_inr_per_kg >= 0),
    refrigeration_cost_inr_per_kg_day NUMERIC(8, 4) CHECK (refrigeration_cost_inr_per_kg_day >= 0),
    cost_source                 VARCHAR(30) NOT NULL DEFAULT 'synthetic',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_storage_cost_warehouse_crop_date UNIQUE (warehouse_id, crop_id, effective_from),
    CONSTRAINT chk_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_cost_source CHECK (cost_source IN ('synthetic', 'actual', 'estimated', 'contract'))
);

COMMENT ON TABLE storage_costs IS 'Per-crop, per-warehouse daily storage and handling costs';
COMMENT ON COLUMN storage_costs.storage_cost_inr_per_kg_day IS 'Daily storage cost per kg (rent, utilities, insurance prorated)';
COMMENT ON COLUMN storage_costs.handling_cost_inr_per_kg IS 'One-time handling cost per kg (loading, unloading, sorting)';
COMMENT ON COLUMN storage_costs.refrigeration_cost_inr_per_kg_day IS 'Additional daily cost for temperature-controlled storage per kg';

CREATE INDEX idx_storage_costs_warehouse_id ON storage_costs(warehouse_id);
CREATE INDEX idx_storage_costs_crop_id ON storage_costs(crop_id);
CREATE INDEX idx_storage_costs_effective_dates ON storage_costs(effective_from, effective_to);

-- ============================================================
-- Audit trigger function for updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers to all tables
CREATE TRIGGER update_fpos_updated_at BEFORE UPDATE ON fpos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_farmers_updated_at BEFORE UPDATE ON farmers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_farms_updated_at BEFORE UPDATE ON farms FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_crops_updated_at BEFORE UPDATE ON crops FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_harvest_batches_updated_at BEFORE UPDATE ON harvest_batches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_warehouses_updated_at BEFORE UPDATE ON warehouses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_inventory_updated_at BEFORE UPDATE ON inventory FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_market_prices_updated_at BEFORE UPDATE ON market_prices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_buyers_updated_at BEFORE UPDATE ON buyers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sales_orders_updated_at BEFORE UPDATE ON sales_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_transport_routes_updated_at BEFORE UPDATE ON transport_routes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_storage_costs_updated_at BEFORE UPDATE ON storage_costs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();