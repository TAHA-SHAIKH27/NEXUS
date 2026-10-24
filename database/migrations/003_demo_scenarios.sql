-- Migration 003: Demo Scenario Markers and Metadata
-- Created: 2026-10-24
-- Description: Creates tables to track demo scenarios and their associated entities for reproducible demonstrations.

-- ============================================================
-- Table: demo_scenarios - Predefined demonstration scenarios
-- ============================================================
CREATE TABLE demo_scenarios (
    scenario_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_code         VARCHAR(30) NOT NULL UNIQUE,
    scenario_name         VARCHAR(200) NOT NULL,
    description           TEXT NOT NULL,
    scenario_type         VARCHAR(50) NOT NULL,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_scenario_type CHECK (scenario_type IN (
        'spoilage_risk', 'market_arbitrage', 'capacity_pressure',
        'multi_buyer_negotiation', 'hold_vs_sell', 'custom'
    ))
);

COMMENT ON TABLE demo_scenarios IS 'Predefined demonstration scenarios for NEXUS presentations';

-- ============================================================
-- Table: demo_scenario_entities - Links scenarios to business entities
-- ============================================================
CREATE TABLE demo_scenario_entities (
    entity_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id           UUID NOT NULL REFERENCES demo_scenarios(scenario_id) ON DELETE CASCADE,
    entity_type           VARCHAR(30) NOT NULL,
    entity_id_ref         UUID NOT NULL,
    role_in_scenario      VARCHAR(100),
    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_entity_type CHECK (entity_type IN (
        'harvest_batch', 'warehouse', 'market_price', 'buyer',
        'sales_order', 'transport_route', 'fpo', 'crop'
    ))
);

COMMENT ON TABLE demo_scenario_entities IS 'Maps demo scenarios to specific business entities (batches, warehouses, etc.)';

CREATE INDEX idx_demo_entities_scenario ON demo_scenario_entities(scenario_id);
CREATE INDEX idx_demo_entities_type_ref ON demo_scenario_entities(entity_type, entity_id_ref);

-- ============================================================
-- Insert predefined demo scenarios
-- ============================================================
INSERT INTO demo_scenarios (scenario_code, scenario_name, description, scenario_type) VALUES
(
    'SCN-A-TOMATO-SPOILAGE',
    'Tomato Spoilage Risk - Nashik Cluster',
    'A large tomato harvest (Batch HB-2026-TOM-NAS-0042) from Nashik is approaching its quality window end while local modal prices have declined 15% over the past week. The batch has 12,500 kg available across two warehouses. Decision: sell immediately at declining local price, transport to distant market with higher price but transport cost, or process into paste.',
    'spoilage_risk'
),
(
    'SCN-B-MARKET-ARBITRAGE',
    'Better Distant Market - Onion Arbitrage',
    'Onion batch HB-2026-ONI-NAN-0017 from Nandurbar has 8,200 kg in storage. Local Lasalgaon market offers ₹1,850/quintal. Mumbai wholesale market offers ₹2,450/quintal but transport cost is ₹320/quintal. Decision: evaluate net revenue after transport (₹2,130 vs ₹1,850 = ₹280/quintal advantage = ₹22,960 total) vs. risk of price change during 6-hour transit.',
    'market_arbitrage'
),
(
    'SCN-C-CAPACITY-PRESSURE',
    'Warehouse Capacity Pressure - Pune Hub',
    'Pune FPO cold storage (WH-PUN-001, capacity 500,000 kg) currently holds 412,000 kg (82% utilized). Upcoming harvest forecast: 180,000 kg of grapes and 95,000 kg of pomegranates over next 14 days. Total projected: 687,000 kg (137% of capacity). Decision: prioritize high-value crops, redirect to satellite warehouses, or negotiate emergency cold storage rental.',
    'capacity_pressure'
),
(
    'SCN-D-MULTI-BUYER',
    'Multiple Buyers - Grape Export Negotiation',
    'Grape batch HB-2026-GRP-SAN-0089 (15,000 kg, premium grade) has two buyers: Buyer A (exporter) offers ₹4,200/quintal for full 15,000 kg with 3-day delivery; Buyer B (domestic processor) offers ₹3,950/quintal for 8,000 kg with immediate pickup. Transport to Buyer A: ₹180/quintal. Transport to Buyer B: ₹45/quintal. Decision: evaluate net revenue - Buyer A: (4200-180)*150 = ₹603,000 vs Buyer B: (3950-45)*80 = ₹312,400 + remaining 7,000 kg at risk.',
    'multi_buyer_negotiation'
),
(
    'SCN-E-HOLD-VS-SELL',
    'Hold vs Immediate Sale - Potato Storage Decision',
    'Potato batch HB-2026-POT-AGR-0023 (25,000 kg, standard grade) harvested 30 days ago. Current local modal price: ₹1,250/quintal. Storage cost: ₹0.08/kg/day. Historical data shows 60% probability of price rising to ₹1,550/quintal in 30 days, 30% probability of staying flat, 10% probability of dropping to ₹1,100. Expected value of holding 30 days: 0.6*(1550-1250-24)*250 + 0.3*(1250-1250-24)*250 + 0.1*(1100-1250-24)*250 = ₹42,150 vs immediate sale profit baseline. Decision requires risk tolerance assessment.',
    'hold_vs_sell'
);

