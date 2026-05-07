import asyncio
import logging
from typing import List, Dict
from services.anac_client import fetch_bandi_ocds, fetch_bandi_by_cpv
from services.supabase_client import get_existing_cigs

logger = logging.getLogger(__name__)

# CPV sopra-soglia UE (solo per TED, integrato con OCDS)
CPV_TED_SUPPLEMENT = [
    "44221000", "44221100", "44221200",
    "45421000", "45421100", "45420000",
]


async def run(radius_km: float) -> List[Dict]:
    """
    Fetcha bandi da due fonti:
    1. ANAC OCDS (file mensile strutturato, principale)
    2. TED (bandi EU sopra-soglia, supplemento real-time)
    Deduplicato per CIG.
    """
    existing_cigs = await get_existing_cigs()
    known_cigs = set(existing_cigs)
    all_bandi: List[Dict] = []

    # Fonte 1: ANAC OCDS (tutti i bandi italiani, inclusi sotto-soglia)
    logger.info("Agent1: avvio fetch ANAC OCDS...")
    try:
        ocds_bandi = await fetch_bandi_ocds(radius_km, known_cigs)
        all_bandi.extend(ocds_bandi)
        logger.info(f"Agent1: OCDS → {len(ocds_bandi)} bandi")
    except Exception as e:
        logger.error(f"Agent1: errore OCDS: {e}")

    # Fonte 2: TED (integrazione sopra-soglia UE, ultimi 7 giorni)
    logger.info("Agent1: avvio fetch TED (integrazione sopra-soglia)...")
    for cpv in CPV_TED_SUPPLEMENT:
        try:
            bandi = await fetch_bandi_by_cpv(cpv, radius_km, known_cigs)
            all_bandi.extend(bandi)
        except Exception as e:
            logger.error(f"Agent1: errore TED CPV {cpv}: {e}")

    logger.info(f"Agent1: totale {len(all_bandi)} bandi grezzi (OCDS + TED)")
    return all_bandi
