"""
Agricultural Conversation Context — Session-scoped structured task context for FPO queries.

Stores:
- Current agricultural intent
- Crop
- Selected batch IDs
- Origin locations
- Risk category
- Candidate markets
- Retrieved evidence references
- Pending decisions
- Previous results

Uses conversation IDs and enforces session isolation. Never blindly reuses expired market prices or forecasts.
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
AGRI_CONTEXT_FILE = DATA_DIR / "agri_conversation_context.json"

_lock = threading.Lock()
_contexts: Dict[str, Dict[str, Any]] = {}

# Context TTL: 30 minutes of inactivity
CONTEXT_TTL_SECONDS = 30 * 60
MAX_CONTEXTS = 50


def _load():
    global _contexts
    try:
        if AGRI_CONTEXT_FILE.exists():
            with open(AGRI_CONTEXT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _contexts = data if isinstance(data, dict) else {}
            # Clean expired contexts
            now = time.time()
            _contexts = {
                cid: ctx for cid, ctx in _contexts.items()
                if now - ctx.get("updated_at", 0) < CONTEXT_TTL_SECONDS
            }
        else:
            _contexts = {}
    except Exception:
        _contexts = {}


def _save():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = str(AGRI_CONTEXT_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_contexts, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, str(AGRI_CONTEXT_FILE))
    except Exception:
        pass


_load()


@dataclass
class AgriContext:
    """Structured agricultural conversation context."""
    conversation_id: str
    intent: Optional[str] = None
    crop: Optional[str] = None
    batch_codes: List[str] = field(default_factory=list)
    batch_ids: List[str] = field(default_factory=list)
    origin_locations: List[str] = field(default_factory=list)  # warehouse names/districts
    risk_level: Optional[str] = None
    candidate_markets: List[str] = field(default_factory=list)
    evidence_references: List[Dict[str, Any]] = field(default_factory=list)
    finance_results: Optional[Dict[str, Any]] = None
    recommendation: Optional[Dict[str, Any]] = None
    pending_decision: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgriContext":
        return cls(**data)

    def is_expired(self) -> bool:
        return (time.time() - self.updated_at) > CONTEXT_TTL_SECONDS

    def update_activity(self):
        self.updated_at = time.time()
        self.message_count += 1


class AgriContextStore:
    """File-backed agricultural conversation context store."""

    def __init__(self):
        self._lock = threading.Lock()

    def _load_all(self) -> Dict[str, AgriContext]:
        with self._lock:
            result = {}
            for cid, data in _contexts.items():
                try:
                    result[cid] = AgriContext.from_dict(data)
                except Exception:
                    continue
            return result

    def _save_all(self, contexts: Dict[str, AgriContext]):
        with self._lock:
            global _contexts
            _contexts = {cid: ctx.to_dict() for cid, ctx in contexts.items()}
            _save()

    def get(self, conversation_id: str) -> Optional[AgriContext]:
        """Get context by conversation ID, returns None if not found or expired."""
        contexts = self._load_all()
        ctx = contexts.get(conversation_id)
        if ctx and not ctx.is_expired():
            return ctx
        elif ctx:
            # Remove expired
            del contexts[conversation_id]
            self._save_all(contexts)
        return None

    def create(self, conversation_id: Optional[str] = None) -> AgriContext:
        """Create a new agricultural context."""
        cid = conversation_id or str(uuid.uuid4())[:12]
        ctx = AgriContext(conversation_id=cid)
        contexts = self._load_all()
        # Enforce max contexts
        if len(contexts) >= MAX_CONTEXTS:
            # Remove oldest
            oldest = min(contexts.items(), key=lambda x: x[1].updated_at)
            del contexts[oldest[0]]
        contexts[cid] = ctx
        self._save_all(contexts)
        return ctx

    def update(self, conversation_id: str, **updates) -> Optional[AgriContext]:
        """Update context fields."""
        contexts = self._load_all()
        ctx = contexts.get(conversation_id)
        if not ctx:
            return None
        if ctx.is_expired():
            del contexts[conversation_id]
            self._save_all(contexts)
            return None

        for key, value in updates.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)
        ctx.update_activity()
        self._save_all(contexts)
        return ctx

    def append_batch_codes(self, conversation_id: str, batch_codes: List[str]) -> Optional[AgriContext]:
        """Append batch codes to context."""
        ctx = self.get(conversation_id)
        if not ctx:
            return None
        for code in batch_codes:
            if code not in ctx.batch_codes:
                ctx.batch_codes.append(code)
        return self.update(conversation_id, batch_codes=ctx.batch_codes)

    def append_batch_ids(self, conversation_id: str, batch_ids: List[str]) -> Optional[AgriContext]:
        """Append batch IDs to context."""
        ctx = self.get(conversation_id)
        if not ctx:
            return None
        for bid in batch_ids:
            if bid not in ctx.batch_ids:
                ctx.batch_ids.append(bid)
        return self.update(conversation_id, batch_ids=ctx.batch_ids)

    def set_intent(self, conversation_id: str, intent: str) -> Optional[AgriContext]:
        return self.update(conversation_id, intent=intent)

    def set_crop(self, conversation_id: str, crop: str) -> Optional[AgriContext]:
        return self.update(conversation_id, crop=crop)

    def set_evidence(self, conversation_id: str, evidence: List[Dict[str, Any]]) -> Optional[AgriContext]:
        return self.update(conversation_id, evidence_references=evidence)

    def set_finance(self, conversation_id: str, finance: Dict[str, Any]) -> Optional[AgriContext]:
        return self.update(conversation_id, finance_results=finance)

    def set_recommendation(self, conversation_id: str, recommendation: Dict[str, Any]) -> Optional[AgriContext]:
        return self.update(conversation_id, recommendation=recommendation)

    def set_candidate_markets(self, conversation_id: str, markets: List[str]) -> Optional[AgriContext]:
        return self.update(conversation_id, candidate_markets=markets)

    def set_risk_level(self, conversation_id: str, risk: str) -> Optional[AgriContext]:
        return self.update(conversation_id, risk_level=risk)

    def set_origin_locations(self, conversation_id: str, locations: List[str]) -> Optional[AgriContext]:
        return self.update(conversation_id, origin_locations=locations)

    def delete(self, conversation_id: str) -> bool:
        contexts = self._load_all()
        if conversation_id in contexts:
            del contexts[conversation_id]
            self._save_all(contexts)
            return True
        return False

    def clear_expired(self) -> int:
        """Remove all expired contexts. Returns count removed."""
        contexts = self._load_all()
        now = time.time()
        before = len(contexts)
        contexts = {
            cid: ctx for cid, ctx in contexts.items()
            if now - ctx.updated_at < CONTEXT_TTL_SECONDS
        }
        self._save_all(contexts)
        return before - len(contexts)


# Global instance
agri_context_store = AgriContextStore()


def get_or_create_context(conversation_id: Optional[str] = None) -> AgriContext:
    """Get existing context or create new one."""
    if conversation_id:
        ctx = agri_context_store.get(conversation_id)
        if ctx:
            return ctx
    return agri_context_store.create(conversation_id)


def resolve_context_from_prompt(prompt: str, conversation_id: Optional[str] = None) -> AgriContext:
    """
    Resolve agricultural context from prompt and conversation history.
    Uses follow-up detection to preserve context.
    """
    ctx = get_or_create_context(conversation_id)
    
    # Detect follow-up patterns that should preserve context
    prompt_lower = prompt.lower().strip()
    
    follow_up_patterns = [
        r"\b(so|then|where should|where to|what about|how about)\b",
        r"\b(sell them|dispatch them|market for them)\b",
        r"\b(compare|versus|vs\.?)\b",
        r"\b(what if|suppose|if we)\b",
    ]
    
    is_follow_up = any(
        re.search(pattern, prompt_lower) for pattern in follow_up_patterns
    )
    
    # If it's a follow-up and we have context, keep the context
    # If it's a new query with explicit crop/intent, update context
    return ctx


def extract_batch_codes_from_evidence(evidence: Dict[str, Any]) -> List[str]:
    """Extract batch codes from evidence payload."""
    codes = []
    data = evidence.get("data", {})
    
    # From Zetaris results
    for zr in evidence.get("zetaris_results", []):
        for row in zr.get("rows", []):
            code = row.get("batch_code") or row.get("batch_id")
            if code:
                codes.append(str(code))
    
    # From risk centre / inventory
    for batch in data.get("risks", {}).get("critical_batches", []):
        if batch.get("batch_code"):
            codes.append(batch["batch_code"])
    
    for batch in data.get("inventory", {}).get("batches", []):
        if batch.get("batch_code"):
            codes.append(batch["batch_code"])
    
    return list(dict.fromkeys(codes))  # Deduplicate preserving order


def extract_batch_ids_from_evidence(evidence: Dict[str, Any]) -> List[str]:
    """Extract batch IDs from evidence payload."""
    ids = []
    data = evidence.get("data", {})
    
    for zr in evidence.get("zetaris_results", []):
        for row in zr.get("rows", []):
            bid = row.get("batch_id")
            if bid:
                ids.append(str(bid))
    
    for batch in data.get("risks", {}).get("critical_batches", []):
        if batch.get("batch_id"):
            ids.append(batch["batch_id"])
    
    for batch in data.get("inventory", {}).get("batches", []):
        if batch.get("batch_id"):
            ids.append(batch["batch_id"])
    
    return list(dict.fromkeys(ids))


def extract_markets_from_finance(finance: Dict[str, Any]) -> List[str]:
    """Extract candidate markets from finance results."""
    markets = []
    for m in finance.get("markets_ranked", []):
        if m.get("market_name"):
            markets.append(m["market_name"])
    return markets


def extract_origin_locations(evidence: Dict[str, Any]) -> List[str]:
    """Extract origin warehouse/district locations from evidence."""
    locations = []
    data = evidence.get("data", {})
    
    # From Zetaris inventory
    for zr in evidence.get("zetaris_results", []):
        for row in zr.get("rows", []):
            for field in ["farm_district", "warehouse_name", "warehouse_id"]:
                val = row.get(field)
                if val and val not in locations:
                    locations.append(str(val))
    
    # From risk centre
    for batch in data.get("risks", {}).get("critical_batches", []):
        for field in ["farm_district", "farm_state"]:
            val = batch.get(field)
            if val and val not in locations:
                locations.append(str(val))
    
    return locations


def build_context_summary(ctx: AgriContext) -> str:
    """Build a human-readable context summary for logging/debugging."""
    parts = [f"Context({ctx.conversation_id[:8]})"]
    if ctx.intent:
        parts.append(f"intent={ctx.intent}")
    if ctx.crop:
        parts.append(f"crop={ctx.crop}")
    if ctx.batch_codes:
        parts.append(f"batches={len(ctx.batch_codes)}")
    if ctx.candidate_markets:
        parts.append(f"markets={len(ctx.candidate_markets)}")
    if ctx.risk_level:
        parts.append(f"risk={ctx.risk_level}")
    return " ".join(parts)