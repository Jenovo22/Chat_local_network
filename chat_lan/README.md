# Chat LAN TCP

Prototipo para Python 3.12+ y Ubuntu: servidor TCP central, hasta 10 conexiones,
clientes de consola y PySide6, historial oficial SQLite y copias locales.
Los nombres pueden repetirse: cada instalación conserva un UUID y un color.

## Inicio rápido

Desde esta carpeta (`chat_lan`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r client/requirements.txt
python server/main.py
```

En otra terminal, con el mismo entorno activado:

```bash
python client/main.py
```

Escribe tu nombre y pulsa **Conectar**. Para otro equipo de la LAN, escribe la IP
privada del equipo que ejecuta el servidor. El puerto predeterminado es 5000.
El servidor escucha en `0.0.0.0`; esta es una dirección de escucha, no la IP que
se introduce en los clientes. `hostname -I` permite consultar las IP del servidor.
Todos los dispositivos deben poder acceder al puerto TCP 5000: revisa el firewall
y el aislamiento de clientes del punto de acceso si no pueden conectarse.

El servidor y el cliente de consola no requieren instalar paquetes:

```bash
python3 server/main.py --host 0.0.0.0 --port 5000
python3 client/main.py --console --host 127.0.0.1 --name Carlos
```

En consola, `/salir` cierra la sesión. `Ctrl+C` detiene el servidor.
También funcionan `python -m server.main` y `python -m client.main` desde esta carpeta.

## Varios clientes en un equipo

Cada dispositivo utiliza su propia base local. Para simular instalaciones
independientes en la misma máquina, especifica archivos distintos:

```bash
python3 client/main.py --console --name Carlos --db data/carlos_a.db
python3 client/main.py --console --name Carlos --db data/carlos_b.db
```

Con PySide6 instalado, omite `--console` para abrir ventanas independientes.
Una segunda conexión con el mismo UUID se rechaza. La conexión número 11 recibe
`SERVER_FULL`. Las conexiones que aún están iniciando sesión también ocupan cupo.

## Persistencia y recuperación

- Servidor: `chat_lan/data/chat_server.db`, configurable con `--db`.
- Cliente: `$XDG_DATA_HOME/chat_lan/chat_local.db`, o
  `~/.local/share/chat_lan/chat_local.db` si la variable no está definida.
- El UUID se genera una sola vez y se conserva en la base local. No copies esa
  base a otro dispositivo si quieres una identidad diferente.
- El servidor conserva usuarios, colores, mensajes y un identificador de base.
- La interfaz muestra el historial local incluso sin conexión. Tras pulsar
  **Conectar**, los mensajes enviados durante un corte se guardan como pendientes.
- La reconexión reintenta con intervalos de 1 a 15 segundos. Primero descarga
  únicamente mensajes posteriores al cursor local, en páginas de hasta 40.
  Después reenvía pendientes. Cada envío tiene un UUID: los reintentos no duplican
  mensajes en el servidor. Un envío confirmado se elimina de la cola.
- Fecha del servidor en UTC e ID incremental definen el orden oficial. Los IDs
  pueden tener saltos, por ejemplo tras reintentos; no se presupone continuidad.
- Para otra conversación/servidor usa otra base local con `--db`. Si el servidor
  tiene una base nueva, el cliente reemplaza su caché y sincroniza desde cero;
  los pendientes se conservan y se envían al servidor al que se conecta.

Para respaldar el historial, detén el proceso y copia su base SQLite. Conserva
la base del servidor para mantener los colores y la identidad del historial.

## Estructura

```text
chat_lan/
├── common/protocol.py       # Enmarcado y validación compartidos
├── server/
│   ├── main.py
│   ├── database.py
│   ├── socket_manager.py
│   ├── user_manager.py
│   ├── protocol.py
│   └── requirements.txt
├── client/
│   ├── main.py              # GUI predeterminada; --console opcional
│   ├── gui.py
│   ├── network.py
│   ├── local_database.py
│   ├── protocol.py
│   └── requirements.txt
├── tests/test_chat.py
└── docs/
    ├── arquitectura.md
    ├── protocolo.md
    └── diagramas/secuencia.mmd
```

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

Las ocho pruebas usan sockets reales en loopback y bases temporales. Cubren
2/5/10 clientes, límite de conexiones, nombres duplicados y colores, orden de
mensajes concurrentes, cola persistente, reconexión, reinicio del servidor,
sincronización paginada, idempotencia, login inválido y fragmentación TCP/Unicode.
No necesitan PySide6. Se ejecutaron satisfactoriamente con Python 3.12.3.

La interfaz fue probada con dos ventanas PySide6 en modo sin pantalla: envío,
recepción, representación segura de texto, persistencia y reconexión automática.
Con PySide6 instalado se ejecutan nueve pruebas, incluyendo la prueba gráfica.
También se probaron dos procesos del ejecutable autónomo: apertura de la GUI,
conexión automática, recepción y persistencia de un mensaje real.
La prueba física entre varios equipos de una LAN queda pendiente.

## Ejecutable para compartir

La entrega está en `dist/ChatLAN` y `dist/ChatLAN-Ubuntu-x86_64.tar.gz`.
Está compilada para **Ubuntu 24.04 x86_64** (glibc 2.39). No requiere instalar
Python, PySide6 ni los archivos del proyecto en el equipo receptor. Necesita un
escritorio Linux compatible. No es un ejecutable universal para Windows, macOS,
Android, iPhone, ARM ni distribuciones Linux anteriores a la base de compilación.

1. Comparte el archivo `ChatLAN-Ubuntu-x86_64.tar.gz`.
2. El usuario lo extrae y abre `ChatLAN` con doble clic.
3. Introduce la IP del servidor y su nombre, y pulsa **Conectar**.

El puerto 5000 se utiliza automáticamente. La siguiente vez, la aplicación
recuerda los datos y conecta sola. Para cambiarlos, pulsa **Desconectar**.
El historial y el UUID se crean en la carpeta personal de cada usuario; el
paquete no incluye ninguna identidad ni base de datos preexistente.
Si el gestor de archivos pregunta, permite ejecutar el archivo como programa
(Propiedades → Permisos). Extraer el tar conserva ese permiso normalmente.
El servidor debe estar iniciado y accesible en la misma LAN.

Para reconstruir el ejecutable en este entorno:

```bash
.venv/bin/python -m pip install -r packaging/requirements.txt
.venv/bin/python packaging/build.py
.venv/bin/python packaging/verify_executable.py
```

La compilación incluye una copia de `libxcb-cursor.so.0` del paquete oficial
Ubuntu `libxcb-cursor0`, extraída bajo `packaging/vendor`. El resto de bibliotecas
Qt y Python necesarias se detectan al empaquetar. Para reproducir esa extracción:

```bash
mkdir -p packaging/vendor
cd packaging/vendor
apt-get download libxcb-cursor0
dpkg-deb -x libxcb-cursor0_*.deb extracted
```

Para Windows o macOS se debe ejecutar `packaging/build.py` en ese sistema con
Python, PySide6 y PyInstaller instalados. Eso genera un binario de esa plataforma;
no se ha compilado ni validado esa variante en esta entrega.

## Alcance del prototipo

Usa una LAN de confianza: el protocolo no incorpora TLS ni autenticación mediante
contraseña; un UUID es identidad persistente, no una credencial. No expongas el
puerto directamente a Internet. No se incluyen adjuntos, salas ni edición/borrado.
Los mensajes admiten hasta 4000 caracteres y las tramas hasta 1 MiB.

Los primeros diez dispositivos registrados reciben colores distintos; la paleta
se reutiliza para dispositivos registrados posteriormente. El UUID visible
permite distinguirlos. El color asignado a cada usuario registrado no cambia.

Las publicaciones se serializan para conservar el orden. Un cliente lento puede
retrasar temporalmente al resto hasta que falle su envío por timeout; una futura
versión puede añadir colas de salida por cliente. La GUI carga todo el historial
local al abrirse, por lo que historiales muy grandes requieren paginación visual.
La recuperación cubre cortes de conexión y reinicios normales, no pérdida del
archivo SQLite o fallos del medio de almacenamiento.
