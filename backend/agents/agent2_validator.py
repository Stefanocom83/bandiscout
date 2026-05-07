import asyncio
import logging
from typing import List, Dict
from services.claude_client import call_claude_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Sei un esperto di appalti pubblici italiani specializzato nel settore serramenti.
Il tuo compito è analizzare la descrizione di un bando di gara e determinare se
riguarda la fornitura e/o installazione di serramenti (finestre, porte, infissi,
oscuranti, tapparelle, vetrate, controtelai, cassonetti, schermature solari).

Rispondi SOLO con un JSON valido, nessun testo fuori dal JSON:
{
  "valido": true,
  "confidence": 0.0,
  "motivo": "spiegazione breve (max 2 righe)",
  "tipo_serramento": "finestre|porte|misto|oscuranti|altro|nessuno"
}

Regola: se il bando riguarda ANCHE serramenti (es. ristrutturazione generale che include
la sostituzione infissi), rispondi valido=true.
"""

CONFIDENCE_THRESHOLD = 0.6
MAX_CONCURRENT = 5


async def _validate_single(bando: Dict, semaphore: asyncio.Semaphore) -> Dict:
    async with semaphore:
        user_msg = f"Titolo: {bando.get('titolo', '')}\nCPV: {bando.get('cpv_code', '')} - {bando.get('cpv_descrizione', '')}"
        try:
            result = await call_claude_json(SYSTEM_PROMPT, user_msg)
            bando["agent2_valido"] = result.get("valido", False) and result.get("confidence", 0) >= CONFIDENCE_THRESHOLD
            bando["agent2_confidence"] = result.get("confidence")
            bando["agent2_motivo"] = result.get("motivo")
        except Exception as e:
            logger.error(f"Agent2: errore validazione CIG {bando.get('cig')}: {e}")
            bando["agent2_valido"] = False
            bando["agent2_motivo"] = f"Errore analisi: {e}"
        return bando


async def run(bandi: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    Valida ogni bando con Claude.
    Restituisce (validi, non_validi).
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [_validate_single(b, semaphore) for b in bandi]
    results = await asyncio.gather(*tasks)

    validi = [b for b in results if b.get("agent2_valido")]
    non_validi = [b for b in results if not b.get("agent2_valido")]

    logger.info(f"Agent2: {len(validi)}/{len(bandi)} bandi validi")
    return validi, non_validi
