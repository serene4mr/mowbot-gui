"""Right sidebar: SET / TCH / RUN tabs, actions, and E-stop."""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QComboBox,
    QWidget,
    QMessageBox,
    QGraphicsOpacityEffect,
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
    undo_requested = Signal()
    clear_teach_requested = Signal()
    tch_mode_path_selected = Signal()
    tch_mode_poly_selected = Signal()
    tch_session_started = Signal()
    tch_session_stopped = Signal()
    execute_mission_requested = Signal()
    delete_mission_requested = Signal()
    load_mission_preview_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tch_session_active: bool = False
        self.setStyleSheet(theme.PANEL_STYLE)
        self._setup_ui()
        self._wire_signals()
        self.set_tch_recording_active(False)

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

        self.btn_tch_toggle = QPushButton("START TEACH-IN")
        self.btn_tch_toggle.setStyleSheet(theme.primary_button_style(theme.BUTTON_START))
        layout.addWidget(self.btn_tch_toggle)

        self.lbl_tch_session_status = QLabel()
        self.lbl_tch_session_status.setWordWrap(True)
        self.lbl_tch_session_status.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_XS}px; "
            "padding: 4px 2px 8px 2px;"
        )
        layout.addWidget(self.lbl_tch_session_status)

        # Everything below is disabled until START is pressed (dimmed + non-interactive).
        self._tch_session_widget = QWidget()
        body = QVBoxLayout(self._tch_session_widget)
        body.setContentsMargins(0, 0, 0, 0)

        self._tch_session_opacity = QGraphicsOpacityEffect(self._tch_session_widget)
        self._tch_session_widget.setGraphicsEffect(self._tch_session_opacity)

        mode_row = QHBoxLayout()
        self.btn_tch_path = QPushButton("PATH")
        self.btn_tch_poly = QPushButton("POLY")
        for b in (self.btn_tch_path, self.btn_tch_poly):
            b.setCheckable(True)
            b.setStyleSheet(theme.TAB_BUTTON_STYLE)
            mode_row.addWidget(b)
        self.btn_tch_path.setChecked(True)
        body.addWidget(QLabel("Recording type:"))
        body.addLayout(mode_row)

        self.lbl_tch_waypoints = QLabel("Waypoints: 0")
        self.lbl_tch_area = QLabel("Area: —")
        for lbl in (self.lbl_tch_waypoints, self.lbl_tch_area):
            lbl.setStyleSheet(f"font-size: {theme.FONT_MD}px;")
        body.addWidget(self.lbl_tch_waypoints)
        body.addWidget(self.lbl_tch_area)

        self.btn_log = QPushButton("LOG POINT")
        self.btn_auto = QPushButton("AUTO-RECORD (OFF)")
        self.btn_undo = QPushButton("UNDO")
        self.btn_clear = QPushButton("CLEAR / RESTART")
        self.btn_save = QPushButton("SAVE")

        self.btn_log.setStyleSheet(theme.action_button_style())
        self.btn_auto.setStyleSheet(theme.action_button_style())
        self.btn_undo.setStyleSheet(theme.action_button_style())
        self.btn_clear.setStyleSheet(theme.action_button_style(bg=theme.ACCENT_RED, bold=True))
        self.btn_save.setStyleSheet(
            theme.action_button_style(bg=theme.ACCENT_ORANGE, bold=True)
            + " QPushButton { margin-top: 10px; }"
        )

        body.addWidget(self.btn_log)
        body.addWidget(self.btn_auto)
        body.addWidget(self.btn_undo)
        body.addWidget(self.btn_clear)
        body.addWidget(self.btn_save)
        body.addStretch()

        layout.addWidget(self._tch_session_widget)
        layout.addStretch()
        return page

    def _build_run_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.combo_mission = QComboBox()
        self.combo_mission.setStyleSheet(
            f"background-color: {theme.BUTTON_BG}; padding: 10px; "
            f"font-size: {theme.FONT_SM}px;"
        )

        self.btn_execute = QPushButton("EXECUTE MISSION")
        self.btn_execute.setStyleSheet(
            theme.primary_button_style(theme.BUTTON_EXECUTE) + " QPushButton { margin-top: 10px; }"
        )

        layout.addWidget(QLabel("Select Mission:"))
        layout.addWidget(self.combo_mission)

        self.btn_load_mission = QPushButton("LOAD ON MAP")
        self.btn_load_mission.setStyleSheet(
            theme.action_button_style(bg=theme.ACCENT_ORANGE, bold=True)
        )
        layout.addWidget(self.btn_load_mission)

        self.btn_delete_mission = QPushButton("DELETE MISSION")
        self.btn_delete_mission.setStyleSheet(
            theme.action_button_style(bg=theme.ACCENT_RED, bold=True)
        )
        layout.addWidget(self.btn_delete_mission)

        layout.addWidget(self.btn_execute)
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
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        self.btn_tch_path.clicked.connect(self._on_path_mode)
        self.btn_tch_poly.clicked.connect(self._on_poly_mode)
        self.btn_tch_toggle.clicked.connect(self._on_tch_toggle_clicked)
        self.btn_execute.clicked.connect(self.execute_mission_requested.emit)
        self.btn_delete_mission.clicked.connect(self.delete_mission_requested.emit)
        self.btn_load_mission.clicked.connect(self.load_mission_preview_requested.emit)

    def _on_path_mode(self) -> None:
        self.btn_tch_path.setChecked(True)
        self.btn_tch_poly.setChecked(False)
        self.tch_mode_path_selected.emit()

    def _on_poly_mode(self) -> None:
        self.btn_tch_poly.setChecked(True)
        self.btn_tch_path.setChecked(False)
        self.tch_mode_poly_selected.emit()

    def _on_tch_toggle_clicked(self) -> None:
        if self._tch_session_active:
            self.set_tch_recording_active(False)
            self.tch_session_stopped.emit()
        else:
            self.set_tch_recording_active(True)
            self.tch_session_started.emit()

    def _refresh_tch_toggle_appearance(self) -> None:
        if self._tch_session_active:
            self.btn_tch_toggle.setText("STOP TEACH-IN")
            self.btn_tch_toggle.setStyleSheet(theme.primary_button_style(theme.ACCENT_RED))
            self.lbl_tch_session_status.setText(
                "Teach-in active — controls below are enabled. "
                "SET and RUN tabs are locked. Press STOP when done."
            )
        else:
            self.btn_tch_toggle.setText("START TEACH-IN")
            self.btn_tch_toggle.setStyleSheet(theme.primary_button_style(theme.BUTTON_START))
            self.lbl_tch_session_status.setText(
                "Press START to unlock recording controls. SET and RUN stay locked during teach-in."
            )

    def set_tch_recording_active(self, active: bool) -> None:
        """When active: enable TCH tools and lock SET/RUN tabs. When inactive: reverse."""
        self._tch_session_active = active
        self._tch_session_widget.setEnabled(active)
        self._tch_session_opacity.setOpacity(1.0 if active else 0.38)
        self.btn_tab_set.setEnabled(not active)
        self.btn_tab_run.setEnabled(not active)
        self._refresh_tch_toggle_appearance()

    def _on_clear_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear teach-in",
            "Discard all logged waypoints and clear the map?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_teach_requested.emit()

    def switch_tab(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        self.btn_tab_set.setChecked(index == 0)
        self.btn_tab_tch.setChecked(index == 1)
        self.btn_tab_run.setChecked(index == 2)
        self.tab_changed.emit(index)

    def set_tch_mode_buttons(self, mode: str) -> None:
        m = (mode or "PATH").upper()
        if m == "POLY":
            self.btn_tch_poly.setChecked(True)
            self.btn_tch_path.setChecked(False)
        else:
            self.btn_tch_path.setChecked(True)
            self.btn_tch_poly.setChecked(False)

    def update_tch_stats(self, waypoint_count: int, area_m2: float) -> None:
        self.lbl_tch_waypoints.setText(f"Waypoints: {waypoint_count}")
        if area_m2 >= 0:
            self.lbl_tch_area.setText(f"Area: ~{area_m2:.1f} m²")
        else:
            self.lbl_tch_area.setText("Area: —")

    def set_auto_record_ui(self, active: bool) -> None:
        if active:
            self.btn_auto.setText("AUTO-RECORD (ON)")
            self.btn_auto.setStyleSheet(
                theme.action_button_style(bg=theme.ACCENT_YELLOW, bold=True)
            )
        else:
            self.btn_auto.setText("AUTO-RECORD (OFF)")
            self.btn_auto.setStyleSheet(theme.action_button_style())

    def set_mission_files(self, filenames: Iterable[str]) -> None:
        names = list(filenames)
        self.combo_mission.clear()
        for name in names:
            self.combo_mission.addItem(name)
        self.btn_delete_mission.setEnabled(len(names) > 0)
        self.btn_load_mission.setEnabled(len(names) > 0)

    def current_mission_filename(self) -> Optional[str]:
        text = self.combo_mission.currentText().strip()
        return text if text else None

    def select_mission_file(self, filename: str) -> None:
        idx = self.combo_mission.findText(filename)
        if idx >= 0:
            self.combo_mission.setCurrentIndex(idx)

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
