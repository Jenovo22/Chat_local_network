"""Caché y bandeja de salida persistentes, compartidas por GUI e hilo de red."""
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from common.protocol import now


class LocalDatabase:
    """Conserva identidad, historial y envíos pendientes entre ejecuciones."""

    def __init__(self, path):
        """Abre la base local e inicializa su esquema y la identidad del dispositivo."""

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # La GUI y el hilo de red comparten una conexión. El RLock serializa su uso
        # y permite que una operación protegida llame a otra que también toma el bloqueo.
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        # WAL permite que las lecturas convivan mejor con las escrituras frecuentes.
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS mensajes(id INTEGER PRIMARY KEY, datos TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pendientes(
                client_message_id TEXT PRIMARY KEY, contenido TEXT NOT NULL, fecha TEXT NOT NULL);
        ''')
        with self.conn:
            # INSERT OR IGNORE conserva la misma identidad en aperturas posteriores.
            self.conn.execute("INSERT OR IGNORE INTO metadata VALUES('device_id', ?)", (str(uuid.uuid4()),))
        self.device_id = self.get('device_id')

    def get(self, key, default=None):
        """Obtiene un metadato o devuelve ``default`` cuando todavía no existe."""

        with self.lock:
            row = self.conn.execute('SELECT valor FROM metadata WHERE clave=?', (key,)).fetchone()
            return row[0] if row else default

    def set(self, key, value):
        """Guarda un metadato como texto dentro de una transacción protegida."""

        # Ambos contextos abarcan la misma operación: el bloqueo evita accesos
        # concurrentes y la conexión confirma o revierte la transacción.
        with self.lock, self.conn:
            self.conn.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', (key, str(value)))

    def use_server(self, server_id):
        """Cambia el servidor asociado y descarta el historial de otro servidor."""

        with self.lock, self.conn:
            changed = self.get('server_id') != server_id
            if changed:
                # Los identificadores de mensajes solo son comparables dentro del
                # historial de un servidor, por eso también se reinicia el cursor.
                self.conn.execute('DELETE FROM mensajes')
                self.conn.execute("INSERT OR REPLACE INTO metadata VALUES('ultimo_mensaje_recibido','0')")
                self.conn.execute("INSERT OR REPLACE INTO metadata VALUES('server_id',?)", (server_id,))
            return changed

    def cursor(self):
        """Devuelve el último identificador confirmado por la sincronización."""

        return int(self.get('ultimo_mensaje_recibido', '0'))

    def store(self, messages, cursor=None):
        """Persiste mensajes recibidos y avanza el cursor de forma atómica."""

        # Cursor e historial se confirman en una sola transacción: nunca queda un
        # cursor avanzado si los mensajes correspondientes no llegaron a guardarse.
        with self.lock, self.conn:
            for message in messages:
                self.conn.execute('INSERT OR REPLACE INTO mensajes VALUES(?,?)', (message['id'], json.dumps(message, ensure_ascii=False)))
                if message['device_id'] == self.device_id:
                    # Recibir el mensaje propio desde el servidor también confirma
                    # su entrega, incluso si se perdió el acuse explícito.
                    self.conn.execute('DELETE FROM pendientes WHERE client_message_id=?', (message['client_message_id'],))
            # Se conserva el mayor cursor conocido aunque la respuesta venga vacía
            # o se vuelva a procesar un lote ya almacenado.
            last = max([self.cursor(), cursor or 0] + [m['id'] for m in messages])
            self.conn.execute("INSERT OR REPLACE INTO metadata VALUES('ultimo_mensaje_recibido',?)", (str(last),))

    def history(self):
        """Reconstruye en orden el historial disponible sin conexión."""

        with self.lock:
            return [json.loads(row[0]) for row in self.conn.execute('SELECT datos FROM mensajes ORDER BY id')]

    def enqueue(self, content):
        """Añade un envío durable y devuelve su identificador idempotente."""

        # El identificador viaja en cada reintento para que el servidor pueda
        # reconocer la misma operación y no crear mensajes duplicados.
        request_id = str(uuid.uuid4())
        with self.lock, self.conn:
            self.conn.execute('INSERT INTO pendientes VALUES(?,?,?)', (request_id, content, now()))
        return request_id

    def pending(self):
        """Devuelve la bandeja de salida en el mismo orden en que fue creada."""

        with self.lock:
            return [{'client_message_id': row[0], 'contenido': row[1]} for row in self.conn.execute(
                'SELECT client_message_id,contenido FROM pendientes ORDER BY rowid')]

    def acknowledge(self, request_id):
        """Retira de la bandeja el envío confirmado por el servidor."""

        with self.lock, self.conn:
            self.conn.execute('DELETE FROM pendientes WHERE client_message_id=?', (request_id,))

    def close(self):
        """Cierra de forma segura la conexión SQLite compartida."""

        with self.lock:
            self.conn.close()
