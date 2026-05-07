import asyncio
import logging
from typing import List, Dict, Optional
from services.claude_client import call_claude_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Sei un consulente esperto di appalti pubblici per un'azienda artigiana italiana
specializzata in serramenti (finestre, porte, infissi). L'azienda si chiama CBS Serramenti.
Analizza il seguente bando di gara e restituisci SOLO un JSON valido:

{
  "semaforo": "verde|giallo|rosso",
  "semaforo_motivo": "perché questo semaforo (1-2 frasi)",
  "riassunto": "spiegazione semplice del bando in 3-4 frasi, come se parlassi a un artigiano",
  "tipo_lavoro": "fornitura|posa|fornitura+posa|manutenzione|altro",
  "materiali_richiesti": ["pvc", "alluminio", "legno", "acciaio", "altro"],
  "importo_base": 0,
  "data_scadenza": "YYYY-MM-DD",
  "requisiti": {
    "soa_richiesta": false,
    "soa_categoria": "non specificato",
    "fatturato_minimo": null,
    "certificazioni_richieste": [],
    "cam_obbligatori": false,
    "cam_note": null
  },
  "difficolta": "bassa|media|alta",
  "difficolta_motivo": "breve motivazione",
  "azione_consigliata": "partecipa|valuta|salta"
}

REGOLE SEMAFORO:
- verde: bando chiaro, importo ragionevole, requisiti accessibili a una PMI artigiana
- giallo: bando interessante ma ha almeno un elemento da valutare (SOA, importo alto, requisiti particolari)
- rosso: bando non adatto (es. richiede SOA che CBS non ha, importo > 5M, troppo lontano dalla specializzazione)
"""

MAX_CONCURRENT = 3


async def _analyze_single(bando: Dict, semaphore: asyncio.Semaphore) -> Dict:
    async with semaphore:
        user_msg = (
            f"Titolo: {bando.get('titolo', '')}\n"
            f"Stazione appaltante: {bando.get('stazione_appaltante', 'N/D')}\n"
            f"Comune: {bando.get('comune', 'N/D')} ({bando.get('provincia', '')})\n"
            f"CPV: {bando.get('cpv_code', '')} - {bando.get('cpv_descrizione', '')}\n"
            f"Importo base: {bando.get('importo_base', 'N/D')}\n"
            f"Data scadenza: {bando.get('data_scadenza', 'N/D')}\n"
            f"Distanza da Gerenzano: {bando.get('distanza_km', 'N/D')} km\n"
        )
        try:
            result = await call_claude_json(SYSTEM_PROMPT, user_msg, max_tokens=1500)
            bando["agent4_semaforo"] = result.get("semaforo", "giallo")
            bando["agent4_riassunto"] = result.get("riassunto")
            bando["agent4_requisiti"] = result.get("requisiti")
            bando["agent4_cam_presenti"] = result.get("requisiti", {}).get("cam_obbligatori", False)
            bando["agent4_note"] = result.get("semaforo_motivo")
        except Exception as e:
            logger.error(f"Agent4: errore analisi CIG {bando.get('cig')}: {e}")
            bando["agent4_semaforo"] = "giallo"
            bando["agent4_note"] = "Analisi non disponibile"
        return bando


async def run(bandi: List[Dict]) -> List[Dict]:
    """Analisi profonda di ogni bando. Concorrenza max 3 chiamate Claude."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [_analyze_single(b, semaphore) for b in bandi]
    results = await asyncio.gather(*tasks)
    logger.info(f"Agent4: analizzati {len(results)} bandi")
    return list(results)
