"""NEXUS FPO Analytics - Zetaris-backed read-only agricultural intelligence.

Architecture (mandated):
    Frontend -> FastAPI -> ZetarisClient -> NEXUS_FPO datasource -> PostgreSQL

Rules honored by this module:
- Every query goes through the authorized Zetaris integration. There are NO
  direct database connections and NO credentials in source code (connection
  settings come from the gitignored config.json / environment).
- All SQL is backend-owned, allowlisted templates. User-controlled values are
  validated/escaped before interpolation. The Zetaris client additionally
  enforces SELECT-only statements and a row cap.
- Zetaris query session tokens are never returned to API callers.
- Every function returns a stable JSON schema: {"status": "success"|"error", ...}.
- The query engine behind Zetaris is Spark-family: use ANSI SQL only
  (no PostgreSQL ``::`` casts, no ``DISTINCT ON``).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

from backend.tools import zetaris as _zetaris

# ── Source & configuration ────────────────────────────────────────────────

SOURCE = "NEXUS_FPO"

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CONFIG_FILE = os.path.join(_PROJECT_ROOT, "config.json")


def _load_config() -> Dict[str, Any]:
    """Load Zetaris connection settings (mirrors main.py; no circular import)."""
    data: Dict[str, Any] = {}
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.setdefault("zetaris_rest_url", "http://localhost:8888/api/v1.0")
    data.setdefault("zetaris_auth_url", "http://localhost:8889")
    data.setdefault("zetaris_org_id", "")
    data.setdefault("zetaris_api_key", "")
    data.setdefault("zetaris_username", os.environ.get("ZETARIS_USERNAME", ""))
    data.setdefault("zetaris_password", os.environ.get("ZETARIS_PASSWORD", ""))
    data.setdefault("zetaris_default_limit", 100)
    data.setdefault("zetaris_max_limit", 100)
    data.setdefault("zetaris_timeout_seconds", 30)
    return data


class FpoQueryError(Exception):
    """Raised when a Zetaris-backed FPO query cannot be completed."""


# ── Client cache ───────────────────────────────────────────────────────────

_client_lock = threading.Lock()
_client: Optional[Any] = None
_client_fingerprint: Optional[str] = None

# Freshness / diagnostics state (process-local, never sensitive)
_state_lock = threading.Lock()
_last_success_at: Optional[float] = None
_last_query_count = 0
_last_error: Optional[str] = None


def _config_fingerprint(cfg: Dict[str, Any]) -> str:
    keys = (
        "zetaris_rest_url", "zetaris_auth_url", "zetaris_org_id",
        "zetaris_username", "zetaris_password",
    )
    return json.dumps({k: cfg.get(k, "") for k in keys}, sort_keys=True)


def _get_client():
    """Return a cached ZetarisClient, rebuilding when config changes."""
    global _client, _client_fingerprint
    cfg = _load_config()
    fp = _config_fingerprint(cfg)
    with _client_lock:
        if _client is None or fp != _client_fingerprint:
            client, err = _zetaris.get_zetaris_client(cfg)
            if err or client is None:
                # Do not echo credentials back - only the missing-key names.
                missing = [k for k in ("zetaris_username", "zetaris_password") if not cfg.get(k)]
                raise FpoQueryError(
                    "Zetaris is not configured"
                    + (f" (missing: {', '.join(missing)})" if missing else "")
                )
            _client = client
            _client_fingerprint = fp
        return _client


def _reset_client() -> None:
    global _client
    with _client_lock:
        _client = None


def _record_success() -> None:
    global _last_success_at, _last_query_count
    with _state_lock:
        _last_success_at = time.time()
        _last_query_count += 1


def _record_error(message: str) -> None:
    global _last_error
    with _state_lock:
        _last_error = message[:300]


def _rows_to_dicts(columns: List[str], rows: List[List[Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if len(columns) == len(row):
            out.append({c: v for c, v in zip(columns, row)})
        else:
            out.append({f"col_{i}": v for i, v in enumerate(row)})
    return out


def _execute(sql: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Run one allowlisted SELECT through Zetaris; returns list of row dicts."""
    client = _get_client()
    result = client.execute_query(sql, limit=limit)
    if result.status == "success":
        _record_success()
        data = result.data or {}
        return _rows_to_dicts(data.get("columns") or [], data.get("rows") or [])
    raise FpoQueryError(result.error or result.message or "Query failed")


