import os
import sys
import time
from audioplayer import AudioPlayer
from PyQt5.QtCore import QObject, QProcess
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox

from key_listener import KeyListener
from result_thread import ResultThread
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from ui.status_window import StatusWindow
from transcription import create_local_model
from input_simulation import InputSimulator
from utils import ConfigManager


class WhisperWriterApp(QObject):
    def __init__(self):
        """
        Initialize the application, opening settings window if no configuration file is found.
        """
        super().__init__()
        self.app = QApplication(sys.argv)
        # Keep app running in tray even when all windows are closed
        self.app.setQuitOnLastWindowClosed(False)
        # Use a modern-looking style
        try:
            self.app.setStyle('Fusion')
        except Exception:
            pass
        self.app.setWindowIcon(QIcon(os.path.join('assets', 'ww-logo.png')))

        ConfigManager.initialize()

        # Defer creating heavy/optional UI until needed
        self.settings_window = None

        if ConfigManager.config_file_exists():
            self.initialize_components()
        else:
            print('No valid configuration file found. Opening settings window...')
            self.ensure_settings_window()
            self.settings_window.show()

    def initialize_components(self):
        """
        Initialize the components of the application.
        """
        self.input_simulator = InputSimulator()

        self.key_listener = KeyListener()
        self.key_listener.add_callback("on_activate", self.on_activation)
        self.key_listener.add_callback("on_deactivate", self.on_deactivation)

        model_options = ConfigManager.get_config_section('model_options')
        # Lazy-create model on first use to speed startup
        self.local_model = None

        self.result_thread = None

        self.main_window = MainWindow()
        self.main_window.openSettings.connect(self.ensure_settings_window)
        self.main_window.openSettings.connect(lambda: self.settings_window.show())
        self.main_window.startListening.connect(self.key_listener.start)

        if not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.status_window = StatusWindow()

        self.create_tray_icon()

        # Auto-start behaviors
        if ConfigManager.get_config_value('misc', 'start_hidden'):
            self.main_window.hide()
        else:
            self.main_window.show()

        if ConfigManager.get_config_value('recording_options', 'auto_start_listening'):
            # Start the listener immediately so hotkey works after boot
            self.key_listener.start()

        # Optional warm-up of local model
        if not ConfigManager.get_config_value('model_options', 'use_api') and ConfigManager.get_config_value('misc', 'warm_up_model_on_launch'):
            # Load the model in a minimal delayed single-shot to avoid blocking UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, self._warm_up_model)

        # Apply Windows startup setting on launch as well
        start_on_login = ConfigManager.get_config_value('misc', 'start_on_login') is True
        try:
            from utils import ConfigManager as _CM
            _CM.ensure_windows_startup(start_on_login)
        except Exception:
            pass

    def _warm_up_model(self):
        if self.local_model is None:
            try:
                self.local_model = create_local_model()
            except Exception:
                pass

    def create_tray_icon(self):
        """
        Create the system tray icon and its context menu.
        """
        self.tray_icon = QSystemTrayIcon(QIcon(os.path.join('assets', 'ww-logo.png')), self.app)
        self.tray_icon.setToolTip('WhisperWriter')

        tray_menu = QMenu()

        # Quick controls
        start_listen_action = QAction('Start Listening', self.app)
        start_listen_action.triggered.connect(self.key_listener.start)
        tray_menu.addAction(start_listen_action)

        start_record_action = QAction('Start Recording Now', self.app)
        start_record_action.triggered.connect(self.start_result_thread)
        tray_menu.addAction(start_record_action)

        stop_action = QAction('Stop', self.app)
        def _stop_all():
            try:
                self.key_listener.stop()
            except Exception:
                pass
            try:
                self.stop_result_thread()
            except Exception:
                pass
        stop_action.triggered.connect(_stop_all)
        tray_menu.addAction(stop_action)

        # Separator between controls and settings
        tray_menu.addSeparator()

        settings_action = QAction('Open Settings', self.app)
        settings_action.triggered.connect(self.ensure_settings_window)
        settings_action.triggered.connect(lambda: self.settings_window.show())
        tray_menu.addAction(settings_action)

        # Separator before exit
        tray_menu.addSeparator()

        exit_action = QAction('Exit', self.app)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Double-click opens Settings
        def on_tray_activated(reason):
            # Open Settings on single left-click or double-click
            if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
                self.ensure_settings_window()
                self.settings_window.show()
        self.tray_icon.activated.connect(on_tray_activated)

    def ensure_settings_window(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow()
            self.settings_window.settings_closed.connect(self.on_settings_closed)
            self.settings_window.settings_saved.connect(self.restart_app)

    def cleanup(self):
        if self.key_listener:
            self.key_listener.stop()
        if self.input_simulator:
            self.input_simulator.cleanup()

    def exit_app(self):
        """
        Exit the application.
        """
        self.cleanup()
        QApplication.quit()

    def restart_app(self):
        """Restart the application to apply the new settings."""
        self.cleanup()
        QApplication.quit()
        QProcess.startDetached(sys.executable, sys.argv)

    def on_settings_closed(self):
        """
        If settings is closed without saving on first run, initialize the components with default values.
        """
        if not os.path.exists(os.path.join('src', 'config.yaml')):
            QMessageBox.information(
                self.settings_window,
                'Using Default Values',
                'Settings closed without saving. Default values are being used.'
            )
            self.initialize_components()

    def on_activation(self):
        """
        Called when the activation key combination is pressed.
        """
        if self.result_thread and self.result_thread.isRunning():
            recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')
            if recording_mode == 'press_to_toggle':
                self.result_thread.stop_recording()
            elif recording_mode == 'continuous':
                self.stop_result_thread()
            return

        self.start_result_thread()

    def on_deactivation(self):
        """
        Called when the activation key combination is released.
        """
        if ConfigManager.get_config_value('recording_options', 'recording_mode') == 'hold_to_record':
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()

    def start_result_thread(self):
        """
        Start the result thread to record audio and transcribe it.
        """
        if self.result_thread and self.result_thread.isRunning():
            return

        # Create local model on first transcription if needed
        if self.local_model is None and not ConfigManager.get_config_value('model_options', 'use_api'):
            self.local_model = create_local_model()

        self.result_thread = ResultThread(self.local_model)
        if not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.result_thread.statusSignal.connect(self.status_window.updateStatus)
            self.status_window.closeSignal.connect(self.stop_result_thread)
        self.result_thread.resultSignal.connect(self.on_transcription_complete)
        self.result_thread.start()

    def stop_result_thread(self):
        """
        Stop the result thread.
        """
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()

    def on_transcription_complete(self, result):
        """
        When the transcription is complete, type the result and start listening for the activation key again.
        """
        # If using paste path and no focus target, warn instead of silently doing nothing
        try:
            will_paste = self.input_simulator.should_use_paste(result)
        except Exception:
            will_paste = False

        if will_paste and hasattr(self.input_simulator, 'can_paste_here') and not self.input_simulator.can_paste_here():
            if not ConfigManager.get_config_value('misc', 'hide_status_window'):
                try:
                    self.status_window.updateDetail('no_target')
                except Exception:
                    pass
        else:
            self.input_simulator.typewrite(result)

        if ConfigManager.get_config_value('misc', 'noise_on_completion'):
            AudioPlayer(os.path.join('assets', 'beep.wav')).play(block=True)

        if ConfigManager.get_config_value('recording_options', 'recording_mode') == 'continuous':
            self.start_result_thread()
        else:
            self.key_listener.start()

    def run(self):
        """
        Start the application.
        """
        sys.exit(self.app.exec_())


if __name__ == '__main__':
    app = WhisperWriterApp()
    app.run()
