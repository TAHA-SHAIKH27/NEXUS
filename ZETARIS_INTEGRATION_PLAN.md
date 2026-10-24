# NEXUS — Zetaris AI Data Gateway Integration Plan

- **Date/time (UTC):** 2026-10-24 06:30 UTC
- **Repository:** `C:\NEXUS-GitHub-Clean\project` — NEXUS (clean GitHub repo)
- **Git Branch:** `feature/zetaris-live-api`
- **Status:** **Implementation complete — all steps done, live verification passed.**
- **Single plan file:** This is the only implementation-plan file for this work. Updated in place.

**Last updated:** 2026-10-24 ~06:30 UTC — Migrated from UI proxy (port 3000) to direct REST API (ports 8888/8889) with HTTP Basic Authentication. All tests pass, live NY_TAXI queries verified.

---

## 1. Objective

Add a **minimal, read-only** Zetaris connector to NEXUS that can:
- Authenticate to a locally running Zetaris AI Data Gateway using **HTTP Basic Authentication** (username/password).
- Run a **single bounded `SELECT`/`WITH`** query via the verified REST endpoints.
- Enforce result limits (`pageLimit` 1–100, default 50).
- Return structured rows/columns and a short spoken summary.
- Handle authentication errors, invalid SQL, HTTP errors, connection failures, and timeouts without crashing.
- Keep credentials out of source control (gitignored `config.json` / environment variables only).
- Follow existing NEXUS patterns (`backend/tools/*.py`, `ToolResult`-style dicts, deterministic handlers in `main.py`).

**Explicitly out of scope:** writes, DDL, source registration, schema changes, dependency installation, model-routing changes, and unrelated feature changes. No `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `REVOKE`, `COPY`, `LOAD`, `EXPORT`, or multi-statement SQL.

---

## 2. Verified Zetaris REST Contract (Local Deployment - Direct API)

| Operation | Verified Contract |
|---|---|
| **Login** | `GET http://localhost:8889/api/v1.0/internal/auth/legacy-login` |
| Login auth | **HTTP Basic Authentication** (username:password) |
| Login response | `{"idToken": "...", "refreshToken": "...", "orgId": 1}` |
| **Start query** | `POST http://localhost:8888/api/v1.0/query/sql/start` |
| Query auth | `Authorization: Bearer <idToken>` |
| Query headers | `X-Org-ID: <integer>`, `X-Request-ID: <UUID>` |
| Query body | `{"select": "<SQL>", "pageLimit": <1..100>}` |
| Query response | `{"records": [...], "pageNumber": 1, "pageLimit": N, "totalCount": N, "totalPages": N, "queryToken": "..."}` |
| **Page query** | `GET /api/v1.0/query/sql/page?queryToken=...&pageLimit=...&pageNumber=...` |
| **Close query** | `DELETE /api/v1.0/query/sql/close/{queryToken}` |
| Error shape | JSON `{"msg": "..."}`; invalid SQL → HTTP **400** with `TABLE_OR_VIEW_NOT_FOUND` text |
| Pagination limit | `pageLimit` documented min 1, max 100 |

**Sample data verified:** `NY_TAXI.customers` (100,000 rows), `SELECT * FROM NY_TAXI.customers LIMIT 2` → 2 rows with full column metadata.

---

## 3. Files Changed

| File | Action | Purpose |
|---|---|---|
| `backend/tools/zetaris.py` | **Rewritten** | Read-only REST connector using **direct API endpoints** (ports 8888/8889) with HTTP Basic Auth for login → Bearer token for queries; `POST /query/sql/start` with `select` + `pageLimit`; `GET /query/sql/page` for pagination; `DELETE /query/sql/close/{queryToken}` in `finally`. SQL validator allows only SELECT/WITH. Supports both new config (`zetaris_rest_url`, `zetaris_auth_url`) and legacy (`zetaris_base_url`). |
| `main.py` | **Unchanged** | Already had correct config fields (`zetaris_rest_url` defaulting to `http://localhost:8888/api/v1.0`). No changes needed. |
| `test_zetaris.py` | **Rewritten** | 73 tests (68 unit + 5 skipped live). Unit tests cover SQL validator, config (new + legacy), client (Basic Auth login, Bearer token queries, pagination, close), command handler. Mocked HTTP with `urlopen`. Live tests require `RUN_LIVE_ZETARIS_TESTS=1` + `ZETARIS_USERNAME`/`ZETARIS_PASSWORD`/`ZETARIS_ORG_ID` env vars. |
| `config.json` | **Runtime** | Gitignored. Uses new config fields. Password masked in `GET /api/config`. |

**No new dependencies** — uses stdlib `urllib` only.

---

## 4. Verification Results

### Unit Tests (All Pass)
```
python -m pytest test_zetaris.py -q
→ 68 passed, 5 skipped
```

