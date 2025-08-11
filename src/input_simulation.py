import subprocess
import os
import signal
import time
from pynput.keyboard import Controller as PynputController, Key

from utils import ConfigManager

def run_command_or_exit_on_failure(command):
    """
    Run a shell command and exit if it fails.

    Args:
        command (list): The command to run as a list of strings.
    """
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
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
        """Decide whether to paste instead of typing based on settings and text length."""
        interval = ConfigManager.get_config_value('post_processing', 'writing_key_press_delay') or 0.0
        mode = (ConfigManager.get_config_value('post_processing', 'writing_mode') or 'auto').lower()
        paste_bulk = ConfigManager.get_config_value('post_processing', 'bulk_paste_threshold') or 80
        if mode == 'paste':
            return True
        if mode == 'type':
            return False
        return (interval <= 0.0) and (len(text) >= int(paste_bulk))

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
            paste_bulk = ConfigManager.get_config_value('post_processing', 'bulk_paste_threshold') or 80
            if mode == 'paste':
                self._paste_pynput(text)
            elif mode == 'type':
                self._typewrite_pynput(text, max(0.0, interval or 0.0))
            else:
                if (interval or 0.0) <= 0 and len(text) >= paste_bulk:
                    self._paste_pynput(text)
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

    def _paste_pynput(self, text):
        try:
            import pyperclip
        except Exception:
            # Fallback to typing if clipboard lib not available
            return self._typewrite_pynput(text, 0.0)
        # Save current clipboard, set text, paste, restore
        try:
            previous = pyperclip.paste()
        except Exception:
            previous = None
        pyperclip.copy(text)
        with self.keyboard.pressed(Key.ctrl):
            self.keyboard.press('v')
            self.keyboard.release('v')
        time.sleep(0.01)
        if previous is not None:
            try:
                pyperclip.copy(previous)
            except Exception:
                pass

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
