"""JSON delimitado por LF; admite fragmentación y agrupación de tramas TCP."""
import json
from datetime import datetime, timezone

MAX_FRAME = 1024 * 1024
MAX_CONTENT = 4000


def now():
    """Devuelve la hora UTC en el formato usado por mensajes y tramas."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ProtocolError(ValueError):
    """Indica que una trama o un campo incumple el protocolo del chat."""

    pass


def encode(tipo, payload=None):
    """Codifica una trama JSON terminada en salto de línea para enviarla por TCP."""

    # El delimitador LF permite reconocer el final aunque TCP fragmente o agrupe envíos.
    data = (json.dumps({"tipo": tipo, "timestamp": now(), "payload": payload or {}},
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ProtocolError("Trama demasiado grande")
    return data


class Reader:
    """Reconstruye tramas completas a partir del flujo de bytes de un socket."""

    def __init__(self, sock):
        """Conserva el socket y los bytes que aún no forman una trama completa."""

        self.sock = sock
        self.buffer = bytearray()

    def receive(self):
        """Lee y valida una trama, dejando en el búfer las tramas posteriores."""

        # El búfer sobrevive a un timeout para no perder fragmentos.
        while b"\n" not in self.buffer:
            if len(self.buffer) >= MAX_FRAME:
                raise ProtocolError("Trama demasiado grande")
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("Conexión cerrada")
            self.buffer.extend(chunk)
        # partition separa sólo la primera trama; el resto puede contener otra completa.
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        if len(line) + 1 > MAX_FRAME:
            raise ProtocolError("Trama demasiado grande")
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ProtocolError("JSON inválido") from exc
        # Una trama válida siempre tiene un comando textual y un objeto como carga útil.
        if not isinstance(value, dict) or not isinstance(value.get("tipo"), str) or not isinstance(value.get("payload"), dict):
            raise ProtocolError("Se requiere tipo y payload objeto")
        return value


def text_field(payload, key, maximum):
    """Obtiene un texto obligatorio, lo valida y elimina espacios exteriores."""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ProtocolError(f"{key}: texto obligatorio, máximo {maximum} caracteres")
    return value.strip()
