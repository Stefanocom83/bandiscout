import os
import io
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from supabase import create_client

app = FastAPI()


def _clean(val: str) -> str:
    return val.lstrip('﻿').strip()


def get_supabase():
    return create_client(
        _clean(os.environ["SUPABASE_URL"]),
        _clean(os.environ["SUPABASE_SERVICE_KEY"]),
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}



@app.get("/api/bandi")
def get_bandi(
    semaforo: Optional[str] = Query(None),
    giorni: Optional[int] = Query(None),
    radius_km: Optional[float] = Query(None),
    solo_attivi: bool = Query(False),
):
    sb = get_supabase()
    query = sb.table("bandi").select("*").order("created_at", desc=True)

    if semaforo:
        query = query.eq("agent4_semaforo", semaforo)
    if solo_attivi:
        now = datetime.now(timezone.utc).isoformat()
        query = query.or_(f"data_scadenza.is.null,data_scadenza.gte.{now}")
    if giorni:
        since = (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat()
        query = query.gte("created_at", since)
    if radius_km:
        query = query.lte("distanza_km", radius_km)

    result = query.limit(200).execute()
    return result.data


@app.get("/api/bandi/{id}")
def get_bando(id: str):
    sb = get_supabase()
    result = sb.table("bandi").select("*").eq("id", id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Bando non trovato")
    return result.data[0]


@app.get("/api/stats")
def get_stats():
    sb = get_supabase()
    totale = sb.table("bandi").select("id", count="exact").execute()
    verdi = sb.table("bandi").select("id", count="exact").eq("agent4_semaforo", "verde").execute()
    gialli = sb.table("bandi").select("id", count="exact").eq("agent4_semaforo", "giallo").execute()
    rossi = sb.table("bandi").select("id", count="exact").eq("agent4_semaforo", "rosso").execute()
    last_run = sb.table("run_logs").select("started_at,status").order("started_at", desc=True).limit(1).execute()

    return {
        "totale": totale.count,
        "verdi": verdi.count,
        "gialli": gialli.count,
        "rossi": rossi.count,
        "last_run": last_run.data[0] if last_run.data else None,
    }


@app.get("/api/config")
def get_config_endpoint():
    sb = get_supabase()
    result = sb.table("config").select("*").execute()
    return {row["key"]: row["value"] for row in result.data}


@app.put("/api/config")
def update_config_endpoint(body: dict):
    sb = get_supabase()
    for key, value in body.items():
        sb.table("config").upsert({"key": key, "value": str(value)}).execute()
    return {"ok": True}


@app.get("/api/run-logs")
def get_run_logs():
    sb = get_supabase()
    result = sb.table("run_logs").select("*").order("started_at", desc=True).limit(10).execute()
    return result.data


@app.post("/api/run-now")
def run_now():
    return {
        "status": "use_github_actions",
        "message": "Avvia la pipeline manualmente da GitHub Actions: Actions → Pipeline Giornaliera → Run workflow",
    }


@app.post("/api/bandi/{bando_id}/analizza-doc")
async def analizza_documento(
    bando_id: str,
    file: UploadFile = File(...),
    tipo: str = Form("bando"),
):
    # Recupera info bando
    sb = get_supabase()
    res = sb.table("bandi").select("titolo,stazione_appaltante,importo_base,agent4_requisiti").eq("id", bando_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bando non trovato")
    bando = res.data[0]

    # Estrai testo dal PDF (max 12 pagine per rispettare timeout Vercel)
    from pypdf import PdfReader
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    testo = ""
    for page in reader.pages[:12]:
        testo += page.extract_text() or ""
        if len(testo) > 7000:
            break
    testo = testo[:7000]

    if not testo.strip():
        raise HTTPException(status_code=422, detail="Impossibile estrarre testo dal PDF")

    # Costruisci prompt in base al tipo
    if tipo == "bando":
        prompt = f"""Sei un consulente appalti per CBS Serramenti (azienda artigiana serramenti, Gerenzano VA).

BANDO: {bando['titolo']}
Stazione appaltante: {bando['stazione_appaltante']}
Importo base: {bando.get('importo_base', 'N/D')}

DOCUMENTO CARICATO (prime pagine):
{testo}

Analizza il documento e rispondi SOLO con JSON valido:
{{
  "tipo_documento": "disciplinare|capitolato|patto_integrita|allegato|altro",
  "riassunto": "cosa contiene questo documento in 2-3 frasi semplici",
  "requisiti_tecnici": ["lista requisiti tecnici specifici"],
  "requisiti_amministrativi": ["lista documenti/dichiarazioni richiesti"],
  "criteri_valutazione": {{"tecnica": "X/100 punti", "prezzo": "Y/100 punti", "note": "come si assegnano i punteggi"}},
  "scadenze": ["lista date importanti con descrizione"],
  "clausole_da_sapere": ["condizioni, penali, obblighi particolari"],
  "alert_cbs": ["cose specifiche che CBS Serramenti deve sapere, preparare o verificare per questo bando"]
}}"""
    else:  # tipo == "mio"
        req = bando.get("agent4_requisiti") or {}
        prompt = f"""Sei un revisore esperto di appalti pubblici italiani.

BANDO: {bando['titolo']}
Requisiti noti del bando: {json.dumps(req, ensure_ascii=False)[:1500]}

DOCUMENTO CARICATO DA CBS SERRAMENTI:
{testo}

Verifica la conformità di questo documento rispetto al bando. Rispondi SOLO con JSON valido:
{{
  "tipo_documento_rilevato": "DGUE|dichiarazione_art94|visura_cciaa|DURC|offerta_tecnica|offerta_economica|portfolio|altro",
  "conformita": "conforme|parziale|non_conforme",
  "elementi_ok": ["cosa è corretto e completo"],
  "elementi_mancanti": ["cosa manca o è incompleto"],
  "elementi_errati": ["cosa è sbagliato, incoerente o scaduto"],
  "azioni_richieste": ["elenco azioni concrete che CBS deve fare prima di presentare"],
  "rischio_esclusione": "basso|medio|alto",
  "rischio_note": "motivo principale del rischio"
}}"""

    # Chiama Claude Haiku (veloce, sotto timeout Vercel)
    import anthropic
    client = anthropic.Anthropic(api_key=_clean(os.environ["ANTHROPIC_API_KEY"]))
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text
    start, end = raw.find("{"), raw.rfind("}") + 1
    analisi = json.loads(raw[start:end])

    return {
        "analisi": analisi,
        "nome_file": file.filename,
        "pagine_lette": min(12, len(reader.pages)),
        "tipo": tipo,
    }
