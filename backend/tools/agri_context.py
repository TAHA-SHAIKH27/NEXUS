"""
Agricultural Conversation Context — Session-scoped memory for FPO multi-turn queries.

Retains crop, batches, intent, evidence, and previous recommendations across turns.
Isolated per conversation ID. Never blindly reuses expired market prices or forecasts.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
CONTEXT_FILE = DATA_DIR / "agri_conversation_context.json"

_lock = threading.RLock()


@dataclass
class AgriTurn:
    """Single turn in an agricultural conversation."""
    turn_id: str
    timestamp: str
    user_prompt: str
    intent: str
    crop: Optional[str] = None
    batch_codes: List[str] = field(default_factory=list)
    batch_ids: List[str] = field(default_factory=list)
    quantities_kg: Dict[str, float] = field(default_factory=dict)
    markets_considered: List[str] = field(default_factory=list)
    recommended_action: Optional[str] = None
    recommended_market: Optional[str] = None
    estimated_net_inr: Optional[float] = None
    evidence_sources: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    finance_snapshot: Optional[Dict[str, Any]] = None


@dataclass
class AgriConversation:
    """Full agricultural conversation context."""
    conversation_id: str
    created_at: str
    updated_at: str
    turns: List[AgriTurn] = field(default_factory=list)
    current_crop: Optional[str] = None
    current_batch_codes: List[str] = field(default_factory=list)
    current_batch_ids: List[str] = field(default_factory=list)
    current_quantities_kg: Dict[str, float] = field(default_factory=dict)
    current_intent: Optional[str] = None
    last_recommendation: Optional[Dict[str, Any]] = None
    last_finance: Optional[Dict[str, Any]] = None
    last_evidence_sources: List[Dict[str, Any]] = field(default_factory=list)
    last_markets: List[str] = field(default_factory=list)


class AgriContextStore:
    """Thread-safe conversation context store."""

    def __init__(self, path: str | None = None):
        self._path = path or str(CONTEXT_FILE)
        self._conversations: Dict[str, AgriConversation] = {}
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for conv_id, conv_data in data.items():
                        turns = []
                        for t in conv_data.get("turns", []):
                            turns.append(AgriTurn(**t))
                        conv_data["turns"] = turns
                        self._conversations[conv_id] = AgriConversation(**conv_data)
        except Exception:
            self._conversations = {}

    def _save(self) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                # Convert dataclasses to dict for JSON serialization
                serializable = {}
                for conv_id, conv in self._conversations.items():
                    conv_dict = self._conv_to_dict(conv)
                    serializable[conv_id] = conv_dict
                json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)
                f.flush()
            os.replace(tmp, self._path)
        except Exception:
            pass

    def _conv_to_dict(self, conv: AgriConversation) -> Dict[str, Any]:
        """Convert AgriConversation to dict for JSON serialization."""
        return {
            "conversation_id": conv.conversation_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "turns": [self._turn_to_dict(t) for t in conv.turns],
            "current_crop": conv.current_crop,
            "current_batch_codes": conv.current_batch_codes,
            "current_batch_ids": conv.current_batch_ids,
            "current_quantities_kg": conv.current_quantities_kg,
            "current_intent": conv.current_intent,
            "last_recommendation": conv.last_recommendation,
            "last_finance": conv.last_finance,
            "last_evidence_sources": conv.last_evidence_sources,
            "last_markets": conv.last_markets,
        }

    def _turn_to_dict(self, turn: AgriTurn) -> Dict[str, Any]:
        """Convert AgriTurn to dict for JSON serialization."""
        return {
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp,
            "user_prompt": turn.user_prompt,
            "intent": turn.intent,
            "crop": turn.crop,
            "batch_codes": turn.batch_codes,
            "batch_ids": turn.batch_ids,
            "quantities_kg": turn.quantities_kg,
            "markets_considered": turn.markets_considered,
            "recommended_action": turn.recommended_action,
            "recommended_market": turn.recommended_market,
            "estimated_net_inr": turn.estimated_net_inr,
            "evidence_sources": turn.evidence_sources,
            "warnings": turn.warnings,
            "finance_snapshot": turn.finance_snapshot,
        }

    def get_or_create(self, conversation_id: str) -> AgriConversation:
        with _lock:
            if conversation_id not in self._conversations:
                now = datetime.now(timezone.utc).isoformat()
                self._conversations[conversation_id] = AgriConversation(
                    conversation_id=conversation_id,
                    created_at=now,
                    updated_at=now,
                )
                self._save()
            return self._conversations[conversation_id]

    def add_turn(self, conversation_id: str, turn: AgriTurn) -> AgriConversation:
        with _lock:
            conv = self.get_or_create(conversation_id)
            conv.turns.append(turn)
            conv.updated_at = datetime.now(timezone.utc).isoformat()
            # Keep last 20 turns
            conv.turns = conv.turns[-20:]
            # Update current context from latest turn
            if turn.crop:
                conv.current_crop = turn.crop
            if turn.batch_codes:
                conv.current_batch_codes = turn.batch_codes
            if turn.batch_ids:
                conv.current_batch_ids = turn.batch_ids
            if turn.quantities_kg:
                conv.current_quantities_kg = turn.quantities_kg
            if turn.intent:
                conv.current_intent = turn.intent
            if turn.recommended_action:
                conv.last_recommendation = {
                    "action": turn.recommended_action,
                    "market": turn.recommended_market,
                    "net_inr": turn.estimated_net_inr,
                    "spoilage_risk_level": turn.finance_snapshot.get("spoilage_risk_level") if turn.finance_snapshot else None,
                    "days_until_quality_window_end": turn.finance_snapshot.get("days_until_quality_window_end") if turn.finance_snapshot else None,
                    "timestamp": turn.timestamp,
                }
            if turn.finance_snapshot:
                conv.last_finance = turn.finance_snapshot
            if turn.evidence_sources:
                conv.last_evidence_sources = turn.evidence_sources
            if turn.markets_considered:
                conv.last_markets = turn.markets_considered
            self._save()
            return conv

    def get_context_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get a compact summary for prompt injection."""
        with _lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return {}
            return {
                "conversation_id": conversation_id,
                "current_crop": conv.current_crop,
                "current_batch_codes": conv.current_batch_codes,
                "current_batch_ids": conv.current_batch_ids,
                "current_quantities_kg": conv.current_quantities_kg,
                "current_intent": conv.current_intent,
                "last_recommendation": conv.last_recommendation,
                "last_markets": conv.last_markets,
                "turn_count": len(conv.turns),
                "last_turn": asdict(conv.turns[-1]) if conv.turns else None,
            }

    def clear(self, conversation_id: str) -> bool:
        with _lock:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
                self._save()
                return True
            return False

    def get(self, conversation_id: str) -> Optional[AgriConversation]:
        """Get conversation by ID, or None if not found."""
        with _lock:
            return self._conversations.get(conversation_id)

    def list_conversations(self) -> List[str]:
        with _lock:
            return list(self._conversations.keys())


