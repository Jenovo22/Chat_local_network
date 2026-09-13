import argparse
import logging
import sys
import threading
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.database import Database
from server.socket_manager import ChatServer


def main():
    parser = argparse.ArgumentParser(description="Servidor Chat LAN TCP")
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--db', default=str(Path(__file__).resolve().parents[1] / 'data' / 'chat_server.db'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    db = Database(args.db)
    server = ChatServer(db, args.host, args.port)
    try:
        server.start()
        threading.Event().wait()
    except KeyboardInterrupt:
        logging.info('Cerrando servidor')
    finally:
        server.stop()
        db.close()


if __name__ == '__main__':
    main()
