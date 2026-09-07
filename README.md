# Blink Tracker

A small macOS app that watches for blinks with your webcam and nudges you when you forget.

## Why this exists

Long stretches in front of screens made my vision feel worse. When I get deep into code, messages, or dashboards, I sometimes go several minutes without blinking. That dryness and strain add up.

I wanted something simple on my Mac: notice when blinking drops off, log what I was doing, and remind me to blink again — without turning into another heavy “eye health” product.

So I put together this lightweight tracker quickly: OpenCV on the built-in camera, a local log, and a configurable reminder.

## What it does

- Detects blinks from the webcam (OpenCV face/eye cascades)
- Logs each blink with time, frontmost app, and a simple fidelity score
- Reminds you after a configurable idle interval (**seconds** in Config)
- Exports a CSV for a date range
- Keeps all data on your machine (`blinks.db` next to the app)

## Requirements

- macOS with a webcam
- Python 3.10+ (a venv is created automatically on first launch)


## Install as a Mac app (Dock)

A packaged app lives in this repo as `Blink Tracker.app` (eye icon).

1. Copy `Blink Tracker.app` into `~/Applications` (or `/Applications`).
2. Open it once from Finder.
3. Right-click the Dock icon → **Options → Keep in Dock**.

Or from Terminal after copying:

```bash
open ~/Applications/Blink\ Tracker.app
```

Camera permission should be granted for **Blink Tracker** (and/or Terminal/Python if you still launch via `start.command`).

Data and config are stored in:

`~/Library/Application Support/BlinkTracker/`


## Quick start

1. Clone this repo (or download the folder).
2. Double-click `start.command`, **or** run:

```bash
chmod +x start.command
./start.command
```

3. Allow **Camera** for Terminal (and Python if listed) when macOS asks  
   (`System Settings → Privacy & Security → Camera`).
4. Optionally allow **Accessibility** for Terminal so “main app” logging is accurate, and **Notifications** for reminders.

## Config

Open **Config** in the app:

- Reminder interval in **seconds** (example: `120` = every 2 minutes)
- CSV export for a start/end timestamp range

## Privacy

- No cloud sync, no account, no analytics in this project
- Blink history stays in a local SQLite file (`blinks.db`), which is gitignored

## Stack

- Python, Tkinter
- OpenCV, NumPy, Pillow
- macOS notifications and frontmost-app via AppleScript

## License

MIT
