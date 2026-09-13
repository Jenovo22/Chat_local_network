"""Validación de identidad; la dirección IP procede del socket."""
import uuid
from common.protocol import ProtocolError, text_field


def login(database, payload, ip):
    device_id = text_field(payload, "device_id", 36)
    try:
        device_id = str(uuid.UUID(device_id))
    except ValueError as exc:
        raise ProtocolError("device_id debe ser un UUID") from exc
    return database.register(device_id, text_field(payload, "nombre", 60), ip)
