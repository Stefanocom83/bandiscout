"""
Client BandiScout - fonti dati bandi italiani:
1. ANAC OCDS (Open Contracting Data Standard) - dati mensili strutturati
2. TED (Tenders Electronic Daily) - bandi EU sopra soglia
"""
import httpx
import asyncio
import math
import logging
import re
import io
from decimal import Decimal
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from config import settings
from services.supabase_client import get_comuni_cache, set_comuni_cache

try:
    import ijson
    IJSON_AVAILABLE = True
except ImportError:
    IJSON_AVAILABLE = False

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
TED_XML_URL = "https://ted.europa.eu/en/notice/{pub}/xml"
OCDS_BASE = "https://dati.anticorruzione.it/opendata/download/dataset/ocds/filesystem/bulk"

_nominatim_lock = asyncio.Lock()
_last_nominatim_call = 0.0

# CPV codes per serramenti / infissi
CPV_SERRAMENTI = {
    "44221000", "44221100", "44221200", "44221210", "44221220",
    "44220000", "44115200", "45421000", "45421100", "45421110",
    "45421120", "45421130", "45421140", "45421150", "45420000",
}

# Procedure non competitive (non bandi aperti)
DIRECT_AWARD_CODES = {"24", "23", "22", "26"}  # codici ANAC per affidamento diretto


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _cpv_match(cpv_id: str) -> Optional[str]:
    """Restituisce il codice CPV normalizzato se è rilevante, None altrimenti."""
    code = cpv_id.split("-")[0] if "-" in cpv_id else cpv_id
    if code in CPV_SERRAMENTI:
        return code
    # Controllo prefisso (es. 44221 per tutta la famiglia)
    for known in CPV_SERRAMENTI:
        if code.startswith(known[:5]):
            return code
    return None


def _decimal_to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_ocds_release(release: dict) -> Optional[dict]:
    """
    Converte un release OCDS nel formato bando BandiScout.
    Include sia bandi aperti che aggiudicazioni recenti (ultimi 90 giorni)
    per fornire intelligence di mercato sulla zona.
    """
    tags = release.get("tag", [])
    # Escludi release senza info tender (es. pure contract/implementation)
    tender = release.get("tender", {})
    buyer = release.get("buyer", {})

    if not tender:
        return None

    # --- Controlla CPV ---
    cpv_found = None
    for item in tender.get("items", []):
        cpv_found = _cpv_match(item.get("classification", {}).get("id", ""))
        if cpv_found:
            break
    if not cpv_found:
        for lot in tender.get("lots", []):
            for item in lot.get("items", []):
                cpv_found = _cpv_match(item.get("classification", {}).get("id", ""))
                if cpv_found:
                    break
    if not cpv_found:
        return None

    # --- Data pubblicazione ---
    raw_date = release.get("date", "")
    data_pub = None
    now = datetime.now(timezone.utc)
    if raw_date:
        date_str = str(raw_date).split("T")[0].strip()
        date_clean = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        if date_clean:
            data_pub = date_clean.group(1)
            try:
                pub = datetime.fromisoformat(data_pub)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                # Includi solo records degli ultimi 90 giorni
                if (now - pub).days > 90:
                    return None
            except Exception:
                pass

    # --- Scadenza ---
    tender_period = tender.get("tenderPeriod", {})
    end_date_raw = tender_period.get("endDate")
    data_scadenza = None
    if end_date_raw:
        try:
            end_clean = str(end_date_raw).replace("T12:00:00Z", "").strip()
            if "T" in end_clean:
                end_clean = end_clean.split("T")[0]
            data_scadenza = f"{end_clean}T23:59:59+01:00"
        except Exception:
            pass

    # --- Determina stato bando ---
    is_aggiudicato = "award" in tags or "contract" in tags
    is_aperto = False
    if data_scadenza:
        try:
            scad = datetime.fromisoformat(data_scadenza)
            if scad.tzinfo is None:
                scad = scad.replace(tzinfo=timezone.utc)
            is_aperto = scad >= now
        except Exception:
            pass

    # --- Costruisce CIG univoco ---
    tender_id = tender.get("id", "")
    ocid = release.get("ocid", "")
    raw_cig = f"ANAC-{tender_id}" if tender_id else f"ANAC-{ocid}"
    # Sanitize: sostituisce chars che rompono URL routing
    cig = re.sub(r'[:/\\?\s]', '-', raw_cig)
    cig = re.sub(r'-+', '-', cig).strip('-')

    # --- Titolo ---
    titolo = tender.get("description") or tender.get("title") or f"Bando {cig}"
    titolo = str(titolo)[:500]

    # --- Stazione appaltante ---
    sa = buyer.get("name") or "N/D"

    # --- Indirizzo / Comune ---
    # In ANAC OCDS, l'indirizzo è in parties[role=buyer].address, non in buyer.address
    comune = None
    provincia = None
    buyer_id = buyer.get("id", "")
    for party in release.get("parties", []):
        if "buyer" in party.get("roles", []) or party.get("id") == buyer_id:
            addr = party.get("address", {})
            comune = addr.get("locality") or addr.get("city")
            provincia = addr.get("region")
            if comune:
                break

    # --- Importo ---
    importo = None
    tender_value = tender.get("value", {})
    if tender_value:
        importo = _decimal_to_float(tender_value.get("amount"))
    if not importo:
        for lot in tender.get("lots", []):
            lot_val = lot.get("value", {})
            if lot_val:
                importo = _decimal_to_float(lot_val.get("amount"))
                if importo:
                    break

    url_bando = "https://www.anticorruzione.it/-/bandi-di-gara"

    return {
        "cig": cig,
        "titolo": titolo,
        "stazione_appaltante": str(sa)[:300],
        "comune": str(comune).strip() if comune else None,
        "provincia": str(provincia).strip() if provincia else None,
        "lat": None,
        "lng": None,
        "distanza_km": None,
        "importo_base": importo,
        "cpv_code": cpv_found,
        "cpv_descrizione": None,
        "data_pubblicazione": data_pub,
        "data_scadenza": data_scadenza,
        "url_bando": url_bando,
        "fonte": "ANAC-OCDS",
    }


