"""Todas las actualizaciones de widgets se ejecutan en el hilo de Qt."""
import html
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QLineEdit, QPushButton, QTextBrowser,
                              QLabel, QMessageBox)
from client.network import NetworkClient


class Bridge(QObject):
    event = Signal(str, dict)


class ChatWindow(QMainWindow):
    def __init__(self, database, host, port, name):
        super().__init__()
        self.db = database
        self.network = None
        self.seen = set()
        self.bridge = Bridge(self)
        self.bridge.event.connect(self.on_event)
        self.setWindowTitle('Chat LAN')
        self.resize(880, 680)
        self.setMinimumSize(620, 480)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f4f7fb; color: #172b4d; font-size: 14px; }
            QLineEdit { background: white; border: 1px solid #d3ddeb;
                        border-radius: 8px; padding: 11px; selection-background-color: #2563eb; }
            QLineEdit:focus { border: 1px solid #2563eb; }
            QPushButton { background: #2563eb; color: white; border: none;
                          border-radius: 8px; padding: 12px 20px; font-weight: bold; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #b8c7dd; }
            QTextBrowser { background: white; border: 1px solid #d3ddeb;
                           border-radius: 12px; padding: 14px; font-size: 15px; }
            QLabel { background: transparent; }
        """)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        title = QLabel('Chat LAN')
        title.setStyleSheet('font-size: 22px; font-weight: bold; padding: 8px;')
        layout.addWidget(title)
        layout.addWidget(QLabel('Tu equipo, en una misma conversación.'))
        form = QHBoxLayout()
        self.host = QLineEdit(host)
        self.host.setPlaceholderText('IP del servidor')
        self.host.setAccessibleName('Dirección del servidor')
        self.port = port
        self.name = QLineEdit(name)
        self.name.setPlaceholderText('Tu nombre')
        self.name.setMaxLength(60)
        self.name.setAccessibleName('Tu nombre')
        self.connect_button = QPushButton('Conectar')
        self.connect_button.clicked.connect(self.connect_chat)
        for widget in (self.host, self.name, self.connect_button):
            form.addWidget(widget)
        layout.addLayout(form)
        self.identity = QLabel(f'Dispositivo: {self.db.device_id[:8]}')
        layout.addWidget(self.identity)
        self.history = QTextBrowser()
        self.history.setOpenLinks(False)
        layout.addWidget(self.history)
        self.status = QLabel('Desconectado · historial local disponible')
        layout.addWidget(self.status)
        self.pending = QLabel(f'Pendientes de confirmar: {len(self.db.pending())}')
        layout.addWidget(self.pending)
        composer = QHBoxLayout()
        self.message = QLineEdit()
        self.message.setPlaceholderText('Escribe un mensaje…')
        self.message.setMaxLength(4000)
        self.message.returnPressed.connect(self.send)
        composer.addWidget(self.message)
        self.send_button = QPushButton('Enviar')
        self.send_button.clicked.connect(self.send)
        self.send_button.setEnabled(False)
        composer.addWidget(self.send_button)
        layout.addLayout(composer)
        self.show_messages(self.db.history())
        self.name.returnPressed.connect(self.connect_chat)
        # Los datos recordados permiten reconectar automáticamente al abrir.
        if name.strip() and host.strip() and self.db.get('host'):
            QTimer.singleShot(0, self.connect_chat)

    def connect_chat(self):
        if self.network:
            self.network.stop()
            self.network = None
            self.connect_button.setText('Conectar')
            self.send_button.setEnabled(False)
            for field in (self.host, self.name):
                field.setEnabled(True)
            self.status.setText('Desconectado')
            return
        try:
            if not self.host.text().strip():
                raise ValueError('Indica la dirección del servidor')
            self.network = NetworkClient(self.db, self.host.text().strip(), self.port,
                                         self.name.text(), self.bridge.event.emit)
        except ValueError as exc:
            QMessageBox.warning(self, 'Revisa los datos', str(exc))
            return
        self.db.set('host', self.host.text().strip())
        self.db.set('port', self.port)
        for field in (self.host, self.name):
            field.setEnabled(False)
        self.connect_button.setText('Desconectar')
        self.send_button.setEnabled(True)
        self.network.start()

    def send(self):
        if not self.network:
            return
        try:
            self.network.send_message(self.message.text())
            self.message.clear()
        except ValueError as exc:
            self.status.setText(str(exc))

    def show_messages(self, messages):
        for message in messages:
            if message['id'] in self.seen:
                continue
            self.seen.add(message['id'])
            color = message['color']
            # No interpretar HTML procedente de nombres o mensajes de la red.
            if len(color) != 7 or color[0] != '#' or any(c not in '0123456789abcdefABCDEF' for c in color[1:]):
                color = '#3498DB'
            self.history.append(f'<p><b style="color:{color}">{html.escape(message["nombre"])}</b> '
                                f'<small>· {html.escape(message["device_id"][:8])} · {html.escape(message["fecha"])}</small><br>'
                                f'{html.escape(message["contenido"]).replace(chr(10), "<br>")}</p>')

    def on_event(self, kind, payload):
        if kind == 'status':
            self.status.setText(payload['texto'])
        elif kind == 'login':
            self.identity.setText(f'{self.name.text()} · {self.db.device_id[:8]} · {payload["color"]}')
            self.identity.setStyleSheet(f'color: {payload["color"]}; font-weight: bold;')
        elif kind == 'messages':
            self.show_messages(payload['mensajes'])
            self.pending.setText(f'Pendientes de confirmar: {len(self.db.pending())}')
        elif kind == 'pending':
            self.pending.setText(f'Pendientes de confirmar: {payload["cantidad"]}')
        elif kind == 'reset':
            self.seen.clear()
            self.history.clear()

    def closeEvent(self, event):
        if self.network:
            self.network.stop()
        event.accept()


def run(database, host, port, name):
    app = QApplication.instance() or QApplication([])
    window = ChatWindow(database, host, port, name)
    window.show()
    return app.exec()
