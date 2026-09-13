import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client.local_database import LocalDatabase
from client.network import NetworkClient


def console(db, host, port, name):
    def event(kind, payload):
        if kind == 'messages':
            for msg in payload['mensajes']:
                print(f'\n[{msg["fecha"]}] {msg["nombre"]} ({msg["device_id"][:8]}, {msg["color"]}): {msg["contenido"]}', flush=True)
        elif kind == 'status':
            print('\n' + payload['texto'], flush=True)
    event('messages', {'mensajes': db.history()})
    network = NetworkClient(db, host, port, name, event)
    network.start()
    print('Escribe mensajes; /salir para cerrar. Los envíos sin conexión quedan pendientes.')
    try:
        while True:
            line = input('> ')
            if line.strip() == '/salir':
                break
            try:
                network.send_message(line)
            except ValueError as exc:
                print(exc)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        network.stop()


def main():
    parser = argparse.ArgumentParser(description='Cliente Chat LAN')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--name', help='Nombre visible (se permiten duplicados)')
    parser.add_argument('--console', action='store_true', help='Usar consola sin PySide6')
    parser.add_argument('--db', default=str(Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'chat_lan/chat_local.db'))
    args = parser.parse_args()
    db = LocalDatabase(args.db)
    try:
        host = args.host or db.get('host', '127.0.0.1' if args.console else '')
        port = args.port or int(db.get('port', '5000'))
        name = args.name or db.get('nombre', '')
        if args.console:
            console(db, host, port, name or input('Tu nombre: '))
        else:
            try:
                from client.gui import run
            except ModuleNotFoundError as exc:
                if exc.name != 'PySide6':
                    raise
                parser.exit(1, 'Falta PySide6. Instala client/requirements.txt o usa --console.\n')
            run(db, host, port, name)
    finally:
        db.close()


if __name__ == '__main__':
    main()
