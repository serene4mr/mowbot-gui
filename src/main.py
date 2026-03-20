# src/main.py
import os
import sys

# Favor software rendering in containerized/headless environments where
# OpenGL/Vulkan contexts are often unavailable.
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QSG_RHI_BACKEND", "opengl")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")

from PySide6.QtWidgets import QApplication
from ui.main_window import MowbotGUI

def main():
    # Initialize the Qt Application
    app = QApplication(sys.argv)
    
    # Optional: Apply global dark theme stylesheet here
    # app.setStyleSheet(open("assets/styles/dark_theme.qss").read())

    # Create and show the Main Window
    window = MowbotGUI()
    window.show()

    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()