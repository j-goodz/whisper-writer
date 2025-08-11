import os
import sys
from dotenv import load_dotenv

print('Starting WhisperWriter...')
load_dotenv()
# Run directly to avoid an extra Python process spawn and speed startup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
import main  # type: ignore

if __name__ == '__main__':
    app = main.WhisperWriterApp()
    app.run()
