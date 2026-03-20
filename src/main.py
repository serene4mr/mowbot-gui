# src/main.py
import sys
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