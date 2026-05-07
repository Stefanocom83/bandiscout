import asyncio
import logging
from typing import List, Dict
from services.anac_client import fetch_bandi_by_cpv

logger = logging.getLogger(__name__)

CPV_ADIACENTI = [
    "45200000",
    "45210000",
    "45211000",
    "45215000",
    "45216000",
    "45220000",
    "45260000",
    "45300000",
    "45320000",
    "45321000",
    "45400000",
    "45420000",
    "45440000",
    "45441000",
    "45443000",
    "45451000",
]

KEYWORDS_SERRAMENTI = {
    "infissi", "finestre", "porte", "serramenti", "oscuranti",
    "tapparelle", "persiane", "involucro", "serrande", "vetrate",
    "controtelai", "cassonetti", "schermature solari", "zanzariere",
    "avvolgibili", "veneziane", "frangisole", "facciata continua",
    "manutenzione finestre", "sostituzione infissi", "adeguamento termico",
    "cappotto", "riqualificazione energetica involucro",
}


def _has_keyword(bando: dict) -> bool:
    testo = (bando.get("titolo") or "").lower()
    return any(kw in testo for kw in KEYWORDS_SERRAMENTI)


async def run(radius_km: float, known_cigs: set) -> List[Dict]:
    """
    TED EU non pubblica bandi italiani sotto-soglia per serramenti.
    Agent3 disabilitato finché non si trova una fonte alternativa real-time.
    """
    logger.info("Agent3: disabilitato (TED non ha bandi italiani sotto-soglia serramenti)")
    return []
