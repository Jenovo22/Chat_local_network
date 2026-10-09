# Matriz de verificación

La matriz vincula requisitos implementados con pruebas ejecutables. “No
cubierto” significa que la evidencia automatizada actual no prueba ese aspecto;
no implica que exista una función adicional.

Los artefactos interactivos complementan la revisión: [arquitectura](diagramas/arquitectura.html)
y [recorrido conectar/sincronizar/enviar/reintentar](diagramas/recorrido.html).
Esta matriz permanece como fuente de verdad para la evidencia y los resultados.

## Comandos reproducibles

Ejecutar desde `chat_lan`:

```bash
python3 -m unittest discover -s tests -v
```

Ejecutar desde `chat_lan/server_go`:

```bash
go test ./...
```

## Trazabilidad requisito → prueba

| Requisito | Prueba o comprobación | Tipo | Resultado de auditoría |
| --- | --- | --- | --- |
| RF-01 | `ChatTests.test_reconnect_outbox_and_persistent_identity`; `ChatTests.test_duplicate_login_and_invalid_first_command` | Integración Python (loopback + SQLite temporal) | Pasa |
| RF-02 | `ChatTests.test_2_5_10_clients_broadcast_and_capacity`; `ChatTests.test_duplicate_login_and_invalid_first_command` | Integración Python | Pasa |
| RF-03 | `ChatTests.test_retry_is_idempotent_and_sync_paginated` | Integración Python | Pasa |
| RF-04 | `ChatTests.test_reconnect_outbox_and_persistent_identity`; `ChatTests.test_server_restart_recovers_and_keeps_color` | Integración Python | Pasa |
| RF-05 | `ChatTests.test_2_5_10_clients_broadcast_and_capacity`; `ChatTests.test_concurrent_messages_have_same_order` | Integración Python | Pasa |
| RF-06 | `ChatTests.test_retry_is_idempotent_and_sync_paginated` | Integración Python | Pasa |
| RF-07 | `ProtocolTests.test_fragmented_unicode_and_multiple_frames`; `ProtocolTests.test_invalid_json_and_oversize` | Unidad/protocolo Python | Pasa |
| RF-08 | `GuiTests.test_two_windows_exchange_and_remember_settings` | Integración GUI PySide6 sin pantalla | Omitida: PySide6 no instalado |
| RG-01 | `TestEncodeProducesLFDelimitedUTF8JSON`; `TestReaderAcceptsFragmentedAndAggregatedFrames`; `TestReaderPreservesBufferAcrossTimeout`; `TestReaderRejectsInvalidFramesAndEOF`; `TestPythonCommonProtocolCompatibility`; `TestReaderAcceptsPythonCompatibleArbitraryTimestamps` | Unidad Go + compatibilidad Python/Go | Pasa |
| RNF-01 | Revisión de `README.md` y `common/protocol.py` | Revisión documental/código | No es una prueba de seguridad |
| RNF-02 | `ProtocolTests.test_invalid_json_and_oversize`; `TestFrameSizeLimit` | Unidad de protocolo Python y Go | Pasa |
| RNF-03 | Revisión de alcance en [descripción funcional](descripcion-funcional.md) | Revisión documental | No aplicable |
| RNF-04 | Revisión de `server_go/` y [README del módulo](migracion-go.md) | Inspección de alcance | Confirmado |

## Resultado de la auditoría

En la auditoría se ejecutaron los dos comandos anteriores: Python completó 9
pruebas, con 8 exitosas y 1 omitida por falta de PySide6; Go completó
`chatlan/server_go/internal/protocol` correctamente. Las pruebas Python usan
sockets reales de loopback y bases SQLite temporales. Las pruebas Go solo cubren
el paquete de protocolo disponible.

## Cobertura pendiente y límites

- No se ejecutó una prueba física entre equipos de una LAN.
- La prueba GUI no se ejecutó en este entorno porque falta PySide6.
- No hay servidor Go completo que probar en integración; solo existe el codec.
- Esta matriz no sustituye pruebas de TLS, autenticación ni resiliencia de disco:
  esas capacidades no forman parte del alcance actual.

Para comprender qué valida cada requisito, consultar
[requisitos y casos de uso](requisitos-y-casos-de-uso.md); para el flujo de
red, consultar [protocolo](protocolo.md) y el
[diagrama de secuencia](diagramas/recorrido.html).
