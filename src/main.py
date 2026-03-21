# src/main.py
import os
import signal
import sys

# Favor software rendering in containerized/headless environments where
# OpenGL/Vulkan contexts are often unavailable.
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QSG_RHI_BACKEND", "opengl")
os.environ.setdefault("QT_OPENGL", "software")
# QWebEngine / MapLibre: WebGL. If you see "Could not create a WebGL context" / libGL errors,
# (1) try SwiftShader (software WebGL) via flags below, or (2) use raster map only:
#     MOWBOT_MAP_BACKEND=leaflet python src/main.py
# Override anytime: QTWEBENGINE_CHROMIUM_FLAGS="..."
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    " ".join(
        [
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--enable-unsafe-swiftshader",  # software WebGL when GPU/GL init fails
            "--disable-gpu-sandbox",
        ]
    ),
)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.main_window import MainWindow

def main():
    # Initialize the Qt Application
    app = QApplication(sys.argv)
    
    # Optional: Apply global dark theme stylesheet here
    # app.setStyleSheet(open("assets/styles/dark_theme.qss").read())

    # Create and show the Main Window
    window = MainWindow()
    window.showFullScreen()

    def _graceful_shutdown(signum, _frame):
        signal_name = signal.Signals(signum).name
        print(f"\nShutdown requested ({signal_name}); closing Qt app...")
        app.quit()

    # Handle terminal and process-manager stop signals gracefully.
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    # Keep Python responsive to signals while Qt event loop is running.
    keepalive = QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(200)

    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()