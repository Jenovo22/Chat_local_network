"""Arranca dos GUI empaquetadas y verifica recepción real y persistencia."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from server.database import Database
from server.socket_manager import ChatServer
from client.local_database import LocalDatabase
from client.network import NetworkClient


def wait_for(predicate):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('El ejecutable no completó la prueba')


with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    official = Database(path / 'server.db')
    server = ChatServer(official, '127.0.0.1', 0)
    server.start()
    processes, databases, logs = [], [], []
    sender_db = LocalDatabase(path / 'sender.db')
    sender = NetworkClient(sender_db, '127.0.0.1', server.port, 'Verificador')
    try:
        for i in range(2):
            local = LocalDatabase(path / f'gui{i}.db')
            databases.append(local)
            local.set('host', '127.0.0.1')
            local.set('port', server.port)
            local.set('nombre', f'Usuario {i}')
            log = open(path / f'gui{i}.log', 'w+')
            logs.append(log)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
            env.pop('PYTHONPATH', None)
            env.pop('VIRTUAL_ENV', None)
            processes.append(subprocess.Popen([str(root / 'dist/ChatLAN'), '--db', str(path / f'gui{i}.db')],
                                               cwd=path, env=env, stdout=log, stderr=log))
        wait_for(lambda: all(db.get('server_id') for db in databases))
        sender.start()
        wait_for(sender.connected.is_set)
        sender.send_message('Mensaje recibido por el ejecutable autónomo 👋')
        wait_for(lambda: all(len(db.history()) == 1 for db in databases))
        assert all(process.poll() is None for process in processes)
        assert databases[0].history() == databases[1].history()
        print('OK: dos ejecutables gráficos conectados, mensaje recibido y guardado; sin Python externo.')
    finally:
        sender.stop()
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
        for log in logs:
            log.seek(0)
            output = log.read()
            if output:
                print(output)
            log.close()
        server.stop()
        official.close()
        sender_db.close()
        for database in databases:
            database.close()
