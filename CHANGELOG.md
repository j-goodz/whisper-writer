# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
### Added
- Auto-start listening at launch (`recording_options.auto_start_listening`).
- Start hidden to tray (`misc.start_hidden`).
- Start on Windows login (`misc.start_on_login`) with registry integration.
- Optional local model warm-up on launch (`misc.warm_up_model_on_launch`).
- Tray quick actions (Start Listening, Start Recording Now, Stop) and single-click to open Settings.
- Activation key “Set” dialog that captures key combos (no manual typing needed).
- Paste-only/auto typing modes (`post_processing.writing_mode`) and bulk paste threshold.
- Numeric inputs (SpinBoxes) for int/float settings for easier editing.
- Hybrid recording mode (`recording_options.recording_mode: hybrid`) that combines voice activity detection with manual toggle - stops recording on silence OR when hotkey is pressed again.
- Improved recording status window with cleaner layout and better instructions.
- Enhanced clipboard paste reliability with retry logic and improved timeout handling for slow UI scenarios.
- New configuration option `paste_retry_attempts` to control clipboard operation retries.

### Changed
- Faster startup via lazy imports and deferring local model creation until first use.
- `run.py` now runs the app directly (no extra Python subprocess).
- Settings UI restyled: grouped sections, scrollable tabs, modern visuals.
- Closing main window now hides the app instead of exiting; app remains in the tray.
- Tray menu grouped with separators; removed “Show Main Menu”.
- Defaults updated: `misc.warm_up_model_on_launch` = true, `misc.start_on_login` = true.
- Increased default clipboard verification timeout from 500ms to 2000ms to better handle slow UI scenarios.
- Increased default clipboard restore delay from 800ms to 1000ms for better compatibility.
- Fixed 'V' character issue that could appear after clipboard paste operations.
- Improved clipboard paste operation with better key handling and timing.
- Enhanced logging for clipboard operations to aid in debugging paste issues.
- Improved privacy: Transcription content is now hashed in logs instead of being logged in plain text.
- Fixed hybrid mode issues: Status window now closes after text insertion, and silence detection works properly even without initial speech.

### Removed
- Deprecated tray item “Show Main Menu”.

## [1.0.1] - 2024-01-28
### Added
- New message to identify whether Whisper was being called using the API or running locally.
- Additional hold-to-talk ([PR #28](https://github.com/savbell/whisper-writer/pull/28)) and press-to-toggle recording methods ([Issue #21](https://github.com/savbell/whisper-writer/issues/21)).
- New configuration options to:
  - Choose recording method (defaulting to voice activity detection).
  - Choose which sound device and sample rate to use.
  - Hide the status window ([PR #28](https://github.com/savbell/whisper-writer/pull/28)).

### Changed
- Migrated from `whisper` to `faster-whisper` ([Issue #11](https://github.com/savbell/whisper-writer/issues/11)).
- Migrated from `pyautogui` to `pynput` ([PR #10](https://github.com/savbell/whisper-writer/pull/10)).
- Migrated from `webrtcvad` to `webrtcvad-wheels` ([PR #17](https://github.com/savbell/whisper-writer/pull/17)).
- Changed default activation key combo from `ctrl+alt+space` to `ctrl+shift+space`.
- Changed to using a local model rather than the API by default.
- Revamped README.md, including new Roadmap, Contributing, and Credits sections.

### Fixed
- Local model is now only loaded once at start-up, rather than every time the activation key combo was pressed.
- Default configuration now auto-chooses compute type for the local model to avoid warnings.
- Graceful degradation to CPU if CUDA isn't available ([PR #30](https://github.com/savbell/whisper-writer/pull/30)).
- Removed long prefix of spaces in transcription ([PR #19](https://github.com/savbell/whisper-writer/pull/19)).

## [1.0.0] - 2023-05-29
### Added
- Initial release of WhisperWriter.
- Added CHANGELOG.md.
- Added Versioning and Known Issues to README.md.

### Changed
- Updated Whisper Python package; the local model is now compatible with Python 3.11.

[Unreleased]: https://github.com/savbell/whisper-writer/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/savbell/whisper-writer/releases/tag/v1.0.0...v1.0.1
[1.0.0]: https://github.com/savbell/whisper-writer/releases/tag/v1.0.0
