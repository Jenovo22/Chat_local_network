"""Caché y bandeja de salida persistentes, compartidas por GUI e hilo de red."""
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from common.protocol import now


class LocalDatabase:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS mensajes(id INTEGER PRIMARY KEY, datos TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pendientes(
                client_message_id TEXT PRIMARY KEY, contenido TEXT NOT NULL, fecha TEXT NOT NULL);
        ''')
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO metadata VALUES('device_id', ?)", (str(uuid.uuid4()),))
        self.device_id = self.get('device_id')

    def get(self, key, default=None):
        with self.lock:
            row = self.conn.execute('SELECT valor FROM metadata WHERE clave=?', (key,)).fetchone()
            return row[0] if row else default

    def set(self, key, value):
        with self.lock, self.conn:
            self.conn.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', (key, str(value)))

    def use_server(self, server_id):
        with self.lock, self.conn:
            changed = self.get('server_id') != server_id
            if changed:
                self.conn.execute('DELETE FROM mensajes')
                self.conn.execute("INSERT OR REPLACE INTO metadata VALUES('ultimo_mensaje_recibido','0')")
                self.conn.execute("INSERT OR REPLACE INTO metadata VALUES('server_id',?)", (server_id,))
            return changed

    def cursor(self):
        return int(self.get('ultimo_mensaje_recibido', '0'))

    def store(self, messages, cursor=None):
        # Cursor e historial se confirman en una sola transacción.
        with self.lock, self.conn:
            for message in messages:
                self.conn.execute('INSERT OR REPLACE INTO mensajes VALUES(?,?)', (message['id'], json.dumps(message, ensure_ascii=False)))
                if message['device_id'] == self.device_id:
                    self.conn.execute('DELETE FROM pendientes WHERE client_message_id=?', (message['client_message_id'],))
            last = max([self.cursor(), cursor or 0] + [m['id'] for m in messages])
            self.conn.execute("INSERT OR REPLACE INTO metadata VALUES('ultimo_mensaje_recibido',?)", (str(last),))

    def history(self):
        with self.lock:
            return [json.loads(row[0]) for row in self.conn.execute('SELECT datos FROM mensajes ORDER BY id')]

    def enqueue(self, content):
        request_id = str(uuid.uuid4())
        with self.lock, self.conn:
            self.conn.execute('INSERT INTO pendientes VALUES(?,?,?)', (request_id, content, now()))
        return request_id

    def pending(self):
        with self.lock:
            return [{'client_message_id': row[0], 'contenido': row[1]} for row in self.conn.execute(
                'SELECT client_message_id,contenido FROM pendientes ORDER BY rowid')]

    def acknowledge(self, request_id):
        with self.lock, self.conn:
            self.conn.execute('DELETE FROM pendientes WHERE client_message_id=?', (request_id,))

    def close(self):
        with self.lock:
            self.conn.close()
