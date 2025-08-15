import subprocess
import os
import signal
import time
from pynput.keyboard import Controller as PynputController, Key
try:
    import win32clipboard  # type: ignore
    import win32con  # type: ignore
except Exception:
    win32clipboard = None
    win32con = None

from utils import ConfigManager, Logger

def run_command_or_exit_on_failure(command):
    """
    Run a shell command and exit if it fails.

    Args:
        command (list): The command to run as a list of strings.
    """
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        Logger.log(f"Error running command: {e}")
        exit(1)

class InputSimulator:
    """
    A class to simulate keyboard input using various methods.
    """

    def __init__(self):
        """
        Initialize the InputSimulator with the specified configuration.
        """
        self.input_method = ConfigManager.get_config_value('post_processing', 'input_method')
        self.dotool_process = None

        if self.input_method == 'pynput':
            self.keyboard = PynputController()
        elif self.input_method == 'dotool':
            self._initialize_dotool()

    def should_use_paste(self, text: str) -> bool:
        """Decide whether to paste instead of typing based on settings, text length, and estimated typing time."""
        interval = ConfigManager.get_config_value('post_processing', 'writing_key_press_delay') or 0.0
        mode = (ConfigManager.get_config_value('post_processing', 'writing_mode') or 'auto').lower()
        paste_bulk = ConfigManager.get_config_value('post_processing', 'bulk_paste_threshold') or 80
        max_typing_ms = ConfigManager.get_config_value('post_processing', 'paste_when_typing_time_exceeds_ms') or 1000
        if mode == 'paste':
            return True
        if mode == 'type':
            return False
        # Auto mode: paste if text is long OR estimated typing time exceeds threshold
        estimated_ms = (interval * len(text)) * 1000.0
        return (len(text) >= int(paste_bulk)) or (estimated_ms >= float(max_typing_ms))

    def can_paste_here(self) -> bool:
        """Best-effort check that there is a reasonable foreground target window to receive input."""
        try:
            if os.name == 'nt':
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    return False
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                # Avoid pasting into our own process window (heuristic)
                if pid.value == os.getpid():
                    return False
                is_enabled = user32.IsWindowEnabled(hwnd)
                is_visible = user32.IsWindowVisible(hwnd)
                return bool(is_enabled and is_visible)
            # Other OS: assume ok
            return True
        except Exception:
            return True

    def _initialize_dotool(self):
        """
        Initialize the dotool process for input simulation.
        """
        self.dotool_process = subprocess.Popen("dotool", stdin=subprocess.PIPE, text=True)
        assert self.dotool_process.stdin is not None

    def _terminate_dotool(self):
        """
        Terminate the dotool process if it's running.
        """
        if self.dotool_process:
            os.kill(self.dotool_process.pid, signal.SIGINT)
            self.dotool_process = None

    def typewrite(self, text):
        """
        Simulate typing the given text with the specified interval between keystrokes.

        Args:
            text (str): The text to type.
        """
        interval = ConfigManager.get_config_value('post_processing', 'writing_key_press_delay')
        mode = (ConfigManager.get_config_value('post_processing', 'writing_mode') or 'auto').lower()
        if self.input_method == 'pynput':
            if self.should_use_paste(text):
                if not self._safe_clipboard_paste(text):
                    # Fallback: accelerate typing if paste failed verification
                    fast_interval = max(0.0, min((ConfigManager.get_config_value('post_processing', 'writing_key_press_delay') or 0.0) / 4.0, 0.002))
                    self._typewrite_pynput(text, fast_interval)
            else:
                self._typewrite_pynput(text, max(0.0, interval or 0.0))
        elif self.input_method == 'ydotool':
            self._typewrite_ydotool(text, interval)
        elif self.input_method == 'dotool':
            self._typewrite_dotool(text, interval)

    def _typewrite_pynput(self, text, interval):
        """
        Simulate typing using pynput.

        Args:
            text (str): The text to type.
            interval (float): The interval between keystrokes in seconds.
        """
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            time.sleep(interval)

    def _safe_clipboard_paste(self, text: str) -> bool:
        """Attempt a robust clipboard paste with verification and controlled restore.

        Returns True if pasted via clipboard; False if caller should fallback to typing.
        """
        verify_timeout_ms = ConfigManager.get_config_value('post_processing', 'paste_verify_timeout_ms') or 500
        restore_delay_ms = ConfigManager.get_config_value('post_processing', 'paste_restore_delay_ms') or 800
        restore_enabled = ConfigManager.get_config_value('post_processing', 'paste_restore_clipboard') is not False
        retry_attempts = ConfigManager.get_config_value('post_processing', 'paste_retry_attempts') or 2

        # Increase timeout for slow UI scenarios
        verify_timeout_ms = max(verify_timeout_ms, 2000)  # Minimum 2 seconds for slow systems
        
        Logger.log(f'Attempting clipboard paste with {verify_timeout_ms}ms timeout and {retry_attempts} retry attempts')

        # Save current clipboard using best available mechanism
        previous_text = None
        try:
            import pyperclip
            previous_text = pyperclip.paste()
        except Exception:
            previous_text = None

        def _set_clipboard_win(txt: str) -> bool:
            if win32clipboard and win32con:
                for _ in range(5):
                    try:
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(txt, win32con.CF_UNICODETEXT)
                        win32clipboard.CloseClipboard()
                        return True
                    except Exception:
                        try:
                            win32clipboard.CloseClipboard()
                        except Exception:
                            pass
                        time.sleep(0.02)
                return False
            else:
                try:
                    import pyperclip
                    pyperclip.copy(txt)
                    return True
                except Exception:
                    return False

        # Verify clipboard content matches what we intend to paste
        def _get_clipboard_text() -> str:
            if win32clipboard and win32con:
                try:
                    win32clipboard.OpenClipboard()
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    return data or ''
                except Exception:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        pass
                    return ''
            try:
                import pyperclip
                return pyperclip.paste() or ''
            except Exception:
                return ''

        # Retry loop for clipboard operations
        for attempt in range(retry_attempts + 1):
            if attempt > 0:
                Logger.log(f'Retrying clipboard paste (attempt {attempt + 1}/{retry_attempts + 1})')
                time.sleep(0.1)  # Brief delay between retries

            # Set clipboard content
            if not _set_clipboard_win(text):
                Logger.log(f'Failed to set clipboard content on attempt {attempt + 1}')
                continue

            # Wait for clipboard verification
            deadline = time.time() + (verify_timeout_ms / 1000.0)
            verification_success = False
            while time.time() < deadline:
                if _get_clipboard_text() == text:
                    verification_success = True
                    break
                time.sleep(0.02)
            
            if not verification_success:
                Logger.log(f'Clipboard verification failed after {verify_timeout_ms}ms timeout on attempt {attempt + 1}')
                continue

            Logger.log(f'Clipboard verification successful on attempt {attempt + 1}, performing paste')

            # Perform paste with improved key handling to prevent 'V' character issue
            try:
                # Use a more reliable paste method that avoids the 'V' character issue
                with self.keyboard.pressed(Key.ctrl):
                    # Add a small delay to ensure Ctrl is fully pressed
                    time.sleep(0.01)
                    # Press and release 'v' in a single operation
                    self.keyboard.tap('v')
                    # Add a small delay to ensure the paste completes
                    time.sleep(0.01)
            except Exception as e:
                Logger.log(f'Error during paste operation on attempt {attempt + 1}: {e}')
                continue

            # Optionally restore clipboard after a delay, only if unchanged
            if restore_enabled:
                time.sleep(max(0.0, restore_delay_ms / 1000.0))
                current = _get_clipboard_text()
                if previous_text is not None and current == text:
                    _set_clipboard_win(previous_text)
                    Logger.log('Previous clipboard content restored')
            
            Logger.log(f'Clipboard paste completed successfully on attempt {attempt + 1}')
            return True

        Logger.log(f'All {retry_attempts + 1} clipboard paste attempts failed')
        return False

    def _typewrite_ydotool(self, text, interval):
        """
        Simulate typing using ydotool.

        Args:
            text (str): The text to type.
            interval (float): The interval between keystrokes in seconds.
        """
        cmd = "ydotool"
        run_command_or_exit_on_failure([
            cmd,
            "type",
            "--key-delay",
            str(interval * 1000),
            "--",
            text,
        ])

    def _typewrite_dotool(self, text, interval):
        """
        Simulate typing using dotool.

        Args:
            text (str): The text to type.
            interval (float): The interval between keystrokes in seconds.
        """
        assert self.dotool_process and self.dotool_process.stdin
        self.dotool_process.stdin.write(f"typedelay {interval * 1000}\n")
        self.dotool_process.stdin.write(f"type {text}\n")
        self.dotool_process.stdin.flush()

    def cleanup(self):
        """
        Perform cleanup operations, such as terminating the dotool process.
        """
        if self.input_method == 'dotool':
            self._terminate_dotool()
