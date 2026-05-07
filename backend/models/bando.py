from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class BandoRaw(BaseModel):
    cig: str
    titolo: str
    stazione_appaltante: Optional[str] = None
    comune: Optional[str] = None
    provincia: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    distanza_km: Optional[float] = None
    importo_base: Optional[float] = None
    cpv_code: Optional[str] = None
    cpv_descrizione: Optional[str] = None
    data_pubblicazione: Optional[datetime] = None
    data_scadenza: Optional[datetime] = None
    url_bando: Optional[str] = None
    fonte: str = "ANAC"


class BandoValidated(BandoRaw):
    agent2_valido: Optional[bool] = None
    agent2_confidence: Optional[float] = None
    agent2_motivo: Optional[str] = None
    agent3_trovato_da_hunter: bool = False


class RequisitiBando(BaseModel):
    soa_richiesta: bool = False
    soa_categoria: Optional[str] = None
    fatturato_minimo: Optional[float] = None
    certificazioni_richieste: List[str] = []
    cam_obbligatori: bool = False
    cam_note: Optional[str] = None


class BandoAnalyzed(BandoValidated):
    agent4_semaforo: Optional[str] = None
    agent4_riassunto: Optional[str] = None
    agent4_requisiti: Optional[RequisitiBando] = None
    agent4_cam_presenti: Optional[bool] = None
    agent4_note: Optional[str] = None
    notifica_inviata: bool = False