-- ============================================================
-- Table: data_generation_log - Tracks data generation runs
-- ============================================================
CREATE TABLE data_generation_log (
    log_id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    generation_run_id     UUID NOT NULL,
    stage                 VARCHAR(20) NOT NULL,
    table_name            VARCHAR(50) NOT NULL,
    records_target        INTEGER NOT NULL,
    records_generated     INTEGER NOT NULL,
    duration_seconds      NUMERIC(8, 2),
    status                VARCHAR(20) NOT NULL,
    error_message         TEXT,
    seed_used             BIGINT,
    started_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at          TIMESTAMPTZ,
    CONSTRAINT chk_generation_stage CHECK (stage IN ('seed', 'integration', 'full', 'reseed')),
    CONSTRAINT chk_generation_status CHECK (status IN ('started', 'completed', 'failed', 'partial'))
);

COMMENT ON TABLE data_generation_log IS 'Audit log of synthetic data generation runs';

CREATE INDEX idx_gen_log_run ON data_generation_log(generation_run_id);
CREATE INDEX idx_gen_log_table ON data_generation_log(table_name);

-- ============================================================
-- Table: schema_version - Tracks applied migrations
-- ============================================================
CREATE TABLE schema_version (
    version_id            SERIAL PRIMARY KEY,
    migration_name        VARCHAR(100) NOT NULL UNIQUE,
    applied_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum              VARCHAR(64),
    applied_by            VARCHAR(100) DEFAULT CURRENT_USER,
    execution_time_ms     INTEGER
);

COMMENT ON TABLE schema_version IS 'Tracks which migrations have been applied';

-- ============================================================
-- Insert initial schema version records
-- ============================================================
INSERT INTO schema_version (migration_name, checksum) VALUES
('001_base_schema', 'sha256:placeholder'),
('002_analytical_views', 'sha256:placeholder'),
('003_demo_scenarios', 'sha256:placeholder');

-- ============================================================
-- Create function to get current schema version
-- ============================================================
CREATE OR REPLACE FUNCTION get_current_schema_version()
RETURNS TABLE (
    version_id INT,
    migration_name VARCHAR(100),
    applied_at TIMESTAMPTZ
) AS $$
    SELECT sv.version_id, sv.migration_name, sv.applied_at
    FROM schema_version sv
    ORDER BY sv.version_id DESC
    LIMIT 1;
$$ LANGUAGE sql;

-- ============================================================
-- Trigger for demo_scenarios updated_at
-- ============================================================
CREATE TRIGGER update_demo_scenarios_updated_at
BEFORE UPDATE ON demo_scenarios
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- View: v_active_demo_scenarios_with_entities
-- Active scenarios with their linked entities for easy retrieval
-- ============================================================
CREATE VIEW v_active_demo_scenarios_with_entities AS
SELECT
    ds.scenario_id,
    ds.scenario_code,
    ds.scenario_name,
    ds.description,
    ds.scenario_type,
    de.entity_type,
    de.entity_id_ref,
    de.role_in_scenario,
    de.notes
FROM demo_scenarios ds
LEFT JOIN demo_scenario_entities de ON ds.scenario_id = de.scenario_id
WHERE ds.is_active = TRUE
ORDER BY ds.scenario_code, de.entity_type;

COMMENT ON VIEW v_active_demo_scenarios_with_entities IS 'Active demo scenarios with linked entities for deterministic retrieval';