async def _get_latest_ocds_url() -> Optional[str]:
    """Trova l'URL del file OCDS più recente disponibile."""
    now = datetime.now(timezone.utc)
    # Genera lista mesi da controllare (dal più recente al più vecchio)
    months_to_check = []
    for months_back in range(0, 8):
        target = now - timedelta(days=30 * months_back + 15)
        months_to_check.append((target.year, target.month))

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for year, month in months_to_check:
            url = f"{OCDS_BASE}/{year}/{month:02d}.json"
            try:
                # Usa GET con Range per verificare che il file esista davvero
                r = await client.get(url, headers={"Range": "bytes=0-99"})
                if r.status_code in (200, 206) and len(r.content) > 10:
                    logger.info(f"OCDS: file confermato disponibile: {url}")
                    return url
            except Exception:
                pass
    return None


async def _download_ocds_chunk(url: str, max_bytes: int = 100 * 1024 * 1024) -> bytes:
    """Scarica fino a max_bytes dal file OCDS con timeout totale di 240 secondi."""
    buf = b""
    deadline = asyncio.get_event_loop().time() + 240  # 4 minuti max

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30, read=30),
        follow_redirects=True,
    ) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            async for chunk in response.aiter_bytes(chunk_size=65536):
                buf += chunk
                if len(buf) >= max_bytes:
                    break
                if asyncio.get_event_loop().time() > deadline:
                    logger.info("OCDS: timeout 120s raggiunto")
                    break
    return buf


async def fetch_bandi_ocds(radius_km: float, known_cigs: set) -> List[Dict]:
    """
    Scarica e filtra bandi dal file OCDS ANAC più recente.
    Limita a 100 MB (~175,000 releases) per bilanciare copertura e tempi.
    Includiamo anche bandi recentemente aggiudicati (ultimi 90 giorni) come intelligence.
    """
    if not IJSON_AVAILABLE:
        logger.warning("ijson non disponibile, OCDS disabilitato")
        return []

    ocds_url = await _get_latest_ocds_url()
    if not ocds_url:
        logger.warning("OCDS: nessun file disponibile")
        return []

    logger.info(f"OCDS: inizio streaming da {ocds_url} (limite 100 MB)")

    results = []
    releases_checked = 0

    try:
        buf = await _download_ocds_chunk(ocds_url, max_bytes=100 * 1024 * 1024)
        logger.info(f"OCDS: scaricati {len(buf)/1024/1024:.0f} MB")

        stream = io.BytesIO(buf)
        for release in ijson.items(stream, "releases.item"):
            releases_checked += 1
            try:
                bando = _parse_ocds_release(release)
                if not bando:
                    continue
                if bando["cig"] in known_cigs:
                    continue
                results.append(bando)
                known_cigs.add(bando["cig"])
            except Exception as e:
                logger.debug(f"OCDS: errore release: {e}")

    except Exception as e:
        logger.error(f"OCDS: errore: {e}")

    logger.info(f"OCDS: analizzati {releases_checked} releases, trovati {len(results)} bandi pre-filtro")

    # Geocodifica e filtro geografico
    geocoded = []
    sem = asyncio.Semaphore(5)

    async def geocode_and_filter(bando: dict):
        async with sem:
            if bando.get("comune"):
                coords = await geocode_comune(bando["comune"])
                if coords:
                    bando["lat"], bando["lng"] = coords

            if bando["lat"] and bando["lng"]:
                dist = haversine_km(settings.cbs_lat, settings.cbs_lng, bando["lat"], bando["lng"])
                bando["distanza_km"] = round(dist, 2)
                if dist <= radius_km:
                    geocoded.append(bando)
            else:
                bando["distanza_km"] = None
                geocoded.append(bando)  # Include se non geocodificabile

    await asyncio.gather(*[geocode_and_filter(b) for b in results])
    logger.info(f"OCDS: {len(geocoded)} bandi dopo filtro geografico {radius_km}km")
    return geocoded


