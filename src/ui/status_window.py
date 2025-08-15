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
        # Bigger app title on the card
        try:
            self.set_title_font_point_size(16)
        except Exception:
            pass
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
        self.show()
        QTimer.singleShot(5000, self.close)

import sys
import os
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon
from PyQt5.QtWidgets import QApplication, QLabel, QHBoxLayout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.base_window import BaseWindow
from utils import ConfigManager

class StatusWindow(BaseWindow):
    statusSignal = pyqtSignal(str)
    closeSignal = pyqtSignal()

    def __init__(self):
        """
        Initialize the status window.
        """
        super().__init__('WhisperWriter Status', 480, 160)  # Increased width to prevent text wrapping
        self.initStatusUI()
        self.statusSignal.connect(self.updateStatus)

    def initStatusUI(self):
        """
        Initialize the status user interface.
        """
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        # Use a centered vertical layout for better visual hierarchy
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(20, 20, 20, 20)
        status_layout.setSpacing(12)
        status_layout.setAlignment(Qt.AlignCenter)

        # Icon container for proper centering
        icon_container = QHBoxLayout()
        icon_container.setAlignment(Qt.AlignCenter)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)  # Larger icon for better visibility
        microphone_path = os.path.join('assets', 'microphone.png')
        pencil_path = os.path.join('assets', 'pencil.png')
        self.microphone_pixmap = QPixmap(microphone_path).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.pencil_pixmap = QPixmap(pencil_path).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.icon_label.setPixmap(self.microphone_pixmap)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        icon_container.addWidget(self.icon_label)
        status_layout.addLayout(icon_container)

        # Main status label - Primary information
        self.status_label = QLabel('Recording...')
        self.status_label.setFont(QFont('Segoe UI', 18, QFont.Bold))  # Larger, bolder font
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #2c3e50; margin: 4px 0;')  # Darker color for better contrast
        status_layout.addWidget(self.status_label)

        # Recording mode label - Secondary information
        self.mode_label = QLabel('')
        self.mode_label.setFont(QFont('Segoe UI', 12))  # Medium size for secondary info
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setStyleSheet('color: #7f8c8d; margin: 2px 0;')  # Muted color
        status_layout.addWidget(self.mode_label)

        # Instruction label - Actionable information
        self.instruction_label = QLabel('')
        self.instruction_label.setObjectName('instruction')
        self.instruction_label.setFont(QFont('Segoe UI', 13, QFont.Medium))  # Larger, readable font
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(False)  # Prevent word wrapping to keep text on one line
        self.instruction_label.setStyleSheet('color: #34495e; margin: 4px 0;')  # Good contrast for readability

        status_layout.addWidget(self.instruction_label)

        self.main_layout.addLayout(status_layout)
        
        # Apply overall styling
        self.setStyleSheet("""
            QLabel {
                color: #333;
            }
            QLabel#instruction {
                color: #34495e;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        
    def show(self):
        """
        Position the window in the bottom center of the screen and show it.
        """
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        window_width = self.width()
        window_height = self.height()

        # Register as a toast and position via BaseWindow stacking logic (higher priority)
        try:
            self.register_toast(priority=10)
        except Exception:
            pass
        super().show()
        # Ensure reposition after show in case of fullscreen geometry quirks
        try:
            from ui.base_window import BaseWindow
            QTimer.singleShot(0, BaseWindow._reposition_toasts)
        except Exception:
            pass
        
    def closeEvent(self, event):
        """
        Emit the close signal when the window is closed.
        """
        try:
            self.unregister_toast()
        except Exception:
            pass
        self.closeSignal.emit()
        super().closeEvent(event)

    @pyqtSlot(str)
    def updateStatus(self, status):
        """
        Update the status window based on the given status.
        """
        if status == 'recording':
            self.icon_label.setPixmap(self.microphone_pixmap)
            
            # Check recording mode to show appropriate message
            try:
                recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')
                mode_display = recording_mode.replace('_', ' ').title()
                
                # Set main status (primary information)
                self.status_label.setText('Recording')
                
                # Set recording mode (secondary information)
                self.mode_label.setText(mode_display)
                
                # Set instructions based on mode (actionable information)
                if recording_mode == 'hybrid':
                    self.instruction_label.setText('Hybrid Mode')
                elif recording_mode == 'press_to_toggle':
                    self.instruction_label.setText('Toggle Mode')
                elif recording_mode == 'hold_to_record':
                    self.instruction_label.setText('Release hotkey to stop')
                else:
                    self.instruction_label.setText('Press hotkey again to stop')
            except Exception:
                self.status_label.setText('Recording')
                self.mode_label.setText('')
                self.instruction_label.setText('Press hotkey again to stop')
            
            self.show()
        elif status == 'transcribing':
            self.icon_label.setPixmap(self.pencil_pixmap)
            self.status_label.setText('Transcribing...')
            self.mode_label.setText('')
            self.instruction_label.setText('')
        # Any other statuses are ignored here; gaming notifications use a separate window
        if status in ('idle', 'error', 'cancel'):
            self.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    status_window = StatusWindow()
    status_window.show()

    # Simulate status updates
    QTimer.singleShot(3000, lambda: status_window.statusSignal.emit('transcribing'))
    QTimer.singleShot(6000, lambda: status_window.statusSignal.emit('idle'))
    
    sys.exit(app.exec_())
