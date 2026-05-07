import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from config import settings
from services.supabase_client import (
    get_config, update_run_log, create_run_log, upsert_bando, get_existing_cigs
)
from services.email_service import send_notification
import agents.agent1_fetcher as agent1
import agents.agent2_validator as agent2
import agents.agent3_hunter as agent3
import agents.agent4_analyzer as agent4

logger = logging.getLogger(__name__)


def _flatten_bando(bando: dict) -> dict:
    """Converte campi annidati (requisiti) in formato Supabase-friendly."""
    flat = dict(bando)
    requisiti = flat.get("agent4_requisiti")
    if isinstance(requisiti, dict):
        flat["agent4_requisiti"] = requisiti
    return flat


async def run_pipeline(radius_km: Optional[float] = None) -> dict:
    run_id = await create_run_log()
    stats = {
        "bandi_fetched": 0,
        "bandi_validi": 0,
        "bandi_hunter": 0,
        "bandi_nuovi": 0,
        "errori": [],
    }

    try:
        if radius_km is None:
            cfg = await get_config("radius_km")
            radius_km = float(cfg) if cfg else settings.default_radius_km

        logger.info(f"Pipeline avviata — raggio {radius_km} km")

        # Snapshot CIG esistenti prima della run (per trovare i "nuovi")
        pre_run_cigs = await get_existing_cigs()

        # Agent 1 + Agent 3 in parallelo
        agent1_task = asyncio.create_task(agent1.run(radius_km))
        # Agent 3 parte subito con CIG vuoti, li filtrerà rispetto ad Agent 1 dopo
        agent3_task = asyncio.create_task(agent3.run(radius_km, set(pre_run_cigs)))

        bandi_grezzi = await agent1_task
        stats["bandi_fetched"] = len(bandi_grezzi)
        logger.info(f"Agent1: trovati {len(bandi_grezzi)} bandi grezzi")

        # Agent 2
        validi, non_validi = await agent2.run(bandi_grezzi)
        stats["bandi_validi"] = len(validi)
        logger.info(f"Agent2: {len(validi)}/{len(bandi_grezzi)} validi")

        # Salva i non validi per audit
        for b in non_validi:
            await upsert_bando(_flatten_bando(b))

        # Attendi Agent 3
        bandi_hunter = await agent3_task
        # Rimuovi eventuali duplicati con Agent 1
        cigs_agent1 = {b["cig"] for b in bandi_grezzi}
        bandi_hunter = [b for b in bandi_hunter if b["cig"] not in cigs_agent1]
        stats["bandi_hunter"] = len(bandi_hunter)
        logger.info(f"Agent3: {len(bandi_hunter)} bandi nascosti unici")

        # Merge e deduplicazione finale
        tutti_validi = validi + bandi_hunter
        seen = set()
        merged = []
        for b in tutti_validi:
            if b["cig"] not in seen:
                seen.add(b["cig"])
                merged.append(b)

        # Agent 4
        analizzati = await agent4.run(merged)
        logger.info(f"Agent4: analizzati {len(analizzati)} bandi")

        # Salva su Supabase
        for b in analizzati:
            await upsert_bando(_flatten_bando(b))

        # Identifica nuovi bandi (non presenti prima di questa run)
        nuovi = [b for b in analizzati if b["cig"] not in pre_run_cigs]
        stats["bandi_nuovi"] = len(nuovi)
        logger.info(f"Nuovi bandi questa run: {len(nuovi)}")

        # Email se ci sono nuovi bandi verde/giallo
        if nuovi:
            await send_notification(nuovi)

        await update_run_log(run_id, {
            **stats,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        })
        logger.info("Pipeline completata con successo")

    except Exception as e:
        logger.exception(f"Errore critico pipeline: {e}")
        stats["errori"].append(str(e))
        await update_run_log(run_id, {
            **stats,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
        })

    return stats
