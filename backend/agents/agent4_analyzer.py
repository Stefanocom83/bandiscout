import asyncio
import logging
from typing import List, Dict
from services.claude_client import call_claude_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Sei un consulente esperto di appalti pubblici italiani per CBS Serramenti, azienda artigiana di Gerenzano (VA) specializzata in serramenti (finestre, porte, infissi, oscuranti, vetrate, facciate continue).

## CODICE CONTRATTI PUBBLICI — D.Lgs. 36/2023 (aggiornato L. 34/2026)

### SOGLIE E TIPO PROCEDURA (art. 50-58)
- Sotto €40.000 → affidamento diretto (nessun bando, contatto diretto)
- €40.000–€150.000 lavori / €40.000–€221.000 forniture → negoziata senza bando (inviti diretti)
- €150.000–€5.538.000 lavori / €221.000+ forniture → procedura aperta (bando pubblico, più competitiva)
- Sopra €5.538.000 → appalto europeo (quasi sempre fuori portata PMI artigiana)

### CAUSE DI ESCLUSIONE — BUSTA AMMINISTRATIVA (art. 94-96)
Il 70% delle esclusioni avviene per errori in fase amministrativa. Le cause principali:
- Mancanza DURC valido (regolarità contributiva INPS/INAIL)
- DGUE incompleto o non firmato digitalmente dal legale rappresentante
- Dichiarazione art. 94 mancante o errata (assenza reati gravi, fallimenti, sanzioni ANAC)
- Visura CCIAA con attività non coerente con oggetto appalto
- PassOE non generato (sistema ANAC per verifica telematica requisiti)
- Firma digitale mancante o apposta da soggetto non legittimato

### SOA — QUALIFICAZIONE OBBLIGATORIA LAVORI >€150.000 (art. 100)
Categorie rilevanti per CBS:
- **OS06** "Finiture in materiali lignei, plastici, metallici e vetrosi" → PRINCIPALE per serramenti
  - Classifica I ≤€258k | II ≤€516k | III ≤€1.033k | IV ≤€2.582k
- **OG2** → solo edifici vincolati (beni culturali)
- Altra SOA non OS06 senza subappalto → rosso automatico

### CAM — CRITERI AMBIENTALI MINIMI (art. 57, DM 23/06/2022)
- Obbligatori per edilizia pubblica sopra soglia
- Per serramenti: trasmittanza termica UNI EN ISO, materiali riciclabili, EPD prodotto
- Non escludono CBS ma richiedono documentazione tecnica da preparare in anticipo

### REGOLE SEMAFORO PER CBS

🟢 VERDE — Partecipa:
- Importo €10k–€500k, procedura negoziata o diretta
- SOA non richiesta O OS06 classe I/II
- Lavori chiaramente su serramenti, distanza ≤50km

🟡 GIALLO — Valuta:
- Importo €500k–€1.500k con SOA OS06 III+
- Bando generico (serramenti sono parte ma non tutto)
- CAM espliciti, procedura aperta, distanza 50–75km

🔴 ROSSO — Salta:
- SOA incompatibile con OS06, importo >€1.5M senza subappalto
- Fatturato minimo richiesto >€500k, distanza >75km

Restituisci SOLO un JSON valido, nessun testo fuori:

{
  "semaforo": "verde|giallo|rosso",
  "semaforo_motivo": "1-2 frasi specifiche",
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
  "azione_consigliata": "partecipa|valuta|salta",
  "checklist_documenti": [
    {
      "documento": "nome documento",
      "busta": "amministrativa|tecnica|economica",
      "obbligatorio": true,
      "nota": "riferimento normativo o avvertenza specifica per questo bando"
    }
  ]
}

La checklist_documenti deve contenere TUTTI i documenti necessari per partecipare a QUESTO specifico bando, compilata in base a importo, procedura e requisiti rilevati. Includi sempre: DGUE, Dichiarazione art. 94, DURC, Visura CCIAA, PassOE. Aggiungi SOA se richiesta, CAM se presenti, referenze bancarie se fatturato minimo richiesto.
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
                "checklist_documenti": result.get("checklist_documenti", []),
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
