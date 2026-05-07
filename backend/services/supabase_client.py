from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


async def get_existing_cigs() -> set[str]:
    """Restituisce tutti i CIG già presenti in Supabase."""
    sb = get_supabase()
    result = sb.table("bandi").select("cig").execute()
    return {row["cig"] for row in result.data}


async def upsert_bando(bando: dict) -> None:
    """Inserisce o aggiorna un bando. Ignora conflitti su CIG duplicato."""
    sb = get_supabase()
    try:
        sb.table("bandi").upsert(bando, on_conflict="cig").execute()
    except Exception as e:
        logger.error(f"Errore upsert bando {bando.get('cig')}: {e}")


async def get_config(key: str) -> str | None:
    sb = get_supabase()
    result = sb.table("config").select("value").eq("key", key).execute()
    if result.data:
        return result.data[0]["value"]
    return None


async def set_config(key: str, value: str) -> None:
    sb = get_supabase()
    sb.table("config").upsert({"key": key, "value": value}).execute()


async def create_run_log() -> str:
    sb = get_supabase()
    result = sb.table("run_logs").insert({"status": "running"}).execute()
    return result.data[0]["id"]


async def update_run_log(run_id: str, data: dict) -> None:
    sb = get_supabase()
    sb.table("run_logs").update(data).eq("id", run_id).execute()


async def get_comuni_cache(comune: str) -> dict | None:
    sb = get_supabase()
    result = sb.table("comuni_cache").select("lat,lng").eq("comune", comune).execute()
    if result.data:
        return result.data[0]
    return None


async def set_comuni_cache(comune: str, lat: float, lng: float) -> None:
    sb = get_supabase()
    try:
        sb.table("comuni_cache").upsert({"comune": comune, "lat": lat, "lng": lng}).execute()
    except Exception:
        pass
