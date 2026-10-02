# Soundboard

A Windows and Linux desktop soundboard built with Python. It stays in the
system tray, copies imported audio into its own library, and plays sounds from
customizable global shortcuts.

## Features

- Global one-, two-, or three-key shortcuts on Windows and Linux X11
- WAV, MP3, and OGG imports with managed copies
- Editable unique tags backed by immutable sound IDs
- Overlapping playback for rapid sound effects
- Session playback history that fades after five seconds
- Atomic `sounds.json` and `keybinds.json` persistence
- System-tray Show and Quit actions

Linux global shortcuts require an X11 session.

## Install and run

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
soundboard
```

On Windows, activate the environment with `.venv\Scripts\activate` before
running the remaining commands.

The same app can be launched without the console entry point:

```bash
python -m soundboard
```

## Add the Heartsteel sound

The repository does not redistribute League of Legends audio. Place a WAV file
you have permission to redistribute at:

```text
assets/heartsteel-proc.wav
```

On the next first launch with an empty library, the application copies it into
the managed library and assigns the tag `heartsteel-proc`. Existing libraries
are not overwritten.

## User data

The operating system's application-data location contains:

- `sounds.json`: sound IDs, tags, display names, and managed file names
- `keybinds.json`: canonical shortcuts linked to immutable sound IDs
- `sounds/`: private copies of imported audio

Typical locations are `%LOCALAPPDATA%\soundboard` on Windows and
`~/.local/share/soundboard` on Linux. The exact directory is chosen
by `platformdirs`.

## Controls

1. Add or select a sound in **Sound library**.
2. On Windows or Linux X11, open **Keybindings**, select the sound, and click
   **Listen**. Press up to three keys and release any one key to save the chord.
3. Close the main window to keep the application running in the system tray.

Pure modifier shortcuts such as `Ctrl+Shift` are rejected. Left and right
modifier keys normalize to the same stored shortcut. A held chord plays once
and must be released before it can trigger again.

## Test

```bash
python -m pytest
```

For a headless Linux GUI test run:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
```

Global listeners and actual audio devices still require manual validation on
their target desktops.
