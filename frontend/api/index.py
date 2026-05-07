import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
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
