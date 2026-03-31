"""Right sidebar: SET / TCH / RUN tabs, actions, and E-stop."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

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
    QProgressBar,
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
        self._system_ready: bool = False
        self._mission_loaded: bool = False
        self._mission_executing: bool = False
        self._docker_service_labels: Dict[str, QLabel] = {}
        self.setStyleSheet(theme.PANEL_STYLE)
        self._setup_ui()
        self._wire_signals()
        self.set_tch_recording_active(False)
        self._apply_system_lock()

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
        layout.addWidget(self.btn_start_system)

        self._docker_service_container = QVBoxLayout()
        self._docker_service_container.setContentsMargins(0, 8, 0, 0)
        layout.addLayout(self._docker_service_container)

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
        self.btn_execute.setEnabled(False)
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

        self.lbl_mission_heading = QLabel("MISSION PROGRESS")
        self.lbl_mission_heading.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_XS}px; "
            "font-weight: bold; margin-top: 12px;"
        )
        self.lbl_mission_status = QLabel("IDLE")
        self.lbl_mission_status.setStyleSheet(
            f"font-size: {theme.FONT_MD}px; font-weight: bold; "
            f"color: {theme.TEXT_MUTED};"
        )
        self.lbl_mission_order = QLabel("--")
        self.lbl_mission_order.setWordWrap(True)
        self.lbl_mission_order.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_XS}px;"
        )
        self.progress_mission = QProgressBar()
        self.progress_mission.setRange(0, 100)
        self.progress_mission.setValue(0)
        self.progress_mission.setTextVisible(True)
        self.progress_mission.setFormat("%p%")
        self.progress_mission.setStyleSheet(
            f"QProgressBar {{ border: 1px solid #444; border-radius: 4px; "
            f"text-align: center; color: {theme.TEXT_WHITE}; height: 22px; }}"
            f"QProgressBar::chunk {{ background-color: {theme.ACCENT_GREEN}; }}"
        )
        self.lbl_mission_fraction = QLabel("")
        self.lbl_mission_fraction.setStyleSheet(
            f"font-size: {theme.FONT_SM}px; color: {theme.TEXT_PRIMARY};"
        )
        layout.addWidget(self.lbl_mission_heading)
        layout.addWidget(self.lbl_mission_status)
        layout.addWidget(self.lbl_mission_order)
        layout.addWidget(self.progress_mission)
        layout.addWidget(self.lbl_mission_fraction)

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
        self.btn_tab_run.setEnabled(not active and self._system_ready)
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

    def set_mission_loaded(self, loaded: bool) -> None:
        self._mission_loaded = loaded
        self._refresh_execute_enabled()

    def _refresh_execute_enabled(self) -> None:
        self.btn_execute.setEnabled(self._mission_loaded and not self._mission_executing)

    def update_mission_progress(
        self,
        status: str,
        order_id: str,
        completed: int,
        total: int,
        _last_node_index: int,
    ) -> None:
        """Update RUN tab mission progress (idle / executing / completed / failed)."""
        st = (status or "idle").strip().lower()
        self._mission_executing = st == "executing"
        self._refresh_execute_enabled()
        if st == "idle":
            self.lbl_mission_status.setText("IDLE")
            self.lbl_mission_status.setStyleSheet(
                f"font-size: {theme.FONT_MD}px; font-weight: bold; "
                f"color: {theme.TEXT_MUTED};"
            )
            self.lbl_mission_order.setText("--")
            self.progress_mission.setValue(0)
            self.lbl_mission_fraction.setText("")
            return

        oid = (order_id or "").strip() or "--"
        self.lbl_mission_order.setText(f"Order: {oid}")

        if st == "completed":
            self.lbl_mission_status.setText("COMPLETED")
            self.lbl_mission_status.setStyleSheet(
                f"font-size: {theme.FONT_MD}px; font-weight: bold; "
                f"color: {theme.ACCENT_BLUE};"
            )
            self.progress_mission.setValue(100)
            if total > 0:
                self.lbl_mission_fraction.setText(f"Node {total} / {total}")
            else:
                self.lbl_mission_fraction.setText("Done")
            return

        if st == "failed":
            self.lbl_mission_status.setText("FAILED")
            self.lbl_mission_status.setStyleSheet(
                f"font-size: {theme.FONT_MD}px; font-weight: bold; "
                f"color: {theme.ACCENT_RED};"
            )
            pct = int(round(100.0 * completed / total)) if total > 0 else 0
            self.progress_mission.setValue(min(100, max(0, pct)))
            if total > 0:
                self.lbl_mission_fraction.setText(f"Node {completed} / {total}")
            else:
                self.lbl_mission_fraction.setText("Failed")
            return

        # executing
        self.lbl_mission_status.setText("EXECUTING")
        self.lbl_mission_status.setStyleSheet(
            f"font-size: {theme.FONT_MD}px; font-weight: bold; "
            f"color: {theme.ACCENT_GREEN};"
        )
        pct = int(round(100.0 * completed / total)) if total > 0 else 0
        self.progress_mission.setValue(min(100, max(0, pct)))
        if total > 0:
            self.lbl_mission_fraction.setText(f"Node {completed} / {total}")
        else:
            self.lbl_mission_fraction.setText("")

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
            self.set_system_starting()
        else:
            self.set_system_stopping()
        self.start_system_state_changed.emit(starting)

    def current_tab_index(self) -> int:
        return self.stacked_widget.currentIndex()

    # ── Docker service status UI ─────────────────────────────

    _PHASE_DISPLAY = {
        "pending": ("--", theme.TEXT_MUTED),
        "starting": ("STARTING", theme.ACCENT_YELLOW),
        "settling": ("SETTLING", theme.ACCENT_YELLOW),
        "ready": ("RUNNING", theme.ACCENT_GREEN),
        "running": ("RUNNING", theme.ACCENT_GREEN),
        "failed": ("FAILED", theme.ACCENT_RED),
        "stopping": ("STOPPING", theme.ACCENT_YELLOW),
        "stopped": ("STOPPED", theme.TEXT_MUTED),
        "missing": ("MISSING", theme.ACCENT_RED),
        "error": ("ERROR", theme.ACCENT_RED),
    }

    def init_docker_service_labels(self, keys: List[str]) -> None:
        """Build one status row per service key (called once at startup)."""
        for key in keys:
            row = QHBoxLayout()
            name_lbl = QLabel(key.replace("_", " ").title())
            name_lbl.setStyleSheet(f"font-size: {theme.FONT_SM}px;")
            status_lbl = QLabel("--")
            status_lbl.setStyleSheet(
                f"font-size: {theme.FONT_SM}px; color: {theme.TEXT_MUTED}; "
                "font-weight: bold;"
            )
            status_lbl.setMinimumWidth(90)
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(status_lbl)
            self._docker_service_container.addLayout(row)
            self._docker_service_labels[key] = status_lbl

    def set_docker_step_status(self, _index: int, key: str, phase: str) -> None:
        """Update the status label for a specific service key."""
        lbl = self._docker_service_labels.get(key)
        if lbl is None:
            return
        text, color = self._PHASE_DISPLAY.get(phase, (phase.upper(), theme.TEXT_MUTED))
        lbl.setText(text)
        lbl.setStyleSheet(
            f"font-size: {theme.FONT_SM}px; color: {color}; font-weight: bold;"
        )

    def _apply_system_lock(self) -> None:
        """Enable/disable TCH and RUN tabs based on system readiness.

        Respects teach-in session lock: if teach-in is active, SET and RUN
        remain locked by the teach-in session regardless of system readiness.
        E-STOP and the START SYSTEM button are never locked by this.
        """
        if self._tch_session_active:
            return
        self.btn_tab_tch.setEnabled(self._system_ready)
        self.btn_tab_run.setEnabled(self._system_ready)

    def set_system_starting(self) -> None:
        self._system_ready = False
        self._apply_system_lock()
        self.btn_start_system.setText("STARTING...")
        self.btn_start_system.setEnabled(False)
        self.btn_start_system.setStyleSheet(
            theme.primary_button_style(theme.ACCENT_YELLOW)
        )
        for lbl in self._docker_service_labels.values():
            lbl.setText("--")
            lbl.setStyleSheet(
                f"font-size: {theme.FONT_SM}px; color: {theme.TEXT_MUTED}; "
                "font-weight: bold;"
            )

    def set_system_stopping(self) -> None:
        self._system_ready = False
        self._apply_system_lock()
        self.btn_start_system.setText("STOPPING...")
        self.btn_start_system.setEnabled(False)
        self.btn_start_system.setStyleSheet(
            theme.primary_button_style(theme.ACCENT_YELLOW)
        )

    def set_system_running(self) -> None:
        self._system_ready = True
        self._apply_system_lock()
        self.btn_start_system.setText("SHUTDOWN SYSTEM")
        self.btn_start_system.setEnabled(True)
        self.btn_start_system.setStyleSheet(
            theme.primary_button_style(theme.ACCENT_RED)
        )

    def set_system_stopped(self) -> None:
        self._system_ready = False
        self._apply_system_lock()
        self.btn_start_system.setText("START SYSTEM")
        self.btn_start_system.setEnabled(True)
        self.btn_start_system.setStyleSheet(
            theme.primary_button_style(theme.BUTTON_START)
        )

    def set_system_failed(self) -> None:
        self._system_ready = False
        self._apply_system_lock()
        self.btn_start_system.setText("START SYSTEM")
        self.btn_start_system.setEnabled(True)
        self.btn_start_system.setStyleSheet(
            theme.primary_button_style(theme.BUTTON_START)
        )
