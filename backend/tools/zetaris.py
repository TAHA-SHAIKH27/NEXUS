"""
Zetaris AI Data Gateway connector — read-only SQL query execution.

Uses the verified Zetaris UI Proxy REST API (gateway for the internal API):
- POST /api/auth/login (username/password JSON -> returns idToken, refreshToken, orgId)
- POST /api/proxy/query/sql/start (execute query with select, pageLimit)
- GET /api/proxy/query/sql/page (fetch result pages)
- DELETE /api/proxy/query/sql/close/{queryToken} (close query)

Authentication: HTTP Basic for login, then Bearer token + X-Org-ID + X-Request-ID headers.
All queries are SELECT-only with enforced row limits (max 100).
Base URL is the UI origin (default: http://localhost:3000).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.tools.result_schema import ToolResult


# --- SQL Validation ---

# Conservative SELECT-only validator. Rejects any statement containing
# write/DDL keywords. Not a full parser — defense in depth only.
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|MERGE|REPLACE|"
    r"GRANT|REVOKE|COMMIT|ROLLBACK|BEGIN\s+TRANSACTION|"
    r"EXEC|EXECUTE|CALL|DECLARE|SET\s+@)\b",
    re.IGNORECASE,
)

# Allow only a single SELECT/WITH statement
_ALLOWED_START = re.compile(
    r"^\s*(WITH|SELECT)\b",
    re.IGNORECASE,
)


def validate_select_only(sql: str) -> tuple[bool, str]:
    """Validate that SQL is a single read-only SELECT/WITH statement.

    Returns (is_valid, error_message).
    Note: Regex validation has limitations - it cannot catch all SQL injection
    vectors or complex multi-statement obfuscation. The server enforces the
    actual permissions. This is a client-side guard only.
    """
    sql = sql.strip()
    if not sql:
        return False, "Empty query"

    # Must start with allowed keyword (SELECT or WITH)
    if not _ALLOWED_START.match(sql):
        return False, "Only SELECT or WITH queries are permitted"

    # Reject write/DDL keywords anywhere
    if _WRITE_KEYWORDS.search(sql):
        return False, "Write/DDL operations are not permitted"

    # Reject multiple statements (semicolon not at end)
    # Allow trailing semicolon
    trimmed = sql.rstrip().rstrip(";")
    if ";" in trimmed:
        return False, "Multiple statements are not permitted"

    return True, ""


# --- Configuration ---

@dataclass
class ZetarisConfig:
    """Zetaris connection configuration."""
    base_url: str = "http://localhost:3000"  # UI origin, not the internal API port
    org_id: str = ""  # Will be discovered from login response
    username: str = ""
    password: str = ""
    default_limit: int = 50
    max_limit: int = 100
    timeout_seconds: int = 30

    @classmethod
    def from_config_dict(cls, config: Dict[str, Any]) -> "ZetarisConfig":
        return cls(
            base_url=config.get("zetaris_base_url", "http://localhost:3000"),
            org_id=config.get("zetaris_org_id", ""),
            username=config.get("zetaris_username", ""),
            password=config.get("zetaris_password", ""),
            default_limit=int(config.get("zetaris_default_limit", 50)),
            max_limit=int(config.get("zetaris_max_limit", 100)),
            timeout_seconds=int(config.get("zetaris_timeout_seconds", 30)),
        )

    def is_configured(self) -> tuple[bool, str]:
        """Check if minimal configuration is present."""
        if not (self.username and self.password):
            return False, "Both zetaris_username and zetaris_password are required for login"
        if not self.base_url:
            return False, "ZETARIS_BASE_URL (zetaris_base_url) is required (UI origin, e.g. http://localhost:3000)"
        return True, ""


# --- Exceptions ---

class ZetarisError(Exception):
    """Base exception for Zetaris connector errors."""
    pass


class ZetarisAuthError(ZetarisError):
    """Authentication/authorization error."""
    pass


class ZetarisTimeoutError(ZetarisError):
    """Request timeout error."""
    pass


# --- Client ---

class ZetarisClient:
    """Read-only Zetaris UI Proxy REST API client."""

    LOGIN_PATH = "/api/auth/login"
    START_QUERY_PATH = "/api/proxy/query/sql/start"
    PAGE_QUERY_PATH = "/api/proxy/query/sql/page"
    CLOSE_QUERY_PATH = "/api/proxy/query/sql/close/"

    def __init__(self, config: ZetarisConfig):
        self.config = config
        self._token: Optional[str] = None
        self._org_id: Optional[str] = config.org_id or None
        self._base = config.base_url.rstrip("/")

    # --- Internal HTTP ---

    def _request(
        self,
        path: str,
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_login_auth: bool = False,
    ) -> Any:
        """Make an HTTP request with timeout and error handling."""
        url = f"{self._base}{path}"
        req_headers = {
            "Accept": "application/json",
            "X-Request-ID": str(uuid.uuid4()),
        }
        if headers:
            req_headers.update(headers)

        if use_login_auth:
            # Login uses JSON body with username/password, no auth header
            req_headers["Content-Type"] = "application/json"
        elif self._token:
            req_headers["Authorization"] = f"Bearer {self._token}"
            req_headers["Content-Type"] = "application/json"
            if self._org_id:
                req_headers["X-Org-ID"] = self._org_id

        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = Request(url, data=data, headers=req_headers, method=method)

        try:
            with urlopen(req, timeout=self.config.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as e:
            detail = e.read(500).decode("utf-8", errors="replace")
            if e.code == 401:
                raise ZetarisAuthError(f"Authentication failed: {detail}") from e
            if e.code == 403:
                raise ZetarisAuthError(f"Forbidden (check X-Org-ID): {detail}") from e
            raise ZetarisError(f"HTTP {e.code}: {detail}") from e
        except (URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", str(e))
            raise ZetarisTimeoutError(f"Cannot reach {self._base}: {reason}") from e

    # --- Authentication ---

    def ensure_authenticated(self) -> None:
        """Ensure we have a valid Bearer token (login if needed)."""
        if self._token and self._org_id:
            return
        if not (self.config.username and self.config.password):
            raise ZetarisAuthError("No username/password configured for login")

        body = {"username": self.config.username, "password": self.config.password}
        try:
            resp = self._request(self.LOGIN_PATH, method="POST", body=body, use_login_auth=True)
        except ZetarisAuthError:
            raise
        except ZetarisError as e:
            raise ZetarisAuthError(f"Login request failed: {e}") from e

        if not isinstance(resp, dict):
            raise ZetarisAuthError(f"Login response is not a JSON object: {resp}")

        token = resp.get("idToken")
        org_id = resp.get("orgId")
        if not token:
            raise ZetarisAuthError(f"Login succeeded but no idToken returned: {resp}")
        if not org_id:
            raise ZetarisAuthError(f"Login succeeded but no orgId returned: {resp}")

        self._token = token
        self._org_id = str(org_id)

    # --- Public API ---

    def test_connection(self) -> ToolResult:
        """Test connectivity by running a simple SELECT 1 query."""
        try:
            self.ensure_authenticated()
            result = self.execute_query("SELECT 1 AS ok")
            if result.status == "success":
                return ToolResult.success(
                    action="zetaris_test_connection",
                    message="Connected to Zetaris; SELECT 1 succeeded",
                    data={"test_query": "SELECT 1", "rows": result.data.get("rows", [])},
                )
            return result
        except ZetarisError as e:
            return ToolResult.error(
                action="zetaris_test_connection",
                message="Zetaris connection test failed",
                error=str(e),
            )

    def execute_query(self, sql: str, limit: Optional[int] = None) -> ToolResult:
        """Execute a read-only SQL query with enforced limits and pagination."""
        # Validate
        valid, err = validate_select_only(sql)
        if not valid:
            return ToolResult.error(
                action="zetaris_execute_query",
                message="Query validation failed",
                error=err,
            )

        # Enforce limit
        limit = limit or self.config.default_limit
        limit = min(limit, self.config.max_limit)
        limit = max(1, min(limit, 100))  # Hard cap at 100 per API spec

        query_token = None
        all_rows: List[List[Any]] = []
        columns: List[str] = []

        try:
            self.ensure_authenticated()

            # Start query
            start_body = {
                "select": sql,
                "pageLimit": limit,
            }
            start_resp = self._request(self.START_QUERY_PATH, method="POST", body=start_body)

            if not isinstance(start_resp, dict):
                return ToolResult.error(
                    action="zetaris_execute_query",
                    message="Query start returned unexpected response format",
                    error=f"Expected dict, got {type(start_resp)}",
                )

            query_token = start_resp.get("queryToken")
            if not query_token:
                return ToolResult.error(
                    action="zetaris_execute_query",
                    message="Query started but no queryToken returned",
                    error=f"Response: {start_resp}",
                )

            # Extract columns from first page if available
            cols = start_resp.get("columns") or start_resp.get("schema") or start_resp.get("fields")
            if isinstance(cols, list):
                columns = [str(c.get("name") if isinstance(c, dict) else c) for c in cols]

            # Extract rows from first page
            records = start_resp.get("records") or []
            for row in records:
                if isinstance(row, dict):
                    # Records are objects with column names as keys
                    if columns:
                        all_rows.append([row.get(col) for col in columns])
                    else:
                        all_rows.append(list(row.values()))
                elif isinstance(row, (list, tuple)):
                    all_rows.append(list(row))
                else:
                    all_rows.append([row])

            # Check if there are more pages
            total_pages = start_resp.get("totalPages", 1)
            current_page = start_resp.get("pageNumber", 1)

            # Fetch additional pages if needed (but respect limit)
            while current_page < total_pages and len(all_rows) < limit:
                current_page += 1
                page_params = urlencode({
                    "queryToken": query_token,
                    "pageLimit": limit,
                    "pageNumber": current_page,
                })
                page_path = f"{self.PAGE_QUERY_PATH}?{page_params}"
                page_resp = self._request(page_path, method="GET")

                if not isinstance(page_resp, dict):
                    break
                records = page_resp.get("records") or []
                for row in records:
                    if len(all_rows) >= limit:
                        break
                    if isinstance(row, dict):
                        if columns:
                            all_rows.append([row.get(col) for col in columns])
                        else:
                            all_rows.append(list(row.values()))
                    elif isinstance(row, (list, tuple)):
                        all_rows.append(list(row))
                    else:
                        all_rows.append([row])

        except ZetarisError as e:
            return ToolResult.error(
                action="zetaris_execute_query",
                message="Query execution failed",
                error=str(e),
            )
        finally:
            # Always close the query
            if query_token:
                try:
                    close_path = f"{self.CLOSE_QUERY_PATH}{query_token}"
                    self._request(close_path, method="DELETE")
                except ZetarisError:
                    # Log but don't fail the result
                    pass

        return ToolResult.success(
            action="zetaris_execute_query",
            message=f"Query returned {len(all_rows)} row(s)",
            data={
                "columns": columns,
                "rows": all_rows,
                "row_count": len(all_rows),
                "query_token": query_token,
            },
        )


# --- Module-level helpers for command integration ---

def get_zetaris_client(config: Dict[str, Any]) -> tuple[Optional[ZetarisClient], Optional[str]]:
    """Create a ZetarisClient from config dict. Returns (client, error_message)."""
    zconfig = ZetarisConfig.from_config_dict(config)
    ok, err = zconfig.is_configured()
    if not ok:
        return None, err
    return ZetarisClient(zconfig), None


def handle_zetaris_command(prompt: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Handle zetaris: commands from the main command processor.

    Supported patterns:
    - zetaris: test connection
    - zetaris: query <sql>
    - zetaris: run <sql>
    - zetaris: select ...

    Returns response dict matching /api/command format, or None if not a zetaris command.
    """
    pl = prompt.lower().strip()
    if not (pl.startswith("zetaris:") or pl.startswith("zetaris ")):
        return None

    # Extract the subcommand
    cmd = pl[len("zetaris:"):].strip() if pl.startswith("zetaris:") else pl[len("zetaris "):].strip()

    client, err = get_zetaris_client(config)
    if err:
        return {
            "speak": f"Zetaris not configured: {err}",
            "speak_lang": "en",
            "logs": [f"INPUT RECEIVED: \"{prompt}\"", f"ZETARIS: Configuration error: {err}"],
            "file_data": None,
            "refresh_files": False,
            "image_data": None,
            "timer_data": None,
            "clarification_needed": None,
            "narration_steps": [],
        }

    if cmd in ("test", "test connection", "ping", "health"):
        result = client.test_connection()
        speak = result.message
        logs = [f"INPUT RECEIVED: \"{prompt}\"", f"ACTION: Zetaris test connection", f"RESULT: {speak}"]
        return {
            "speak": speak,
            "speak_lang": "en",
            "logs": logs,
            "file_data": result.data,
            "refresh_files": False,
            "image_data": None,
            "timer_data": None,
            "clarification_needed": None,
            "narration_steps": [],
        }

    # Query execution: "query SELECT ..." or "run SELECT ..." or direct "SELECT ..."
    if cmd.startswith("query ") or cmd.startswith("run ") or _ALLOWED_START.match(cmd):
        sql = cmd
        if cmd.startswith("query "):
            sql = cmd[len("query "):].strip()
        elif cmd.startswith("run "):
            sql = cmd[len("run "):].strip()

        result = client.execute_query(sql)
        if result.status == "success":
            rows = result.data.get("rows", [])
            speak = result.message
            logs = [f"INPUT RECEIVED: \"{prompt}\"", f"ACTION: Zetaris query", f"RESULT: {speak}"]
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": logs,
                "file_data": result.data,
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": [],
            }
        else:
            speak = f"Query failed: {result.error}"
            logs = [f"INPUT RECEIVED: \"{prompt}\"", f"ACTION: Zetaris query", f"RESULT: {speak}"]
            return {
                "speak": speak,
                "speak_lang": "en",
                "logs": logs,
                "file_data": None,
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": [],
            }

    return {
        "speak": "Unknown Zetaris command. Try: zetaris: test connection, or zetaris: query SELECT ...",
        "speak_lang": "en",
        "logs": [f"INPUT RECEIVED: \"{prompt}\"", "ZETARIS: Unknown subcommand"],
        "file_data": None,
        "refresh_files": False,
        "image_data": None,
        "timer_data": None,
        "clarification_needed": None,
        "narration_steps": [],
    }