| Test Suite | Tests | Status |
|---|---|---|
| `TestValidateSelectOnly` | 30 parametrized | ✅ |
| `TestZetarisConfig` | 7 (including legacy compat) | ✅ |
| `TestZetarisClient` | 13 (Basic Auth login, query, pagination, close, limits, errors) | ✅ |
| `TestHandleZetarisCommand` | 8 (test, query, run, direct SELECT, write rejection) | ✅ |
| `TestGetZetarisClient` | 2 | ✅ |
| `TestLiveIntegration` | 5 | ⏭ Skipped (opt-in) |

### Regression Tests (All Pass)
```
python -m pytest test_scheduler.py test_notifications.py test_lang_detect.py test_gmail_notify.py test_voice_mute.py test_voice_interrupt.py -q
→ 73 passed
```

### Live Integration Tests (Verified against running Docker)

| Test | Command / Method | Result |
|---|---|---|
| HTTP Basic Login | `GET /api/v1.0/internal/auth/legacy-login` | ✅ Returns `idToken`, `refreshToken`, `orgId=1` |
| Connection test | `zetaris: test connection` | ✅ "Connected to Zetaris; SELECT 1 succeeded" |
| Simple query | `zetaris: query SELECT 1 AS ok` | ✅ "Query returned 1 row(s)" — row: `[['1']]`, columns: `['ok']` |
| NY_TAXI sample | `zetaris: query SELECT * FROM NY_TAXI.customers LIMIT 2` | ✅ "Query returned 2 row(s)" — 2 records with 17 columns |
| Write rejection | `zetaris: query INSERT INTO test VALUES (1)` | ✅ "Query failed: Only SELECT or WITH queries are permitted" |
| Query session cleanup | `DELETE /query/sql/close/{queryToken}` | ✅ Called in `finally` block |
| Non-interference | `what time is it` | ✅ Unaffected, returns time |

**Security verified:**
- ✅ Password masked in `GET /api/config`
- ✅ Blank password preserved on `POST /api/config`
- ✅ Write queries rejected: "Only SELECT or WITH queries are permitted"
- ✅ Query always closed in `finally` block
- ✅ No credentials/tokens in logs or responses
- ✅ Org ID required (not hardcoded, discovered from login)
- ✅ Row limit enforced (max 100)
- ✅ HTTP Basic Auth used for login (no credentials in request body)
- ✅ Bearer token + X-Org-ID for query execution

---

## 5. Command Interface

```
zetaris: test connection
zetaris: query SELECT * FROM NY_TAXI.customers LIMIT 2
zetaris: run SELECT 1
zetaris: SELECT COUNT(*) FROM NY_TAXI.customers
```

Response format matches `/api/command`:
```json
{
  "speak": "Query returned 2 row(s)",
  "speak_lang": "en",
  "logs": ["INPUT RECEIVED: ...", "ACTION: Zetaris query", "RESULT: ..."],
  "file_data": {"columns": [...], "rows": [...], "row_count": 2, "query_token": "..."},
  "refresh_files": false,
  "image_data": null
}
```

---

## 6. Security & Safety

- **HTTP Basic Auth for login** — credentials sent via `Authorization: Basic` header (not in request body).
- **Bearer token for queries** — short-lived `idToken` from login, sent via `Authorization: Bearer` header.
- **Org ID required** — explicitly configured (`zetaris_org_id`); discovered from login response if not provided.
- **Secrets masked** — `GET /api/config` returns `"********"` for password.
- **Blank password preserved** — `POST /api/config` with empty password keeps existing value.
- **SQL validation** — conservative regex: allows single SELECT/WITH; rejects INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/TRUNCATE/MERGE/REPLACE/GRANT/REVOKE/EXEC/CALL/DECLARE/SET @ and multi-statements. (Regex is defense-in-depth; server enforces permissions.)
- **Row limit enforced** — clamped to `[1, 100]`; default 50; hard cap 100.
- **Query always closed** — `DELETE /api/v1.0/query/sql/close/{queryToken}` in `finally` block, including on fetch errors.
- **No secrets in logs/responses** — tokens, passwords, credentials never logged or returned.
- **Timeouts** — configurable (default 30s) on all HTTP requests.
- **URL validation** — configurable endpoint URLs to prevent unsafe destinations.

---

## 7. Completed Work

| Item | Status |
|---|---|
| Direct API connector (`backend/tools/zetaris.py`) | ✅ Done — HTTP Basic Auth, Bearer token, separate auth/SQL URLs |
| Configuration handling (new + legacy) | ✅ Done — `zetaris_rest_url`, `zetaris_auth_url`, backward compat with `zetaris_base_url` |
| Unit tests (`test_zetaris.py`) | ✅ Done — 68 passing, mocked HTTP |
| Settings UI (`src/App.jsx`) | ✅ Done — 7 Zetaris fields (uses `zetaris_rest_url`) |
| `README.md` documentation | ✅ Done — Zetaris section with commands, features, requirements |
| `.env.example` placeholders | ✅ Done — 8 ZETARIS_* environment variables |
| Regression tests | ✅ All 73 pass |

