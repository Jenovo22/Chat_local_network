"""JSON delimitado por LF; admite fragmentación y agrupación de tramas TCP."""
import json
from datetime import datetime, timezone

MAX_FRAME = 1024 * 1024
MAX_CONTENT = 4000


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ProtocolError(ValueError):
    pass


def encode(tipo, payload=None):
    data = (json.dumps({"tipo": tipo, "timestamp": now(), "payload": payload or {}},
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ProtocolError("Trama demasiado grande")
    return data


class Reader:
    def __init__(self, sock):
        self.sock = sock
        self.buffer = bytearray()

    def receive(self):
        # El búfer sobrevive a un timeout para no perder fragmentos.
        while b"\n" not in self.buffer:
            if len(self.buffer) >= MAX_FRAME:
                raise ProtocolError("Trama demasiado grande")
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("Conexión cerrada")
            self.buffer.extend(chunk)
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        if len(line) + 1 > MAX_FRAME:
            raise ProtocolError("Trama demasiado grande")
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ProtocolError("JSON inválido") from exc
        if not isinstance(value, dict) or not isinstance(value.get("tipo"), str) or not isinstance(value.get("payload"), dict):
            raise ProtocolError("Se requiere tipo y payload objeto")
        return value


def text_field(payload, key, maximum):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ProtocolError(f"{key}: texto obligatorio, máximo {maximum} caracteres")
    return value.strip()
