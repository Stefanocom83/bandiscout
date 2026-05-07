import resend
import logging
from datetime import date
from config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


def _format_importo(val) -> str:
    if val is None:
        return "N/D"
    return f"€ {val:,.0f}".replace(",", ".")


def _format_scadenza(val) -> str:
    if not val:
        return "N/D"
    try:
        return str(val)[:10]
    except Exception:
        return str(val)


def _bando_block(bando: dict) -> str:
    return (
        f"  📌 {bando.get('titolo', '')}\n"
        f"  🏢 {bando.get('stazione_appaltante', 'N/D')} ({bando.get('comune', 'N/D')})\n"
        f"  💰 Base d'asta: {_format_importo(bando.get('importo_base'))}\n"
        f"  📅 Scadenza: {_format_scadenza(bando.get('data_scadenza'))}\n"
        f"  🔗 {bando.get('url_bando') or 'N/D'}\n"
        f"  💬 {bando.get('agent4_riassunto') or ''}\n"
        f"  ---"
    )


async def send_notification(bandi_nuovi: list) -> None:
    verdi = [b for b in bandi_nuovi if b.get("agent4_semaforo") == "verde"]
    gialli = [b for b in bandi_nuovi if b.get("agent4_semaforo") == "giallo"]

    if not verdi and not gialli:
        logger.info("Nessun bando verde/giallo: notifica non inviata.")
        return

    oggi = date.today().strftime("%d/%m/%Y")
    n_nuovi = len(verdi) + len(gialli)
    radius_km = settings.default_radius_km

    sezione_verdi = ""
    if verdi:
        sezione_verdi = "--- BANDI VERDI (priorità alta) ---\n"
        sezione_verdi += "\n".join(_bando_block(b) for b in verdi)

    sezione_gialli = ""
    if gialli:
        sezione_gialli = "\n--- BANDI GIALLI (da valutare) ---\n"
        sezione_gialli += "\n".join(_bando_block(b) for b in gialli)

    body = (
        f"Ciao Stefano,\n\n"
        f"Oggi {oggi} ho trovato {n_nuovi} nuovi bandi nel raggio di {radius_km} km da Gerenzano.\n\n"
        f"{len(verdi)} bandi VERDI 🟢  |  {len(gialli)} bandi GIALLI 🟡\n\n"
        f"{sezione_verdi}\n{sezione_gialli}\n\n"
        f"Apri la dashboard per tutti i dettagli: {settings.dashboard_url}\n\n"
        f"BandiScout · CBS Serramenti"
    )

    try:
        resend.Emails.send({
            "from": "BandiScout <onboarding@resend.dev>",
            "to": [settings.email_notifications],
            "subject": f"🔍 BandiScout — {n_nuovi} nuovi bandi serramenti trovati oggi",
            "text": body,
        })
        logger.info(f"Email inviata: {n_nuovi} bandi ({len(verdi)} verdi, {len(gialli)} gialli)")
    except Exception as e:
        logger.error(f"Errore invio email: {e}")
