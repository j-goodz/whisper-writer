import os
import sys
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QLabel, QHBoxLayout, QPushButton, QVBoxLayout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.base_window import BaseWindow


class GameStatusWindow(BaseWindow):
    ignoreAppClicked = pyqtSignal(str)
    forceAppClicked = pyqtSignal(str)

    def __init__(self):
        super().__init__('WhisperWriter Notice', 520, 140)
        self._current_app_name = ''
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.title_label = QLabel('')
        self.title_label.setFont(QFont('Segoe UI', 15, QFont.Bold))
        self.title_label.setStyleSheet('color: #333;')
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.detail_label = QLabel('')
        self.detail_label.setFont(QFont('Segoe UI', 12))
        self.detail_label.setStyleSheet('color: #444;')
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.detail_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.setAlignment(Qt.AlignCenter)

        self.ignore_button = QPushButton('Ignore this app')
        self.ignore_button.setVisible(False)
        self.ignore_button.setCursor(Qt.PointingHandCursor)
        self.ignore_button.setMinimumSize(150, 40)
        self.ignore_button.setFont(QFont('Segoe UI', 14))
        try:
            from PyQt5.QtWidgets import QSizePolicy
            self.ignore_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        except Exception:
            pass
        self.ignore_button.setStyleSheet('''
            QPushButton {
                background-color: transparent;
                color: #2d7dff;
                border: 2px solid #2d7dff;
                border-radius: 10px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #eaf2ff;
            }
        ''')
        self.ignore_button.clicked.connect(self._on_ignore_clicked)
        buttons.addWidget(self.ignore_button)

        self.force_button = QPushButton('Treat as game')
        self.force_button.setVisible(False)
        self.force_button.setCursor(Qt.PointingHandCursor)
        self.force_button.setMinimumSize(150, 40)
        self.force_button.setFont(QFont('Segoe UI', 14))
        try:
            from PyQt5.QtWidgets import QSizePolicy
            self.force_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        except Exception:
            pass
        self.force_button.setStyleSheet('''
            QPushButton {
                background-color: #2d7dff;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #1f67db;
            }
        ''')
        self.force_button.clicked.connect(self._on_force_clicked)
        buttons.addWidget(self.force_button)

        layout.addLayout(buttons)
        # Prevent vertical stacking by allowing the card to grow horizontally within bounds
        self.setMinimumWidth(420)
        self.setMaximumWidth(720)
        # Adaptive bounds already set; ensure width large enough to keep buttons side-by-side

        self.main_layout.addLayout(layout)

    def show_paused(self, app_name: str):
        self._current_app_name = app_name
        self.title_label.setText('Paused for fullscreen app')
        detail = f'Detected: {app_name}' if app_name else 'Detected a fullscreen application.'
        self.detail_label.setText(detail)
        visible = bool(app_name)
        self.ignore_button.setVisible(visible)
        self.force_button.setVisible(visible)
        self._apply_adaptive_size()
        self._auto_close()

    def show_resumed(self):
        self._current_app_name = ''
        self.title_label.setText('Resumed after fullscreen app')
        self.detail_label.setText('WhisperWriter is active again.')
        self.ignore_button.setVisible(False)
        self.force_button.setVisible(False)
        self._apply_adaptive_size()
        self._auto_close()

    def _on_ignore_clicked(self):
        if self._current_app_name:
            self.ignoreAppClicked.emit(self._current_app_name)
        self.close()

    def _on_force_clicked(self):
        if self._current_app_name:
            self.forceAppClicked.emit(self._current_app_name)
        self.close()

    def _auto_close(self):
        # Register as a toast and position via BaseWindow stacking logic (lower priority)
        try:
            self.register_toast(priority=1)
        except Exception:
            pass
        self.show()
        # Ensure reposition after show in case of fullscreen geometry quirks
        try:
            from ui.base_window import BaseWindow
            QTimer.singleShot(0, BaseWindow._reposition_toasts)
        except Exception:
            pass
        QTimer.singleShot(5000, self.close)

    def _apply_adaptive_size(self):
        # Choose a target width within min/max so labels can wrap nicely
        min_w = max(self.minimumWidth(), 420)
        max_w = max(self.maximumWidth(), min_w)
        hint_w = self.sizeHint().width()
        target_w = max(min_w, min(hint_w, max_w))
        try:
            # Allow height to expand with content; avoid fixing the height
            self.setMinimumWidth(min_w)
            self.setMaximumWidth(max_w)
            self.resize(target_w, self.sizeHint().height())
        except Exception:
            pass
        # Re-evaluate after the event loop to capture final metrics
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.resize(target_w, self.sizeHint().height()))
        except Exception:
            pass


