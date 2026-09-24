import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.agent import generate_reply
from app.config import get_settings
from app.dispatch import handle_inbound, send_instagram_text
from app.instagram import extract_inbound_messages, signature_is_valid, verification_challenge
from app.memory import init_db, recent_messages, recent_outbox, save_outbox

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Instagram AI", lifespan=lifespan)


class ReplyRequest(BaseModel):
    sender_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class SendRequest(BaseModel):
    recipient_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "n8n_configured": bool(settings.n8n_webhook_url),
        "model_configured": bool(settings.openai_api_key),
        "instagram_configured": bool(settings.ig_access_token and settings.ig_user_id),
    }


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    challenge = verification_challenge(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        return PlainTextResponse("forbidden", status_code=403)
    return PlainTextResponse(challenge)


@app.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not signature_is_valid(body, request.headers.get("x-hub-signature-256")):
        return JSONResponse({"error": "invalid signature"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    messages = extract_inbound_messages(payload if isinstance(payload, dict) else {})
    for message in messages:
        background.add_task(handle_inbound, message)
    log.info("Webhook alındı, işlenecek mesaj: %s", len(messages))
    return {"status": "ok", "accepted": len(messages)}


@app.post("/v1/reply")
async def reply(body: ReplyRequest) -> dict:
    text = await generate_reply(body.sender_id, body.text.strip())
    return {"sender_id": body.sender_id, "reply": text}


@app.post("/v1/send")
async def send(body: SendRequest):
    text = body.text.strip()
    try:
        result = await send_instagram_text(body.recipient_id, text)
    except RuntimeError:
        save_outbox(body.recipient_id, text, "local")
        return {
            "delivered": False,
            "mode": "local",
            "recipient_id": body.recipient_id,
            "text": text,
        }
    save_outbox(body.recipient_id, text, "instagram")
    return {"delivered": True, "mode": "instagram", "result": result}


@app.get("/v1/outbox")
async def outbox() -> dict:
    return {"messages": recent_outbox()}


@app.get("/v1/conversations/{sender_id}")
async def conversation(sender_id: str) -> dict:
    settings = get_settings()
    return {
        "sender_id": sender_id,
        "messages": recent_messages(sender_id, settings.history_limit),
    }
