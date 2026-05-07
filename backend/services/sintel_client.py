"""
Client SINTEL Lombardia via Open Data dati.lombardia.it
Dataset 8txy-zjw2: Procedure di gara gestite tramite Sintel
Restituisce solo bandi con stato aperto e scadenza futura.
"""
import httpx
import re
import asyncio
import math
import logging
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from config import settings
from services.supabase_client import get_comuni_cache, set_comuni_cache

logger = logging.getLogger(__name__)

SINTEL_API = "https://www.dati.lombardia.it/resource/8txy-zjw2.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Prefissi CPV serramenti/infissi/porte/finestre
CPV_PREFIXES = ["44220", "44221", "45421", "45420"]

# Stati che indicano bando aperto (accetta offerte)
STATI_APERTI = {"Pubblicata", "Aperta pre-qualifica", "Asta Elettronica Aperta"}

_nominatim_lock = asyncio.Lock()
_last_nominatim_call = 0.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _match_cpv(cpv_raw: str) -> Optional[str]:
    """Normalizza CPV SINTEL ('44221000-7' → '44221000') e verifica pertinenza."""
    code = cpv_raw.split("-")[0].strip() if cpv_raw else ""
    for prefix in CPV_PREFIXES:
        if code.startswith(prefix):
            return code
    return None


def _extract_comune(stazione_appaltante: str) -> Optional[str]:
    """Estrae comune da 'Comune di X', 'Città di X', ecc."""
    m = re.match(
        r"(?:Comune|Municipio|Citt[àa])\s+di\s+(.+)",
        stazione_appaltante,
        re.IGNORECASE,
    )
    return m.group(1).strip().title() if m else None


async def _geocode(query: str) -> Tuple[Optional[float], Optional[float]]:
    """Geocodifica tramite Nominatim con cache Supabase e rate limit 1 req/s."""
    global _last_nominatim_call

    cached = await get_comuni_cache(query)
    if cached:
        return cached.get("lat"), cached.get("lng")

    async with _nominatim_lock:
        elapsed = time.time() - _last_nominatim_call
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    NOMINATIM_URL,
                    params={
                        "q": f"{query}, Lombardia, Italia",
                        "format": "json",
                        "limit": 1,
                        "countrycodes": "it",
                    },
                    headers={"User-Agent": "BandiScout/1.0 (CBS Serramenti)"},
                )
        except Exception as e:
            logger.debug(f"Nominatim error for '{query}': {e}")
            return None, None
        finally:
            _last_nominatim_call = time.time()

        if r.status_code == 200 and r.json():
            res = r.json()[0]
            lat, lng = float(res["lat"]), float(res["lon"])
            await set_comuni_cache(query, lat, lng)
            return lat, lng

    return None, None


async def fetch_bandi_sintel(radius_km: float, known_cigs: set) -> List[Dict]:
    """
    Scarica da SINTEL (dataset 8txy-zjw2) i bandi con stato aperto,
    filtra per CPV serramenti, scadenza futura e raggio km da Gerenzano.
    """
    now = datetime.now(timezone.utc)

    stati_filter = " OR ".join(f"stato_procedura='{s}'" for s in STATI_APERTI)
    where_clause = f"({stati_filter})"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                SINTEL_API,
                params={
                    "$where": where_clause,
                    "$limit": 2000,
                    "$order": "data_fine_negoziazione DESC",
                },
            )
            r.raise_for_status()
            records = r.json()
    except Exception as e:
        logger.error(f"SINTEL: errore download: {e}")
        return []

    logger.info(f"SINTEL: {len(records)} procedure aperte totali")

    results = []
    for rec in records:
        cpv = _match_cpv(rec.get("codice_cpv", ""))
        if not cpv:
            continue

        # Scadenza: deve essere futura
        scadenza_raw = rec.get("data_fine_negoziazione", "")
        if scadenza_raw:
            try:
                scad = datetime.fromisoformat(scadenza_raw.replace(".000", "").replace("Z", "+00:00"))
                if scad.tzinfo is None:
                    scad = scad.replace(tzinfo=timezone.utc)
                if scad < now:
                    continue
            except Exception:
                pass

        # CIG univoco
        cig_raw = rec.get("cig", "") or ""
        id_proc = rec.get("id_procedura", "")
        if cig_raw and "X" not in cig_raw:
            cig = f"SINTEL-{cig_raw}"
        else:
            cig = f"SINTEL-{id_proc}"

        if cig in known_cigs:
            continue

        # Geocoding
        sa = rec.get("stazione_appaltante", "")
        comune = _extract_comune(sa)
        lat, lng = await _geocode(comune or sa)

        if lat is None:
            continue

        dist = haversine_km(settings.cbs_lat, settings.cbs_lng, lat, lng)
        if dist > radius_km:
            continue

        link_proc = rec.get("link_procedura", {})
        url_bando = (link_proc.get("url") if isinstance(link_proc, dict) else None) \
            or "https://www.sintel.regione.lombardia.it"

        importo = None
        for field in ("valore_economico_procedura", "base_asta_lotto", "importo_aggiudicaz_procedura"):
            try:
                val = rec.get(field)
                if val:
                    importo = float(val)
                    break
            except (ValueError, TypeError):
                pass

        data_pub = (rec.get("data_inizio_negoziazione") or "")[:10] or None
        data_scad = (scadenza_raw[:10] + "T23:59:59+01:00") if scadenza_raw else None

        results.append({
            "cig": cig,
            "titolo": rec.get("nome_procedura", f"Procedura {id_proc}")[:500],
            "stazione_appaltante": sa[:300],
            "comune": (comune or sa)[:100],
            "provincia": None,
            "lat": lat,
            "lng": lng,
            "distanza_km": round(dist, 2),
            "importo_base": importo,
            "cpv_code": cpv,
            "cpv_descrizione": None,
            "data_pubblicazione": data_pub,
            "data_scadenza": data_scad,
            "url_bando": url_bando,
            "fonte": "SINTEL",
        })

    logger.info(f"SINTEL: {len(results)} bandi serramenti aperti nel raggio {radius_km}km")
    return results
