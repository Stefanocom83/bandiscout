from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import logging
from scheduler import init_scheduler, scheduler
from orchestrator import run_pipeline
from services.supabase_client import get_supabase, get_config, set_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="BandiScout API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
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
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        query = query.or_(f"data_scadenza.is.null,data_scadenza.gte.{now}")
    if giorni:
        from datetime import datetime, timezone, timedelta
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
async def get_config_endpoint():
    sb = get_supabase()
    result = sb.table("config").select("*").execute()
    return {row["key"]: row["value"] for row in result.data}


@app.put("/api/config")
async def update_config_endpoint(body: dict):
    for key, value in body.items():
        await set_config(key, str(value))
    return {"ok": True}


@app.post("/api/run-now")
async def run_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline)
    return {"status": "started", "message": "Pipeline avviata in background"}


@app.get("/api/run-logs")
def get_run_logs():
    sb = get_supabase()
    result = sb.table("run_logs").select("*").order("started_at", desc=True).limit(10).execute()
    return result.data
