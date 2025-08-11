# Contributing

Thanks for your interest in improving WhisperWriter!

## Getting set up
- Use Python 3.11.
- Create and activate a virtual environment, then install dependencies:
  - `python -m venv venv`
  - `venv/Scripts/activate` (Windows) or `source venv/bin/activate` (macOS/Linux)
  - `pip install -r requirements.txt`
- Run locally:
  - `python run.py`

## Development tips
- App auto-starts listening (configurable). Use the tray to open Settings.
- For quick testing, use the tray “Restart” action after code changes.
- Local model loads lazily; enable warm-up in Settings if you want it ready sooner.

## Coding guidelines
- Prefer clear, readable code. Follow the project’s existing style.
- Avoid deep nesting; add brief docstrings for non-trivial functions.
- Keep unrelated changes out of the same PR.
- UI: prefer consistent naming and spacing; keep behavior discoverable.

## Branch, commits, PRs
- Branch: `feature/xyz`, `fix/xyz`, or `chore/xyz`.
- Commits: concise subject, imperative mood; body if needed.
- PRs: include a short summary, screenshots/gifs for UI changes, and a checklist of tested scenarios.

## Tests & manual QA
- Manual checks to perform:
  - Hotkey capture dialog correctly sets `activation_key` and pauses/resumes listening.
  - Auto/paste/type modes insert text as expected; long text uses paste in Auto.
  - Tray actions: Start Listening, Start Recording Now, Stop, Restart, Settings, Exit.
  - Windows start-on-login toggle works (registry), and Start hidden behavior.
  - Sound device “System default” and named device selection both record.

## Releasing
- Update CHANGELOG.md under [Unreleased] with noteworthy changes.
- Update the README if behavior or defaults changed.
- Tag and draft a GitHub release with highlights and links.

## License & credits
- This fork remains under the GNU GPL per upstream licensing.
- Credit the upstream repository in notes and release text.
