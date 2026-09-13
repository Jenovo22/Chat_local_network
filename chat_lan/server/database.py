"""Historial oficial. El gestor serializa las operaciones con su bloqueo."""
import sqlite3
import uuid
from pathlib import Path
from common.protocol import now

COLORS = ["#3498DB", "#E74C3C", "#27AE60", "#9B59B6", "#E67E22",
          "#16A085", "#C0392B", "#8E44AD", "#2C3E50", "#B77900"]


class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS metadata (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY, device_id TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL, ip TEXT NOT NULL, color TEXT NOT NULL,
                fecha_registro TEXT NOT NULL, ultima_conexion TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'OFFLINE');
            CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                contenido TEXT NOT NULL, fecha TEXT NOT NULL,
                client_message_id TEXT NOT NULL, nombre TEXT NOT NULL, color TEXT NOT NULL,
                UNIQUE(usuario_id, client_message_id));
        """)
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO metadata VALUES ('server_id', ?)", (str(uuid.uuid4()),))
            self.conn.execute("UPDATE usuarios SET estado='OFFLINE'")
        self.server_id = self.conn.execute("SELECT valor FROM metadata WHERE clave='server_id'").fetchone()[0]

    def register(self, device_id, nombre, ip):
        date = now()
        with self.conn:
            existing = self.conn.execute("SELECT * FROM usuarios WHERE device_id=?", (device_id,)).fetchone()
            if existing is None:
                count = self.conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
                self.conn.execute("INSERT INTO usuarios(device_id,nombre,ip,color,fecha_registro,ultima_conexion,estado) VALUES(?,?,?,?,?,?,'ONLINE')",
                                  (device_id, nombre, ip, COLORS[count % len(COLORS)], date, date))
            else:
                self.conn.execute("UPDATE usuarios SET nombre=?,ip=?,ultima_conexion=?,estado='ONLINE' WHERE device_id=?",
                                  (nombre, ip, date, device_id))
        return dict(self.conn.execute("SELECT * FROM usuarios WHERE device_id=?", (device_id,)).fetchone())

    def offline(self, device_id):
        with self.conn:
            self.conn.execute("UPDATE usuarios SET estado='OFFLINE',ultima_conexion=? WHERE device_id=?", (now(), device_id))

    def last_id(self):
        return self.conn.execute("SELECT COALESCE(MAX(id),0) FROM mensajes").fetchone()[0]

    def history(self, after, limit=40):
        return [dict(row) for row in self.conn.execute(
            "SELECT m.*,u.device_id FROM mensajes m JOIN usuarios u ON u.id=m.usuario_id WHERE m.id>? ORDER BY m.id LIMIT ?", (after, limit))]

    def save_message(self, user, content, request_id):
        with self.conn:
            cursor = self.conn.execute("INSERT OR IGNORE INTO mensajes(usuario_id,contenido,fecha,client_message_id,nombre,color) VALUES(?,?,?,?,?,?)",
                                       (user['id'], content, now(), request_id, user['nombre'], user['color']))
        row = self.conn.execute("SELECT m.*,u.device_id FROM mensajes m JOIN usuarios u ON u.id=m.usuario_id WHERE usuario_id=? AND client_message_id=?",
                                (user['id'], request_id)).fetchone()
        return dict(row), cursor.rowcount == 1

    def close(self):
        self.conn.close()
