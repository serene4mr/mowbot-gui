# src/ui/main_window.py
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class MowbotGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- 1. WINDOW SETUP (Kiosk Mode) ---
        self.setWindowTitle("Mowbot VDA5050 Fleet Manager")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #121212; color: #FFFFFF;")

        # --- 2. LAYER 0: MAP BACKGROUND ---
        # Later, this will be replaced by QWebEngineView for ESRI Maps
        self.map_placeholder = QLabel("ESRI MAP BACKGROUND\n(Awaiting WebEngine)", self)
        self.map_placeholder.setAlignment(Qt.AlignCenter)
        self.map_placeholder.setStyleSheet("background-color: #2A2A2A; color: #555555; font-size: 40px; font-weight: bold;")
        self.setCentralWidget(self.map_placeholder)

        # --- 3. LAYER 1: TOP HEADER (Status Bar) ---
        self.header_panel = QFrame(self)
        self.header_panel.setStyleSheet("background-color: rgba(0, 0, 0, 180); border-bottom: 2px solid #333;")
        self.header_layout = QHBoxLayout(self.header_panel)
        
        # Header Components
        self.lbl_robot_id = QLabel("🚜 MOWBOT-001")
        self.lbl_robot_id.setStyleSheet("font-size: 24px; font-weight: bold; color: #00E676;")
        
        self.lbl_vda_mode = QLabel("MODE: MANUAL")
        self.lbl_vda_mode.setStyleSheet("font-size: 20px; color: #FFD600;")
        
        self.lbl_battery = QLabel("🔋 100%")
        self.lbl_battery.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.header_layout.addWidget(self.lbl_robot_id)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.lbl_vda_mode)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.lbl_battery)

        # --- 4. LAYER 2: RIGHT SIDEBAR (Controls) ---
        self.sidebar_panel = QFrame(self)
        self.sidebar_panel.setStyleSheet("background-color: rgba(20, 20, 20, 230); border-left: 2px solid #333;")
        self.sidebar_layout = QVBoxLayout(self.sidebar_panel)
        self.sidebar_layout.setContentsMargins(20, 30, 20, 30)
        self.sidebar_layout.setSpacing(20)

        # Sidebar Components
        lbl_control_title = QLabel("MISSION CONTROL")
        lbl_control_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #AAAAAA;")
        lbl_control_title.setAlignment(Qt.AlignCenter)

        self.btn_start_system = QPushButton("START SYSTEM")
        self.btn_start_system.setMinimumHeight(80)
        self.btn_start_system.setStyleSheet("""
            QPushButton { background-color: #2962FF; font-size: 22px; font-weight: bold; border-radius: 10px; }
            QPushButton:pressed { background-color: #0039CB; }
        """)

        # Container Status Indicators (Fake data for skeleton)
        self.lbl_container_status = QLabel(
            "🟢 Hardware Sensing\n"
            "🔴 Localization (Wait)\n"
            "🔴 Navigation (Wait)"
        )
        self.lbl_container_status.setStyleSheet("font-size: 18px; line-height: 1.5;")

        self.btn_estop = QPushButton("EMERGENCY STOP")
        self.btn_estop.setMinimumHeight(120)
        self.btn_estop.setStyleSheet("""
            QPushButton { background-color: #D50000; color: white; font-size: 28px; font-weight: bold; border-radius: 15px; }
            QPushButton:pressed { background-color: #9B0000; }
        """)

        # Assemble Sidebar
        self.sidebar_layout.addWidget(lbl_control_title)
        self.sidebar_layout.addWidget(self.btn_start_system)
        self.sidebar_layout.addWidget(self.lbl_container_status)
        self.sidebar_layout.addStretch() # Pushes E-STOP to the very bottom
        self.sidebar_layout.addWidget(self.btn_estop)

        # Connect Quit for testing (Remove in production!)
        self.btn_estop.clicked.connect(self.close)

        # Show fullscreen only after all child widgets exist.
        self.showFullScreen()  # Fullscreen for the actual robot display

    def resizeEvent(self, event):
        """Dynamically pin the Overlays to the edges when the screen resizes."""
        super().resizeEvent(event)
        if not hasattr(self, "header_panel") or not hasattr(self, "sidebar_panel"):
            return
        w = self.width()
        h = self.height()
        
        # Header: Full width minus sidebar, 70px tall, positioned at Top-Left
        sidebar_width = 350
        header_height = 70
        self.header_panel.setGeometry(0, 0, w - sidebar_width, header_height)
        
        # Sidebar: 350px wide, Full height, positioned at Right edge
        self.sidebar_panel.setGeometry(w - sidebar_width, 0, sidebar_width, h)