"""Mocked tests for the NL-to-SQL query planner."""

import json
from backend.tools.nl_to_sql import (
    parse_natural_language,
    create_query_plan,
    SCHEMA_REGISTRY,
    sanitize_identifier,
    sanitize_literal,
    QueryExecutor,
    QueryTypeValue,
)

class FakeZetarisClient:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0
    
    def execute_query(self, sql, limit=None):
        from backend.tools.result_schema import ToolResult
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return ToolResult.error("zetaris_execute_query", "No more mocked responses", error="exhausted")


def test_parse_natural_language_crop():
    intent = parse_natural_language("Show tomato spoilage risk in Nashik")
    assert intent.crop == "Tomato"
    assert intent.districts == ["Nashik"]
    assert intent.intent_type == "spoilage"


def test_parse_natural_language_market():
    intent = parse_natural_language("Compare tomato prices in Mumbai and Pune")
    assert intent.crop == "Tomato"
    assert "Mumbai" in intent.markets
    assert "Pune" in intent.markets
    assert intent.intent_type == "market_selection"


def test_parse_natural_language_hold_vs_sell():
    intent = parse_natural_language("Should we hold vs sell onions?")
    assert intent.crop == "Onion"
    assert intent.intent_type == "hold_vs_sell"


def test_parse_natural_language_transport():
    intent = parse_natural_language("Transport cost from warehouse to Mumbai")
    assert intent.intent_type == "storage_transport"
    assert "Mumbai" in intent.markets


def test_parse_natural_language_batch():
    intent = parse_natural_language("Details for batch BAT-123")
    assert intent.batch_code == "BAT-123"
    assert intent.intent_type == "batch_recommendation"


def test_sanitize_identifier():
    assert sanitize_identifier("valid_name") == "valid_name"
    assert sanitize_identifier("valid123") == "valid123"
    try:
        sanitize_identifier("invalid-name")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    try:
        sanitize_identifier("123invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_sanitize_literal():
    assert sanitize_literal("normal") == "normal"
    assert sanitize_literal("with'quote") == "withquote"
    assert sanitize_literal('with"double') == "withdouble"
    assert sanitize_literal("with;semicolon") == "withsemicolon"
    assert sanitize_literal(123) == 123


def test_schema_registry():
    assert SCHEMA_REGISTRY.validate_table("fpos")
    assert SCHEMA_REGISTRY.validate_table("crops")
    assert not SCHEMA_REGISTRY.validate_table("nonexistent")
    
    cols = SCHEMA_REGISTRY.validate_columns("fpos", ["fpo_id", "fpo_name", "invalid"])
    assert cols == ["fpo_id", "fpo_name"]
    
    col_type = SCHEMA_REGISTRY.get_column_type("fpos", "fpo_id")
    assert col_type == "uuid"


def test_create_spoilage_query():
    from backend.tools.nl_to_sql import NLParsedIntent
    intent = NLParsedIntent(
        intent_type="spoilage",
        crop="Tomato",
        districts=["Nashik"],
    )
    plan = create_query_plan(intent)
    assert plan.query_type == "spoilage_risk"
    assert "Tomato" in plan.params
    assert "Nashik" in plan.params
    assert "v_batch_spoilage_risk" in plan.tables


def test_create_market_query():
    from backend.tools.nl_to_sql import NLParsedIntent
    intent = NLParsedIntent(
        intent_type="market_selection",
        crop="Onion",
        markets=["Mumbai", "Pune"],
    )
    plan = create_query_plan(intent)
    assert plan.query_type == "market_prices"
    assert "Onion" in plan.params
    assert "Mumbai" in plan.params
    assert "Pune" in plan.params


def test_create_transport_query():
    from backend.tools.nl_to_sql import NLParsedIntent
    intent = NLParsedIntent(
        intent_type="storage_transport",
        markets=["Mumbai"],
    )
    plan = create_query_plan(intent)
    assert plan.query_type == "transport_routes"
    assert "Mumbai" in plan.params


def test_create_overview_query():
    from backend.tools.nl_to_sql import NLParsedIntent
    intent = NLParsedIntent(intent_type="overview")
    plan = create_query_plan(intent)
    assert plan.query_type == "overview"
    assert plan.params == []


def test_query_executor():
    from backend.tools.result_schema import ToolResult
    
    # Mock response
    mock_response = ToolResult.success(
        action="test",
        message="OK",
        data={
            "columns": ["crop_name", "count"],
            "rows": [["Tomato", 10], ["Onion", 5]],
            "row_count": 2,
        }
    )
    
    client = FakeZetarisClient([mock_response])
    executor = QueryExecutor(config={})
    executor._client = client
    
    from backend.tools.nl_to_sql import NLParsedIntent
    intent = NLParsedIntent(intent_type="spoilage", crop="Tomato")
    plan = create_query_plan(intent)
    
    result = executor.execute(plan)
    
    assert result["status"] == "success"
    assert result["query_type"] == "spoilage_risk"
    assert result["row_count"] == 2
    assert len(result["rows"]) == 2
    assert result["rows"][0]["crop_name"] == "Tomato"


def test_schema_catalog():
    catalog = SCHEMA_REGISTRY.get_allowlist()
    assert "fpos" in catalog
    assert "crops" in catalog
    assert "harvest_batches" in catalog
    assert "v_batch_spoilage_risk" in catalog
    
    # Check relationships
    from backend.tools.nl_to_sql import get_schema_catalog
    schema = get_schema_catalog()
    assert "tables" in schema
    assert "relationships" in schema
    assert len(schema["relationships"]) > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])