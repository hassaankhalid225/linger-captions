# Live Caption Recorder

**Keep every line from Windows 11 Live Captions — until *you* stop.**

Windows Live Captions shows only the last couple of lines and throws everything else away.
Live Caption Recorder sits on top of it, collects every sentence into a clean, de-duplicated
transcript and lets you copy, save or export it — while staying out of your way as a
frosted-glass caption bar.

> Works with any audio playing on your PC: meetings (Teams, Meet, Zoom), lectures, YouTube,
> podcasts. Speech recognition runs **on-device** in Windows — nothing is uploaded anywhere.

<!-- Add a screenshot: docs/screenshot.png -->

## Features

- **Persistent transcript** — captions accumulate until you press Stop; no more lines vanishing.
- **Smart de-duplication** — handles Live Captions' rolling window, re-punctuation and revisions.
- **Keeps running when minimized** — Live Captions itself is parked off-screen so it never pauses.
- **Copy, save & export** — plain text, text with timestamps, Markdown or `.srt` subtitles.
- **Auto-save** — every session is written to `Documents\Live Caption Recorder` as you go.
- **Frosted-glass UI** — compact caption bar or expanded transcript view, adjustable text size,
  always-on-top, draggable and resizable.
- **Private mode** *(optional)* — hides the window from screen sharing and recordings, handy when
  you present your screen but want captions only for yourself. Enables real background blur.
- **System tray**, single instance, crash logging, self-healing if Live Captions freezes.

## Requirements

- Windows 11 **22H2 or newer** (Live Captions is built in). Set it up once with **Win + Ctrl + L**
  and download a language when Windows asks.
- Python 3.10+ (only when running from source).

## Install & run

### Option A — standalone app
Download `LiveCaptionRecorder-<version>-win64.zip` from the
[Releases](https://github.com/hassaankhalid225/live-caption-recorder/releases) page, unzip, run
`LiveCaptionRecorder.exe`.

### Option B — from source
```powershell
git clone https://github.com/hassaankhalid225/live-caption-recorder.git
cd live-caption-recorder
python -m pip install -e .
live-caption-recorder            # or: pythonw run.pyw   /   double-click "Start Live Caption Recorder.bat"
```

Command-line options: `--start` (begin recording right away), `--debug` (verbose log), `--version`.

## Usage

| Action | How |
|---|---|
| Start / stop | **▶ Start** button or `Ctrl+R` |
| Copy everything | Copy icon or `Ctrl+Shift+C` (select text + `Ctrl+C` copies a part) |
| Save / export | Save icon or `Ctrl+S` → choose `.txt`, `.md` or `.srt` |
| Bigger / smaller text | `A+` / `A−` or `Ctrl+=` / `Ctrl+-` |
| Expand transcript | Chevron icon, `Ctrl+E` or double-click the title bar |
| Settings | **⋯** menu: always on top, private mode, glass blur, timestamps, auto-save, transcripts folder |
| Quit | ✕ or `Ctrl+Q` (Live Captions is restored to normal) |

**Which audio is captioned?** Live Captions listens to your PC's *output* (what you hear).
Your microphone is only included if you enable *Include microphone audio* in Live Captions'
own settings.

## How it works

1. Live Captions renders its text in a XAML `TextBlock` (`CaptionsTextBlock`); the app reads it
   through **UI Automation** a few times per second.
2. Each snapshot goes through `Transcript`, which anchors new text against what's already been
   committed, keeps the unfinished sentence separate and ignores text that existed before you
   pressed Start.
3. Live Captions stops updating when minimized, so the app moves its window far off-screen and
   removes its taskbar button instead — and puts it back when you quit.

```
src/live_caption_recorder/
├── core/          # platform-independent: text utils, Transcript, Recorder loop (unit-tested)
├── win/           # Win32 bindings + Live Captions controller (UI Automation)
├── ui/            # PySide6 glass window, widgets, tray, theme
├── config.py      # settings (QSettings) and paths
└── app.py         # entry point: logging, single instance, wiring
```

## Privacy

- No network access. Speech recognition is done by Windows on your device.
- Transcripts are saved only where you choose (default `Documents\Live Caption Recorder`); turn
  auto-save off in the ⋯ menu.
- Logs (no transcript text) live in `%LOCALAPPDATA%\LiveCaptionRecorder\logs`.
- Please respect the people you record: follow your local laws and your organisation's policies,
  and ask for consent where required.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Live Captions unavailable" | Needs Windows 11 22H2+. Press Win + Ctrl + L once and finish its setup. |
| Nothing appears | Make sure audio is actually playing and Live Captions' language matches the speech. |
| Live Captions window is still hidden after a crash | Start and quit the app once, or press Win + Ctrl + L twice. |
| Private mode has no effect | Requires Windows 10 version 2004 or newer. |

## Development

```powershell
python -m pip install -e ".[dev]"
ruff check src tests
python -m pytest
powershell -ExecutionPolicy Bypass -File scripts\build.ps1   # builds dist\LiveCaptionRecorder
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Releases are built automatically by GitHub Actions when a
`v*` tag is pushed.

## License

[MIT](LICENSE)

*Not affiliated with Microsoft. "Windows" and "Live Captions" are trademarks of Microsoft Corporation.*
