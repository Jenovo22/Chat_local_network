# Servidor Go para Chat LAN

Este módulo contiene la implementación Go aislada del servidor de Chat LAN. En T2 solo existe el codec de protocolo; todavía no incluye base de datos, servidor TCP ni CLI.

## Módulo

- Módulo Go: `chatlan/server_go`
- Toolchain usada: `~/.local/bin/go` 1.27.1
- Protocolo cubierto: JSON UTF-8 delimitado por LF compatible con `chat_lan/common/protocol.py`

## Codec de protocolo

El paquete `internal/protocol` implementa:

- `Encode(tipo, payload)` con `tipo`, `timestamp` UTC en milisegundos y `payload` objeto.
- `Reader.Receive()` para tramas fragmentadas o agrupadas en el mismo flujo TCP.
- Validación de UTF-8, JSON, `tipo` string y `payload` objeto.
- Límite `MaxFrame` de 1 MiB y `MaxContent` de 4000 caracteres para validaciones posteriores.
- Preservación del búfer cuando una lectura devuelve timeout u otro error transitorio.
- EOF explícito cuando la conexión se cierra sin una trama completa.

Las pruebas incluyen fixtures cruzados que llaman al codec Python para comprobar decodificación Go→Python y Python→Go.
