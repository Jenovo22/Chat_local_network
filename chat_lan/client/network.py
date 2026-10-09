"""Cliente sin dependencia gráfica; un único hilo posee el socket."""
import socket
import threading
import time
from common.protocol import Reader, encode, ProtocolError, MAX_CONTENT


class NetworkClient:
    """Sincroniza la base local con el servidor desde un hilo de fondo."""

    def __init__(self, database, host, port, name, callback=None):
        """Configura la conexión y el callback que cruza hacia la interfaz."""

        if not name.strip() or len(name) > 60:
            raise ValueError('El nombre debe tener entre 1 y 60 caracteres')
        self.db, self.host, self.port, self.name = database, host, port, name.strip()
        # La capa de red solo publica eventos; consola y Qt deciden cómo mostrarlos.
        self.callback = callback or (lambda kind, payload: None)
        self.stop_event = threading.Event()
        self.connected = threading.Event()
        self.thread = None
        self.sock = None
        self.db.set('nombre', self.name)

    def emit(self, kind, payload):
        """Entrega un evento sin acoplar el transporte a una interfaz concreta."""

        self.callback(kind, payload)

    def start(self):
        """Inicia el ciclo de conexión sin bloquear el hilo de la interfaz."""

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def send_message(self, content):
        """Valida y encola un mensaje; el hilo de red lo enviará al conectarse."""

        if not content.strip() or len(content) > MAX_CONTENT:
            raise ValueError(f'Escribe entre 1 y {MAX_CONTENT} caracteres')
        request_id = self.db.enqueue(content.strip())
        self.emit('pending', {'cantidad': len(self.db.pending())})
        return request_id

    def _send(self, kind, payload):
        """Codifica un paquete completo antes de escribirlo en el socket."""

        # sendall evita dejar una trama parcialmente escrita; encode añade el
        # encuadre que Reader necesita para separar paquetes del flujo TCP.
        self.sock.sendall(encode(kind, payload))

    def _run(self):
        """Mantiene conexión, sincronización y reintentos hasta recibir ``stop``."""

        delay = 1
        while not self.stop_event.is_set():
            try:
                self.emit('status', {'texto': 'Conectando…'})
                self.sock = socket.create_connection((self.host, self.port), timeout=3)
                self.sock.settimeout(1)
                # Reader conserva bytes incompletos entre lecturas y entrega una
                # trama solo cuando el flujo TCP contiene el paquete completo.
                reader = Reader(self.sock)
                self._send('LOGIN', {'device_id': self.db.device_id, 'nombre': self.name})
                # Evita reenviar en cada vuelta los pendientes ya escritos durante
                # esta conexión. Tras reconectar se crea vacío para reintentarlos.
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
                                # La siguiente página parte del cursor que se acaba
                                # de confirmar junto con este lote en SQLite.
                                self._send('SYNC', {'ultimo_id': self.db.cursor()})
                            else:
                                # La cola offline se libera solo después de completar
                                # el historial, preservando el orden de sincronización.
                                delay = 1
                                self.connected.set()
                                self.emit('status', {'texto': 'Conectado · historial sincronizado'})
                        elif kind == 'MESSAGE':
                            self.db.store([payload])
                            self.emit('messages', {'mensajes': [payload]})
                        elif kind == 'MESSAGE_ACK':
                            # El mismo client_message_id enlaza cola, reintento y acuse.
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
                    # monotonic no retrocede si cambia el reloj del sistema.
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
                # Cada intento deja un estado limpio antes de aplicar la espera.
                self.connected.clear()
                if self.sock:
                    self.sock.close()
                    self.sock = None
            if self.stop_event.wait(delay):
                break
            # La espera exponencial limita intentos repetidos, con un máximo de 15 s.
            delay = min(delay * 2, 15)

    def stop(self):
        """Solicita la salida y espera brevemente a que termine el hilo."""

        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
