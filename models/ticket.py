"""Modelos de ticket y reglas de transición de estado."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CategoriaEnum(str, Enum):
    SOPORTE = "Soporte"
    TECNICO = "Tecnico"
    FACTURACION = "Facturacion"
    CUENTA = "Cuenta"
    OTRO = "Otro"


class PrioridadEnum(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"


class EstadoEnum(str, Enum):
    ABIERTO = "Abierto"
    EN_PROCESO = "En Proceso"
    RESUELTO = "Resuelto"
    CERRADO = "Cerrado"


# Transiciones válidas de estado. Un salto directo a "Resuelto" desde "Abierto"
# no está permitido: el flujo es Abierto -> En Proceso -> Resuelto -> Cerrado.
TRANSICIONES: dict[EstadoEnum, set[EstadoEnum]] = {
    EstadoEnum.ABIERTO: {EstadoEnum.EN_PROCESO, EstadoEnum.CERRADO},
    EstadoEnum.EN_PROCESO: {EstadoEnum.RESUELTO, EstadoEnum.ABIERTO},
    EstadoEnum.RESUELTO: {EstadoEnum.CERRADO, EstadoEnum.EN_PROCESO},
    EstadoEnum.CERRADO: {EstadoEnum.ABIERTO},
}

# Transiciones reservadas a los administradores (reabrir un ticket cerrado).
TRANSICIONES_SOLO_ADMIN: set[EstadoEnum] = {EstadoEnum.CERRADO}


def transicion_valida(actual: EstadoEnum, nuevo: EstadoEnum, es_admin: bool) -> bool:
    """Indica si se puede pasar de `actual` a `nuevo`."""
    if actual == nuevo:
        return True
    if nuevo not in TRANSICIONES.get(actual, set()):
        return False
    return not (actual in TRANSICIONES_SOLO_ADMIN and not es_admin)


class Ticket(BaseModel):
    """Datos que envía el cliente al crear o actualizar un ticket."""

    titulo: str = Field(min_length=5, max_length=120)
    descripcion: str = Field(min_length=1, max_length=4000)
    categoria: CategoriaEnum
    prioridad: PrioridadEnum = PrioridadEnum.MEDIA


class TicketCreate(Ticket):
    pass


class TicketUpdate(Ticket):
    pass


class TicketEstadoUpdate(BaseModel):
    """Cambio de estado de un ticket."""

    estado: EstadoEnum


class TicketResponse(Ticket):
    id: str
    estado: EstadoEnum = EstadoEnum.ABIERTO
    fecha_creacion: datetime
    ultima_actualizacion: datetime
    propietario: str
