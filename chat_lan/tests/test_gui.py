"""Prueba gráfica sin monitor: QT_QPA_PLATFORM=offscreen."""
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HAS_QT = importlib.util.find_spec('PySide6') is not None


@unittest.skipUnless(HAS_QT, 'PySide6 no instalado')
class GuiTests(unittest.TestCase):
    def test_two_windows_exchange_and_remember_settings(self):
        from PySide6.QtWidgets import QApplication
        from client.gui import ChatWindow
        from client.local_database import LocalDatabase
        from server.database import Database
        from server.socket_manager import ChatServer
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = Database(root / 'server.db')
            server = ChatServer(database, '127.0.0.1', 0)
            server.start()
            locals_ = [LocalDatabase(root / f'client{i}.db') for i in range(2)]
            windows = [ChatWindow(db, '127.0.0.1', server.port, name)
                       for db, name in zip(locals_, ('Jerónimo', 'Carlos'))]
            def wait(predicate):
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    app.processEvents()
                    if predicate():
                        return
                    time.sleep(.02)
                self.fail('La interfaz no completó la operación')
            try:
                for window in windows:
                    window.show()
                    window.connect_button.click()
                wait(lambda: all(w.network.connected.is_set() for w in windows))
                windows[0].message.setText('Hola equipo 👋 <mensaje seguro>')
                windows[0].send_button.click()
                wait(lambda: all('Hola equipo' in w.history.toPlainText() for w in windows))
                self.assertIn('<mensaje seguro>', windows[1].history.toPlainText())
                self.assertEqual(locals_[0].get('host'), '127.0.0.1')
                self.assertEqual(locals_[0].get('nombre'), 'Jerónimo')
                windows[0].grab().save('/tmp/chat-lan-interfaz.png')
                for window in windows:
                    window.close()
                reopened = ChatWindow(locals_[0], locals_[0].get('host'), server.port, locals_[0].get('nombre'))
                windows.append(reopened)
                reopened.show()
                wait(lambda: reopened.network is not None and reopened.network.connected.is_set())
            finally:
                for window in windows:
                    window.close()
                app.processEvents()
                server.stop()
                database.close()
                for db in locals_:
                    db.close()
