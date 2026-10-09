"""Historial oficial. El gestor serializa las operaciones con su bloqueo."""
import sqlite3
import uuid
from pathlib import Path
from common.protocol import now

COLORS = ["#3498DB", "#E74C3C", "#27AE60", "#9B59B6", "#E67E22",
          "#16A085", "#C0392B", "#8E44AD", "#2C3E50", "#B77900"]


class Database:
    """Administra identidades e historial persistente en una base SQLite."""

    def __init__(self, path):
        """Crea el archivo, inicializa el esquema y recupera la identidad del servidor."""

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # El servidor comparte esta conexión entre hilos bajo el bloqueo de ChatServer.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # WAL favorece las lecturas; las claves foráneas protegen la relación del historial.
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
        # El contexto confirma ambas sentencias juntas o revierte si alguna falla.
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO metadata VALUES ('server_id', ?)", (str(uuid.uuid4()),))
            # Tras reiniciar el proceso no puede quedar ningún usuario realmente conectado.
            self.conn.execute("UPDATE usuarios SET estado='OFFLINE'")
        self.server_id = self.conn.execute("SELECT valor FROM metadata WHERE clave='server_id'").fetchone()[0]

    def register(self, device_id, nombre, ip):
        """Registra un dispositivo nuevo o actualiza su sesión y devuelve su usuario."""

        date = now()
        with self.conn:
            existing = self.conn.execute("SELECT * FROM usuarios WHERE device_id=?", (device_id,)).fetchone()
            if existing is None:
                count = self.conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
                # El módulo reparte la paleta de forma circular y estable al registrar.
                self.conn.execute("INSERT INTO usuarios(device_id,nombre,ip,color,fecha_registro,ultima_conexion,estado) VALUES(?,?,?,?,?,?,'ONLINE')",
                                  (device_id, nombre, ip, COLORS[count % len(COLORS)], date, date))
            else:
                self.conn.execute("UPDATE usuarios SET nombre=?,ip=?,ultima_conexion=?,estado='ONLINE' WHERE device_id=?",
                                  (nombre, ip, date, device_id))
        return dict(self.conn.execute("SELECT * FROM usuarios WHERE device_id=?", (device_id,)).fetchone())

    def offline(self, device_id):
        """Marca un dispositivo como desconectado y registra cuándo ocurrió."""

        with self.conn:
            self.conn.execute("UPDATE usuarios SET estado='OFFLINE',ultima_conexion=? WHERE device_id=?", (now(), device_id))

    def last_id(self):
        """Devuelve el último identificador de mensaje, o cero si no hay historial."""

        return self.conn.execute("SELECT COALESCE(MAX(id),0) FROM mensajes").fetchone()[0]

    def history(self, after, limit=40):
        """Devuelve hasta ``limit`` mensajes posteriores al cursor ``after``."""

        # El JOIN incorpora device_id sin duplicarlo en la tabla de mensajes.
        return [dict(row) for row in self.conn.execute(
            "SELECT m.*,u.device_id FROM mensajes m JOIN usuarios u ON u.id=m.usuario_id WHERE m.id>? ORDER BY m.id LIMIT ?", (after, limit))]

    def save_message(self, user, content, request_id):
        """Persiste un mensaje de forma idempotente e indica si fue una inserción nueva."""

        with self.conn:
            # La restricción UNIQUE convierte un reintento del cliente en una no-op segura.
            cursor = self.conn.execute("INSERT OR IGNORE INTO mensajes(usuario_id,contenido,fecha,client_message_id,nombre,color) VALUES(?,?,?,?,?,?)",
                                       (user['id'], content, now(), request_id, user['nombre'], user['color']))
        # Se consulta también tras un reintento para devolver el mismo mensaje confirmado.
        row = self.conn.execute("SELECT m.*,u.device_id FROM mensajes m JOIN usuarios u ON u.id=m.usuario_id WHERE usuario_id=? AND client_message_id=?",
                                (user['id'], request_id)).fetchone()
        # SQLite informa una fila afectada únicamente cuando INSERT OR IGNORE insertó.
        return dict(row), cursor.rowcount == 1

    def close(self):
        """Cierra la conexión persistente con SQLite."""

        self.conn.close()
