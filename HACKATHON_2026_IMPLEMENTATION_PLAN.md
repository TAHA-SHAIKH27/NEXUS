# NEXUS — Hackathon 2026 Implementation Plan

- **Date/time (UTC):** 2026-10-24 08:30 UTC
- **Repository:** `C:\NEXUS-GitHub-Clean\project` — NEXUS (clean GitHub repo)
- **Git Branch:** `feature/fpo-data-platform`
- **Status:** **Phase 1 Complete (Zetaris Direct API). Phase 2 In Progress (Schema + Seed Data).**
- **Single plan file:** This is the only implementation-plan file for this work. Updated in place.

**Last updated:** 2026-10-24 ~08:30 UTC — Phase 1 complete, Phase 2 schema deployed, validation seed generated and verified.

---

## Phase 1 Summary: Zetaris Live API Integration ✅ COMPLETE

### Objective
Add a minimal, read-only Zetaris connector to NEXUS using direct REST API endpoints.

### Key Achievements
- **Authentication**: HTTP Basic Auth (login) → Bearer token (queries) on ports 8888/8889
- **Endpoints**: Direct API (not UI proxy): `GET /api/v1.0/internal/auth/legacy-login`, `POST /api/v1.0/query/sql/start`
- **Security**: SQL validation (SELECT/WITH only), row limits (max 100), query cleanup in `finally`, no credential leakage
- **Tests**: 68 unit tests + 73 regression tests passing
- **Live Verification**: NY_TAXI queries verified end-to-end

### Files Changed (Phase 1)
| File | Action |
|---|---|
| `backend/tools/zetaris.py` | Rewritten for direct API with HTTP Basic Auth |
| `test_zetaris.py` | Rewritten with 68 unit tests |
| `ZETARIS_INTEGRATION_PLAN.md` | Updated |

---

## Phase 2: FPO Database & Data Platform 🚧 IN PROGRESS

### Objective
Build a realistic FPO operational database with 500,000 synthetic records across 12 related tables, register it in Zetaris, and enable NEXUS-to-Zetaris-to-FPO query flow.

### 2.1 Database Schema (Migration 001) ✅ DEPLOYED
**12 Core Business Tables:**
| Table | Purpose | Key Fields |
|---|---|---|
| `fpos` | Farmer Producer Organizations | fpo_id, fpo_code, district, state, lat/lon |
| `farmers` | Registered farmers | farmer_id, fpo_id, farmer_code, land_area_hectares |
| `farms` | Farm plots | farm_id, farmer_id, area_hectares, soil_type, irrigation_type |
| `crops` | Crop master data | crop_id, crop_name, variety, storage_days, temp_range, perishability |
| `harvest_batches` | Individual harvests | batch_id, farm_id, crop_id, harvest_date, quantity, quality_window |
| `warehouses` | Storage facilities | warehouse_id, fpo_id, capacity_kg, storage_type, temp_controlled |
| `inventory` | Stock positions | inventory_id, batch_id, warehouse_id, available_kg, reserved_kg |
| `market_prices` | Price observations | price_id, crop_id, market, date, min/modal/max price, source_type |
| `buyers` | Wholesale buyers | buyer_id, buyer_type, market, lat/lon |
| `sales_orders` | Sales transactions | order_id, batch_id, buyer_id, quantity, price, status |
| `transport_routes` | Logistics | route_id, origin_wh, dest_buyer, distance, vehicle_type, cost |
| `storage_costs` | Holding costs | storage_cost_id, warehouse_id, crop_id, cost_per_kg_day |

**Constraints & Features:**
- UUID primary keys, FK constraints, CHECK constraints for data quality
- `updated_at` triggers on all tables
- Partial indexes for common query patterns
- Price ordering constraint: min ≤ modal ≤ max

### 2.2 Analytical Views (Migration 002) ✅ DEPLOYED
| View | Purpose |
|---|---|
| `v_batch_inventory_summary` | Aggregated inventory per batch with farm/FPO context |
| `v_warehouse_capacity_utilization` | Real-time warehouse utilization % |
| `v_crop_market_price_trends` | 90-day price trends with day-over-day change % |
| `v_batch_spoilage_risk` | Batches at risk with days until quality window end |
| `v_fpo_revenue_summary` | Aggregated sales revenue per FPO |
| `v_transport_cost_analysis` | Per-kg transport cost per route |
| `v_sales_with_transport_cost` | Sales orders with matched transport costs for net revenue |
| `v_active_demo_scenarios_with_entities` | Active demo scenarios with linked entities |