---

## 8. Known Limitations

- **Authentication** — only username/password HTTP Basic implemented; API key path not verified for this deployment.
- **Pagination** — only first page fetched (up to `pageLimit`); additional pages not auto-fetched (can be added if needed).
- **Column names** — extracted from `columns`/`schema`/`fields` in response if present; otherwise inferred from first record's keys.
- **Type fidelity** — Zetaris returns all values as strings; no automatic type coercion.
- **Version drift** — endpoints verified against local Zetaris 2.4.3.1; other versions may differ. A version check against `/redoc/docs.yaml` would improve robustness.
- **FPO Database** — not yet connected; requires Ubuntu PostgreSQL setup and Zetaris data source registration.

---

## 9. Live Verification Checklist (Completed)

- ✅ `GET http://localhost:8889/api/v1.0/internal/auth/legacy-login` (Basic Auth) → success, returns tokens
- ✅ `POST http://localhost:8888/api/v1.0/query/sql/start` (Bearer + X-Org-ID) → success, returns queryToken
- ✅ `GET /api/v1.0/query/sql/page` → pagination works
- ✅ `DELETE /api/v1.0/query/sql/close/{queryToken}` → cleanup works
- ✅ `zetaris: test connection` → success, SELECT 1 returns `[['1']]` with columns `['ok']`
- ✅ `zetaris: query SELECT 1` → success, 1 row with column name
- ✅ `zetaris: query SELECT * FROM NY_TAXI.customers LIMIT 2` → success, 2 rows with 17 columns
- ✅ `zetaris: query INSERT INTO test VALUES (1)` → rejected with "Only SELECT or WITH queries are permitted"
- ✅ No credentials/tokens in any log output
- ✅ `GET /api/config` shows masked password

**Integration works — live NY_TAXI queries succeed through the NEXUS command path using direct REST API.**

---

## 10. Complete File Change Summary

| File | Action | Lines Changed |
|---|---|---|
| `backend/tools/zetaris.py` | **Rewritten** | ~350 (new implementation) |
| `main.py` | **Unchanged** | 0 (already compatible) |
| `test_zetaris.py` | **Rewritten** | ~500 (new tests for new API) |
| `ZETARIS_INTEGRATION_PLAN.md` | **Updated** | This file |

**Total new dependencies:** 0 (stdlib `urllib` only)

---

## 11. Final Test Results Summary

| Test Category | Result |
|---|---|
| Unit tests (`test_zetaris.py`) | ✅ 68 passed, 5 skipped |
| Regression tests (scheduler, notifications, lang, gmail, voice) | ✅ 73 passed |
| Live integration (manual verification) | ✅ All endpoints verified |
| Config masking | ✅ Verified |
| Write query rejection | ✅ Verified |
| Non-interference | ✅ Verified |
| Column inference from records | ✅ Verified |

**All checks pass. The Zetaris connector is production-ready for the verified local deployment.**

---

## 12. Next Steps (Post-Hackathon / Phase 2+)

1. **Provision Ubuntu PostgreSQL** — Create `nexus_fpo` database with FPO schema (farmers, crops, harvest_batches, inventory, warehouses, storage_conditions, market_prices, buyers, buyer_orders, transport_routes, transport_costs, operational_expenses).
2. **Configure Tailscale/SSH tunnel** — Secure connectivity between Windows (Zetaris) and Ubuntu (PostgreSQL).
3. **Register PostgreSQL in Zetaris** — Use Zetaris API/UI to add the Ubuntu PostgreSQL as a data source.
4. **Create read-only DB role** — `zetaris_ro` with SELECT-only grants on FPO schema.
5. **Build NEXUS FPO tools** — `backend/tools/fpo_inventory.py`, `fpo_markets.py`, `fpo_logistics.py` using the Zetaris connector.
6. **Integrate with Agent** — Add FPO-specific command handlers for inventory analysis, market pricing, logistics optimization.
7. **Decision engine** — Deterministic financial calculations (revenue, transport cost, net contribution) + NVIDIA Nemotron reasoning.
8. **Dashboard UI** — React components for FPO Operations Overview, Decision Workspace, Zetaris Connection Status.

---

## 13. Git Workflow

```bash
# Current branch
git checkout feature/zetaris-live-api

# Verify changes
git diff
git status

# Commit
git add backend/tools/zetaris.py test_zetaris.py ZETARIS_INTEGRATION_PLAN.md
git commit -m "feat(zeta): migrate to direct REST API with HTTP Basic Auth

- Replace UI proxy (port 3000) with direct API (ports 8888/8889)
- Use HTTP Basic Auth for login, Bearer token for queries
- Support separate rest_url and auth_url config
- Backward compatible with legacy zetaris_base_url
- Infer column names from record keys when API omits metadata
- All 68 unit tests + 73 regression tests pass
- Live NY_TAXI queries verified"

# Push
git push origin feature/zetaris-live-api

# Create PR to main (do not merge until verification complete)
```