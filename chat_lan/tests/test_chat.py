import socket
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from common.protocol import Reader, ProtocolError, encode, MAX_FRAME
from server.database import Database
from server.socket_manager import ChatServer
from client.local_database import LocalDatabase
from client.network import NetworkClient


def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.03)
    raise AssertionError('No se cumplió la condición dentro del plazo')


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / 'server.db')
        self.server = ChatServer(self.db, '127.0.0.1', 0)
        self.server.start()
        self.clients, self.locals, self.sockets = [], [], []

    def tearDown(self):
        for client in self.clients:
            client.stop()
        for sock in self.sockets:
            sock.close()
        self.server.stop()
        for database in self.locals:
            database.close()
        self.db.close()
        self.tmp.cleanup()

    def local(self, name):
        database = LocalDatabase(self.root / f'{name}.db')
        self.locals.append(database)
        return database

    def connect(self, database):
        client = NetworkClient(database, '127.0.0.1', self.server.port, 'Carlos')
        self.clients.append(client)
        client.start()
        wait_for(client.connected.is_set)
        return client

    def raw(self, device=None):
        sock = socket.create_connection(('127.0.0.1', self.server.port), 3)
        self.sockets.append(sock)
        reader = Reader(sock)
        sock.sendall(encode('LOGIN', {'device_id': device or str(uuid.uuid4()), 'nombre': 'Carlos'}))
        return sock, reader, reader.receive()

    def test_2_5_10_clients_broadcast_and_capacity(self):
        databases = []
        for expected, count in enumerate((2, 5, 10), 1):
            while len(databases) < count:
                database = self.local(str(len(databases)))
                databases.append(database)
                self.connect(database)
            self.clients[0].send_message(f'Hola a {count} clientes 👋')
            wait_for(lambda: all(len(db.history()) == expected for db in databases))
            self.assertTrue(all(db.history() == databases[0].history() for db in databases))
        self.assertEqual(len({db.get('color') for db in databases}), 10)
        sock = socket.create_connection(('127.0.0.1', self.server.port), 3)
        self.sockets.append(sock)
        self.assertEqual(Reader(sock).receive()['payload']['codigo'], 'SERVER_FULL')

    def test_reconnect_outbox_and_persistent_identity(self):
        first, second = self.local('a'), self.local('b')
        a, b = self.connect(first), self.connect(second)
        a.send_message('Antes del corte')
        wait_for(lambda: second.cursor() == 1)
        color, identity = second.get('color'), second.device_id
        b.stop()
        a.send_message('Durante el corte')
        b.send_message('Pendiente sin conexión')
        wait_for(lambda: first.cursor() == 2)
        second.close()
        self.locals.remove(second)
        second = self.local('b')
        self.assertEqual(second.device_id, identity)
        self.assertEqual(len(second.pending()), 1)
        self.connect(second)
        wait_for(lambda: second.cursor() == 3 and first.cursor() == 3)
        self.assertEqual(first.history(), second.history())
        self.assertEqual(second.get('color'), color)
        self.assertEqual(second.pending(), [])

    def test_retry_is_idempotent_and_sync_paginated(self):
        sock, reader, response = self.raw()
        self.assertEqual(response['tipo'], 'LOGIN_OK')
        sock.sendall(encode('SYNC', {'ultimo_id': 0}))
        reader.receive()
        request = {'contenido': 'Una sola vez', 'client_message_id': str(uuid.uuid4())}
        sock.sendall(encode('MESSAGE', request))
        self.assertEqual(reader.receive()['tipo'], 'MESSAGE')
        self.assertEqual(reader.receive()['tipo'], 'MESSAGE_ACK')
        sock.sendall(encode('MESSAGE', request))
        self.assertEqual(reader.receive()['tipo'], 'MESSAGE_ACK')
        for i in range(84):
            sock.sendall(encode('MESSAGE', {'contenido': f'Mensaje {i}'}))
            reader.receive()
            reader.receive()
        other, incoming, _ = self.raw()
        cursor, pages, ids = 0, 0, []
        while True:
            other.sendall(encode('SYNC', {'ultimo_id': cursor}))
            data = incoming.receive()['payload']
            ids.extend(m['id'] for m in data['mensajes'])
            cursor = data['ultimo_id']
            pages += 1
            if not data['hay_mas']:
                break
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(len(ids), 85)
        self.assertEqual(pages, 3)

    def test_concurrent_messages_have_same_order(self):
        databases = [self.local(f'c{i}') for i in range(5)]
        clients = [self.connect(db) for db in databases]
        workers = [threading.Thread(target=lambda c=c: [c.send_message(f'Mensaje {i}') for i in range(8)]) for c in clients]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        wait_for(lambda: all(len(db.history()) == 40 for db in databases))
        self.assertTrue(all(db.history() == databases[0].history() for db in databases))

    def test_duplicate_login_and_invalid_first_command(self):
        identity = str(uuid.uuid4())
        _, _, first = self.raw(identity)
        _, _, duplicate = self.raw(identity)
        self.assertEqual(first['tipo'], 'LOGIN_OK')
        self.assertEqual(duplicate['tipo'], 'ERROR')
        sock = socket.create_connection(('127.0.0.1', self.server.port), 3)
        self.sockets.append(sock)
        sock.sendall(encode('MESSAGE', {'contenido': 'Sin login'}))
        self.assertEqual(Reader(sock).receive()['tipo'], 'ERROR')

    def test_server_restart_recovers_and_keeps_color(self):
        local = self.local('restart')
        client = self.connect(local)
        client.send_message('Persistido')
        wait_for(lambda: local.cursor() == 1)
        server_id, color, port = self.db.server_id, local.get('color'), self.server.port
        self.server.stop()
        self.db.close()
        wait_for(lambda: not client.connected.is_set())
        client.send_message('Durante reinicio')
        self.db = Database(self.root / 'server.db')
        self.server = ChatServer(self.db, '127.0.0.1', port)
        self.server.start()
        wait_for(lambda: len(local.history()) == 2)
        self.assertEqual(server_id, self.db.server_id)
        self.assertEqual(color, local.get('color'))


class ProtocolTests(unittest.TestCase):
    def test_fragmented_unicode_and_multiple_frames(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        b.settimeout(.05)
        data = encode('MESSAGE', {'contenido': 'Hola 👋\nsegunda línea'})
        reader = Reader(b)
        a.sendall(data[:12])
        with self.assertRaises(socket.timeout):
            reader.receive()
        a.sendall(data[12:] + encode('PING'))
        self.assertEqual(reader.receive()['payload']['contenido'], 'Hola 👋\nsegunda línea')
        self.assertEqual(reader.receive()['tipo'], 'PING')

    def test_invalid_json_and_oversize(self):
        class FakeSocket:
            def __init__(self, data):
                self.data = data
            def recv(self, _):
                return self.data
        for data in (b'not json\n', b'[]\n', b'x' * MAX_FRAME):
            with self.assertRaises(ProtocolError):
                Reader(FakeSocket(data)).receive()


if __name__ == '__main__':
    unittest.main()