# Global store instance
_context_store = AgriContextStore()


def get_context_store() -> AgriContextStore:
    return _context_store


def create_conversation_id() -> str:
    """Generate a new conversation ID."""
    return f"agri_{uuid.uuid4().hex[:12]}"


def extract_batch_info_from_evidence(evidence: Dict[str, Any]) -> tuple[List[str], List[str], Dict[str, float]]:
    """Extract batch codes, batch IDs, and quantities from evidence."""
    batch_codes = []
    batch_ids = []
    quantities = {}

    # From Zetaris results
    for result in evidence.get("zetaris_results", []):
        for row in result.get("rows", []):
            if isinstance(row, dict):
                code = row.get("batch_code")
                bid = row.get("batch_id")
                qty = row.get("net_available_kg")
                if code:
                    batch_codes.append(code)
                if bid:
                    batch_ids.append(bid)
                if code and qty is not None:
                    try:
                        quantities[code] = float(qty)
                    except Exception:
                        pass

    # From fpo_analytics fallback
    data = evidence.get("data", {})
    for key in ("risks", "inventory", "zetaris_inventory", "zetaris_data"):
        items = data.get(key)
        if isinstance(items, list):
            for row in items:
                if isinstance(row, dict):
                    code = row.get("batch_code")
                    bid = row.get("batch_id")
                    qty = row.get("net_available_kg")
                    if code:
                        batch_codes.append(code)
                    if bid:
                        batch_ids.append(bid)
                    if code and qty is not None:
                        try:
                            quantities[code] = float(qty)
                        except Exception:
                            pass
        # Also check for nested critical_batches in risks
        if key == "risks" and isinstance(items, dict):
            critical_batches = items.get("critical_batches", [])
            for row in critical_batches:
                if isinstance(row, dict):
                    code = row.get("batch_code")
                    bid = row.get("batch_id")
                    qty = row.get("net_available_kg")
                    if code:
                        batch_codes.append(code)
                    if bid:
                        batch_ids.append(bid)
                    if code and qty is not None:
                        try:
                            quantities[code] = float(qty)
                        except Exception:
                            pass

    return list(dict.fromkeys(batch_codes)), list(dict.fromkeys(batch_ids)), quantities


