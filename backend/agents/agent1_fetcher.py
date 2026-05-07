import logging
from typing import List, Dict
from services.sintel_client import fetch_bandi_sintel
from services.supabase_client import get_existing_cigs

logger = logging.getLogger(__name__)


async def run(radius_km: float) -> List[Dict]:
    """
    Fetcha bandi aperti da SINTEL Lombardia (dati.lombardia.it).
    Fonte unica: bandi con scadenza futura e CPV serramenti nel raggio indicato.
    """
    existing_cigs = await get_existing_cigs()
    known_cigs = set(existing_cigs)

    logger.info("Agent1: avvio fetch SINTEL Lombardia...")
    try:
        bandi = await fetch_bandi_sintel(radius_km, known_cigs)
        logger.info(f"Agent1: totale {len(bandi)} bandi grezzi da SINTEL")
        return bandi
    except Exception as e:
        logger.error(f"Agent1: errore SINTEL: {e}")
        return []