**Materialized View:** `mv_daily_crop_market_summary` — Daily aggregated prices (refresh via `refresh_analytical_views()`)

### 2.3 Demo Scenarios & Metadata (Migration 003) ✅ DEPLOYED
| Table | Purpose |
|---|---|
| `demo_scenarios` | 5 predefined scenarios (spoilage_risk, market_arbitrage, capacity_pressure, multi_buyer, hold_vs_sell) |
| `demo_scenario_entities` | Links scenarios to specific business entities |
| `data_generation_log` | Audit log of synthetic data generation runs |
| `schema_version` | Tracks applied migrations |

**5 Demo Scenarios:**
1. **SCN-A**: Tomato spoilage risk in Nashik cluster
2. **SCN-B**: Onion market arbitrage (local vs Mumbai)
3. **SCN-C**: Warehouse capacity pressure at Pune hub
4. **SCN-D**: Multi-buyer negotiation for grape export
5. **SCN-E**: Hold vs immediate sale for potato storage

### 2.4 Validation Seed Generation (Stage A) ✅ COMPLETE
**Records Generated:** ~1,800 across all tables
- fpos: 5, farmers: 100, farms: 150, crops: 20
- harvest_batches: 200, warehouses: 20, inventory: 189
- market_prices: 500, buyers: 100, sales_orders: 100
- transport_routes: 192, storage_costs: 151

**Validation Results:**
| Check | Status |
|---|---|
| Foreign key integrity | ✅ 0 broken across 14 FKs |
| Negative quantities | ✅ 0 violations |
| Reserved ≤ Available | ✅ 0 violations |
| Price ordering (min ≤ modal ≤ max) | ✅ 0 violations |
| Positive capacities/distances | ✅ 0 violations |
| Views return data | ✅ All 8 views populated |
| Materialized view refresh | ✅ 500 rows after refresh |
| Demo scenarios inserted | ✅ 5 scenarios |

---

## Phase 2 Remaining Work

### 2.5 Full Dataset Generation (Stage B: 50K → Stage C: 500K) 🔄 NEXT
**Target Allocation:**
| Table | Target Records |
|---|---:|
| fpos | 50 |
| farmers | 15,000 |
| farms | 20,000 |
| crops | 50 |
| harvest_batches | 75,000 |
| warehouses | 400 |
| inventory | 75,000 |
| market_prices | 180,000 |
| buyers | 2,000 |
| sales_orders | 80,000 |
| transport_routes | 40,000 |
| storage_costs | 12,500 |
| **TOTAL** | **500,000** |

**Requirements:**
- Deterministic generation with fixed seed (42)
- Batch inserts with `execute_batch` / `COPY`
- Resumable generation (idempotent via ON CONFLICT DO NOTHING)
- Scenario markers embedded in generated data
- NUMERIC/DECIMAL for all financial amounts

### 2.6 Read-Only Zetaris Role (`zetaris_ro`) ⏳ PENDING
```sql
CREATE ROLE zetaris_ro WITH LOGIN PASSWORD '<secure>';
GRANT CONNECT ON DATABASE nexus_fpo TO zetaris_ro;
GRANT USAGE ON SCHEMA public TO zetaris_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO zetaris_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO zetaris_ro;
-- Test: INSERT must fail
```

### 2.7 Zetaris ↔ PostgreSQL Connectivity ⏳ PENDING
**Docker Network Setup:**
- Both Zetaris and `nexus-fpo-db` on same user-defined network
- JDBC URL: `jdbc:postgresql://nexus-fpo-db:5432/nexus_fpo`
- Verify from inside Zetaris container: `psql -h nexus-fpo-db -U zetaris_ro -d nexus_fpo`

### 2.8 Zetaris Data Source Registration ⏳ PENDING
- Data source name: `NEXUS_FPO`
- Register via Zetaris UI or API
- Verify table discovery and query execution
- Confirm write denial at DB level

### 2.9 NEXUS Integration Tests ⏳ PENDING
Test queries through NEXUS Zetaris connector:
```sql
SELECT COUNT(*) FROM NEXUS_FPO.harvest_batches;
SELECT * FROM NEXUS_FPO.v_batch_spoilage_risk WHERE spoilage_risk_level = 'high_risk';
SELECT * FROM NEXUS_FPO.v_warehouse_capacity_utilization WHERE utilization_pct > 80;
```

