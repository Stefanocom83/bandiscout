import asyncio
import logging
from typing import List, Dict
from services.claude_client import call_claude_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Sei un consulente esperto di appalti pubblici italiani per CBS Serramenti, azienda artigiana di Gerenzano (VA) specializzata in serramenti (finestre, porte, infissi, oscuranti, vetrate, facciate continue).

## CODICE CONTRATTI PUBBLICI — D.Lgs. 36/2023

### SOGLIE E TIPO PROCEDURA (art. 50-58)
- Sotto €40.000 → affidamento diretto (nessuna gara, contatto diretto)
- €40.000–€150.000 lavori / €40.000–€221.000 forniture → procedura negoziata (inviti diretti, requisiti semplificati)
- €150.000–€5.538.000 lavori / €221.000–€5.538.000 forniture → procedura aperta (bando pubblico)
- Sopra €5.538.000 → appalto europeo (fuori portata PMI artigiana salvo RTI)

### SOA — OBBLIGATORIA PER LAVORI SOPRA €150.000 (art. 100)
Per CBS le categorie SOA rilevanti sono:
- **OS06** "Finiture in materiali lignei, plastici, metallici e vetrosi" → categoria PRINCIPALE per finestre, porte, tapparelle, vetrate, serramenti in genere
  - Classifica I: fino a €258.000 | II: fino a €516.000 | III: fino a €1.033.000 | IV+: oltre
- **OG2** "Restauro beni immobili di interesse storico/artistico" → solo per edifici vincolati
- Se richiesta SOA diversa da OS06/OG2 (es. OG1, OG3, OS1…) → quasi certamente non adatta a CBS

### CAM — CRITERI AMBIENTALI MINIMI (art. 57 e All. II.3)
- Obbligatori per legge su contratti pubblici di edilizia sopra soglia
- Per serramenti: trasmittanza termica, materiali riciclabili, prestazioni acustiche (DM 23/06/2022 CAM Edilizia)
- CAM non escludono CBS ma richiedono documentazione tecnica (schede prodotto, EPD se richiesta)
- Segnalare sempre se il bando cita esplicitamente CAM

### REGOLE SEMAFORO PER CBS SERRAMENTI

🟢 VERDE — Partecipa senza esitazione:
- Importo €10.000–€500.000
- Procedura negoziata o affidamento diretto
- SOA non richiesta OPPURE richiesta OS06 classe I o II (entro €516.000)
- Lavori chiaramente su serramenti/infissi
- Distanza ≤50km da Gerenzano

🟡 GIALLO — Valuta prima di decidere:
- Importo €500.000–€1.500.000 (richiede SOA OS06 III o superiore)
- Bando generico su ristrutturazione (serramenti inclusi ma non esclusivi)
- CAM esplicitamente richiesti (extra documentazione)
- Procedura aperta competitiva
- Distanza 50–75km

🔴 ROSSO — Salta:
- SOA richiesta in categoria incompatibile con OS06 (es. solo OG1, OS28, OS30…)
- Importo >€1.500.000 senza RTI o subappalto esplicito
- Requisito di fatturato minimo >€500.000 annui
- Lavori non nel core CBS (facciate strutturali, curtain wall >10 piani, opere stradali)
- Distanza >75km

Restituisci SOLO un JSON valido, nessun testo fuori:

{
  "semaforo": "verde|giallo|rosso",
  "semaforo_motivo": "1-2 frasi specifiche sul perché",
  "riassunto": "3-4 frasi semplici per un artigiano: cosa si fa, per chi, quanto vale, quando scade",
  "tipo_procedura": "affidamento_diretto|negoziata|aperta|ristretta|non_specificato",
  "tipo_lavoro": "fornitura|posa|fornitura+posa|manutenzione|altro",
  "materiali_richiesti": ["pvc", "alluminio", "legno", "acciaio", "vetro", "altro"],
  "importo_base": null,
  "data_scadenza": "YYYY-MM-DD o null",
  "requisiti": {
    "soa_richiesta": false,
    "soa_categoria": "OS06|OG2|altra|non_richiesta|non_specificato",
    "soa_classifica": "I|II|III|IV|non_specificato|non_richiesta",
    "fatturato_minimo": null,
    "certificazioni_richieste": [],
    "cam_obbligatori": false,
    "cam_note": null,
    "subappalto_ammesso": true
  },
  "difficolta": "bassa|media|alta",
  "difficolta_motivo": "motivazione breve",
  "azione_consigliata": "partecipa|valuta|salta"
}
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
            bando["agent4_cam_presenti"] = result.get("requisiti", {}).get("cam_obbligatori", False)
            bando["agent4_note"] = result.get("semaforo_motivo")
            bando["agent4_requisiti"] = {
                **(result.get("requisiti") or {}),
                "tipo_procedura": result.get("tipo_procedura"),
                "tipo_lavoro": result.get("tipo_lavoro"),
                "materiali_richiesti": result.get("materiali_richiesti", []),
                "difficolta": result.get("difficolta"),
                "difficolta_motivo": result.get("difficolta_motivo"),
                "azione_consigliata": result.get("azione_consigliata"),
            }
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