# ─── Geocodifica ──────────────────────────────────────────────────────────────

async def geocode_comune(comune: str) -> Optional[tuple[float, float]]:
    """Geocodifica un comune con Nominatim (max 1 req/sec). Usa cache Supabase."""
    global _last_nominatim_call

    cached = await get_comuni_cache(comune)
    if cached:
        return cached["lat"], cached["lng"]

    async with _nominatim_lock:
        now = asyncio.get_event_loop().time()
        elapsed = now - _last_nominatim_call
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={"q": f"{comune}, Italia", "format": "json", "limit": 1},
                    headers={"User-Agent": "BandiScout/1.0 (CBS Serramenti)"},
                )
                _last_nominatim_call = asyncio.get_event_loop().time()
                data = resp.json()
                if data:
                    lat = float(data[0]["lat"])
                    lng = float(data[0]["lon"])
                    await set_comuni_cache(comune, lat, lng)
                    return lat, lng
        except Exception as e:
            logger.warning(f"Geocoding fallito per {comune}: {e}")

    return None


# ─── TED (backup per bandi sopra soglia UE) ───────────────────────────────────

def _parse_ted_xml(xml_text: str, pub_number: str, cpv_code: str) -> Optional[dict]:
    is_italian = (
        'listName="country">ITA<' in xml_text
        or '<ISO_COUNTRY VALUE="IT"' in xml_text
        or 'listName="nuts">IT' in xml_text
    )
    if not is_italian:
        return None

    titolo = None
    for lang in ['ITA', 'ENG', '']:
        pattern = rf'<cbc:Name[^>]*languageID="{lang}"[^>]*>([^<]{{10,300}})</cbc:Name>'
        m = re.search(pattern, xml_text)
        if m:
            titolo = m.group(1).strip()
            break
    if not titolo:
        m = re.search(r'<ML_TI_DOC LG="IT">.*?<TI_TEXT>.*?<P>(.*?)</P>', xml_text, re.DOTALL)
        if m:
            titolo = m.group(1).strip()
    if not titolo:
        titolo = f"Bando TED {pub_number}"

    sa = None
    m = re.search(r'<cbc:Name[^>]*>([^<]{5,200})</cbc:Name>', xml_text)
    if m:
        sa = m.group(1).strip()
    if not sa:
        m = re.search(r'<OFFICIALNAME>([^<]+)</OFFICIALNAME>', xml_text)
        if m:
            sa = m.group(1).strip()

    comune = None
    m = re.search(r'<cbc:CityName>([^<]+)</cbc:CityName>', xml_text)
    if m:
        comune = m.group(1).strip()
    if not comune:
        m = re.search(r'<TOWN>([^<]+)</TOWN>', xml_text)
        if m:
            comune = m.group(1).strip()

    importo = None
    m = re.search(r'<cbc:Amount[^>]*currencyID="EUR"[^>]*>([0-9.,]+)</cbc:Amount>', xml_text)
    if m:
        try:
            importo = float(m.group(1).replace(',', '.'))
        except ValueError:
            pass
    if not importo:
        m = re.search(r'<VALUE[^>]*CURRENCY="EUR"[^>]*>([0-9.,]+)</VALUE>', xml_text)
        if m:
            try:
                importo = float(m.group(1).replace(',', '.'))
            except ValueError:
                pass

    data_scad = None
    m = re.search(r'<cbc:EndDate>(\d{4}-\d{2}-\d{2})</cbc:EndDate>', xml_text)
    if m:
        data_scad = m.group(1) + "T23:59:59+01:00"
    if not data_scad:
        m = re.search(r'<DT_DATE_FOR_SUBMISSION>(\d{8})', xml_text)
        if m:
            d = m.group(1)
            data_scad = f"{d[:4]}-{d[4:6]}-{d[6:8]}T23:59:59+01:00"

    data_pub = None
    m = re.search(r'<cbc:IssueDate>(\d{4}-\d{2}-\d{2})</cbc:IssueDate>', xml_text)
    if m:
        data_pub = m.group(1)
    if not data_pub:
        m = re.search(r'<DATE_PUB>(\d{8})</DATE_PUB>', xml_text)
        if m:
            d = m.group(1)
            data_pub = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    return {
        "cig": f"TED-{pub_number}",
        "titolo": titolo[:500],
        "stazione_appaltante": (sa or "N/D")[:300],
        "comune": comune,
        "provincia": None,
        "lat": None,
        "lng": None,
        "distanza_km": None,
        "importo_base": importo,
        "cpv_code": cpv_code,
        "cpv_descrizione": None,
        "data_pubblicazione": data_pub,
        "data_scadenza": data_scad,
        "url_bando": f"https://ted.europa.eu/it/notice/-/detail/{pub_number}",
        "fonte": "TED",
    }


