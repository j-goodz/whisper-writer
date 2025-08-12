import os
import sys
import io
import atexit
from dotenv import load_dotenv
import faulthandler


def _setup_logging_for_pythonw() -> None:
    """Ensure stdout/stderr are safe under pythonw by redirecting to a log file.

    - Creates a log directory under %LOCALAPPDATA%/WhisperWriter/logs if possible
    - Falls back to the repository directory if needed
    - Enables faulthandler to write crashes to the same file
    """
    log_file_handle = None
    try:
        base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        log_dir = os.path.join(base_dir, "WhisperWriter", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "whisper-writer.log")
        log_file_handle = open(log_path, mode="a", buffering=1, encoding="utf-8")
    except Exception:
        try:
            repo_dir = os.path.dirname(__file__)
            log_path = os.path.join(repo_dir, "whisper-writer.log")
            log_file_handle = open(log_path, mode="a", buffering=1, encoding="utf-8")
        except Exception:
            log_file_handle = None

    if log_file_handle is not None:
        sys.stdout = log_file_handle
        sys.stderr = log_file_handle
        try:
            faulthandler.enable(file=log_file_handle)
        except Exception:
            # If enabling faulthandler fails, continue without it
            pass
        # Ensure the file is closed on exit to flush buffers
        atexit.register(log_file_handle.close)
    else:
        # As a last resort, swallow writes to avoid crashes under pythonw
        class _DevNull:
            def write(self, *args, **kwargs):
                pass

            def flush(self):
                pass

            def fileno(self):  # pragma: no cover - not used, but prevents faulthandler use
                raise io.UnsupportedOperation("no fileno")

        devnull = _DevNull()
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            faulthandler.disable()
        except Exception:
            pass


# Configure safe logging before any prints occur
_setup_logging_for_pythonw()

# Ensure CWD is the repository directory so relative assets load reliably
try:
    repo_dir = os.path.dirname(__file__)
    if repo_dir:
        os.chdir(repo_dir)
except Exception:
    pass

print("Starting WhisperWriter...")

load_dotenv()

# Run directly to avoid an extra Python process spawn and speed startup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
import main  # type: ignore

if __name__ == '__main__':
    app = main.WhisperWriterApp()
    app.run()