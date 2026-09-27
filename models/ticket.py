from pydantic import BaseModel
from datetime import datetime
from enum import Enum


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


class Ticket(BaseModel):
    id: str | None = None
    titulo: str
    descripcion: str
    categoria: CategoriaEnum
    prioridad: PrioridadEnum = PrioridadEnum.MEDIA


class TicketResponse(Ticket):
    estado: EstadoEnum = EstadoEnum.ABIERTO
    fecha_creacion: datetime
    ultima_actualizacion: datetime
    propietario: str | None = None
