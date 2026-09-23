import hashlib
import hmac
from dataclasses import asdict, dataclass

from app.config import get_settings


@dataclass
class InboundMessage:
    sender_id: str
    recipient_id: str
    text: str
    message_id: str
    timestamp: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def verification_challenge(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    settings = get_settings()
    if mode == "subscribe" and token == settings.verify_token and challenge:
        return challenge
    return None


def signature_is_valid(body: bytes, header: str | None) -> bool:
    secret = get_settings().meta_app_secret
    if not secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def extract_inbound_messages(payload: dict) -> list[InboundMessage]:
    """Metin içeren müşteri mesajlarını ayıklar. Echo ve okundu bilgisi elenir."""
    if payload.get("object") not in (None, "instagram", "page"):
        return []

    messages: list[InboundMessage] = []
    for entry in payload.get("entry") or []:
        for event in entry.get("messaging") or []:
            message = event.get("message") or {}
            if not message:
                continue
            if message.get("is_echo") or message.get("is_self") or message.get("is_deleted"):
                continue
            if message.get("is_unsupported"):
                continue
            text = (message.get("text") or "").strip()
            sender_id = (event.get("sender") or {}).get("id")
            recipient_id = (event.get("recipient") or {}).get("id")
            message_id = message.get("mid")
            if not text or not sender_id or not recipient_id or not message_id:
                continue
            if sender_id == recipient_id:
                continue
            messages.append(
                InboundMessage(
                    sender_id=str(sender_id),
                    recipient_id=str(recipient_id),
                    text=text,
                    message_id=str(message_id),
                    timestamp=event.get("timestamp"),
                )
            )
    return messages
