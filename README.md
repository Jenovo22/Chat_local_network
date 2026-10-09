# Proyecto de chat TCP en LAN

La implementación activa está en [chat_lan](chat_lan/README.md): servidor TCP
Python con SQLite, clientes de consola y PySide6, sincronización y pruebas. La
documentación verificable del módulo se encuentra en
[chat_lan/docs](chat_lan/docs/descripcion-funcional.md).

```bash
cd chat_lan
python3 server/main.py
```

En otra terminal, desde `chat_lan`:

```bash
python3 client/main.py --console --name Jerónimo
```

El cliente gráfico listo para abrir y compartir está en
[ChatLAN](chat_lan/dist/ChatLAN). El paquete de distribución es
[ChatLAN-Ubuntu-x86_64.tar.gz](chat_lan/dist/ChatLAN-Ubuntu-x86_64.tar.gz).
Consulta la guía del proyecto para los requisitos y la reconstrucción.
El archivo `servidor.py` y el historial de texto corresponden al prototipo
previo; no utilizan el nuevo protocolo ni se importan automáticamente al
historial SQLite.