def build_turn_from_pipeline(
    prompt: str,
    pipeline_result: Dict[str, Any],
    conversation_id: str,
) -> AgriTurn:
    """Build an AgriTurn from a completed pipeline result."""
    evidence = pipeline_result.get("evidence", {})
    finance = pipeline_result.get("finance", {})
    recommendation = pipeline_result.get("recommendation", {})

    batch_codes, batch_ids, quantities = extract_batch_info_from_evidence(evidence)

    return AgriTurn(
        turn_id=f"turn_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_prompt=prompt,
        intent=pipeline_result.get("intent", "unknown"),
        crop=evidence.get("crop"),
        batch_codes=batch_codes,
        batch_ids=batch_ids,
        quantities_kg=quantities,
        markets_considered=[m.get("market_name") for m in finance.get("markets_ranked", []) if m.get("market_name")],
        recommended_action=finance.get("recommended_action"),
        recommended_market=recommendation.get("best_market", {}).get("market_name") if recommendation.get("best_market") else None,
        estimated_net_inr=finance.get("sell_now", {}).get("estimated_net_inr") if finance.get("sell_now") else None,
        evidence_sources=evidence.get("sources", []),
        warnings=evidence.get("warnings", []) + finance.get("warnings", []),
        finance_snapshot={
            "quantity_kg_at_risk": finance.get("quantity_kg_at_risk"),
            "markets_ranked": finance.get("markets_ranked", [])[:3],
            "cheapest_route": finance.get("cheapest_route"),
            "sell_now": finance.get("sell_now"),
            "hold_proxy": finance.get("hold_proxy"),
            "price_spread_per_kg_inr": finance.get("price_spread_per_kg_inr"),
            "days_until_quality_window_end": finance.get("days_until_quality_window_end"),
            "spoilage_risk_level": finance.get("spoilage_risk_level"),
        },
    )


def get_context_for_prompt(conversation_id: str, prompt: str) -> Dict[str, Any]:
    """Get relevant context for a new prompt, including follow-up detection."""
    store = get_context_store()
    conv = store.get_or_create(conversation_id)
    summary = store.get_context_summary(conversation_id)

    # Detect follow-up by checking if prompt references previous context
    is_followup = False
    followup_indicators = ["so", "then", "them", "those", "it", "where should", "what about", "compare"]
    prompt_lower = prompt.lower()
    # Follow-up if prompt has indicators AND (has turns OR has previous intent/crop)
    has_previous_context = bool(conv.turns or conv.current_intent or conv.current_crop)
    if any(ind in prompt_lower for ind in followup_indicators) and has_previous_context:
        is_followup = True

    return {
        "conversation_id": conversation_id,
        "is_followup": is_followup,
        "previous_crop": conv.current_crop,
        "previous_batch_codes": conv.current_batch_codes,
        "previous_batch_ids": conv.current_batch_ids,
        "previous_quantities_kg": conv.current_quantities_kg,
        "previous_intent": conv.current_intent,
        "previous_recommendation": conv.last_recommendation,
        "previous_markets": conv.last_markets,
        "turn_count": summary.get("turn_count", 0),
    }


def resolve_followup_entities(
    prompt: str,
    context: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve ambiguous references in follow-up questions using conversation context."""
    prompt_lower = prompt.lower()

    # If follow-up asks "where should I sell them" or similar, use previous crop/batches
    if any(k in prompt_lower for k in ("where should i sell", "where to sell", "sell them", "dispatch them")):
        if context.get("previous_crop") and not evidence.get("crop"):
            evidence["crop"] = context["previous_crop"]
        if context.get("previous_batch_codes") and not evidence.get("batch_codes"):
            evidence["batch_codes"] = context["previous_batch_codes"]
        if context.get("previous_batch_ids") and not evidence.get("batch_ids"):
            evidence["batch_ids"] = context["previous_batch_ids"]

    # If follow-up asks "compare X vs Y", preserve previous context
    if "compare" in prompt_lower:
        if context.get("previous_crop") and not evidence.get("crop"):
            evidence["crop"] = context["previous_crop"]

    return evidence