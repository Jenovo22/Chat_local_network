# Protocolo TCP v1

UTF-8, un objeto JSON por línea, terminado con LF. Cada trama generada contiene:

```json
{"tipo":"MESSAGE","timestamp":"2026-09-12T18:00:00.000+00:00","payload":{"contenido":"Hola"}}
```

`timestamp` lo genera el emisor; la fecha oficial de los mensajes la genera el
servidor. Por compatibilidad con los ejemplos de LOGIN/SYNC, el receptor no exige
`timestamp`. Sí exige `tipo` texto y `payload` objeto. Máximo 1 MiB por trama;
contenido no vacío de hasta 4000 caracteres, nombre no vacío de hasta 60.

| Comando | Dirección | Payload |
| --- | --- | --- |
| LOGIN | Cliente → servidor | `device_id` UUID, `nombre`; `ip` opcional se ignora en favor del socket |
| LOGIN_OK | Servidor → cliente | `color`, `ultimo_id`, `server_id`, `usuario` |
| SYNC | Cliente → servidor | `ultimo_id`: entero no negativo, no mayor que el máximo oficial |
| SYNC_RESPONSE | Servidor → cliente | `mensajes`, `ultimo_id` de la página, `hay_mas` |
| MESSAGE | Cliente → servidor | `contenido`, `client_message_id` UUID de envío |
| MESSAGE | Servidor → clientes sincronizados | Mensaje oficial descrito debajo |
| MESSAGE_ACK | Servidor → emisor | `client_message_id`, `id` oficial |
| PING / PONG | Cliente → servidor / respuesta | `{}` |
| LOGOUT | Cliente → servidor | `{}`; cierre sin respuesta |
| ERROR | Servidor → cliente | `codigo`, `detalle`; después cierra la conexión |

Mensaje oficial:

```json
{
  "id": 251,
  "usuario_id": 1,
  "device_id": "267f4562-43a6-41a9-968b-3acf463d9911",
  "nombre": "Carlos",
  "color": "#3498DB",
  "contenido": "Hola equipo",
  "fecha": "2026-09-12T18:00:00.000+00:00",
  "client_message_id": "508263aa-d227-4ee0-ad64-146745637b74"
}
```

LOGIN debe ser el primer comando. Cada UUID sólo admite una sesión simultánea.
SYNC es obligatorio antes de MESSAGE. SYNC_RESPONSE contiene hasta 40 mensajes;
se repite SYNC con el cursor de la respuesta mientras `hay_mas` sea verdadero.

El cliente oficial siempre incluye `client_message_id` y lo persiste antes de
enviar. Un cliente mínimo puede omitirlo: el servidor genera uno, pero ese cliente
pierde la garantía de deduplicación en sus reintentos. Un UUID repetido confirma
el mensaje original, aunque el contenido del reintento sea distinto.

Códigos de error: `SERVER_FULL` al superar diez conexiones; `PROTOCOL_ERROR`
para campos inválidos, UUID ya conectado, JSON inválido o comandos fuera de
secuencia. Los errores de almacenamiento se registran y cierran la conexión,
sin confirmar una escritura fallida.
