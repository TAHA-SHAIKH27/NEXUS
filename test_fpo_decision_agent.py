"""Pipeline tests for FPO decision intelligence. Analytics and models are injected."""

from backend.tools.fpo_decision_agent import (
    calculate_finance,
    classify_intent,
    handle_fpo_decision_command,
    run_pipeline,
    validate_reasoning,
)
from backend.tools.agri_context import (
    AgriContextStore,
    AgriConversation,
    create_conversation_id,
    get_context_for_prompt,
    get_context_store,
)


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
    # Build evidence_package with KEY_NUMBERS_TO_QUOTE from finance
    evidence_package = {"KEY_NUMBERS_TO_QUOTE": finance}
    checked = validate_reasoning("Sell for 999999 rupees on 3 kg", {"KEY_NUMBERS_TO_QUOTE": finance})
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
    store = get_context_store()
    store.clear(conv_id)  # Clean start
    
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
    ctx = store.get(conv_id)
    assert ctx is not None
    assert ctx.current_intent == "spoilage"
    assert ctx.current_crop == "Tomato"
    assert len(ctx.current_batch_codes) > 0  # Should have extracted batch codes
    
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
    ctx = store.get(conv_id)
    assert len(ctx.turns) == 2  # Should have two turns
    assert len(ctx.last_markets) > 0  # Should have markets from finance
    assert ctx.last_recommendation is not None
    assert ctx.last_recommendation.get("spoilage_risk_level") == "high_risk"


def test_followup_classify_intent_uses_context():
    """Test that follow-up queries use context for intent classification."""
    store = get_context_store()
    conv_id = "test-followup"
    store.clear(conv_id)
    
    # Create a context with previous intent
    conv = store.get_or_create(conv_id)
    conv.current_intent = "spoilage"
    conv.current_crop = "Tomato"
    conv.updated_at = datetime.now(timezone.utc).isoformat()
    store._save()
    
    context = get_context_for_prompt(conv_id, "So where should I sell them?")
    
    # Without context, this would be INTENT_GENERAL
    assert classify_intent("So where should I sell them?") == "general"
    
    # With context, it should use the previous intent
    assert classify_intent("So where should I sell them?", context) == "spoilage"
    assert classify_intent("Where to dispatch them?", context) == "spoilage"
    assert classify_intent("What about Mumbai market?", context) == "spoilage"
    assert classify_intent("Compare markets for them", context) == "spoilage"


from datetime import datetime, timezone

def test_new_query_overrides_context():
    """Test that explicit new queries override context."""
    store = get_context_store()
    conv_id = "test-override"
    store.clear(conv_id)
    
    # Create a context with previous intent
    conv = store.get_or_create(conv_id)
    conv.current_intent = "spoilage"
    conv.current_crop = "Tomato"
    conv.updated_at = datetime.now(timezone.utc).isoformat()
    store._save()
    
    context = get_context_for_prompt(conv_id, "Which market gives best net profit for onions?")
    
    # Explicit new intent should win
    assert classify_intent("Which market gives best net profit for onions?", context) == "net_profit"
    assert classify_intent("Show onion inventory", context) == "inventory"
    assert classify_intent("Hold vs sell potatoes", context) == "hold_vs_sell"


def test_agri_context_store_crud():
    """Test basic CRUD operations on AgriContextStore."""
    store = get_context_store()
    
    # Create
    conv_id = "test-crud-1"
    store.clear(conv_id)
    ctx = store.get_or_create(conv_id)
    assert ctx.conversation_id == "test-crud-1"
    assert ctx.current_intent is None
    
    # Update
    ctx = store.add_turn(conv_id, type("Turn", (), {
        "turn_id": "t1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_prompt": "test",
        "intent": "market_selection",
        "crop": "Onion",
        "batch_codes": [],
        "batch_ids": [],
        "quantities_kg": {},
        "markets_considered": [],
        "recommended_action": None,
        "recommended_market": None,
        "estimated_net_inr": None,
        "evidence_sources": [],
        "warnings": [],
        "finance_snapshot": None,
    })())
    # Note: The new API doesn't have direct update method, it uses add_turn
    # For direct updates, we modify the conversation object
    ctx.current_intent = "market_selection"
    ctx.current_crop = "Onion"
    store._save()
    
    # Get
    ctx = store.get(conv_id)
    assert ctx.current_intent == "market_selection"
    assert ctx.current_crop == "Onion"
    
    # Test batch codes through turn
    turn = type("Turn", (), {
        "turn_id": "t2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_prompt": "test",
        "intent": "market_selection",
        "crop": "Onion",
        "batch_codes": ["BAT-1", "BAT-2"],
        "batch_ids": ["id-1", "id-2"],
        "quantities_kg": {},
        "markets_considered": [],
        "recommended_action": None,
        "recommended_market": None,
        "estimated_net_inr": None,
        "evidence_sources": [],
        "warnings": [],
        "finance_snapshot": None,
    })()
    ctx = store.add_turn(conv_id, turn)
    assert ctx.current_batch_codes == ["BAT-1", "BAT-2"]
    assert ctx.current_batch_ids == ["id-1", "id-2"]
    
    # Delete
    assert store.clear(conv_id) is True
    assert store.get(conv_id) is None
    assert store.clear(conv_id) is False


def test_context_expiry():
    """Test that contexts can be manually cleared."""
    store = get_context_store()
    
    # Create context
    store.clear("test-expiry")
    ctx = store.get_or_create("test-expiry")
    assert ctx.conversation_id == "test-expiry"
    
    # Delete it
    assert store.clear("test-expiry") is True
    assert store.get("test-expiry") is None
    
    # Double delete should return False
    assert store.clear("test-expiry") is False