def _query(sql: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Execute, retrying exactly once if the cached bearer token expired."""
    try:
        return _execute(sql, limit)
    except FpoQueryError as exc:
        text = str(exc)
        if "Authentication failed" in text or "HTTP 401" in text or "HTTP 403" in text:
            _reset_client()
            _record_error("auth retry: " + text)
            return _execute(sql, limit)
        _record_error(text)
        raise


def _query_parallel(specs: Dict[str, Any], max_workers: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """Run independent allowlisted queries concurrently.

    Each query opens its own Zetaris query session; the shared bearer token is
    reused. specs: {key: (sql, limit)} -> {key: rows}.
    """
    from concurrent.futures import ThreadPoolExecutor

    results: Dict[str, List[Dict[str, Any]]] = {}

    def _run(item):
        key, (sql, limit) = item
        return key, _query(sql, limit)

    workers = max(1, min(max_workers, len(specs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key, rows in pool.map(_run, specs.items()):
            results[key] = rows
    return results


# ── Parameter safety helpers ───────────────────────────────────────────────

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _uuid(value: str) -> str:
    v = str(value or "").strip().lower()
    if not _UUID_RE.match(v):
        raise FpoQueryError("Invalid identifier")
    return v


def _sstr(value: Optional[str], max_len: int = 200) -> str:
    """Safely escaped SQL string literal (single quotes doubled)."""
    v = str(value or "").strip()[:max_len]
    return "'" + v.replace("'", "''") + "'"


def _like_pattern(value: Optional[str], max_len: int = 120) -> str:
    """Quoted SQL LIKE pattern literal: '%term%' with wildcards/quotes stripped from the term."""
    v = str(value or "").strip()[:max_len]
    v = v.replace("'", "").replace("%", "").replace("_", " ").strip()
    return "'%" + v + "%'"


def _ci_like_any(columns: List[str], term: Optional[str]) -> str:
    """Case-insensitive multi-column search that works on this Zetaris build.

    IMPORTANT: ILIKE / LOWER() / UPPER() / RLIKE '(?i)' are silently broken on
    the current Zetaris federation (they match every row). Only exact-case
    LIKE filters correctly, so case-insensitivity is emulated by OR-ing LIKE
    patterns for the common casings of the escaped term.
    """
    v = str(term or "").strip()[:120]
    v = v.replace("'", "").replace("%", "").replace("_", " ").strip()
    if not v:
        return "1=1"
    variants = []
    for cand in (v, v.lower(), v.upper(), v.capitalize()):
        if cand and cand not in variants:
            variants.append(cand)
    pats = [f"'%{c}%'" for c in variants]
    per_col = [f"({col} LIKE {' OR '.join(pats)})" for col in columns]
    return "(" + " OR ".join(per_col) + ")"


def _int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _enum(value: Optional[str], allowed: List[str]) -> Optional[str]:
    v = str(value or "").strip().lower()
    return v if v in allowed else None


_INT_STR_RE = re.compile(r"^-?\d+$")


def _num(value: Any) -> Any:
    """Convert a Zetaris numeric (may arrive as str) to int/float, tolerantly."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    s = value.strip()
    if _INT_STR_RE.match(s):
        try:
            return int(s)
        except ValueError:
            return value
    try:
        return float(s)
    except (TypeError, ValueError):
        return value


def _clean_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize numerics that arrive as Spark decimal strings."""
    cleaned = []
    for r in rows:
        cleaned.append({k: _num(v) for k, v in r.items()})
    return cleaned


def _safe_error(exc: Exception) -> Dict[str, Any]:
    msg = str(exc) or "Unable to retrieve FPO data from Zetaris."
    return {
        "status": "error",
        "message": msg[:400],
        "source": SOURCE,
    }


# ── 1. Operations overview ──────────────────────────────────────────────────

def get_overview_stats(fpo_id: Optional[str] = None,
                       crop_name: Optional[str] = None) -> Dict[str, Any]:
    """Core FPO network KPIs, spoilage distribution, crops, warehouses, alerts."""
    try:
        crop_clause = ""
        if crop_name and crop_name != "All":
            crop_clause = f" AND c.crop_name = {_sstr(crop_name)}"

        fpo_clause_w = ""
        if fpo_id and fpo_id != "All":
            fpo_clause_w = f" AND v.fpo_id = '{_uuid(fpo_id)}'"

        specs = {
            "kpi_core": (f"""
                SELECT
                    (SELECT COUNT(*) FROM {SOURCE}.fpos) AS total_fpos,
                    (SELECT COUNT(*) FROM {SOURCE}.farmers) AS total_farmers,
                    (SELECT COUNT(*) FROM {SOURCE}.crops) AS total_crops,
                    (SELECT COUNT(*) FROM {SOURCE}.harvest_batches
                        WHERE status IN ('harvested','stored','partial_sold')) AS active_batches,
                    (SELECT COUNT(*) FROM {SOURCE}.harvest_batches
                        WHERE status = 'planned') AS planned_batches,
                    (SELECT COALESCE(SUM(harvested_quantity_kg), 0)
                        FROM {SOURCE}.harvest_batches
                        WHERE status = 'planned') AS planned_harvest_kg,
                    (SELECT COALESCE(SUM(quantity_available_kg), 0)
                        FROM {SOURCE}.inventory) AS physical_stock_kg,
                    (SELECT COALESCE(SUM(quantity_reserved_kg), 0)
                        FROM {SOURCE}.inventory) AS reserved_stock_kg
            """, 1),
            "kpi_warehouse": (f"""
                SELECT ROUND(AVG(v.utilization_pct), 1) AS avg_warehouse_utilization_pct,
                       COUNT(*) AS total_warehouses,
                       SUM(CASE WHEN v.utilization_pct >= 80 THEN 1 ELSE 0 END) AS warehouses_near_capacity,
                       COALESCE(SUM(v.remaining_capacity_kg), 0) AS available_capacity_kg
                FROM {SOURCE}.v_warehouse_capacity_utilization v
                WHERE 1=1{fpo_clause_w}
            """, 1),
            "kpi_revenue": (f"""
                SELECT COALESCE(SUM(total_revenue_inr), 0) AS recorded_revenue_inr
                FROM {SOURCE}.v_fpo_revenue_summary
            """, 1),
            "spoilage": (f"""
                SELECT spoilage_risk_level, COUNT(*) AS batch_count,
                       COALESCE(SUM(net_available_kg), 0) AS total_kg
                FROM {SOURCE}.v_batch_spoilage_risk
                GROUP BY spoilage_risk_level
            """, 8),
            "top_crops": (f"""
                SELECT c.crop_name, c.perishability_category,
                       COALESCE(SUM(i.quantity_available_kg), 0) AS available_kg,
                       COUNT(DISTINCT hb.batch_id) AS batch_count
                FROM {SOURCE}.inventory i
                JOIN {SOURCE}.harvest_batches hb ON i.batch_id = hb.batch_id
                JOIN {SOURCE}.crops c ON hb.crop_id = c.crop_id
                WHERE 1=1{crop_clause}
                GROUP BY c.crop_name, c.perishability_category
                ORDER BY available_kg DESC
                LIMIT 8
            """, 8),
            "warehouse_summary": (f"""
                SELECT storage_type, COUNT(*) AS total_warehouses,
                       ROUND(AVG(utilization_pct), 1) AS avg_utilization_pct,
                       COALESCE(SUM(capacity_kg), 0) AS total_capacity_kg,
                       COALESCE(SUM(current_stock_kg), 0) AS total_stock_kg
                FROM {SOURCE}.v_warehouse_capacity_utilization
                WHERE 1=1{fpo_clause_w}
                GROUP BY storage_type
                ORDER BY total_capacity_kg DESC
            """, 8),
            "market_snapshot": ("""
                SELECT crop_name, market_name, district, state, observation_date,
                       modal_price_inr_per_quintal, price_change_pct, source_type
                FROM (
                    SELECT crop_name, market_name, district, state, observation_date,
                           modal_price_inr_per_quintal, price_change_pct, source_type,
                           ROW_NUMBER() OVER (PARTITION BY crop_name
                                              ORDER BY observation_date DESC) AS rn
                    FROM %s.v_crop_market_price_trends
                ) t
                WHERE rn = 1
                ORDER BY crop_name
                LIMIT 12
            """ % SOURCE, 12),
            "urgent_alerts": (f"""
                SELECT batch_code, crop_name, variety, net_available_kg,
                       days_until_quality_window_end, spoilage_risk_level, farm_district
                FROM {SOURCE}.v_batch_spoilage_risk
                WHERE spoilage_risk_level IN ('critical_today', 'high_risk')
                ORDER BY days_until_quality_window_end ASC
                LIMIT 6
            """, 6),
        }

        res = _query_parallel(specs, max_workers=5)

        overview: Dict[str, Any] = {}
        overview.update((res.get("kpi_core") or [{}])[0])
        overview.update((res.get("kpi_warehouse") or [{}])[0])
        overview.update((res.get("kpi_revenue") or [{}])[0])
        overview = _clean_rows([overview])[0]

        high_risk = sum(int(r.get("batch_count") or 0)
                        for r in res.get("spoilage", [])
                        if r.get("spoilage_risk_level") in ("critical_today", "high_risk", "expired"))
        overview["high_risk_batches"] = high_risk

        return {
            "status": "success",
            "source": SOURCE,
            "overview": overview,
            "spoilage": _clean_rows(res.get("spoilage", [])),
            "top_crops": _clean_rows(res.get("top_crops", [])),
            "warehouse_summary": _clean_rows(res.get("warehouse_summary", [])),
            "market_snapshot": _clean_rows(res.get("market_snapshot", [])),
            "urgent_alerts": _clean_rows(res.get("urgent_alerts", [])),
        }
    except FpoQueryError as exc:
        return _safe_error(exc)
    except Exception as exc:  # defensive: never leak traces to API callers
        _record_error(str(exc))
        return _safe_error(exc)


# ── 2. Inventory intelligence ──────────────────────────────────────────────

_RISK_ORDER_SQL = (
    "CASE spoilage_risk_level "
    "WHEN 'critical_today' THEN 1 WHEN 'high_risk' THEN 2 "
    "WHEN 'medium_risk' THEN 3 WHEN 'low_risk' THEN 4 ELSE 5 END"
)


def _inventory_where(crop_name: Optional[str], district: Optional[str],
                     risk_level: Optional[str], search: Optional[str]) -> str:
    conditions: List[str] = ["1=1"]
    if crop_name and crop_name != "All":
        conditions.append(f"crop_name = {_sstr(crop_name)}")
    if district and district != "All":
        conditions.append(f"farm_district = {_sstr(district)}")
    if risk_level and risk_level != "All":
        conditions.append(f"spoilage_risk_level = {_sstr(risk_level)}")
    if search:
        conditions.append(_ci_like_any(["batch_code", "crop_name", "variety"], search))
    return " AND ".join(conditions)


def get_inventory_batches(page: int = 1, page_size: int = 25,
                         crop_name: Optional[str] = None,
                         district: Optional[str] = None,
                         risk_level: Optional[str] = None,
                         search: Optional[str] = None) -> Dict[str, Any]:
    """Server-side paginated current-stock batch list."""
    try:
        page = _int(page, 1, 1, 10000)
        page_size = _int(page_size, 25, 5, 100)
        offset = (page - 1) * page_size
        where = _inventory_where(crop_name, district, risk_level, search)

        res = _query_parallel({
            "count": (f"""
                SELECT COUNT(*) AS total
                FROM {SOURCE}.v_batch_spoilage_risk
                WHERE {where}
            """, 1),
            "batches": (f"""
                SELECT batch_id, batch_code, crop_name, variety, perishability_category,
                       harvest_date, initial_quality_grade, estimated_quality_window_end,
                       days_until_quality_window_end, spoilage_risk_level, batch_status,
                       harvested_quantity_kg, total_available_kg, total_reserved_kg,
                       net_available_kg, warehouse_count, farm_district, farm_state
                FROM {SOURCE}.v_batch_spoilage_risk
                WHERE {where}
                ORDER BY {_RISK_ORDER_SQL}, days_until_quality_window_end ASC
                LIMIT {page_size} OFFSET {offset}
            """, page_size),
        }, max_workers=2)

        count_rows = res.get("count", [])
        total = int((count_rows[0] or {}).get("total", 0)) if count_rows else 0
        batches = res.get("batches", [])

        return {
            "status": "success",
            "source": SOURCE,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size else 1,
            "batches": _clean_rows(batches),
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


def get_batch_detail(batch_id: str) -> Dict[str, Any]:
    """Full batch profile: identity, stock, warehouse split, sales history."""
    try:
        bid = _uuid(batch_id)
        res = _query_parallel({
            "detail": (f"""
                SELECT bis.batch_id, bis.batch_code, bis.harvest_date, bis.crop_name,
                       bis.variety, bis.perishability_category, bis.typical_storage_days,
                       bis.harvested_quantity_kg, bis.initial_quality_grade,
                       bis.estimated_quality_window_end, bis.batch_status,
                       bis.farm_district, bis.farm_state, bis.fpo_id,
                       fpo.fpo_name, fpo.fpo_code,
                       fr.full_name AS farmer_name, fr.farmer_code,
                       bis.total_available_kg, bis.total_reserved_kg,
                       bis.net_available_kg, bis.warehouse_count,
                       bis.last_inventory_update
                FROM {SOURCE}.v_batch_inventory_summary bis
                JOIN {SOURCE}.fpos fpo ON bis.fpo_id = fpo.fpo_id
                JOIN {SOURCE}.farmers fr ON bis.farmer_id = fr.farmer_id
                WHERE bis.batch_id = '{bid}'
            """, 1),
            "risk": (f"""
                SELECT spoilage_risk_level, days_until_quality_window_end
                FROM {SOURCE}.v_batch_spoilage_risk
                WHERE batch_id = '{bid}'
            """, 1),
            "warehouses": (f"""
                SELECT w.warehouse_name, w.district AS warehouse_district, w.storage_type,
                       w.temperature_controlled, i.quantity_available_kg,
                       i.quantity_reserved_kg, i.stock_status, i.last_updated
                FROM {SOURCE}.inventory i
                JOIN {SOURCE}.warehouses w ON i.warehouse_id = w.warehouse_id
                WHERE i.batch_id = '{bid}'
                ORDER BY i.quantity_available_kg DESC
            """, 20),
            "orders": (f"""
                SELECT so.order_code, b.buyer_name, b.buyer_type, b.market_name,
                       so.quantity_kg, so.agreed_price_inr_per_quintal,
                       so.transaction_value_inr, so.order_date, so.delivery_date,
                       so.order_status
                FROM {SOURCE}.sales_orders so
                JOIN {SOURCE}.buyers b ON so.buyer_id = b.buyer_id
                WHERE so.batch_id = '{bid}'
                ORDER BY so.order_date DESC
            """, 20),
        }, max_workers=4)

        detail_rows = res.get("detail", [])
        if not detail_rows:
            return {"status": "error", "message": "Batch not found"}
        detail = _clean_rows(detail_rows)[0]

        risk_rows = res.get("risk", [])
        if risk_rows:
            detail["spoilage_risk_level"] = risk_rows[0].get("spoilage_risk_level")
            detail["days_until_quality_window_end"] = risk_rows[0].get("days_until_quality_window_end")

        return {
            "status": "success",
            "source": SOURCE,
            "batch": detail,
            "warehouses": _clean_rows(res.get("warehouses", [])),
            "sales_orders": _clean_rows(res.get("orders", [])),
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


# ── 3. Market intelligence ─────────────────────────────────────────────────

_KNOWN_CROPS_TTL = 600.0
_known_crops_cache: List[str] = []
_known_crops_at = 0.0
_crop_cache_lock = threading.Lock()


def _known_crops() -> List[str]:
    global _known_crops_cache, _known_crops_at
    with _crop_cache_lock:
        now = time.time()
        if _known_crops_cache and now - _known_crops_at < _KNOWN_CROPS_TTL:
            return _known_crops_cache
    rows = _query(f"SELECT DISTINCT crop_name FROM {SOURCE}.crops ORDER BY crop_name", limit=60)
    names = [str(r.get("crop_name")) for r in rows if r.get("crop_name")]
    with _crop_cache_lock:
        if names:
            _known_crops_cache = names
            _known_crops_at = now
    return _known_crops_cache


def get_market_intelligence(crop_name: Optional[str] = None,
                            market_name: Optional[str] = None,
                            days: int = 30) -> Dict[str, Any]:
    """Price trends, market comparison and buyer intel for one crop."""
    try:
        crops = _known_crops()
        target_crop = None
        if crop_name and crop_name != "All":
            target_crop = crop_name if crop_name in crops else crop_name
        if not target_crop:
            target_crop = "Tomato" if "Tomato" in crops else (crops[0] if crops else "Tomato")
        days = _int(days, 30, 7, 90)
        market_clause = ""
        if market_name and market_name != "All":
            market_clause = f" AND market_name = {_sstr(market_name)}"

        res = _query_parallel({
            "trends": (f"""
                SELECT observation_date, market_name, district, state,
                       ROUND(AVG(modal_price_inr_per_quintal), 2) AS avg_modal_price,
                       ROUND(MIN(minimum_price_inr_per_quintal), 2) AS min_price,
                       ROUND(MAX(maximum_price_inr_per_quintal), 2) AS max_price,
                       source_type
                FROM {SOURCE}.v_crop_market_price_trends
                WHERE crop_name = {_sstr(target_crop)}{market_clause}
                GROUP BY observation_date, market_name, district, state, source_type
                ORDER BY observation_date DESC
                LIMIT 60
            """, 60),
            "market_comparison": (f"""
                SELECT market_name, district, state,
                       ROUND(AVG(modal_price_inr_per_quintal), 2) AS avg_price,
                       ROUND(MIN(minimum_price_inr_per_quintal), 2) AS min_price,
                       ROUND(MAX(maximum_price_inr_per_quintal), 2) AS max_price,
                       COUNT(*) AS observations_count,
                       MAX(observation_date) AS latest_observation,
                       source_type
                FROM {SOURCE}.v_crop_market_price_trends
                WHERE crop_name = {_sstr(target_crop)}{market_clause}
                GROUP BY market_name, district, state, source_type
                ORDER BY avg_price DESC
                LIMIT 15
            """, 15),
            "top_buyers": (f"""
                SELECT b.buyer_name, b.buyer_type, b.market_name, b.district, b.state,
                       COUNT(so.order_id) AS total_orders,
                       ROUND(SUM(so.transaction_value_inr), 2) AS total_purchase_inr,
                       ROUND(AVG(so.agreed_price_inr_per_quintal), 2) AS avg_price_per_quintal
                FROM {SOURCE}.buyers b
                JOIN {SOURCE}.sales_orders so ON b.buyer_id = so.buyer_id
                JOIN {SOURCE}.harvest_batches hb ON so.batch_id = hb.batch_id
                JOIN {SOURCE}.crops c ON hb.crop_id = c.crop_id
                WHERE c.crop_name = {_sstr(target_crop)}
                GROUP BY b.buyer_name, b.buyer_type, b.market_name, b.district, b.state
                ORDER BY total_purchase_inr DESC
                LIMIT 10
            """, 10),
        }, max_workers=3)

        trends = res.get("trends", [])

        return {
            "status": "success",
            "source": SOURCE,
            "crop": target_crop,
            "available_crops": crops,
            "period_days": days,
            "data_provenance": "synthetic" if all(
                (r.get("source_type") or "synthetic") == "synthetic" for r in trends
            ) else "mixed",
            "trends": _clean_rows(trends),
            "market_comparison": _clean_rows(res.get("market_comparison", [])),
            "top_buyers": _clean_rows(res.get("top_buyers", [])),
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


# ── 4. Logistics intelligence ───────────────────────────────────────────────

def get_logistics_intelligence(limit: int = 25) -> Dict[str, Any]:
    """Warehouses (with coordinates) and active transport routes."""
    try:
        limit = _int(limit, 25, 5, 100)

        res = _query_parallel({
            "warehouses": (f"""
                SELECT v.warehouse_id, v.warehouse_name, v.district, v.state,
                       v.capacity_kg, v.current_stock_kg, v.remaining_capacity_kg,
                       v.utilization_pct, v.storage_type, v.temperature_controlled,
                       v.distinct_batches, v.distinct_crops,
                       w.latitude, w.longitude
                FROM {SOURCE}.v_warehouse_capacity_utilization v
                JOIN {SOURCE}.warehouses w ON v.warehouse_id = w.warehouse_id
                ORDER BY v.utilization_pct DESC
                LIMIT {limit}
            """, limit),
            "routes": (f"""
                SELECT tr.route_id, w.warehouse_name AS origin_warehouse,
                       w.district AS origin_district, w.state AS origin_state,
                       w.latitude AS origin_latitude, w.longitude AS origin_longitude,
                       b.buyer_name, b.buyer_type, b.market_name AS destination_market,
                       b.district AS destination_district, b.state AS destination_state,
                       b.latitude AS destination_latitude, b.longitude AS destination_longitude,
                       tr.distance_km, tr.expected_transit_hours, tr.vehicle_type,
                       tr.capacity_kg, tr.fixed_cost_inr, tr.variable_cost_inr_per_km,
                       tr.estimated_total_cost_inr, tr.route_status
                FROM {SOURCE}.transport_routes tr
                JOIN {SOURCE}.warehouses w ON tr.origin_warehouse_id = w.warehouse_id
                JOIN {SOURCE}.buyers b ON tr.destination_buyer_id = b.buyer_id
                WHERE tr.route_status = 'active'
                ORDER BY tr.estimated_total_cost_inr ASC
                LIMIT {limit}
            """, limit),
        }, max_workers=2)

        return {
            "status": "success",
            "source": SOURCE,
            "warehouses": _clean_rows(res.get("warehouses", [])),
            "routes": _clean_rows(res.get("routes", [])),
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


# ── 5. Risk centre ──────────────────────────────────────────────────────────

_RISK_LEVELS = ["critical_today", "high_risk", "medium_risk", "low_risk", "expired"]


def get_risk_centre(risk_level: Optional[str] = None) -> Dict[str, Any]:
    """Spoilage risk board, capacity pressure, crop exposure and data staleness."""
    try:
        level = _enum(risk_level, _RISK_LEVELS)
        level_clause = ""
        if level:
            level_clause = f" AND spoilage_risk_level = {_sstr(level)}"

        res = _query_parallel({
            "critical_batches": (f"""
                SELECT batch_id, batch_code, crop_name, variety, perishability_category,
                       harvest_date, estimated_quality_window_end,
                       days_until_quality_window_end, spoilage_risk_level,
                       net_available_kg, farm_district, farm_state
                FROM {SOURCE}.v_batch_spoilage_risk
                WHERE spoilage_risk_level IN ('critical_today', 'high_risk'){level_clause}
                ORDER BY days_until_quality_window_end ASC
                LIMIT 30
            """, 30),
            "congested_warehouses": (f"""
                SELECT warehouse_id, warehouse_name, district, state, capacity_kg,
                       current_stock_kg, remaining_capacity_kg, utilization_pct,
                       storage_type, temperature_controlled
                FROM {SOURCE}.v_warehouse_capacity_utilization
                WHERE utilization_pct >= 90
                ORDER BY utilization_pct DESC
                LIMIT 20
            """, 20),
            "crop_risk_summary": (f"""
                SELECT crop_name,
                       COUNT(*) AS total_batches,
                       SUM(CASE WHEN spoilage_risk_level = 'critical_today' THEN 1 ELSE 0 END) AS critical_count,
                       SUM(CASE WHEN spoilage_risk_level = 'high_risk' THEN 1 ELSE 0 END) AS high_risk_count,
                       ROUND(SUM(net_available_kg), 0) AS at_risk_quantity_kg
                FROM {SOURCE}.v_batch_spoilage_risk
                WHERE spoilage_risk_level IN ('critical_today', 'high_risk')
                GROUP BY crop_name
                ORDER BY at_risk_quantity_kg DESC
            """, 15),
            "staleness": (f"""
                SELECT MAX(observation_date) AS latest_price_date,
                       COUNT(*) AS observations_last_90_days
                FROM {SOURCE}.v_crop_market_price_trends
            """, 1),
            "distribution": (f"""
                SELECT spoilage_risk_level, COUNT(*) AS batch_count,
                       COALESCE(SUM(net_available_kg), 0) AS total_kg
                FROM {SOURCE}.v_batch_spoilage_risk
                GROUP BY spoilage_risk_level
            """, 8),
        }, max_workers=5)

        staleness = res.get("staleness", [])

        return {
            "status": "success",
            "source": SOURCE,
            "critical_batches": _clean_rows(res.get("critical_batches", [])),
            "congested_warehouses": _clean_rows(res.get("congested_warehouses", [])),
            "crop_risk_summary": _clean_rows(res.get("crop_risk_summary", [])),
            "market_data_staleness": _clean_rows(staleness)[0] if staleness else {},
            "risk_distribution": _clean_rows(res.get("distribution", [])),
            "note": "Risk levels are estimates from estimated quality windows, not confirmed losses.",
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


# ── 6. Decisions & reports ─────────────────────────────────────────────────

def get_decisions_scenarios() -> Dict[str, Any]:
    """Demo scenarios + deterministic sales/net-revenue analysis.

    The Phase 3 decision engine (LLM-assisted recommendations) is NOT yet
    implemented; ``decision_engine`` reports that honestly so the frontend can
    label the workspace accordingly instead of fabricating recommendations.
    """
    try:
        res = _query_parallel({
            "scenarios": (f"""
                SELECT scenario_id, scenario_code, scenario_name, description,
                       scenario_type, is_active
                FROM {SOURCE}.demo_scenarios
                ORDER BY scenario_code
            """, 10),
            "linked_entities": (f"""
                SELECT scenario_code, entity_type, entity_id_ref, role_in_scenario, notes
                FROM {SOURCE}.v_active_demo_scenarios_with_entities
                ORDER BY scenario_code
            """, 40),
            "sales_analysis": (f"""
                SELECT order_code, crop_name, buyer_name, quantity_kg,
                       gross_revenue_inr, transport_cost_inr,
                       estimated_net_revenue_inr, net_margin_pct,
                       order_status, order_date
                FROM {SOURCE}.v_sales_with_transport_cost
                ORDER BY estimated_net_revenue_inr DESC
                LIMIT 15
            """, 15),
        }, max_workers=3)

        return {
            "status": "success",
            "source": SOURCE,
            "decision_engine": {
                "available": False,
                "message": ("Phase 3 decision engine is not yet implemented. "
                            "Deterministic financial figures below come from validated "
                            "database views (v_sales_with_transport_cost)."),
            },
            "scenarios": _clean_rows(res.get("scenarios", [])),
            "linked_entities": _clean_rows(res.get("linked_entities", [])),
            "sales_analysis": _clean_rows(res.get("sales_analysis", [])),
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


# ── 7. Data sources status ─────────────────────────────────────────────────

def get_datasources_status() -> Dict[str, Any]:
    """Safe connectivity/health snapshot. No credentials, tokens or headers."""
    zetaris_status: Dict[str, Any] = {"connected": False, "message": "Not checked"}
    try:
        client = _get_client()
        res = client.test_connection()
        zetaris_status = {
            "connected": res.status == "success",
            "message": res.message or "Connected",
        }
    except Exception as exc:
        zetaris_status = {"connected": False, "message": str(exc)[:200]}

    source_status: Dict[str, Any] = {"registered": False, "message": "Not checked"}
    table_counts: Dict[str, Any] = {}
    view_counts: Dict[str, Any] = {}
    if zetaris_status.get("connected"):
        try:
            rows = _query(f"SELECT COUNT(*) AS n FROM {SOURCE}.fpos", limit=1)
            source_status = {
                "registered": True,
                "message": f"{SOURCE} datasource reachable ({rows[0].get('n')} FPOs)" if rows else "reachable",
            }
        except Exception as exc:
            source_status = {"registered": False, "message": str(exc)[:200]}

        if source_status.get("registered"):
            count_union = " UNION ALL ".join([
                f"SELECT 'fpos' AS t, COUNT(*) AS n FROM {SOURCE}.fpos",
                f"SELECT 'farmers', COUNT(*) FROM {SOURCE}.farmers",
                f"SELECT 'farms', COUNT(*) FROM {SOURCE}.farms",
                f"SELECT 'crops', COUNT(*) FROM {SOURCE}.crops",
                f"SELECT 'harvest_batches', COUNT(*) FROM {SOURCE}.harvest_batches",
                f"SELECT 'warehouses', COUNT(*) FROM {SOURCE}.warehouses",
                f"SELECT 'inventory', COUNT(*) FROM {SOURCE}.inventory",
                f"SELECT 'market_prices', COUNT(*) FROM {SOURCE}.market_prices",
                f"SELECT 'buyers', COUNT(*) FROM {SOURCE}.buyers",
                f"SELECT 'sales_orders', COUNT(*) FROM {SOURCE}.sales_orders",
                f"SELECT 'transport_routes', COUNT(*) FROM {SOURCE}.transport_routes",
                f"SELECT 'storage_costs', COUNT(*) FROM {SOURCE}.storage_costs",
                f"SELECT 'demo_scenarios', COUNT(*) FROM {SOURCE}.demo_scenarios",
            ])
            try:
                for r in _query(count_union, limit=20):
                    table_counts[str(r.get("t"))] = r.get("n")
            except Exception as exc:
                table_counts["error"] = str(exc)[:200]

            view_union = " UNION ALL ".join([
                f"SELECT 'v_batch_inventory_summary' AS v, COUNT(*) AS n FROM {SOURCE}.v_batch_inventory_summary",
                f"SELECT 'v_warehouse_capacity_utilization', COUNT(*) FROM {SOURCE}.v_warehouse_capacity_utilization",
                f"SELECT 'v_batch_spoilage_risk', COUNT(*) FROM {SOURCE}.v_batch_spoilage_risk",
                f"SELECT 'v_crop_market_price_trends', COUNT(*) FROM {SOURCE}.v_crop_market_price_trends",
                f"SELECT 'v_fpo_revenue_summary', COUNT(*) FROM {SOURCE}.v_fpo_revenue_summary",
                f"SELECT 'v_transport_cost_analysis', COUNT(*) FROM {SOURCE}.v_transport_cost_analysis",
                f"SELECT 'v_sales_with_transport_cost', COUNT(*) FROM {SOURCE}.v_sales_with_transport_cost",
            ])
            try:
                for r in _query(view_union, limit=10):
                    view_counts[str(r.get("v"))] = r.get("n")
            except Exception as exc:
                view_counts["error"] = str(exc)[:200]

    with _state_lock:
        last_success = _last_success_at
        query_count = _last_query_count
        last_error = _last_error

    return {
        "status": "success",
        "zetaris": zetaris_status,
        "datasource": {
            "name": SOURCE,
            **source_status,
        },
        "postgresql": {
            # Proven transitively: Zetaris reaches PostgreSQL when the
            # NEXUS_FPO source query succeeds.
            "reachable": bool(source_status.get("registered")),
            "database": "nexus_fpo",
            "container": "nexus-fpo-db",
        },
        "table_counts": table_counts,
        "view_counts": view_counts,
        "diagnostics": {
            "last_successful_query_at": last_success,
            "successful_queries_this_process": query_count,
            "last_error": last_error,
        },
    }


# ── 8. Filter options ──────────────────────────────────────────────────────

def get_filter_options() -> Dict[str, Any]:
    """Dropdown metadata for filters. Cached cheaply by the frontend."""
    try:
        crops = _known_crops()
        res = _query_parallel({
            "districts": (f"SELECT DISTINCT district FROM {SOURCE}.fpos ORDER BY district", 100),
            "fpos": (f"""
                SELECT fpo_id, fpo_code, fpo_name, district, state
                FROM {SOURCE}.fpos
                ORDER BY fpo_name
                LIMIT 60
            """, 60),
            "markets": (f"""
                SELECT DISTINCT market_name FROM {SOURCE}.market_prices ORDER BY market_name
            """, 200),
            "warehouses": (f"""
                SELECT warehouse_name, district, state FROM {SOURCE}.warehouses
                ORDER BY warehouse_name LIMIT 100
            """, 100),
        }, max_workers=4)
        return {
            "status": "success",
            "crops": crops,
            "districts": [r.get("district") for r in res.get("districts", [])],
            "fpos": _clean_rows(res.get("fpos", [])),
            "markets": [r.get("market_name") for r in res.get("markets", [])],
            "warehouses": _clean_rows(res.get("warehouses", [])),
            "risk_levels": _RISK_LEVELS,
        }
    except Exception as exc:
        _record_error(str(exc))
        return _safe_error(exc)


# ── 9. Agent (natural language) command bridge ─────────────────────────────

def _agent_response(speak: str, prompt: str, logs: List[str],
                    file_data: Optional[Dict[str, Any]],
                    narration_steps: List[str]) -> Dict[str, Any]:
    """Response dict matching the /api/command contract exactly."""
    return {
        "speak": speak,
        "speak_lang": "en",
        "logs": [f'INPUT RECEIVED: "{prompt}"'] + logs,
        "file_data": file_data,
        "refresh_files": False,
        "image_data": None,
        "timer_data": None,
        "clarification_needed": None,
        "narration_steps": narration_steps,
    }


def _match_crop(prompt_lower: str) -> Optional[str]:
    """Match a crop by whole word (so 'prices' never matches 'Rice')."""
    try:
        for crop in _known_crops():
            if re.search(r"\b" + re.escape(crop.lower()) + r"\b", prompt_lower):
                return crop
    except Exception:
        pass
    return None


def _fmt_int(value: Any) -> str:
    """Human-friendly integer formatting for spoken replies."""
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_inr(value: Any) -> str:
    try:
        return f"Rs {float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def handle_fpo_agent_command(prompt: str) -> Optional[Dict[str, Any]]:
    """Natural-language agricultural questions answered with real FPO data.

    Returns None when the prompt is not an FPO question (falling through to
    the normal NEXUS agent). Only data-backed intents are handled; every
    number spoken comes from a Zetaris query executed for this command.
    """
    p = (prompt or "").lower().strip()
    if not p:
        return None

    # Spoilage / risk board
    if any(k in p for k in ("spoilage", "risk", "urgent attention", "shelf life",
                            "batches at risk", "quality window")):
        res = get_risk_centre()
        if res.get("status") == "success":
            batches = res.get("critical_batches", [])[:5]
            speak = (f"Found {len(res.get('critical_batches', []))} batches with active "
                     f"spoilage risk. {len(batches)} need priority dispatch.")
            lines = [f"• {b['batch_code']} ({b['crop_name']}): {b['net_available_kg']} kg, "
                     f"{b['days_until_quality_window_end']} days left ({b['spoilage_risk_level']})"
                     for b in batches]
            return _agent_response(
                speak + (" " + " ".join(lines[:2]) if lines else ""),
                prompt,
                [f"QUERY: {SOURCE}.v_batch_spoilage_risk",
                 f"RESULT: {len(res.get('critical_batches', []))} at-risk batches"],
                {"type": "risk_report", "source": SOURCE, "batches": batches,
                 "crops": res.get("crop_risk_summary", [])[:4]},
                ["Analyzing crop perishability", "Checking quality windows",
                 "Ranking dispatch priority"],
            )

    # Warehouse capacity
    if any(k in p for k in ("warehouse", "capacity", "godown", "storage utilization",
                            "almost full", "storage facility")):
        res = get_logistics_intelligence(limit=6)
        if res.get("status") == "success":
            whs = res.get("warehouses", [])[:5]
            speak = (f"The most utilized warehouse is {whs[0]['warehouse_name']} at "
                     f"{whs[0]['utilization_pct']}% capacity.") if whs else "No warehouses returned."
            return _agent_response(
                speak, prompt,
                [f"QUERY: {SOURCE}.v_warehouse_capacity_utilization",
                 f"RESULT: {len(whs)} warehouses checked"],
                {"type": "warehouse_report", "source": SOURCE, "warehouses": whs},
                ["Scanning storage network", "Aggregating utilization metrics"],
            )

    # Market prices (needs a crop mention or defaults)
    if any(k in p for k in ("market", "price", "mandi", "rate", "bhav", "compare")):
        crop = _match_crop(p)
        if crop:
            res = get_market_intelligence(crop_name=crop)
            if res.get("status") == "success":
                comps = res.get("market_comparison", [])[:4]
                speak = (f"{crop} averages up to {_fmt_inr(comps[0]['avg_price'])} per quintal at "
                         f"{comps[0]['market_name']}.") if comps else f"No recent {crop} prices."
                return _agent_response(
                    speak, prompt,
                    [f"QUERY: {SOURCE}.v_crop_market_price_trends (crop: {crop})",
                     f"RESULT: {len(comps)} markets compared"],
                    {"type": "market_report", "source": SOURCE, "crop": crop,
                     "markets": comps, "provenance": res.get("data_provenance")},
                    ["Querying price observations", "Comparing regional markets"],
                )

    # Registered farmers / FPO network size
    if any(k in p for k in ("how many farmers", "registered farmers", "farmer count",
                            "how many fpos", "fpo count", "network summary")):
        res = get_overview_stats()
        if res.get("status") == "success":
            ov = res.get("overview", {})
            speak = (f"NEXUS tracks {_fmt_int(ov.get('total_fpos', 0))} FPOs with "
                     f"{_fmt_int(ov.get('total_farmers', 0))} registered farmers and "
                     f"{_fmt_int(ov.get('physical_stock_kg', 0))} kg of physical inventory.")
            return _agent_response(
                speak, prompt,
                [f"QUERY: {SOURCE} network KPIs",
                 f"RESULT: {ov.get('total_fpos', 0)} FPOs, {ov.get('total_farmers', 0)} farmers"],
                {"type": "overview_report", "source": SOURCE, "stats": ov},
                ["Aggregating FPO network metrics", "Verifying live data freshness"],
            )

    # Crop inventory
    crop = _match_crop(p)
    if crop and any(k in p for k in ("inventory", "stock", "available", "how much", "show")):
        res = get_inventory_batches(page=1, page_size=5, crop_name=crop)
        if res.get("status") == "success":
            total = res.get("total", 0)
            speak = f"{crop} has {total} batch(es) with current physical stock."
            return _agent_response(
                speak, prompt,
                [f"QUERY: {SOURCE}.v_batch_spoilage_risk (crop: {crop})",
                 f"RESULT: {total} batches"],
                {"type": "inventory_report", "source": SOURCE, "crop": crop,
                 "batches": res.get("batches", [])[:5]},
                ["Filtering inventory by crop", "Summarizing available stock"],
            )

    return None
