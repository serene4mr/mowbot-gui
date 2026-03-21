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

from ui import theme


class RightSidebar(QFrame):
    tab_changed = Signal(int)
    start_system_state_changed = Signal(bool)
    save_mission_requested = Signal()
    estop_pressed = Signal()
    log_point_requested = Signal()
    auto_record_clicked = Signal()
    execute_mission_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(theme.PANEL_STYLE)
        self._setup_ui()
        self._wire_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        tab_layout = QHBoxLayout()
        self.btn_tab_set = QPushButton("SET")
        self.btn_tab_tch = QPushButton("TCH")
        self.btn_tab_run = QPushButton("RUN")

        for btn in (self.btn_tab_set, self.btn_tab_tch, self.btn_tab_run):
            btn.setStyleSheet(theme.TAB_BUTTON_STYLE)
            btn.setCheckable(True)
            tab_layout.addWidget(btn)

        self.btn_tab_set.setChecked(True)
        main_layout.addLayout(tab_layout)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self._build_set_page())
        self.stacked_widget.addWidget(self._build_tch_page())
        self.stacked_widget.addWidget(self._build_run_page())
        main_layout.addWidget(self.stacked_widget)

        self.btn_estop = QPushButton("EMERGENCY STOP")
        self.btn_estop.setStyleSheet(theme.ESTOP_STYLE)
        main_layout.addWidget(self.btn_estop)

    def _build_set_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.btn_start_system = QPushButton("START SYSTEM")
        self.btn_start_system.setStyleSheet(theme.primary_button_style(theme.BUTTON_START))

        lbl_status = QLabel(
            "\n[OK] Sensing Layer\n[OK] Localization\n[OK] Navigation\n\nSTATUS: READY"
        )
        lbl_status.setStyleSheet(f"font-size: {theme.FONT_MD}px; line-height: 1.5;")

        layout.addWidget(self.btn_start_system)
        layout.addWidget(lbl_status)
        layout.addStretch()
        return page

    def _build_tch_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("TYPE: [ PATH ] | [ POLY ]"))
        layout.addWidget(QLabel("Waypoints: 24\nArea: ~150 m^2\n"))

        self.btn_log = QPushButton("LOG POINT")
        self.btn_auto = QPushButton("AUTO-RECORD (ON)")
        self.btn_save = QPushButton("FINISH & SAVE")

        self.btn_log.setStyleSheet(theme.action_button_style())
        self.btn_auto.setStyleSheet(theme.action_button_style())
        self.btn_save.setStyleSheet(
            theme.action_button_style(bg=theme.ACCENT_ORANGE, bold=True)
            + " margin-top: 10px;"
        )

        layout.addWidget(self.btn_log)
        layout.addWidget(self.btn_auto)
        layout.addWidget(self.btn_save)
        layout.addStretch()
        return page

    def _build_run_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.combo_mission = QComboBox()
        self.combo_mission.addItems(["Lawn_Zone_A_01.json", "Backyard_Path.json"])
        self.combo_mission.setStyleSheet(
            f"background-color: {theme.BUTTON_BG}; padding: 10px; "
            f"font-size: {theme.FONT_SM}px;"
        )

        self.btn_execute = QPushButton("EXECUTE MISSION")
        self.btn_execute.setStyleSheet(
            theme.primary_button_style(theme.BUTTON_EXECUTE) + " margin-top: 10px;"
        )

        layout.addWidget(QLabel("Select Mission:"))
        layout.addWidget(self.combo_mission)
        layout.addWidget(self.btn_execute)
        layout.addWidget(QLabel("\nProgress: 65%"))

        self.mission_progress = QProgressBar()
        self.mission_progress.setValue(65)
        layout.addWidget(self.mission_progress)

        layout.addWidget(QLabel("Action: MOWING"))
        layout.addStretch()
        return page

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
        starting = "START" in self.btn_start_system.text()
        if starting:
            self.btn_start_system.setText("SHUTDOWN SYSTEM")
            self.btn_start_system.setStyleSheet(
                theme.primary_button_style(theme.ACCENT_RED)
            )
        else:
            self.btn_start_system.setText("START SYSTEM")
            self.btn_start_system.setStyleSheet(
                theme.primary_button_style(theme.BUTTON_START)
            )
        self.start_system_state_changed.emit(starting)

    def current_tab_index(self) -> int:
        return self.stacked_widget.currentIndex()
