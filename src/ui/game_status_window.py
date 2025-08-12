import os
import sys
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QLabel, QHBoxLayout, QPushButton, QVBoxLayout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.base_window import BaseWindow


class GameStatusWindow(BaseWindow):
    ignoreAppClicked = pyqtSignal(str)

    def __init__(self):
        super().__init__('WhisperWriter Notice', 520, 140)
        self._current_app_name = ''
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.title_label = QLabel('')
        self.title_label.setFont(QFont('Segoe UI', 12, QFont.Bold))
        self.title_label.setStyleSheet('color: #333;')
        layout.addWidget(self.title_label)

        self.detail_label = QLabel('')
        self.detail_label.setFont(QFont('Segoe UI', 10))
        self.detail_label.setStyleSheet('color: #444;')
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.ignore_button = QPushButton('Ignore this app')
        self.ignore_button.setVisible(False)
        self.ignore_button.clicked.connect(self._on_ignore_clicked)
        buttons.addWidget(self.ignore_button)
        layout.addLayout(buttons)

        self.main_layout.addLayout(layout)

    def show_paused(self, app_name: str):
        self._current_app_name = app_name
        self.title_label.setText('Paused for fullscreen app')
        detail = f'Detected: {app_name}' if app_name else 'Detected a fullscreen application.'
        self.detail_label.setText(detail)
        self.ignore_button.setVisible(bool(app_name))
        self._auto_close()

    def show_resumed(self):
        self._current_app_name = ''
        self.title_label.setText('Resumed after fullscreen app')
        self.detail_label.setText('WhisperWriter is active again.')
        self.ignore_button.setVisible(False)
        self._auto_close()

    def _on_ignore_clicked(self):
        if self._current_app_name:
            self.ignoreAppClicked.emit(self._current_app_name)
        self.close()

    def _auto_close(self):
        # Position near bottom center like the recording indicator
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        window_width = self.width()
        window_height = self.height()
        x = (screen_width - window_width) // 2
        y = screen_height - window_height - 120
        self.move(x, y)
        self.show()
        QTimer.singleShot(5000, self.close)


