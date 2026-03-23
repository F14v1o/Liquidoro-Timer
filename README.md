# Pomodoro Productivity Tool

A modern, "Liquid Glass" Pomodoro timer with an integrated To-Do list.

## Features
- **Liquid Glass Aesthetic**: High-blur frosted transparency with a sleek 1px border.
- **Dual-Pane Layout**: Large timer on the left, slim To-Do list on the right.
- **Timer Presets**: Quick-start with 25m, 50m, or 90m slots.
- **Custom Duration**: Click the timer text to set a custom time.
- **Integrated Alarm**: Uses `Lofi.mp3` as a fixed alarm sound (11s looping segment).
- **Integrated To-Do**: Add tasks, check them off, and delete them.
- **Local Task Persistence**: To-Dos are saved locally and restored on next app start.
- **Always on Top**: Toggle the 'Pin' icon to keep the timer visible over other windows.
- **Focus Mode**: Compact overlay mode with drag support and double-click to exit.
- **Compact Mode**: Collapse the To-Do list for a minimal timer view.
- **System Tray**: Minimizes to the system tray (Hidden Icons) to stay out of the taskbar.
- **Custom Window Controls**: Includes `MIN` and `X` (close app).

## Download / Run
- **From source build output**: `dist/PomodoroTimer.exe`
- **For sharing**: Publish `dist/PomodoroTimer.exe` in a GitHub Release (recommended).

## Development
- **Language**: Python 3.11
- **UI Framework**: PyQt6
- **Dependencies**: PyQt6, qframelesswindow, BlurWindow, PyInstaller

To rebuild the project:
1. Install dependencies: `pip install -r requirements.txt`
2. Run build script: `python build_exe.py`

## Data storage
- Tasks are saved per Windows user in:
  - `%APPDATA%\PomodoroTimer\tasks.json`
