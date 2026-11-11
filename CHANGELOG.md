# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-11-11

### Added
- Persistent, de-duplicated transcript built from Windows Live Captions.
- Recording continues while minimized (Live Captions is parked off-screen, restored on exit).
- Copy all, save/export as text, text with timestamps, Markdown and SRT.
- Auto-save of each session to `Documents\Live Caption Recorder`.
- Frosted-glass caption bar with compact/expanded modes, adjustable font size, always-on-top.
- Optional private mode (hidden from screen capture) with real background blur.
- System tray icon, single-instance guard, rotating log file, crash dialog.
- Automatic recovery when Live Captions stops responding.
- Unit tests, ruff lint, GitHub Actions CI and PyInstaller release build.
