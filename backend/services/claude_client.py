import anthropic
import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
    reraise=True,
)
async def call_claude(system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
    """Chiama Claude async e restituisce il testo della risposta."""
    client = get_client()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


async def call_claude_json(system_prompt: str, user_message: str, max_tokens: int = 1024) -> dict:
    """
    Chiama Claude e parsa la risposta come JSON.
    Solleva ValueError se la risposta non è JSON valido.
    """
    raw = await call_claude(system_prompt, user_message, max_tokens)
    raw = raw.strip()
    # Rimuove eventuali markdown code block
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
