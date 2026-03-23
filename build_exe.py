import os
import PyInstaller.__main__

project_root = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(project_root, "Hour.ico")
project_lofi_path = os.path.join(project_root, "Lofi.mp3")
downloads_lofi_path = os.path.join(os.path.expanduser("~"), "Downloads", "Lofi.mp3")

build_args = [
    "main.py",
    "--onefile",
    "--windowed",
    "--name=PomodoroTimer",
    "--clean",
    "--hidden-import=PyQt6.QtCore",
    "--hidden-import=PyQt6.QtGui",
    "--hidden-import=PyQt6.QtWidgets",
    "--hidden-import=PyQt6.QtMultimedia",
    "--hidden-import=qframelesswindow",
    "--hidden-import=BlurWindow",
]

if os.path.exists(icon_path):
    build_args.append(f"--icon={icon_path}")

if os.path.exists(project_lofi_path):
    build_args.append(f"--add-data={project_lofi_path};.")
elif os.path.exists(downloads_lofi_path):
    build_args.append(f"--add-data={downloads_lofi_path};.")
else:
    print("Warning: Lofi.mp3 not found in project or Downloads. EXE will run without bundled alarm audio.")

PyInstaller.__main__.run(build_args)
