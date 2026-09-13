"""Cliente sin dependencia gráfica; un único hilo posee el socket."""
import socket
import threading
import time
from common.protocol import Reader, encode, ProtocolError, MAX_CONTENT


class NetworkClient:
    def __init__(self, database, host, port, name, callback=None):
        if not name.strip() or len(name) > 60:
            raise ValueError('El nombre debe tener entre 1 y 60 caracteres')
        self.db, self.host, self.port, self.name = database, host, port, name.strip()
        self.callback = callback or (lambda kind, payload: None)
        self.stop_event = threading.Event()
        self.connected = threading.Event()
        self.thread = None
        self.sock = None
        self.db.set('nombre', self.name)

    def emit(self, kind, payload):
        self.callback(kind, payload)

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def send_message(self, content):
        if not content.strip() or len(content) > MAX_CONTENT:
            raise ValueError(f'Escribe entre 1 y {MAX_CONTENT} caracteres')
        request_id = self.db.enqueue(content.strip())
        self.emit('pending', {'cantidad': len(self.db.pending())})
        return request_id

    def _send(self, kind, payload):
        self.sock.sendall(encode(kind, payload))

    def _run(self):
        delay = 1
        while not self.stop_event.is_set():
            try:
                self.emit('status', {'texto': 'Conectando…'})
                self.sock = socket.create_connection((self.host, self.port), timeout=3)
                self.sock.settimeout(1)
                reader = Reader(self.sock)
                self._send('LOGIN', {'device_id': self.db.device_id, 'nombre': self.name})
                sent = set()
                last_ping = last_receive = time.monotonic()
                while not self.stop_event.is_set():
                    try:
                        packet = reader.receive()
                    except socket.timeout:
                        packet = None
                    if packet:
                        last_receive = time.monotonic()
                        kind, payload = packet['tipo'], packet['payload']
                        if kind == 'LOGIN_OK':
                            if self.db.use_server(payload['server_id']):
                                self.emit('reset', {})
                            self.db.set('color', payload['color'])
                            self.emit('login', payload)
                            self._send('SYNC', {'ultimo_id': self.db.cursor()})
                        elif kind == 'SYNC_RESPONSE':
                            self.db.store(payload['mensajes'], payload['ultimo_id'])
                            self.emit('messages', {'mensajes': payload['mensajes']})
                            if payload['hay_mas']:
                                self._send('SYNC', {'ultimo_id': self.db.cursor()})
                            else:
                                delay = 1
                                self.connected.set()
                                self.emit('status', {'texto': 'Conectado · historial sincronizado'})
                        elif kind == 'MESSAGE':
                            self.db.store([payload])
                            self.emit('messages', {'mensajes': [payload]})
                        elif kind == 'MESSAGE_ACK':
                            self.db.acknowledge(payload['client_message_id'])
                            sent.discard(payload['client_message_id'])
                            self.emit('pending', {'cantidad': len(self.db.pending())})
                        elif kind == 'ERROR':
                            raise ProtocolError(payload.get('detalle', 'Error del servidor'))
                    if self.connected.is_set():
                        for pending in self.db.pending():
                            if pending['client_message_id'] not in sent:
                                self._send('MESSAGE', pending)
                                sent.add(pending['client_message_id'])
                    current = time.monotonic()
                    if current - last_ping >= 10:
                        self._send('PING', {})
                        last_ping = current
                    if current - last_receive > 25:
                        raise OSError('El servidor no responde')
                try:
                    self._send('LOGOUT', {})
                except OSError:
                    pass
            except (OSError, EOFError, ProtocolError) as exc:
                if not self.stop_event.is_set():
                    self.emit('status', {'texto': f'Sin conexión: {exc}. Reintento en {delay} s.'})
            finally:
                self.connected.clear()
                if self.sock:
                    self.sock.close()
                    self.sock = None
            if self.stop_event.wait(delay):
                break
            delay = min(delay * 2, 15)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
