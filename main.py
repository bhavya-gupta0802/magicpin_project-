from typing import Any, Dict, Optional
from datetime import datetime, timezone
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bot.context_store import ContextStore
from bot.decision_engine import DecisionEngine
from bot.reply_engine import ReplyEngine


# =========================================================
# Application
# =========================================================

app = FastAPI(
    title="Vera AI Challenge Bot",
    version="1.0.0",
    description="AI message engine for the magicpin Vera Challenge",
)


# =========================================================
# Global state
# =========================================================

context_store = ContextStore()

decision_engine = DecisionEngine(
    context_store
)

reply_engine = ReplyEngine()

START_TIME = time.time()

SUBMITTED_AT = datetime.now(
    timezone.utc
).isoformat()


# =========================================================
# Request Models
# =========================================================

class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str]


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: Optional[str] = None
    turn_number: int


# =========================================================
# GET /v1/healthz
# =========================================================

@app.get("/v1/healthz")
def healthz():

    uptime_seconds = int(
        time.time() - START_TIME
    )

    return {
        "status": "ok",
        "uptime_seconds": uptime_seconds,
        "contexts_loaded": context_store.count_by_scope(),
    }


# =========================================================
# GET /v1/metadata
# =========================================================

@app.get("/v1/metadata")
def metadata():

    return {
        "team_name": "Bhavya Gupta",
        "team_members": [
            "Bhavya Gupta"
        ],
        "model": "deterministic-rule-engine",
        "approach": (
            "deterministic context-aware message composer "
            "with trigger-based dispatch and stateful reply handling"
        ),
        "contact_email": "",
        "version": "1.0.0",
        "submitted_at": SUBMITTED_AT,
    }


# =========================================================
# POST /v1/context
# =========================================================

@app.post("/v1/context")
def receive_context(
    request: ContextRequest
):

    result, stored = context_store.save(
        scope=request.scope,
        context_id=request.context_id,
        version=request.version,
        payload=request.payload,
        delivered_at=request.delivered_at,
    )

    # -----------------------------------------------------
    # Same or older version
    # -----------------------------------------------------

    if result == "stale":

        return JSONResponse(
            status_code=409,
            content={
                "accepted": False,
                "reason": "stale_version",
                "current_version": stored["version"],
            },
        )

    # -----------------------------------------------------
    # New or higher version
    # -----------------------------------------------------

    return {
        "accepted": True,
        "ack_id": (
            f"ack_{request.context_id}_v"
            f"{request.version}"
        ),
        "stored_at": (
            request.delivered_at
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }


# =========================================================
# POST /v1/tick
# =========================================================

@app.post("/v1/tick")
def tick(
    request: TickRequest
):

    actions = []

    # -----------------------------------------------------
    # Evaluate triggers in judge-supplied order
    #
    # Challenge cap = 20 actions per tick
    # -----------------------------------------------------

    for trigger_id in request.available_triggers:

        # -------------------------------------------------
        # Stop once the challenge action cap is reached
        # -------------------------------------------------

        if len(actions) >= 20:
            break

        action = decision_engine.decide(
            trigger_id=trigger_id,
            now=request.now,
        )

        if action is None:
            continue

        # -------------------------------------------------
        # Prevent messaging conversations that were
        # explicitly ended through /v1/reply
        # -------------------------------------------------

        conversation_id = action.get(
            "conversation_id"
        )

        if (
            conversation_id
            and reply_engine.is_ended(
                conversation_id
            )
        ):
            continue

        # -------------------------------------------------
        # Add valid action
        # -------------------------------------------------

        actions.append(action)

    return {
        "actions": actions
    }


# =========================================================
# POST /v1/reply
# =========================================================

@app.post("/v1/reply")
def reply(
    request: ReplyRequest
):

    # -----------------------------------------------------
    # Delegate conversational state handling to ReplyEngine
    # -----------------------------------------------------

    result = reply_engine.handle_reply(
        conversation_id=request.conversation_id,
        merchant_id=request.merchant_id,
        customer_id=request.customer_id,
        message=request.message,
        turn_number=request.turn_number,
    )

    return result


# =========================================================
# Root endpoint
# =========================================================

@app.get("/")
def root():

    return {
        "service": "Vera AI Challenge Bot",
        "status": "running",
        "endpoints": [
            "/v1/healthz",
            "/v1/metadata",
            "/v1/context",
            "/v1/tick",
            "/v1/reply",
        ],
    }