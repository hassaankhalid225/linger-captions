# Contributing

Thanks for helping improve Live Caption Recorder!

## Setup

```powershell
git clone https://github.com/hassaankhalid225/live-caption-recorder.git
cd live-caption-recorder
python -m venv .venv; .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Run the app with `python -m live_caption_recorder --debug` (logs also go to the console).

## Before opening a pull request

```powershell
ruff check src tests      # lint (ruff check --fix for auto-fixes)
python -m pytest          # tests
```

- Keep `core/` free of Qt and Windows imports so it stays unit-testable on any OS.
- Anything touching Live Captions goes in `win/live_captions.py`; never make blocking Win32
  calls against its window (use the `*Async` variants) — it can hang.
- New transcript edge cases: add a failing snapshot sequence to `tests/test_transcript.py` first.
- UI strings are English; keep them short and friendly.

## Handy dev flags

`python -m live_caption_recorder --start --screenshot shot.png --screenshot-delay 8000`
starts recording and saves a picture of the window after 8 s (useful for README screenshots and
visual checks).

## Releasing

1. Bump `__version__` in `src/live_caption_recorder/__init__.py` and update `CHANGELOG.md`.
2. `git tag v1.2.3 && git push --tags` — GitHub Actions builds the zip and drafts the release.