async def _get_pub_numbers(cpv: str, days_back: int = 7) -> List[str]:
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y%m%d")
    pubs = []
    page = 1
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            await asyncio.sleep(0.3)
            try:
                resp = await client.post(
                    TED_SEARCH_URL,
                    json={
                        "query": f"PC={cpv} AND PD>{since}",
                        "fields": ["publication-number"],
                        "page": page,
                        "limit": 50,
                    },
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                data = resp.json()
                if resp.status_code != 200:
                    logger.debug(f"TED search {cpv}: {data.get('message','')[:60]}")
                    break
                notices = data.get("notices", [])
                pubs.extend(n["publication-number"] for n in notices)
                if len(notices) < 50:
                    break
                page += 1
            except Exception as e:
                logger.error(f"TED search errore CPV {cpv}: {e}")
                break
    return pubs


async def _download_and_parse_ted(pub: str, cpv: str, client: httpx.AsyncClient) -> Optional[dict]:
    await asyncio.sleep(0.5)
    try:
        resp = await client.get(
            TED_XML_URL.format(pub=pub),
            headers={"User-Agent": "BandiScout/1.0"},
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        return _parse_ted_xml(resp.text, pub, cpv)
    except Exception as e:
        logger.warning(f"Errore download XML TED {pub}: {e}")
        return None


async def fetch_bandi_by_cpv(cpv: str, radius_km: float, known_cigs: set, **kwargs) -> List[Dict]:
    """Fetcha bandi TED per un CPV specifico (backup sopra-soglia UE). Max 50 XML per CPV."""
    now = datetime.now(timezone.utc)
    pub_numbers = await _get_pub_numbers(cpv, days_back=7)
    logger.info(f"TED CPV {cpv}: {len(pub_numbers)} notices negli ultimi 7 giorni")
    # Limita XML downloads per evitare timeout su CPV generici molto popolari
    pub_numbers = pub_numbers[:50]

    results = []
    sem = asyncio.Semaphore(3)

    async def process(pub: str):
        cig_key = f"TED-{pub}"
        if cig_key in known_cigs:
            return
        async with sem:
            async with httpx.AsyncClient(timeout=15) as client:
                bando = await _download_and_parse_ted(pub, cpv, client)
        if not bando:
            return

        if bando.get("data_scadenza"):
            try:
                scad = datetime.fromisoformat(bando["data_scadenza"])
                if scad.tzinfo is None:
                    scad = scad.replace(tzinfo=timezone.utc)
                if scad < now:
                    return
            except Exception:
                pass

        if not bando["lat"] and bando.get("comune"):
            coords = await geocode_comune(bando["comune"])
            if coords:
                bando["lat"], bando["lng"] = coords

        if bando["lat"] and bando["lng"]:
            dist = haversine_km(settings.cbs_lat, settings.cbs_lng, bando["lat"], bando["lng"])
            bando["distanza_km"] = round(dist, 2)
            if dist > radius_km:
                return
        else:
            bando["distanza_km"] = None

        known_cigs.add(bando["cig"])
        results.append(bando)

    await asyncio.gather(*[process(pub) for pub in pub_numbers])
    logger.info(f"TED CPV {cpv}: {len(results)} bandi italiani nel raggio {radius_km}km")
    return results
