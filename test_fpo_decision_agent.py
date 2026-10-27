"""Pipeline tests for FPO decision intelligence. Analytics and models are injected."""

from backend.tools.fpo_decision_agent import (
    calculate_finance,
    classify_intent,
    handle_fpo_decision_command,
    run_pipeline,
    validate_reasoning,
)
from backend.agent.agri_context import AgriContext, agri_context_store


class StubAnalytics:
    def __init__(self, *, fail=False):
        self.fail = fail

    def _err(self):
        return {"status": "error", "message": "stubbed outage"}

    def get_market_intelligence(self, crop_name=None, market_name=None):
        if self.fail:
            return self._err()
        return {
            "status": "success",
            "crop": crop_name or "Tomato",
            "market_comparison": [
                {"market_name": "Mumbai", "district": "Mumbai", "avg_price": "2400", "observations_count": 12},
                {"market_name": "Lasalgaon", "district": "Nashik", "avg_price": "1800", "observations_count": 20},
            ],
            "trends": [],
            "top_buyers": [],
        }

    def get_risk_centre(self, risk_level=None):
        if self.fail:
            return self._err()
        return {
            "status": "success",
            "critical_batches": [
                {
                    "batch_code": "BAT-1",
                    "crop_name": "Tomato",
                    "net_available_kg": "1000",
                    "days_until_quality_window_end": 2,
                    "spoilage_risk_level": "high_risk",
                }
            ],
            "congested_warehouses": [],
            "crop_risk_summary": [],
        }

    def get_logistics_intelligence(self):
        if self.fail:
            return self._err()
        return {
            "status": "success",
            "warehouses": [],
            "routes": [
                {
                    "origin_warehouse": "Nashik Hub",
                    "origin_district": "Nashik",
                    "destination_market": "Mumbai",
                    "distance_km": "180",
                    "transport_cost_per_kg_inr": "1.25",
                    "vehicle_type": "truck",
                }
            ],
        }

    def get_decisions_scenarios(self):
        if self.fail:
            return self._err()
        return {
            "status": "success",
            "scenarios": [],
            "sales_analysis": [
                {
                    "order_code": "SO-1",
                    "crop_name": "Tomato",
                    "gross_revenue_inr": "50000",
                    "transport_cost_inr": "4000",
                    "estimated_net_revenue_inr": "46000",
                    "net_margin_pct": "8.5",
                }
            ],
        }

    def get_inventory_batches(self, **kwargs):
        if self.fail:
            return self._err()
        return {"status": "success", "items": []}


class FakeLLM:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def chat(self, prompt, system_prompt="", model=None):
        self.calls += 1
        return self.text


def test_intents():
    assert classify_intent("Should we hold vs sell tomatoes") == "hold_vs_sell"
    assert classify_intent("Which market for onion") == "market_selection"
    assert classify_intent("Compare net profit") == "net_profit"
    assert classify_intent("Tomato spoilage risk") == "spoilage"


def test_finance_uses_only_retrieved_numbers():
    evidence = {
        "crop": "Tomato",
        "warnings": [],
        "data": {
            "market": StubAnalytics().get_market_intelligence("Tomato"),
            "logistics": StubAnalytics().get_logistics_intelligence(),
            "risks": StubAnalytics().get_risk_centre(),
            "scenarios": StubAnalytics().get_decisions_scenarios(),
        },
    }
    finance = calculate_finance(evidence)
    sell = finance["sell_now"]
    assert sell["quantity_kg"] == 1000.0
    assert sell["gross_per_kg_inr"] == 24.0  # 2400 / 100
    assert sell["transport_per_kg_inr"] == 1.25
    assert sell["net_per_kg_inr"] == 22.75
    assert sell["estimated_net_inr"] == 22750.0
    assert finance["recommended_action"] == "sell_now"
    assert finance["days_until_quality_window_end"] == 2


def test_missing_data_warnings_on_outage():
    result = run_pipeline("hold vs sell tomato", analytics=StubAnalytics(fail=True))
    assert result["live_model"] is False
    assert result["provider"] == "deterministic"
    assert result["evidence"]["warnings"]
    assert result["recommendation"]["action"] == "insufficient_data"


def test_llm_numbers_not_in_finance_are_rejected():
    finance = {"estimated_net_inr": 22750.0, "quantity_kg": 1000}
    checked = validate_reasoning("Sell for 999999 rupees on 3 kg", finance)
    assert checked["ok"] is False
    assert "999999" in checked["invented_tokens"]


def test_meterless_explanation_accepted_when_numbers_match():
    llm = FakeLLM("Sell now. Net is 22750.0 INR on 1000.0 kg after 1.25 freight.")
    result = run_pipeline(
        "hold vs sell tomato",
        analytics=StubAnalytics(),
        meterless_client=llm,
    )
    assert result["live_model"] is True
    assert result["provider"] == "meterless"
    assert llm.calls == 1
    assert "22750.0" in result["speak"]


