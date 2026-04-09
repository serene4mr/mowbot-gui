"""Top status bar: robot ID, mode, and system summary."""

from __future__ import annotations

import html as html_lib
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from ui import theme

# Whole-word "ERROR" highlighted in red; rest of line stays normal color.
_STATUS_ERROR_TOKEN_RE = re.compile(r"\bERROR\b", re.IGNORECASE)
_GNSS_VALUE_RE = re.compile(r"(GNSS:\s*)([A-Z0-9_]+)", re.IGNORECASE)


def _status_line_html(plain: str) -> str:
    """Plain status → HTML: base neutral, key tokens colorized."""
    s = str(plain)
    inner = html_lib.escape(s)

    # Highlight ERROR tokens in red.
    parts: list[str] = []
    last = 0
    for m in _STATUS_ERROR_TOKEN_RE.finditer(inner):
        parts.append(inner[last : m.start()])
        parts.append(f'<span style="color:{theme.ACCENT_RED};">{m.group(0)}</span>')
        last = m.end()
    parts.append(inner[last:])
    inner = "".join(parts)

    # Highlight GNSS value by quality/state while keeping labels neutral.
    def _gnss_repl(m: re.Match[str]) -> str:
        prefix = m.group(1)
        value = m.group(2).upper()
        if value in {"RTK_FIXED", "FLOAT"}:
            color = theme.ACCENT_GREEN
        elif value in {"SINGLE", "WARNING", "WARN"}:
            color = theme.ACCENT_YELLOW
        elif value in {"NO_FIX", "FATAL"}:
            color = theme.ACCENT_RED
        else:
            color = theme.TEXT_PRIMARY
        return f'{prefix}<span style="color:{color};">{value}</span>'

    inner = _GNSS_VALUE_RE.sub(_gnss_repl, inner)
    return (
        f'<span style="color:{theme.TEXT_PRIMARY}; font-size:{theme.FONT_LG}px; '
        f'font-weight: bold; white-space: nowrap;">{inner}</span>'
    )


class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(theme.TOPBAR_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.lbl_robot_id = QLabel("MOWBOT-001")
        self.lbl_robot_id.setStyleSheet(
            f"font-weight: bold; color: {theme.TEXT_PRIMARY}; "
            f"font-size: {theme.FONT_XL}px;"
        )

        self.lbl_global_mode = QLabel("MODE: SYSTEM SETUP")
        self.lbl_global_mode.setStyleSheet(
            f"font-weight: bold; color: {theme.ACCENT_BLUE}; "
            f"font-size: {theme.FONT_LG}px;"
        )

        self.status_icons = QLabel()
        self.status_icons.setTextFormat(Qt.TextFormat.RichText)
        self.status_icons.setWordWrap(False)
        self.status_icons.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.status_icons.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        # Base typography only — line colors come from rich text.
        self.status_icons.setStyleSheet(
            f"font-size: {theme.FONT_LG}px; font-weight: bold;"
        )
        self.set_status_line("BAT: --")

        layout.addWidget(self.lbl_robot_id)
        layout.addStretch()
        layout.addWidget(self.lbl_global_mode)
        layout.addStretch()
        layout.addWidget(self.status_icons)

    def set_mode(self, mode_text: str) -> None:
        """Update the centered mode label (e.g. MODE: AUTO-RUN)."""
        self.lbl_global_mode.setText(mode_text)

    def set_robot_id(self, robot_id: str) -> None:
        self.lbl_robot_id.setText(robot_id)

    def set_status_line(self, text: str) -> None:
        """GPS / battery / MQTT line; ERROR (etc.) words in red, rest green."""
        self.status_icons.setText(_status_line_html(text))

    def set_error_line(self, text: str) -> None:
        """Same partial highlighting as status (e.g. VDA error line)."""
        self.set_status_line(text)
