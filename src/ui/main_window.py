import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QStackedWidget, 
                               QComboBox, QProgressBar, QFrame, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWebEngineWidgets import QWebEngineView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mowbot Control")
        self.resize(1280, 800)
        self.setStyleSheet("QMainWindow { background-color: #121212; }")

        # ==========================================
        # LAYER 1: BACKGROUND MAP
        # ==========================================
        self.map_view = QWebEngineView(self)
        # Temporary HTML placeholder instead of a real ESRI map
        self.map_view.setHtml("""
            <body style='background-color:#1e1e1e; color:#555; display:flex; 
            justify-content:center; align-items:center; height:100vh; margin:0; font-family:sans-serif;'>
            <h1>ESRI MAP AREA</h1></body>
        """)
        self.setCentralWidget(self.map_view)

        # ==========================================
        # LAYER 2: LEFT HUD (MONITORING)
        # ==========================================
        self.hud_panel = QFrame(self)
        self.hud_panel.setStyleSheet("background-color: rgba(20, 25, 30, 210); border-radius: 10px; color: white;")
        self.setup_left_hud()

        # ==========================================
        # LAYER 3: RIGHT SIDEBAR (CONTROL)
        # ==========================================
        self.sidebar_panel = QFrame(self)
        self.sidebar_panel.setStyleSheet("background-color: rgba(20, 25, 30, 210); border-radius: 10px; color: white;")
        self.setup_right_sidebar()

    # ---------------------------------------------------------
    # SET UP LEFT HUD
    # ---------------------------------------------------------
    def setup_left_hud(self):
        layout = QVBoxLayout(self.hud_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("TELEMETRY")
        title.setStyleSheet("color: #00E676; font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        self.lbl_pos = QLabel("📍 POS: 12.45, -5.20, 45°")
        self.lbl_vel = QLabel("🚀 VEL: 0.55 m/s")
        self.lbl_gps = QLabel("🛰️ GPS: RTK FIX")
        self.lbl_bat = QLabel("🔋 BAT: 85% (25.4V)")

        for lbl in [self.lbl_pos, self.lbl_vel, self.lbl_gps, self.lbl_bat]:
            lbl.setStyleSheet("font-size: 15px; font-family: monospace;")
            layout.addWidget(lbl)

        layout.addStretch() # Push all content to the top

    # ---------------------------------------------------------
    # SET UP RIGHT SIDEBAR (3 TABS)
    # ---------------------------------------------------------
    def setup_right_sidebar(self):
        main_layout = QVBoxLayout(self.sidebar_panel)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- 1. TAB SWITCH MENU ---
        tab_layout = QHBoxLayout()
        self.btn_tab_set = QPushButton("SET")
        self.btn_tab_tch = QPushButton("TCH")
        self.btn_tab_run = QPushButton("RUN")

        tab_style = """
            QPushButton { background-color: #333; color: white; border-radius: 5px; padding: 10px; font-weight:bold;}
            QPushButton:checked { background-color: #00B0FF; }
        """
        for btn in [self.btn_tab_set, self.btn_tab_tch, self.btn_tab_run]:
            btn.setStyleSheet(tab_style)
            btn.setCheckable(True)
            tab_layout.addWidget(btn)
        
        self.btn_tab_set.setChecked(True) # SET is selected by default
        main_layout.addLayout(tab_layout)

        # --- 2. QSTACKEDWIDGET (DYNAMIC AREA) ---
        self.stacked_widget = QStackedWidget()
        
        # Page 1: SET (Setup)
        page_set = QWidget()
        layout_set = QVBoxLayout(page_set)
        self.btn_start_system = QPushButton("🚀 START SYSTEM")
        self.btn_start_system.setStyleSheet("background-color: #2962FF; color: white; font-size: 16px; font-weight: bold; padding: 20px; border-radius: 8px;")
        
        lbl_status = QLabel("\nHEALTH CHECK:\n🟢 Sensing Layer\n🟢 Localization\n🟢 Navigation\n\nSTATUS: READY")
        lbl_status.setStyleSheet("font-size: 15px; line-height: 1.5;")
        
        layout_set.addWidget(self.btn_start_system)
        layout_set.addWidget(lbl_status)
        layout_set.addStretch()
        self.stacked_widget.addWidget(page_set)

        # Page 2: TCH (Teach-In)
        page_tch = QWidget()
        layout_tch = QVBoxLayout(page_tch)
        layout_tch.addWidget(QLabel("TYPE: [ PATH ] | [ POLY ]"))
        layout_tch.addWidget(QLabel("Waypoints: 24\nArea: ~150 m²\n"))
        
        btn_log = QPushButton("📍 LOG POINT")
        btn_auto = QPushButton("⏺ AUTO-RECORD (ON)")
        self.btn_save = QPushButton("💾 FINISH & SAVE")
        
        btn_action_style = "background-color: #424242; color: white; padding: 15px; border-radius: 8px; margin-bottom: 5px;"
        btn_log.setStyleSheet(btn_action_style)
        btn_auto.setStyleSheet(btn_action_style)
        self.btn_save.setStyleSheet("background-color: #FF6D00; color: white; padding: 15px; font-weight: bold; border-radius: 8px; margin-top: 10px;")
        
        layout_tch.addWidget(btn_log)
        layout_tch.addWidget(btn_auto)
        layout_tch.addWidget(self.btn_save)
        layout_tch.addStretch()
        self.stacked_widget.addWidget(page_tch)

        # Page 3: RUN (Auto-Run)
        page_run = QWidget()
        layout_run = QVBoxLayout(page_run)
        
        combo_mission = QComboBox()
        combo_mission.addItems(["Lawn_Zone_A_01.json", "Backyard_Path.json"])
        combo_mission.setStyleSheet("background-color: #333; padding: 10px; font-size: 14px;")
        
        btn_execute = QPushButton("🚀 EXECUTE MISSION")
        btn_execute.setStyleSheet("background-color: #00C853; color: white; font-size: 16px; font-weight: bold; padding: 20px; border-radius: 8px; margin-top: 10px;")
        
        layout_run.addWidget(QLabel("Select Mission:"))
        layout_run.addWidget(combo_mission)
        layout_run.addWidget(btn_execute)
        
        layout_run.addWidget(QLabel("\nProgress: 65%"))
        prog = QProgressBar()
        prog.setValue(65)
        layout_run.addWidget(prog)
        layout_run.addWidget(QLabel("Action: MOWING"))
        layout_run.addStretch()
        self.stacked_widget.addWidget(page_run)

        main_layout.addWidget(self.stacked_widget)

        # --- 3. STATIC SECTION: LARGE E-STOP BUTTON ---
        self.btn_estop = QPushButton("EMERGENCY STOP")
        self.btn_estop.setStyleSheet("""
            QPushButton { background-color: #D50000; color: white; font-size: 18px; font-weight: bold; padding: 25px; border-radius: 8px; }
            QPushButton:pressed { background-color: #9b0000; }
        """)
        main_layout.addWidget(self.btn_estop)

        # --- CONNECT SIGNALS ---
        self.btn_tab_set.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_tch.clicked.connect(lambda: self.switch_tab(1))
        self.btn_tab_run.clicked.connect(lambda: self.switch_tab(2))
        self.btn_start_system.clicked.connect(self.toggle_system)
        self.btn_save.clicked.connect(self.show_save_dialog)

    # ---------------------------------------------------------
    # EVENT HANDLING LOGIC
    # ---------------------------------------------------------
    def switch_tab(self, index):
        """Switch QStackedWidget and update tab button UI state."""
        self.stacked_widget.setCurrentIndex(index)
        self.btn_tab_set.setChecked(index == 0)
        self.btn_tab_tch.setChecked(index == 1)
        self.btn_tab_run.setChecked(index == 2)

    def toggle_system(self):
        """Simulate toggling the Start/Shutdown button state."""
        if "START" in self.btn_start_system.text():
            self.btn_start_system.setText("🛑 SHUTDOWN SYSTEM")
            self.btn_start_system.setStyleSheet("background-color: #D50000; color: white; font-size: 16px; font-weight: bold; padding: 20px; border-radius: 8px;")
        else:
            self.btn_start_system.setText("🚀 START SYSTEM")
            self.btn_start_system.setStyleSheet("background-color: #2962FF; color: white; font-size: 16px; font-weight: bold; padding: 20px; border-radius: 8px;")

    def show_save_dialog(self):
        """Simulate showing a save dialog and automatically switch to RUN."""
        QMessageBox.information(self, "Save Mission", "Mission 'Lawn_Zone_A_01' saved successfully!\n\nSwitching to AUTO-RUN mode.")
        self.switch_tab(2) # Automatically switch to the RUN tab

    # ---------------------------------------------------------
    # POSITION FLOATING PANELS (ABSOLUTE POSITIONING)
    # ---------------------------------------------------------
    def resizeEvent(self, event):
        """Keep HUD and Sidebar correctly positioned when resizing the window."""
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        margin = 20
        
        # Keep the Left HUD fixed on the left side
        hud_width = 250
        hud_height = 200
        self.hud_panel.setGeometry(margin, margin, hud_width, hud_height)

        # Keep the Right Sidebar fixed on the right, spanning top to bottom
        sidebar_width = 350
        self.sidebar_panel.setGeometry(w - sidebar_width - margin, margin, sidebar_width, h - (margin * 2))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MowbotGUI()
    window.show()
    sys.exit(app.exec())