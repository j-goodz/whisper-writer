import os
import sys
import time
from audioplayer import AudioPlayer
from PyQt5.QtCore import QObject, QProcess, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox

from key_listener import KeyListener
from result_thread import ResultThread
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from ui.status_window import StatusWindow
from transcription import create_local_model
from input_simulation import InputSimulator
from utils import ConfigManager, Logger


class WhisperWriterApp(QObject):
    def __init__(self):
        """
        Initialize the application, opening settings window if no configuration file is found.
        """
        super().__init__()
        Logger.log('WhisperWriterApp initializing')
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
        Logger.log('Configuration initialized')

        # Defer creating heavy/optional UI until needed
        self.settings_window = None

        if ConfigManager.config_file_exists():
            Logger.log('Configuration file found; initializing components')
            self.initialize_components()
        else:
            Logger.log('No configuration file found. Opening settings window...')
            self.ensure_settings_window()
            self.settings_window.show()

    def initialize_components(self):
        """
        Initialize the components of the application.
        """
        Logger.log('Initializing components')
        self.input_simulator = InputSimulator()

        self.key_listener = KeyListener()
        self.key_listener.add_callback("on_activate", self.on_activation)
        self.key_listener.add_callback("on_deactivate", self.on_deactivation)

        model_options = ConfigManager.get_config_section('model_options')
        # Lazy-create model on first use to speed startup
        self.local_model = None

        self.result_thread = None

        self.main_window = MainWindow()
        self.main_window.openSettings.connect(self.show_settings_window)
        self.main_window.startListening.connect(self.key_listener.start)

        if not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.status_window = StatusWindow()
            # Allow one-click ignore of detected app (lazy import to avoid startup issues)
            try:
                from ui.game_status_window import GameStatusWindow  # type: ignore
                self.game_status_window = GameStatusWindow()
                self.game_status_window.ignoreAppClicked.connect(self._ignore_detected_app)
                self.game_status_window.forceAppClicked.connect(self._force_detected_app)
            except Exception:
                self.game_status_window = None

        self.create_tray_icon()
        Logger.log('System tray initialized')

        # Auto-start behaviors
        if ConfigManager.get_config_value('misc', 'start_hidden'):
            self.main_window.hide()
            Logger.log('Main window hidden on start')
        else:
            self.main_window.show()
            Logger.log('Main window shown on start')

        if ConfigManager.get_config_value('recording_options', 'auto_start_listening'):
            # Start the listener immediately so hotkey works after boot
            self.key_listener.start()
            Logger.log('Key listener auto-started')

        # Optional warm-up of local model
        if not ConfigManager.get_config_value('model_options', 'use_api') and ConfigManager.get_config_value('misc', 'warm_up_model_on_launch'):
            # Load the model in a minimal delayed single-shot to avoid blocking UI
            Logger.log('Scheduling local model warm-up')
            QTimer.singleShot(100, self._warm_up_model)

        # Apply Windows startup setting on launch as well
        start_on_login = ConfigManager.get_config_value('misc', 'start_on_login') is True
        try:
            from utils import ConfigManager as _CM
            _CM.ensure_windows_startup(start_on_login)
        except Exception:
            pass

        # Start performance guard (gaming mode) if enabled
        if os.name == 'nt' and ConfigManager.get_config_value('performance', 'enabled'):
            interval = ConfigManager.get_config_value('performance', 'poll_interval_ms') or 1500
            self._perf_timer = QTimer()
            self._perf_timer.timeout.connect(self._check_fullscreen_and_guard)
            self._perf_timer.start(int(interval))
            self._is_game_active = False
            Logger.log(f'Performance guard enabled (interval={interval} ms)')

    def _warm_up_model(self):
        if self.local_model is None:
            try:
                Logger.log('Warming up local model...')
                self.local_model = create_local_model()
                Logger.log('Local model ready')
            except Exception:
                Logger.log('Local model warm-up failed; continuing without pre-load')
                pass

    def _check_fullscreen_and_guard(self):
        try:
            is_fullscreen, app_name = self._detect_fullscreen_info()
        except Exception:
            is_fullscreen, app_name = False, ''

        if is_fullscreen and not self._is_game_active:
            self._is_game_active = True
            # Pause listener if configured
            if ConfigManager.get_config_value('performance', 'pause_listener_on_game') and self.key_listener and self.key_listener.is_running():
                try:
                    self.key_listener.stop()
                except Exception:
                    pass
                Logger.log(f'Paused key listener due to fullscreen app: {app_name}')
            # Unload local model if configured
            if ConfigManager.get_config_value('performance', 'suspend_local_model_on_game') and self.local_model is not None:
                try:
                    self.local_model = None
                except Exception:
                    pass
                Logger.log('Suspended local model due to fullscreen app')
            if ConfigManager.get_config_value('performance', 'show_notifications') and not ConfigManager.get_config_value('misc', 'hide_status_window') and getattr(self, 'game_status_window', None):
                try:
                    self.game_status_window.show_paused(app_name)
                except Exception:
                    pass
        elif not is_fullscreen and self._is_game_active:
            self._is_game_active = False
            # Resume listener
            if ConfigManager.get_config_value('performance', 'pause_listener_on_game'):
                try:
                    self.key_listener.start()
                except Exception:
                    pass
                Logger.log('Resumed key listener after leaving fullscreen app')
            # Warm up model after game if desired
            if (not ConfigManager.get_config_value('model_options', 'use_api') and
                ConfigManager.get_config_value('performance', 'warm_up_model_after_game')):
                QTimer.singleShot(100, self._warm_up_model)
                Logger.log('Scheduling local model warm-up after game')
            if ConfigManager.get_config_value('performance', 'show_notifications') and not ConfigManager.get_config_value('misc', 'hide_status_window') and getattr(self, 'game_status_window', None):
                try:
                    self.game_status_window.show_resumed()
                except Exception:
                    pass

    def _detect_fullscreen_info(self) -> tuple[bool, str]:
        if os.name != 'nt':
            return False, ''
        import ctypes
        try:
            import psutil  # type: ignore
        except Exception:
            psutil = None
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False, ''
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top

        # Use the monitor that contains the window
        MONITOR_DEFAULTTONEAREST = 2
        hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", ctypes.wintypes.RECT),
                ("rcWork", ctypes.wintypes.RECT),
                ("dwFlags", ctypes.c_ulong),
            ]
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))

        mon_w = mi.rcMonitor.right - mi.rcMonitor.left
        mon_h = mi.rcMonitor.bottom - mi.rcMonitor.top
        work_w = mi.rcWork.right - mi.rcWork.left
        work_h = mi.rcWork.bottom - mi.rcWork.top
        # Get process name of foreground window
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = ''
        if psutil is not None:
            try:
                proc = psutil.Process(int(pid.value))
                proc_name = (proc.name() or '').lower()
            except Exception:
                proc_name = ''
        else:
            proc_name = ''
        ignore = [str(x).lower() for x in (ConfigManager.get_config_value('performance', 'ignore_processes') or [])]
        force = [str(x).lower() for x in (ConfigManager.get_config_value('performance', 'force_game_processes') or [])]
        ignore_lc = ignore
        force_lc = force
        if proc_name and any(proc_name == x or proc_name.endswith('\\'+x) for x in ignore_lc):
            return False, proc_name
        if proc_name and any(proc_name == x or proc_name.endswith('\\'+x) for x in force_lc):
            return True, proc_name
        # Treat maximized-to-work-area as not fullscreen unless explicitly allowed
        is_maximized_to_work_area = (win_w >= work_w and win_h >= work_h)
        if is_maximized_to_work_area and not ConfigManager.get_config_value('performance', 'treat_maximized_as_fullscreen'):
            return False, proc_name

        # Consider true fullscreen if covering almost the full physical monitor (borderless fullscreen)
        threshold = float(ConfigManager.get_config_value('performance', 'fullscreen_threshold_percent') or 98) / 100.0
        covers_full_monitor = (win_w >= int(mon_w * threshold)) and (win_h >= int(mon_h * threshold))
        if covers_full_monitor:
            return True, proc_name

        # If user opted in, treat maximized windows as fullscreen
        if is_maximized_to_work_area and ConfigManager.get_config_value('performance', 'treat_maximized_as_fullscreen'):
            return True, proc_name
        return False, proc_name

    def _ignore_detected_app(self, app_name: str):
        if not app_name:
            return
        app = app_name.lower().strip()
        ignore = list(ConfigManager.get_config_value('performance', 'ignore_processes') or [])
        force = list(ConfigManager.get_config_value('performance', 'force_game_processes') or [])
        ignore_lc = set([str(x).lower() for x in ignore])
        if app not in ignore_lc:
            ignore.append(app)
        # Ensure exclusivity: remove from force if present
        force = [x for x in force if str(x).lower() != app]
        ConfigManager.set_config_value(ignore, 'performance', 'ignore_processes')
        ConfigManager.set_config_value(force, 'performance', 'force_game_processes')
        ConfigManager.save_config()

    def _force_detected_app(self, app_name: str):
        if not app_name:
            return
        app = app_name.lower().strip()
        force = list(ConfigManager.get_config_value('performance', 'force_game_processes') or [])
        ignore = list(ConfigManager.get_config_value('performance', 'ignore_processes') or [])
        force_lc = set([str(x).lower() for x in force])
        if app not in force_lc:
            force.append(app)
        # Ensure exclusivity: remove from ignore if present
        ignore = [x for x in ignore if str(x).lower() != app]
        ConfigManager.set_config_value(force, 'performance', 'force_game_processes')
        ConfigManager.set_config_value(ignore, 'performance', 'ignore_processes')
        ConfigManager.save_config()

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
        settings_action.triggered.connect(self.show_settings_window)
        tray_menu.addAction(settings_action)

        # Separator before exit
        tray_menu.addSeparator()

        restart_action = QAction('Restart', self.app)
        restart_action.triggered.connect(self.restart_app)
        tray_menu.addAction(restart_action)

        exit_action = QAction('Exit', self.app)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Double-click opens Settings
        def on_tray_activated(reason):
            # Open Settings on single left-click or double-click
            if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
                self.show_settings_window()
        self.tray_icon.activated.connect(on_tray_activated)

    def ensure_settings_window(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow()
            self.settings_window.settings_closed.connect(self.on_settings_closed)
            self.settings_window.settings_saved.connect(self.restart_app)
            # Pause/resume listening while capturing activation key
            self.settings_window.listening_pause_request.connect(self._pause_listening_for_capture)
            self.settings_window.listening_resume_request.connect(self._resume_listening_after_capture)
            # Update listener keys if activation key changed on save
            def _update_keys_on_save():
                try:
                    self.key_listener.update_activation_keys()
                except Exception:
                    pass
            self.settings_window.settings_saved.connect(_update_keys_on_save)

    def show_settings_window(self):
        self.ensure_settings_window()
        try:
            # Restore if minimized or hidden, then bring to front and focus
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()
        except Exception:
            pass

    def cleanup(self):
        if self.key_listener:
            self.key_listener.stop()
        if self.input_simulator:
            self.input_simulator.cleanup()

    def exit_app(self):
        """
        Exit the application.
        """
        Logger.log('Exit requested; shutting down')
        self.cleanup()
        QApplication.quit()

    def restart_app(self):
        """Restart the application to apply the new settings."""
        Logger.log('Restart requested; shutting down and relaunching')
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
        Logger.log('Activation key pressed')
        if self.result_thread and self.result_thread.isRunning():
            recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')
            if recording_mode in ('press_to_toggle', 'hybrid'):
                self.result_thread.stop_recording()
            elif recording_mode == 'continuous':
                self.stop_result_thread()
            return

        self.start_result_thread()



    def on_deactivation(self):
        """
        Called when the activation key combination is released.
        """
        Logger.log('Activation key released')
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
            Logger.log('Creating local model for first transcription')
            self.local_model = create_local_model()

        self.result_thread = ResultThread(self.local_model)
        if not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.result_thread.statusSignal.connect(self.status_window.updateStatus)
            self.status_window.closeSignal.connect(self.stop_result_thread)
        self.result_thread.resultSignal.connect(self.on_transcription_complete)
        self.result_thread.start()
        Logger.log('Result thread started (recording)')

    def stop_result_thread(self):
        """
        Stop the result thread.
        """
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()
            Logger.log('Result thread stop requested')

    def _pause_listening_for_capture(self):
        self._was_listening = self.key_listener.is_running()
        if self._was_listening:
            try:
                self.key_listener.stop()
            except Exception:
                pass

    def _resume_listening_after_capture(self):
        if getattr(self, '_was_listening', False):
            try:
                self.key_listener.start()
            except Exception:
                pass

    def on_transcription_complete(self, result):
        """
        When the transcription is complete, type the result and start listening for the activation key again.
        """
        Logger.log(f'Transcription complete (chars={len(result) if isinstance(result, str) else "n/a"})')
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
            # Keep status as 'transcribing' until after insertion, then idle
            if not ConfigManager.get_config_value('misc', 'hide_status_window'):
                try:
                    self.status_window.updateStatus('transcribing')
                except Exception:
                    pass
            Logger.log('Inserting transcription into active window')
            self.input_simulator.typewrite(result)
            if not ConfigManager.get_config_value('misc', 'hide_status_window'):
                try:
                    self.status_window.updateStatus('idle')
                except Exception:
                    pass

        if ConfigManager.get_config_value('misc', 'noise_on_completion'):
            AudioPlayer(os.path.join('assets', 'beep.wav')).play(block=True)
            Logger.log('Played completion sound')

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
