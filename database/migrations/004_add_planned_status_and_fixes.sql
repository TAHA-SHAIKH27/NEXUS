-- Migration 004: Add 'planned' status and fix constraints
-- Created: 2026-10-24
-- Description: Adds 'planned' status to harvest_batches for future harvests,
-- fixes inventory stock_status constraints, and adds missing indexes.

-- ============================================================
-- Add 'planned' status to harvest_batches
-- ============================================================
-- First drop the existing check constraint
ALTER TABLE harvest_batches DROP CONSTRAINT IF EXISTS chk_batch_status;

-- Add new constraint with 'planned' status
ALTER TABLE harvest_batches ADD CONSTRAINT chk_batch_status 
CHECK (status IN ('planned', 'harvested', 'stored', 'partial_sold', 'fully_sold', 'spoiled', 'discarded'));

COMMENT ON COLUMN harvest_batches.status IS 'Current lifecycle status: planned (future harvest), harvested, stored, partial_sold, fully_sold, spoiled, discarded';

-- ============================================================
-- Ensure inventory stock_status includes all needed values
-- ============================================================
ALTER TABLE inventory DROP CONSTRAINT IF EXISTS chk_stock_status;
ALTER TABLE inventory ADD CONSTRAINT chk_stock_status 
CHECK (stock_status IN ('available', 'reserved', 'in_transit', 'quality_hold', 'spoiled', 'disposed'));

COMMENT ON COLUMN inventory.stock_status IS 'Operational status of this stock lot';

-- ============================================================
-- Add index for planned batches
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_harvest_batches_planned 
ON harvest_batches(harvest_date) WHERE status = 'planned';

-- ============================================================
-- Add index for inventory with zero available quantity
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_inventory_zero_available 
ON inventory(batch_id) WHERE quantity_available_kg = 0;

-- ============================================================
-- Update schema version
-- ============================================================
INSERT INTO schema_version (migration_name, checksum) VALUES
('004_add_planned_status_and_fixes', 'sha256:placeholder');