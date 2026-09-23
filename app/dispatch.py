import logging

import httpx

from app.agent import generate_reply
from app.config import get_settings
from app.instagram import InboundMessage
from app.memory import claim_message, release_message

log = logging.getLogger(__name__)


async def post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()


async def send_instagram_text(recipient_id: str, text: str) -> dict:
    settings = get_settings()
    if not settings.ig_access_token or not settings.ig_user_id:
        raise RuntimeError("IG_ACCESS_TOKEN ve IG_USER_ID tanımlı değil")

    url = (
        f"{settings.graph_base_url.rstrip('/')}/"
        f"{settings.graph_api_version}/{settings.ig_user_id}/messages"
    )
    headers = {"Authorization": f"Bearer {settings.ig_access_token}"}
    body = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    return await post_json(url, body, headers)


async def handle_inbound(message: InboundMessage) -> None:
    if not claim_message(message.message_id):
        log.info("Yinelenen mesaj atlandı: %s", message.message_id)
        return

    try:
        settings = get_settings()
        if settings.n8n_webhook_url:
            await post_json(settings.n8n_webhook_url, message.as_dict())
            log.info("Mesaj n8n akışına iletildi: %s", message.message_id)
            return

        reply = await generate_reply(message.sender_id, message.text)
        try:
            await send_instagram_text(message.sender_id, reply)
            log.info("Yanıt Instagram'a gönderildi: %s", message.message_id)
        except RuntimeError:
            log.info("Token yok, yanıt yalnızca yerel geçmişe yazıldı: %s", reply)
    except Exception:
        release_message(message.message_id)
        log.exception("Mesaj işlenemedi: %s", message.message_id)
