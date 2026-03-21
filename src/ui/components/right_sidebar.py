"""Right sidebar: SET / TCH / RUN tabs, actions, and E-stop."""

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QComboBox,
    QProgressBar,
    QWidget,
)
from PySide6.QtCore import Signal


class RightSidebar(QFrame):
    tab_changed = Signal(int)
    start_system_state_changed = Signal(bool)  # True when "system running" (shutdown shown)
    save_mission_requested = Signal()
    estop_pressed = Signal()
    log_point_requested = Signal()
    auto_record_clicked = Signal()
    execute_mission_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(20, 25, 30, 210); border-radius: 10px; color: white;"
        )
        self._setup_ui()
        self._wire_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        tab_layout = QHBoxLayout()
        self.btn_tab_set = QPushButton("SET")
        self.btn_tab_tch = QPushButton("TCH")
        self.btn_tab_run = QPushButton("RUN")

        tab_style = """
            QPushButton { background-color: #333; color: white; border-radius: 5px; padding: 10px; font-weight:bold;}
            QPushButton:checked { background-color: #00B0FF; }
        """
        for btn in (self.btn_tab_set, self.btn_tab_tch, self.btn_tab_run):
            btn.setStyleSheet(tab_style)
            btn.setCheckable(True)
            tab_layout.addWidget(btn)

        self.btn_tab_set.setChecked(True)
        main_layout.addLayout(tab_layout)

        self.stacked_widget = QStackedWidget()

        # SET
        page_set = QWidget()
        layout_set = QVBoxLayout(page_set)
        self.btn_start_system = QPushButton("START SYSTEM")
        self.btn_start_system.setStyleSheet(
            "background-color: #2962FF; color: white; font-size: 16px; font-weight: bold; "
            "padding: 20px; border-radius: 8px;"
        )
        lbl_status = QLabel(
            "\n[OK] Sensing Layer\n[OK] Localization\n[OK] Navigation\n\nSTATUS: READY"
        )
        lbl_status.setStyleSheet("font-size: 15px; line-height: 1.5;")
        layout_set.addWidget(self.btn_start_system)
        layout_set.addWidget(lbl_status)
        layout_set.addStretch()
        self.stacked_widget.addWidget(page_set)

        # TCH
        page_tch = QWidget()
        layout_tch = QVBoxLayout(page_tch)
        layout_tch.addWidget(QLabel("TYPE: [ PATH ] | [ POLY ]"))
        layout_tch.addWidget(QLabel("Waypoints: 24\nArea: ~150 m^2\n"))
        self.btn_log = QPushButton("LOG POINT")
        self.btn_auto = QPushButton("AUTO-RECORD (ON)")
        self.btn_save = QPushButton("FINISH & SAVE")
        btn_style = (
            "background-color: #424242; color: white; padding: 15px; "
            "border-radius: 8px; margin-bottom: 5px;"
        )
        self.btn_log.setStyleSheet(btn_style)
        self.btn_auto.setStyleSheet(btn_style)
        self.btn_save.setStyleSheet(
            "background-color: #FF6D00; color: white; padding: 15px; font-weight: bold; "
            "border-radius: 8px; margin-top: 10px;"
        )
        layout_tch.addWidget(self.btn_log)
        layout_tch.addWidget(self.btn_auto)
        layout_tch.addWidget(self.btn_save)
        layout_tch.addStretch()
        self.stacked_widget.addWidget(page_tch)

        # RUN
        page_run = QWidget()
        layout_run = QVBoxLayout(page_run)
        self.combo_mission = QComboBox()
        self.combo_mission.addItems(["Lawn_Zone_A_01.json", "Backyard_Path.json"])
        self.combo_mission.setStyleSheet(
            "background-color: #333; padding: 10px; font-size: 14px;"
        )
        self.btn_execute = QPushButton("EXECUTE MISSION")
        self.btn_execute.setStyleSheet(
            "background-color: #00C853; color: white; font-size: 16px; font-weight: bold; "
            "padding: 20px; border-radius: 8px; margin-top: 10px;"
        )
        layout_run.addWidget(QLabel("Select Mission:"))
        layout_run.addWidget(self.combo_mission)
        layout_run.addWidget(self.btn_execute)
        layout_run.addWidget(QLabel("\nProgress: 65%"))
        self.mission_progress = QProgressBar()
        self.mission_progress.setValue(65)
        layout_run.addWidget(self.mission_progress)
        layout_run.addWidget(QLabel("Action: MOWING"))
        layout_run.addStretch()
        self.stacked_widget.addWidget(page_run)

        main_layout.addWidget(self.stacked_widget)

        self.btn_estop = QPushButton("EMERGENCY STOP")
        self.btn_estop.setStyleSheet(
            """
            QPushButton { background-color: #D50000; color: white; font-size: 18px;
                font-weight: bold; padding: 25px; border-radius: 8px; }
            QPushButton:pressed { background-color: #9b0000; }
        """
        )
        main_layout.addWidget(self.btn_estop)

    def _wire_signals(self):
        self.btn_tab_set.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_tch.clicked.connect(lambda: self.switch_tab(1))
        self.btn_tab_run.clicked.connect(lambda: self.switch_tab(2))
        self.btn_start_system.clicked.connect(self._toggle_start_system)
        self.btn_save.clicked.connect(self.save_mission_requested.emit)
        self.btn_estop.clicked.connect(self.estop_pressed.emit)
        self.btn_log.clicked.connect(self.log_point_requested.emit)
        self.btn_auto.clicked.connect(self.auto_record_clicked.emit)
        self.btn_execute.clicked.connect(self.execute_mission_requested.emit)

    def switch_tab(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        self.btn_tab_set.setChecked(index == 0)
        self.btn_tab_tch.setChecked(index == 1)
        self.btn_tab_run.setChecked(index == 2)
        self.tab_changed.emit(index)

    def _toggle_start_system(self) -> None:
        if "START" in self.btn_start_system.text():
            self.btn_start_system.setText("SHUTDOWN SYSTEM")
            self.btn_start_system.setStyleSheet(
                "background-color: #D50000; color: white; font-size: 16px; font-weight: bold; "
                "padding: 20px; border-radius: 8px;"
            )
            self.start_system_state_changed.emit(True)
        else:
            self.btn_start_system.setText("START SYSTEM")
            self.btn_start_system.setStyleSheet(
                "background-color: #2962FF; color: white; font-size: 16px; font-weight: bold; "
                "padding: 20px; border-radius: 8px;"
            )
            self.start_system_state_changed.emit(False)

    def current_tab_index(self) -> int:
        return self.stacked_widget.currentIndex()