---

## Security & Operational Safeguards

| Safeguard | Implementation |
|---|---|
| Synthetic data labeling | `source_type = 'synthetic'` on all generated records |
| No real PII | No Aadhaar, real phone numbers, or sensitive identities |
| Financial precision | `NUMERIC` types for all monetary values |
| Read-only enforcement | DB-level `zetaris_ro` role + NEXUS SQL validator |
| Network isolation | Private Docker network, no public PostgreSQL exposure |
| Credential management | Local env vars only, not in Git |
| Query limits | Row limit 100, 30s timeout |

---

## Test Results Summary

| Category | Phase 1 | Phase 2 (Seed) |
|---|---|---|
| Unit Tests | ✅ 68 passed | — |
| Regression Tests | ✅ 73 passed | — |
| FK Integrity | — | ✅ 0 broken (14 FKs) |
| Data Quality | — | ✅ 0 violations (11 checks) |
| View Functionality | — | ✅ All 8 views + 1 matview |
| Demo Scenarios | — | ✅ 5 inserted |

---

## Git Workflow

```bash
# Phase 2 branch
git checkout -b feature/fpo-data-platform

# Commit schema migrations
git add database/migrations/
git commit -m "feat(db): FPO schema migrations (001-003)

- 12 core tables with FKs, CHECK constraints, triggers
- 8 analytical views + 1 materialized view
- 5 demo scenarios + metadata tables
- Stage A seed generator with validation"

# Commit generators
git add database/generators/
git commit -m "feat(db): Stage A validation seed generator

- Generates ~1,800 records across 12 tables
- All FK integrity, data quality checks pass
- Deterministic seed 42"

# Push
git push origin feature/fpo-data-platform
```

---

## Next Milestones

| Milestone | Target | Blockers |
|---|---|---|
| Stage B: 50K records | Week 2 | Generator scaling |
| Stage C: 500K records | Week 3 | Performance tuning |
| `zetaris_ro` role | Week 2 | DB admin access |
| Docker network setup | Week 2 | Zetaris container access |
| Zetaris registration | Week 3 | Zetaris UI/API access |
| NEXUS E2E queries | Week 3 | Connector + registration |

---

## Known Issues / Limitations

1. **Inventory count slightly below target** — ON CONFLICT DO NOTHING skips duplicates on (batch_id, warehouse_id) unique constraint. Acceptable for seed.
2. **Materialized view requires manual refresh** — Automate via `pg_cron` or external scheduler.
3. **Demo scenario entities not yet linked** — Will be populated during full generation with specific batch/warehouse IDs.
4. **Zetaris registration untested** — Depends on Zetaris deployment capabilities; may require UI manual steps.
5. **Network connectivity** — Requires shared Docker network between Zetaris and FPO PostgreSQL.

---

## Reproduction Instructions

### Prerequisites
- Docker Desktop with 4 Zetaris containers + `nexus-fpo-db`
- Python 3.11+ with `psycopg2-binary`
- Git

### Setup
```bash
# Clone repo
git clone https://github.com/TAHA-SHAIKH27/NEXUS.git
cd NEXUS
git checkout feature/fpo-data-platform

# Start database (if not running)
docker start nexus-fpo-db

# Run seed generator
cd database/generators
python generate_seed.py

# Verify
docker exec nexus-fpo-db psql -U nexus_admin -d nexus_fpo -c "
SELECT table_name, COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
GROUP BY table_name ORDER BY table_name;"
```

---

## Final Deliverables Checklist

| Deliverable | Status |
|---|---|
| 12 table schema | ✅ Deployed |
| Migration scripts (001-003) | ✅ Committed |
| Seed generator | ✅ Working |
| 500K record generator | 🔄 Next |
| Data integrity tests | ✅ Passing |
| Read-only role (`zetaris_ro`) | ⏳ Pending |
| Docker network + Zetaris connectivity | ⏳ Pending |
| Zetaris data source registration | ⏳ Pending |
| NEXUS E2E query flow | ⏳ Pending |
| 5 demo scenarios embedded | 🔄 Next |
| Performance benchmarks | ⏳ Pending |
| Updated implementation plan | ✅ This file |
| Git commits + push | ✅ Phase 1, 🔄 Phase 2 |

---

**Next Action:** Build Stage B (50K records) generator with batch COPY optimization, then Stage C (500K). Then create `zetaris_ro` role and configure Docker networking.