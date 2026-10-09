"""Servidor con un hilo por conexión y publicación ordenada tras persistir."""
import logging
import socket
import threading
import uuid
from common.protocol import Reader, encode, ProtocolError, text_field, MAX_CONTENT
from server.user_manager import login

log = logging.getLogger(__name__)


class Peer:
    """Mantiene el socket y el estado de protocolo de una conexión cliente."""

    def __init__(self, sock):
        """Crea una conexión aún no autenticada ni preparada para mensajes."""

        self.sock = sock
        self.user = None
        self.ready = False

    def send(self, tipo, payload):
        """Codifica y envía una trama completa al cliente."""

        # sendall reintenta internamente hasta entregar todos los bytes o fallar.
        self.sock.sendall(encode(tipo, payload))

    def close(self):
        """Interrumpe ambos sentidos del socket y libera su descriptor."""

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class ChatServer:
    """Coordina conexiones TCP, secuencia del protocolo y acceso compartido a datos."""

    def __init__(self, database, host="0.0.0.0", port=5000, max_clients=10):
        """Configura el servicio sin abrir aún el socket de escucha."""

        self.db = database
        self.host, self.port = host, port
        self.max_clients = max_clients
        # Un RLock serializa estado, base de datos y publicación entre hilos clientes.
        self.lock = threading.RLock()
        self.peers = set()
        self.threads = set()
        self.stopped = threading.Event()
        self.listener = None

    def start(self):
        """Abre el socket de escucha e inicia el hilo que acepta conexiones."""

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Permite reiniciar pronto el proceso aunque el puerto siga en TIME_WAIT.
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        # Si se pidió el puerto 0, el sistema asignó uno que debe publicarse aquí.
        self.port = self.listener.getsockname()[1]
        self.listener.listen(self.max_clients)
        # El timeout permite revisar periódicamente la señal de parada.
        self.listener.settimeout(.5)
        self.accept_thread = threading.Thread(target=self._accept, daemon=True)
        self.accept_thread.start()
        log.info("Servidor iniciado: %s:%s", self.host, self.port)

    def _accept(self):
        """Acepta conexiones y crea un hilo de atención para cada cliente admitido."""

        while not self.stopped.is_set():
            try:
                sock, address = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            sock.settimeout(15)
            peer = Peer(sock)
            with self.lock:
                if len(self.peers) >= self.max_clients:
                    try:
                        peer.send("ERROR", {"codigo": "SERVER_FULL", "detalle": "Máximo 10 conexiones"})
                    except OSError:
                        pass
                    peer.close()
                    continue
                self.peers.add(peer)
                # Cada hilo recibe sólo su conexión; el RLock protege el estado común.
                thread = threading.Thread(target=self._handle, args=(peer, address), daemon=True)
                self.threads.add(thread)
                thread.start()

    def _handle(self, peer, address):
        """Lee tramas de un cliente hasta su salida, error o parada del servidor."""

        reader = Reader(peer.sock)
        try:
            while not self.stopped.is_set():
                packet = reader.receive()
                # El despacho completo queda ordenado respecto de los demás clientes.
                with self.lock:
                    if not self._dispatch(peer, address, packet):
                        break
        except (OSError, EOFError):
            pass
        except ProtocolError as exc:
            with self.lock:
                peer.ready = False
                try:
                    peer.send("ERROR", {"codigo": "PROTOCOL_ERROR", "detalle": str(exc)})
                except OSError:
                    pass
        except Exception:
            log.exception("Error atendiendo a %s", address)
        finally:
            # La limpieza se ejecuta tanto en cierres normales como ante errores.
            with self.lock:
                self.peers.discard(peer)
                if peer.user:
                    self.db.offline(peer.user['device_id'])
                self.threads.discard(threading.current_thread())
            peer.close()

    def _dispatch(self, peer, address, packet):
        """Valida la secuencia de un comando y aplica su efecto bajo el bloqueo global."""

        kind, payload = packet['tipo'], packet['payload']
        if peer.user is None:
            if kind != "LOGIN":
                raise ProtocolError("LOGIN debe ser el primer comando")
            device_id = text_field(payload, "device_id", 36)
            try:
                # La conversión también normaliza variantes textuales del mismo UUID.
                device_id = str(uuid.UUID(device_id))
            except ValueError as exc:
                raise ProtocolError("device_id debe ser UUID") from exc
            # La comprensión corta al encontrar el mismo dispositivo ya autenticado.
            if any(p.user and p.user['device_id'] == device_id for p in self.peers):
                raise ProtocolError("El dispositivo ya está conectado")
            peer.user = login(self.db, payload, address[0])
            peer.sock.settimeout(30)
            peer.send("LOGIN_OK", {"color": peer.user['color'], "ultimo_id": self.db.last_id(),
                                   "server_id": self.db.server_id, "usuario": peer.user})
            log.info("Cliente conectado: device=%s nombre=%s color=%s", device_id, peer.user['nombre'], peer.user['color'])
        elif kind == "SYNC":
            after = payload.get('ultimo_id')
            # type(...) evita aceptar bool, que en Python es una subclase de int.
            if type(after) is not int or after < 0 or after > self.db.last_id():
                raise ProtocolError("Cursor de sincronización inválido")
            messages = self.db.history(after)
            # Sin resultados, el cursor válido continúa siendo el solicitado.
            cursor = messages[-1]['id'] if messages else after
            more = cursor < self.db.last_id()
            peer.send("SYNC_RESPONSE", {"mensajes": messages, "ultimo_id": cursor, "hay_mas": more})
            # Sólo se habilita el envío cuando el cliente alcanzó el final del historial.
            peer.ready = not more
        elif kind == "MESSAGE":
            if not peer.ready:
                raise ProtocolError("Debe completar SYNC antes de enviar")
            content = text_field(payload, 'contenido', MAX_CONTENT)
            # El valor predeterminado mantiene compatibilidad con clientes sin id propio.
            request_id = payload.get('client_message_id', str(uuid.uuid4()))
            try:
                request_id = str(uuid.UUID(request_id))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ProtocolError("client_message_id inválido") from exc
            message, created = self.db.save_message(peer.user, content, request_id)
            if created:
                # La copia evita iterar directamente sobre un conjunto que puede cambiar.
                for target in list(self.peers):
                    if target.ready:
                        try:
                            target.send("MESSAGE", message)
                        except OSError:
                            target.close()
            # Un reintento sólo confirma, nunca vuelve a publicar el mensaje.
            peer.send("MESSAGE_ACK", {"client_message_id": request_id, "id": message['id']})
        elif kind == "PING":
            peer.send("PONG", {})
        elif kind == "LOGOUT":
            return False
        else:
            raise ProtocolError("Comando desconocido o fuera de secuencia")
        return True

    def stop(self):
        """Detiene la aceptación, cierra clientes y espera brevemente a los hilos."""

        self.stopped.set()
        if self.listener:
            self.listener.close()
            if hasattr(self, "accept_thread"):
                self.accept_thread.join(timeout=2)
        with self.lock:
            # Las copias permiten liberar el bloqueo antes de esperar a cada hilo.
            peers, threads = list(self.peers), list(self.threads)
            for peer in peers:
                peer.close()
        for thread in threads:
            thread.join(timeout=5)
