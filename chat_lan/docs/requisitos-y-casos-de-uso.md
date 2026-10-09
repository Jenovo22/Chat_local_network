# Requisitos y casos de uso

Este documento deriva requisitos del comportamiento implementado; no amplía el
alcance del prototipo. La trazabilidad de cada identificador está en la
[matriz de verificación](verificacion.md).

El [recorrido interactivo de Archify](../../.archify/sequence-chat-lan-20261009-081900/sequence-chat-lan.html)
visualiza CU-01 a CU-04 sin reemplazar estos requisitos ni su trazabilidad.

## Casos de uso

### CU-01 — Conectarse e identificar el dispositivo

**Actor:** persona usuaria con un cliente.<br>
**Flujo:** abre consola o GUI, aporta nombre y destino, y el cliente envía
`LOGIN` con el UUID persistente. El servidor registra o actualiza al usuario y
devuelve identidad, color, cursor máximo e identidad de la base.<br>
**Reglas:** los nombres no son únicos; el UUID debe ser válido y no puede estar
conectado simultáneamente.

### CU-02 — Sincronizar el historial

**Actor:** cliente conectado.<br>
**Flujo:** solicita `SYNC` desde el cursor local, persiste cada página recibida
y repite hasta que `hay_mas` sea falso. Solo entonces el servidor habilita el
flujo de publicaciones para ese cliente.

### CU-03 — Enviar y recibir un mensaje

**Actor:** cliente sincronizado.<br>
**Flujo:** guarda el texto y un UUID de envío como pendiente, envía `MESSAGE`,
y recibe la publicación oficial con el mismo UUID. Al almacenarla localmente,
el cliente elimina el pendiente confirmado.

### CU-04 — Recuperarse de una desconexión

**Actor:** cliente que pierde conectividad.<br>
**Flujo:** conserva los pendientes, reintenta con espera progresiva, sincroniza
antes de reenviar y usa el mismo UUID de envío. La confirmación posterior
elimina el pendiente sin volver a publicar el mensaje.

## Requisitos trazables

| ID | Requisito |
| --- | --- |
| RF-01 | El sistema debe registrar la identidad persistente del dispositivo y permitir nombres visibles repetidos. |
| RF-02 | El servidor Python debe rechazar sesiones simultáneas del mismo UUID y limitar las conexiones a diez. |
| RF-03 | Un cliente debe sincronizar el historial oficial por cursor, en páginas de hasta 40 mensajes, antes de publicar o enviar mensajes. |
| RF-04 | El cliente debe persistir historial, cursor e intentos pendientes en SQLite local. |
| RF-05 | El servidor debe persistir un mensaje antes de publicarlo y confirmar su UUID de envío. |
| RF-06 | Reintentar el mismo UUID de envío no debe crear una segunda publicación. |
| RF-07 | El protocolo debe aceptar tramas JSON UTF-8 delimitadas por LF, incluso fragmentadas o agrupadas, y rechazar JSON inválido o tramas sobredimensionadas. |
| RF-08 | Debe existir un cliente de consola; la GUI PySide6 debe usar el mismo flujo de red y persistencia cuando su dependencia esté disponible. |
| RG-01 | El codec Go debe codificar y decodificar el contrato básico de trama compatible con el codec Python. |

## Restricciones y fuera de alcance

| ID | Restricción |
| --- | --- |
| RNF-01 | La comunicación está pensada para una LAN de confianza; no incorpora TLS ni contraseñas. |
| RNF-02 | El contenido no vacío admite hasta 4000 caracteres y una trama hasta 1 MiB. |
| RNF-03 | No se entregan salas, adjuntos, edición ni borrado. |
| RNF-04 | Go no implementa aún base de datos, servidor TCP, CLI ni clientes; solo codec. |

Consulta [protocolo](protocolo.md) para los mensajes de red y
[arquitectura](arquitectura.md) para los mecanismos que satisfacen estos
requisitos.