def test_invented_llm_falls_back_without_claiming_live_success():
    llm = FakeLLM("Guaranteed profit of 888888 INR")
    result = run_pipeline(
        "hold vs sell tomato",
        analytics=StubAnalytics(),
        meterless_client=llm,
    )
    assert result["live_model"] is False
    assert result["provider"] == "deterministic"
    assert "888888" not in result["speak"]


def test_nvidia_used_when_meterless_missing():
    llm = FakeLLM("Use Mumbai. Net 22750.0 INR.")
    result = run_pipeline(
        "which market for tomato",
        analytics=StubAnalytics(),
        nvidia_client=llm,
    )
    assert result["provider"] == "nvidia_nim"
    assert result["live_model"] is True


def test_handle_command_ignores_unrelated():
    assert handle_fpo_decision_command("what time is it") is None


def test_handle_command_routes_decision():
    # Uses real analytics module — may error if DB down; still must not claim live.
    result = handle_fpo_decision_command("hold vs sell tomato", config={})
    assert result is not None
    assert result["live_model"] is False
    assert "file_data" in result


def test_conversation_context_persists_across_turns():
    """Test that agricultural conversation context persists across multiple turns."""
    conv_id = "test-conv-123"
    
    # First turn: query high-risk tomatoes
    result1 = run_pipeline(
        "Find all extremely high-risk tomato batches",
        analytics=StubAnalytics(),
        conversation_id=conv_id,
    )
    assert result1["conversation_id"] == conv_id
    assert result1["intent"] == "spoilage"
    assert result1["evidence"]["crop"] == "Tomato"
    
    # Check context was created and populated
    ctx = agri_context_store.get(conv_id)
    assert ctx is not None
    assert ctx.intent == "spoilage"
    assert ctx.crop == "Tomato"
    assert len(ctx.batch_codes) > 0  # Should have extracted batch codes
    msg_count_after_first = ctx.message_count
    
    # Second turn: follow-up "So where should I sell them?"
    result2 = run_pipeline(
        "So where should I sell them?",
        analytics=StubAnalytics(),
        conversation_id=conv_id,
    )
    assert result2["conversation_id"] == conv_id
    # Follow-up should inherit the previous intent
    assert result2["intent"] == "spoilage"
    assert result2["evidence"]["crop"] == "Tomato"
    
    # Context should be updated with new data
    ctx = agri_context_store.get(conv_id)
    assert ctx.message_count > msg_count_after_first  # Should have incremented
    assert len(ctx.candidate_markets) > 0  # Should have markets from finance
    assert ctx.risk_level == "high_risk"


def test_followup_classify_intent_uses_context():
    """Test that follow-up queries use context for intent classification."""
    ctx = AgriContext(conversation_id="test-followup", intent="spoilage", crop="Tomato")
    
    # Without context, this would be INTENT_GENERAL
    assert classify_intent("So where should I sell them?") == "general"
    
    # With context, it should use the previous intent
    assert classify_intent("So where should I sell them?", ctx) == "spoilage"
    assert classify_intent("Where to dispatch them?", ctx) == "spoilage"
    assert classify_intent("What about Mumbai market?", ctx) == "spoilage"
    assert classify_intent("Compare markets for them", ctx) == "spoilage"


def test_new_query_overrides_context():
    """Test that explicit new queries override context."""
    ctx = AgriContext(conversation_id="test-override", intent="spoilage", crop="Tomato")
    
    # Explicit new intent should win
    assert classify_intent("Which market gives best net profit for onions?", ctx) == "net_profit"
    assert classify_intent("Show onion inventory", ctx) == "inventory"
    assert classify_intent("Hold vs sell potatoes", ctx) == "hold_vs_sell"


def test_agri_context_store_crud():
    """Test basic CRUD operations on AgriContextStore."""
    store = agri_context_store
    
    # Create
    ctx = store.create("test-crud-1")
    assert ctx.conversation_id == "test-crud-1"
    assert ctx.intent is None
    
    # Update
    ctx = store.update("test-crud-1", intent="market_selection", crop="Onion")
    assert ctx.intent == "market_selection"
    assert ctx.crop == "Onion"
    
    # Get
    ctx = store.get("test-crud-1")
    assert ctx.intent == "market_selection"
    assert ctx.crop == "Onion"
    
    # Append batch codes
    ctx = store.append_batch_codes("test-crud-1", ["BAT-1", "BAT-2"])
    assert ctx.batch_codes == ["BAT-1", "BAT-2"]
    
    # Append batch IDs
    ctx = store.append_batch_ids("test-crud-1", ["id-1", "id-2"])
    assert ctx.batch_ids == ["id-1", "id-2"]
    
    # Delete
    assert store.delete("test-crud-1") is True
    assert store.get("test-crud-1") is None
    assert store.delete("test-crud-1") is False


def test_context_expiry():
    """Test that expired contexts are cleaned up."""
    store = agri_context_store
    
    # Create context with old timestamp
    ctx = store.create("test-expiry")
    # Manually set old timestamp
    import time
    ctx.updated_at = time.time() - 3600  # 1 hour ago (older than 30 min TTL)
    store._save_all({"test-expiry": ctx})
    
    # Should return None for expired context
    assert store.get("test-expiry") is None
    
    # Clean up
    store.delete("test-expiry")
