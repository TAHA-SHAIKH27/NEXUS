"""
Unit tests for Zetaris connector (backend/tools/zetaris.py).

Run with: pytest test_zetaris.py -v
Live integration tests require RUN_LIVE_ZETARIS_TESTS=1 and valid credentials
in environment variables (ZETARIS_USERNAME, ZETARIS_PASSWORD, ZETARIS_ORG_ID).
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.tools.zetaris import (
    ZetarisClient,
    ZetarisConfig,
    validate_select_only,
    handle_zetaris_command,
    get_zetaris_client,
    ZetarisAuthError,
    ZetarisTimeoutError,
    ZetarisError,
)
from urllib.error import HTTPError


# --- Test Configuration ---

TEST_CONFIG = {
    "zetaris_rest_url": "http://localhost:8888/api/v1.0",
    "zetaris_auth_url": "http://localhost:8889",
    "zetaris_org_id": "",
    "zetaris_username": "admin@zetaris.com",
    "zetaris_password": "Zetaris1@",
    "zetaris_default_limit": 50,
    "zetaris_max_limit": 100,
    "zetaris_timeout_seconds": 30,
}

MINIMAL_CONFIG = {
    "zetaris_rest_url": "http://localhost:8888/api/v1.0",
    "zetaris_auth_url": "http://localhost:8889",
    "zetaris_username": "admin@zetaris.com",
    "zetaris_password": "Zetaris1@",
}

INCOMPLETE_CONFIGS = [
    {},  # Missing everything
    {"zetaris_rest_url": "http://localhost:8888/api/v1.0"},  # Missing auth
    {"zetaris_username": "admin@zetaris.com"},  # Missing password
]


# --- validate_select_only Tests ---

class TestValidateSelectOnly:
    """Test the SQL validator."""

    @pytest.mark.parametrize("sql,expected_valid", [
        ("SELECT 1", True),
        ("select * from table", True),
        ("SELECT a, b FROM t WHERE c = 1", True),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", True),
        ("  SELECT 1  ", True),
        ("SELECT 1;", True),
        ("", False),
        ("INSERT INTO t VALUES (1)", False),
        ("UPDATE t SET a = 1", False),
        ("DELETE FROM t", False),
        ("CREATE TABLE t (a INT)", False),
        ("DROP TABLE t", False),
        ("ALTER TABLE t ADD COLUMN b INT", False),
        ("TRUNCATE TABLE t", False),
        ("MERGE INTO t USING ...", False),
        ("REPLACE INTO t VALUES (1)", False),
        ("GRANT SELECT ON t TO u", False),
        ("REVOKE SELECT ON t FROM u", False),
        ("COMMIT", False),
        ("ROLLBACK", False),
        ("BEGIN TRANSACTION", False),
        ("EXEC sp_something", False),
        ("EXECUTE sp_something", False),
        ("CALL sp_something()", False),
        ("DECLARE @x INT", False),
        ("SET @x = 1", False),
        ("SELECT 1; SELECT 2", False),
        ("SELECT 1; DROP TABLE t", False),
        ("SHOW DATABASES", False),
        ("SHOW TABLES", False),
        ("DESCRIBE table", False),
        ("DESC table", False),
        ("EXPLAIN SELECT * FROM t", False),
    ])
    def test_validate_select_only(self, sql, expected_valid):
        valid, err = validate_select_only(sql)
        assert valid == expected_valid, f"SQL: {sql!r} -> expected {expected_valid}, got {valid} (err: {err})"


# --- ZetarisConfig Tests ---

class TestZetarisConfig:
    """Test configuration loading."""

    def test_from_config_dict_full(self):
        config = ZetarisConfig.from_config_dict(TEST_CONFIG)
        assert config.rest_url == "http://localhost:8888/api/v1.0"
        assert config.auth_url == "http://localhost:8889"
        assert config.org_id == ""
        assert config.username == "admin@zetaris.com"
        assert config.password == "Zetaris1@"
        assert config.default_limit == 50
        assert config.max_limit == 100
        assert config.timeout_seconds == 30

    def test_from_config_dict_minimal(self):
        config = ZetarisConfig.from_config_dict(MINIMAL_CONFIG)
        assert config.rest_url == "http://localhost:8888/api/v1.0"
        assert config.auth_url == "http://localhost:8889"
        assert config.org_id == ""
        assert config.username == "admin@zetaris.com"
        assert config.password == "Zetaris1@"

    def test_from_config_dict_defaults(self):
        config = ZetarisConfig.from_config_dict({})
        assert config.rest_url == "http://localhost:8888/api/v1.0"
        assert config.auth_url == "http://localhost:8889"
        assert config.org_id == ""
        assert config.username == ""
        assert config.password == ""
        assert config.default_limit == 50
        assert config.max_limit == 100
        assert config.timeout_seconds == 30

    def test_from_config_dict_old_base_url(self):
        """Test backward compatibility with old zetaris_base_url config."""
        old_config = {
            "zetaris_base_url": "http://localhost:3000",
            "zetaris_username": "admin@zetaris.com",
            "zetaris_password": "Zetaris1@",
        }
        config = ZetarisConfig.from_config_dict(old_config)
        # Should derive auth_url from base_url
        assert config.auth_url == "http://localhost:8889"
        assert config.rest_url == "http://localhost:3000"  # falls back to base_url

    def test_from_config_dict_old_base_url_8888(self):
        """Test backward compatibility with old zetaris_base_url on 8888."""
        old_config = {
            "zetaris_base_url": "http://localhost:8888/api/v1.0",
            "zetaris_username": "admin@zetaris.com",
            "zetaris_password": "Zetaris1@",
        }
        config = ZetarisConfig.from_config_dict(old_config)
        assert config.auth_url == "http://localhost:8889"
        assert config.rest_url == "http://localhost:8888/api/v1.0"

    @pytest.mark.parametrize("config", INCOMPLETE_CONFIGS)
    def test_is_configured_fails(self, config):
        zconfig = ZetarisConfig.from_config_dict(config)
        ok, err = zconfig.is_configured()
        assert not ok
        assert err

    def test_is_configured_succeeds_with_user_pass(self):
        zconfig = ZetarisConfig.from_config_dict(MINIMAL_CONFIG)
        ok, err = zconfig.is_configured()
        assert ok
        assert not err


# --- ZetarisClient Tests (Mocked) ---

class TestZetarisClient:
    """Test ZetarisClient with mocked HTTP."""

    def setup_method(self):
        self.config = ZetarisConfig.from_config_dict(MINIMAL_CONFIG)
        self.client = ZetarisClient(self.config)

    def test_init_no_token(self):
        assert self.client._token is None
        assert self.client._org_id is None

    def test_rest_and_auth_base_urls(self):
        assert self.client._rest_base == "http://localhost:8888/api/v1.0"
        assert self.client._auth_base == "http://localhost:8889"

    @patch("backend.tools.zetaris.urlopen")
    def test_request_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"records": [[1, "test"]]}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_resp

        result = self.client._request("/test", method="GET")
        assert result == {"records": [[1, "test"]]}

    @patch("backend.tools.zetaris.urlopen")
    def test_request_http_error_401(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"error": "unauthorized"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=None)
        http_error = HTTPError("url", 401, "Unauthorized", {}, mock_resp)
        mock_urlopen.side_effect = http_error

        with pytest.raises(ZetarisAuthError):
            self.client._request("/test")

    @patch("backend.tools.zetaris.urlopen")
    def test_request_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timeout")

        with pytest.raises(ZetarisTimeoutError):
            self.client._request("/test")

    @patch.object(ZetarisClient, "_request")
    def test_ensure_authenticated_login_success(self, mock_request):
        # Login returns idToken and orgId via HTTP Basic Auth (GET)
        mock_request.return_value = {"idToken": "new-token", "refreshToken": "refresh-token", "orgId": 1}

        self.client.ensure_authenticated()
        assert self.client._token == "new-token"
        assert self.client._org_id == "1"
        # Should call GET /api/v1.0/internal/auth/legacy-login with use_auth_base=True
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/api/v1.0/internal/auth/legacy-login"
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["use_auth_base"] is True

    @patch.object(ZetarisClient, "_request")
    def test_ensure_authenticated_login_failure(self, mock_request):
        mock_request.side_effect = ZetarisAuthError("bad credentials")

        with pytest.raises(ZetarisAuthError):
            self.client.ensure_authenticated()

    @patch.object(ZetarisClient, "_request")
    def test_ensure_authenticated_no_credentials(self, mock_request):
        config = ZetarisConfig.from_config_dict({
            "zetaris_rest_url": "http://localhost:8888/api/v1.0",
            "zetaris_auth_url": "http://localhost:8889",
        })
        client = ZetarisClient(config)

        with pytest.raises(ZetarisAuthError):
            client.ensure_authenticated()
        mock_request.assert_not_called()

    @patch.object(ZetarisClient, "_request")
    def test_test_connection_success(self, mock_request):
        # test_connection -> ensure_authenticated (login) -> execute_query -> start + close
        mock_request.side_effect = [
            {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1},  # login
            {  # start query
                "records": [{"ok": "1"}],
                "queryToken": "token-123",
                "columns": [{"name": "ok"}],
                "pageNumber": 1,
                "totalPages": 1,
            },
            None,  # close
        ]
        result = self.client.test_connection()
        assert result.status == "success"
        assert "SELECT 1 succeeded" in result.message
        assert mock_request.call_count == 3

    @patch.object(ZetarisClient, "_request")
    def test_execute_query_success_single_page(self, mock_request):
        # start query response
        mock_request.side_effect = [
            {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1},  # login
            {  # start query
                "records": [{"id": 1, "name": "zone1"}, {"id": 2, "name": "zone2"}],
                "queryToken": "token-123",
                "columns": [{"name": "id"}, {"name": "name"}],
                "pageNumber": 1,
                "totalPages": 1,
            },
            None,  # close
        ]

        result = self.client.execute_query("SELECT * FROM NY_TAXI.taxi_zones LIMIT 2")
        assert result.status == "success"
        assert result.data["row_count"] == 2
        assert result.data["rows"] == [[1, "zone1"], [2, "zone2"]]
        assert result.data["columns"] == ["id", "name"]
        assert result.data["query_token"] == "token-123"

        # Verify calls: login + start query + close
        assert mock_request.call_count == 3
        start_call = mock_request.call_args_list[1]
        assert start_call[0][0] == "/query/sql/start"
        assert start_call[1]["method"] == "POST"
        assert start_call[1]["body"]["select"] == "SELECT * FROM NY_TAXI.taxi_zones LIMIT 2"
        assert start_call[1]["body"]["pageLimit"] == 50

        close_call = mock_request.call_args_list[2]
        assert close_call[0][0] == "/query/sql/close/token-123"
        assert close_call[1]["method"] == "DELETE"

    @patch.object(ZetarisClient, "_request")
    def test_execute_query_multi_page(self, mock_request):
        # start query response (page 1 of 2)
        mock_request.side_effect = [
            {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1},  # login
            {  # start query (page 1)
                "records": [{"id": 1, "name": "zone1"}],
                "queryToken": "token-123",
                "columns": [{"name": "id"}, {"name": "name"}],
                "pageNumber": 1,
                "totalPages": 2,
            },
            {  # page 2
                "records": [{"id": 2, "name": "zone2"}],
                "queryToken": "token-123",
                "pageNumber": 2,
                "totalPages": 2,
            },
            None,  # close
        ]

        result = self.client.execute_query("SELECT * FROM NY_TAXI.taxi_zones LIMIT 2")
        assert result.status == "success"
        assert result.data["row_count"] == 2
        assert result.data["rows"] == [[1, "zone1"], [2, "zone2"]]

        # Verify calls: login + start + page + close
        assert mock_request.call_count == 4
        page_call = mock_request.call_args_list[2]
        assert page_call[0][0].startswith("/query/sql/page")
        assert "pageNumber=2" in page_call[0][0]

    @patch.object(ZetarisClient, "_request")
    def test_execute_query_validation_failure(self, mock_request):
        result = self.client.execute_query("INSERT INTO t VALUES (1)")
        assert result.status == "error"
        assert "Only SELECT or WITH queries are permitted" in result.error
        mock_request.assert_not_called()

    @patch.object(ZetarisClient, "_request")
    def test_execute_query_enforces_limit(self, mock_request):
        mock_request.side_effect = [
            {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1},  # login
            {"records": [], "queryToken": "token-123", "pageNumber": 1, "totalPages": 1},
            None,
        ]
        self.client.execute_query("SELECT * FROM t", limit=500)  # Over max
        # Should be capped at max_limit (100) and then at hard cap (100)
        start_call = mock_request.call_args_list[1]
        assert start_call[1]["body"]["pageLimit"] == 100

    @patch.object(ZetarisClient, "_request")
    def test_execute_query_close_on_error(self, mock_request):
        # Simulate error on start query
        mock_request.side_effect = [
            {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1},  # login
            ZetarisAuthError("auth failed"),  # start query fails
        ]

        result = self.client.execute_query("SELECT 1")
        assert result.status == "error"
        # Close should not be called if query never started
        assert mock_request.call_count == 2

    @patch.object(ZetarisClient, "_request")
    def test_execute_query_close_failure_logged(self, mock_request):
        mock_request.side_effect = [
            {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1},  # login
            {"records": [{"ok": "1"}], "queryToken": "token-123", "pageNumber": 1, "totalPages": 1},
            ZetarisError("close failed"),  # close fails
        ]

        result = self.client.execute_query("SELECT 1")
        assert result.status == "success"
        assert mock_request.call_count == 3

    @patch.object(ZetarisClient, "_request")
    def test_login_uses_basic_auth_header(self, mock_request):
        """Verify that login uses HTTP Basic Authentication header."""
        mock_request.return_value = {"idToken": "token-123", "refreshToken": "refresh", "orgId": 1}
        
        self.client.ensure_authenticated()
        
        # Check that the request was made with use_auth_base=True (which triggers Basic Auth)
        call_args = mock_request.call_args
        assert call_args[1]["use_auth_base"] is True
        # The _request method should add the Basic Auth header when use_auth_base=True


# --- handle_zetaris_command Tests ---

class TestHandleZetarisCommand:
    """Test the command handler integration."""

    def test_not_zetaris_command_returns_none(self):
        result = handle_zetaris_command("what time is it", MINIMAL_CONFIG)
        assert result is None

    def test_unknown_zetaris_command(self):
        result = handle_zetaris_command("zetaris: unknown", MINIMAL_CONFIG)
        assert result is not None
        assert "Unknown Zetaris command" in result["speak"]

    def test_test_connection(self):
        with patch("backend.tools.zetaris.ZetarisClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.test_connection.return_value = MagicMock(
                status="success",
                message="Connected to Zetaris; SELECT 1 succeeded",
                data={"test_query": "SELECT 1", "rows": [["1"]]},
            )
            mock_client_class.return_value = mock_client

            result = handle_zetaris_command("zetaris: test connection", MINIMAL_CONFIG)
            assert result is not None
            assert "SELECT 1 succeeded" in result["speak"]
            assert result["file_data"]["rows"] == [["1"]]

    def test_query_select(self):
        with patch("backend.tools.zetaris.ZetarisClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.execute_query.return_value = MagicMock(
                status="success",
                message="Query returned 2 row(s)",
                data={"rows": [[1, "zone1"], [2, "zone2"]], "row_count": 2, "columns": ["id", "name"]},
            )
            mock_client_class.return_value = mock_client

            result = handle_zetaris_command("zetaris: query SELECT * FROM NY_TAXI.customers LIMIT 2", MINIMAL_CONFIG)
            assert result is not None
            assert "2 row(s)" in result["speak"]
            assert result["file_data"]["row_count"] == 2

    def test_query_run_keyword(self):
        with patch("backend.tools.zetaris.ZetarisClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.execute_query.return_value = MagicMock(
                status="success",
                message="Query returned 1 row(s)",
                data={"rows": [[1]], "row_count": 1},
            )
            mock_client_class.return_value = mock_client

            result = handle_zetaris_command("zetaris: run SELECT 1", MINIMAL_CONFIG)
            assert result is not None
            assert "1 row(s)" in result["speak"]

    def test_direct_select(self):
        with patch("backend.tools.zetaris.ZetarisClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.execute_query.return_value = MagicMock(
                status="success",
                message="Query returned 1 row(s)",
                data={"rows": [[1]], "row_count": 1},
            )
            mock_client_class.return_value = mock_client

            result = handle_zetaris_command("zetaris: SELECT 1", MINIMAL_CONFIG)
            assert result is not None
            assert "1 row(s)" in result["speak"]

    def test_config_error(self):
        result = handle_zetaris_command("zetaris: test", {})
        assert result is not None
        assert "Zetaris not configured" in result["speak"]

    def test_query_rejected_write(self):
        with patch("backend.tools.zetaris.ZetarisClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.execute_query.return_value = MagicMock(
                status="error",
                error="Write/DDL operations are not permitted",
            )
            mock_client_class.return_value = mock_client

            result = handle_zetaris_command("zetaris: query INSERT INTO t VALUES (1)", MINIMAL_CONFIG)
            assert result is not None
            assert "Query failed" in result["speak"]
            assert "Write/DDL operations are not permitted" in result["speak"]


# --- get_zetaris_client Tests ---

class TestGetZetarisClient:
    """Test the client factory function."""

    def test_returns_client_and_none_error(self):
        client, err = get_zetaris_client(MINIMAL_CONFIG)
        assert client is not None
        assert err is None

    def test_returns_none_and_error(self):
        client, err = get_zetaris_client({})
        assert client is None
        assert err is not None


# --- Live Integration Test (opt-in) ---

class TestLiveIntegration:
    """Live integration tests against real Zetaris instance.

    These tests are skipped unless RUN_LIVE_ZETARIS_TESTS=1 is set
    and valid credentials are configured in environment variables.
    Config.json credentials are NOT used for live tests to avoid
    accidental runs with placeholder credentials.
    """

    @pytest.fixture(scope="class")
    def live_config(self):
        """Load config from environment variables only."""
        if not os.environ.get("RUN_LIVE_ZETARIS_TESTS"):
            pytest.skip("RUN_LIVE_ZETARIS_TESTS=1 not set")
        
        config = {
            "zetaris_rest_url": os.environ.get("ZETARIS_REST_URL", "http://localhost:8888/api/v1.0"),
            "zetaris_auth_url": os.environ.get("ZETARIS_AUTH_URL", "http://localhost:8889"),
            "zetaris_org_id": os.environ.get("ZETARIS_ORG_ID", ""),
            "zetaris_username": os.environ.get("ZETARIS_USERNAME", ""),
            "zetaris_password": os.environ.get("ZETARIS_PASSWORD", ""),
        }
        # Require explicit credentials from environment
        if not config["zetaris_username"] or not config["zetaris_password"]:
            pytest.skip("ZETARIS_USERNAME and ZETARIS_PASSWORD not set in environment")
        return config

    @pytest.fixture(scope="class")
    def client(self, live_config):
        zconfig = ZetarisConfig.from_config_dict(live_config)
        ok, err = zconfig.is_configured()
        if not ok:
            pytest.skip(f"Zetaris not configured: {err}")
        return ZetarisClient(zconfig)

    def test_live_connection(self, client):
        """Test that we can connect to Zetaris."""
        result = client.test_connection()
        assert result.status == "success", f"Connection failed: {result.error}"
        print(f"Live test: {result.message}")

    def test_live_select_1(self, client):
        """Test SELECT 1."""
        result = client.execute_query("SELECT 1")
        assert result.status == "success", f"SELECT 1 failed: {result.error}"
        assert result.data["row_count"] == 1
        assert result.data["rows"][0][0] in (1, "1")

    def test_live_select_ny_taxi(self, client):
        """Test SELECT from NY_TAXI (if available)."""
        # Try a simple query - NY_TAXI.customers was verified to work
        result = client.execute_query("SELECT * FROM NY_TAXI.customers LIMIT 2")
        if result.status == "error" and "not found" in result.error.lower():
            pytest.skip(f"Table not found: {result.error}")

        assert result.status == "success", f"Query failed: {result.error}"
        assert result.data["row_count"] <= 2, "Row limit not enforced"
        print(f"NY_TAXI.customers query returned {result.data['row_count']} rows")

    def test_live_select_count(self, client):
        """Test COUNT query on NY_TAXI.customers."""
        result = client.execute_query("SELECT COUNT(*) FROM NY_TAXI.customers")
        if result.status == "error" and "not found" in result.error.lower():
            pytest.skip(f"Table not found: {result.error}")

        assert result.status == "success", f"Query failed: {result.error}"
        assert result.data["row_count"] == 1
        print(f"Count: {result.data['rows'][0][0]}")

    def test_live_rejects_write(self, client):
        """Test that write queries are rejected."""
        result = client.execute_query("INSERT INTO test VALUES (1)")
        assert result.status == "error"
        assert "not permitted" in result.error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])