# Descripción funcional

Chat LAN es un chat TCP para una red local de confianza. Un servidor Python
central conserva el historial oficial en SQLite y los clientes de consola o
PySide6 conservan una copia local para mostrar el historial y reintentar
envíos cuando vuelve la conexión.

## Recorrido principal

1. La persona abre un cliente, indica servidor y nombre, y se conecta.
2. El cliente se identifica con un UUID persistente y sincroniza los mensajes
   posteriores a su cursor local.
3. Envía texto; el cliente lo registra primero como pendiente y el servidor lo
   persiste, publica y confirma.
4. Si se corta la conexión, el cliente conserva los pendientes y, al
   reconectar, sincroniza antes de reenviarlos.

## Capacidades verificadas

| Capacidad | Comportamiento observable | Fuente de evidencia |
| --- | --- | --- |
| Identidad por dispositivo | El UUID local persiste; los nombres visibles pueden repetirse, pero un mismo UUID no puede tener dos sesiones simultáneas. | [Guía de ejecución](guia-de-ejecucion.md), `server/user_manager.py`, `tests/test_chat.py` |
| Historial y sincronización | El servidor ordena por ID oficial y entrega páginas de hasta 40 mensajes. | [arquitectura](arquitectura.md), `server/database.py`, `server/socket_manager.py` |
| Entrega recuperable | Los pendientes locales se reintentan después de sincronizar y `client_message_id` evita republicar un reintento. | `client/network.py`, [protocolo](protocolo.md) |
| Operación de clientes | Hay modo consola y GUI PySide6; ambos usan la misma base local y cliente de red. | `client/main.py`, `client/gui.py` |
| Límites de sesión | El servidor Python admite hasta diez conexiones, incluidas las que aún no hicieron LOGIN. | `server/socket_manager.py`, `tests/test_chat.py` |

## Límites explícitos

- La red debe ser de confianza: no hay TLS ni autenticación por contraseña.
- No hay salas, adjuntos, edición ni borrado de mensajes.
- El orden oficial depende de la SQLite del servidor; la recuperación no cubre
  pérdida del archivo de base de datos ni fallos del medio.
- El módulo [Go](migracion-go.md) contiene únicamente un codec
  experimental compatible; no es un servidor alternativo ejecutable.

## Documentos relacionados

- [Diagrama interactivo de arquitectura](diagramas/arquitectura.html): componentes operativos, persistencia y alcance del codec Go.
- [Diagrama interactivo del recorrido](diagramas/recorrido.html): conexión, sincronización, envío y reintento.
- [Requisitos y casos de uso](requisitos-y-casos-de-uso.md): comportamiento
  esperado y alcance.
- [Arquitectura](arquitectura.md): responsabilidades y sincronización.
- [Protocolo TCP](protocolo.md): contrato en la red.
- [Matriz de verificación](verificacion.md): requisitos, pruebas y límites de
  la evidencia.
