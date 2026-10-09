"""Prueba la interfaz Qt, su sincronización de red y la configuración guardada.

Qt usa una plataforma fuera de pantalla para poder ejecutar la prueba sin
monitor. Si PySide6 no está disponible, unittest informa un salto explícito.
"""
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

# Debe configurarse antes de importar QApplication para que Qt elija el backend.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HAS_QT = importlib.util.find_spec('PySide6') is not None


@unittest.skipUnless(HAS_QT, 'PySide6 no instalado')
class GuiTests(unittest.TestCase):
    """Comprueba la GUI contra un servidor y bases temporales reales."""

    def test_two_windows_exchange_and_remember_settings(self):
        """Intercambia un mensaje y reabre una ventana con sus datos previos."""

        # Las importaciones quedan dentro del caso para que el módulo pueda
        # cargarse y marcarse como omitido en equipos que no tienen PySide6.
        from PySide6.QtWidgets import QApplication
        from client.gui import ChatWindow
        from client.local_database import LocalDatabase
        from server.database import Database
        from server.socket_manager import ChatServer
        # QApplication es única por proceso; se reutiliza si otro test la creó.
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = Database(root / 'server.db')
            server = ChatServer(database, '127.0.0.1', 0)
            server.start()
            locals_ = [LocalDatabase(root / f'client{i}.db') for i in range(2)]
            # zip asocia cada base local con una identidad distinta sin depender
            # de índices paralelos dentro del constructor.
            windows = [ChatWindow(db, '127.0.0.1', server.port, name)
                       for db, name in zip(locals_, ('Jerónimo', 'Carlos'))]
            def wait(predicate):
                """Procesa eventos de Qt hasta que se cumpla una condición."""

                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    # Sin el bucle principal app.exec(), el test debe entregar
                    # manualmente a Qt sus señales, clics y repintados pendientes.
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
                # La vista devuelve texto, no HTML: los ángulos intactos prueban
                # que el contenido se escapó y no se interpretó como una etiqueta.
                self.assertIn('<mensaje seguro>', windows[1].history.toPlainText())
                self.assertEqual(locals_[0].get('host'), '127.0.0.1')
                self.assertEqual(locals_[0].get('nombre'), 'Jerónimo')
                windows[0].grab().save('/tmp/chat-lan-interfaz.png')
                for window in windows:
                    window.close()
                reopened = ChatWindow(locals_[0], locals_[0].get('host'), server.port, locals_[0].get('nombre'))
                windows.append(reopened)
                reopened.show()
                # La reconexión se programa mediante un temporizador de Qt; por
                # eso se espera tanto la creación del cliente como su conexión.
                wait(lambda: reopened.network is not None and reopened.network.connected.is_set())
            finally:
                for window in windows:
                    window.close()
                app.processEvents()
                server.stop()
                database.close()
                for db in locals_:
                    db.close()
