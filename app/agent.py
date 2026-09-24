import logging

import httpx

from app.config import get_settings
from app.memory import add_message, recent_messages

log = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Merhaba, mesajını aldım. Yapay zeka anahtarı henüz bağlı değil; "
    "bu otomatik bir test yanıtı."
)


def load_system_prompt() -> str:
    settings = get_settings()
    path = settings.resolve_path(settings.system_prompt_path)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return "Gelen Instagram mesajına kısa ve nazik bir Türkçe yanıt ver."


async def generate_reply(sender_id: str, text: str) -> str:
    settings = get_settings()
    history = recent_messages(sender_id, settings.history_limit)
    add_message(sender_id, "user", text)

    reply = await _complete(history + [{"role": "user", "content": text}])
    add_message(sender_id, "assistant", reply)
    return reply


async def _complete(history: list[dict[str, str]]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return FALLBACK_REPLY

    payload = {
        "model": settings.openai_model,
        "temperature": 0.4,
        "max_tokens": 800,
        "messages": [{"role": "system", "content": load_system_prompt()}, *history],
    }
    if "gpt-oss" in settings.openai_model:
        payload["reasoning_effort"] = "low"
    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            content = message.get("content")
    except httpx.HTTPStatusError as error:
        log.error("Model isteği başarısız: %s %s", error.response.status_code, error.response.text[:300])
        return "Mesajını aldım. Şu an yanıt üretemiyorum, kısa süre içinde tekrar yazarım."
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        log.exception("Yanıt üretilemedi")
        return "Mesajını aldım. Şu an yanıt üretemiyorum, kısa süre içinde tekrar yazarım."

    cleaned = (content or "").strip()
    return cleaned or FALLBACK_REPLY
