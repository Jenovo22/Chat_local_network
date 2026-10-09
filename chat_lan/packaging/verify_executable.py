"""Verifica el ejecutable construido mediante dos interfaces gráficas reales.

La comprobación inicia un servidor temporal, dos copias del binario y un
cliente emisor. Está separada de las pruebas unitarias porque requiere que
``dist/ChatLAN`` ya exista y ejecuta procesos externos.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
# Los módulos del proyecto no están instalados como paquete durante esta
# verificación, por lo que se añade su raíz únicamente a este proceso.
sys.path.insert(0, str(root))
from server.database import Database
from server.socket_manager import ChatServer
from client.local_database import LocalDatabase
from client.network import NetworkClient


def wait_for(predicate):
    """Espera una condición asíncrona o falla tras un plazo acotado."""

    # monotonic no retrocede si cambia el reloj del sistema durante la prueba.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('El ejecutable no completó la prueba')


with tempfile.TemporaryDirectory() as folder:
    # Todas las bases y salidas quedan aisladas y se eliminan al terminar.
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
            # offscreen evita depender de un monitor. Quitar las variables del
            # entorno Python comprueba que el binario sea realmente autónomo.
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
        # Además de recibir el mensaje, ambos procesos deben seguir vivos y
        # haber persistido exactamente el mismo historial.
        assert all(process.poll() is None for process in processes)
        assert databases[0].history() == databases[1].history()
        print('OK: dos ejecutables gráficos conectados, mensaje recibido y guardado; sin Python externo.')
    finally:
        # La limpieza también se ejecuta si una espera o aserción falla.
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
