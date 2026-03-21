"""Top status bar: robot ID, mode, and system summary."""

from __future__ import annotations

import html as html_lib
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from ui import theme

# Whole-word "ERROR" highlighted in red; rest of line stays normal color.
_STATUS_ERROR_TOKEN_RE = re.compile(r"\bERROR\b", re.IGNORECASE)


def _status_line_html(plain: str) -> str:
    """Plain status → HTML: default green bold, matched tokens red."""
    s = str(plain)
    parts: list[str] = []
    last = 0
    for m in _STATUS_ERROR_TOKEN_RE.finditer(s):
        parts.append(html_lib.escape(s[last : m.start()]))
        tok = m.group(0)
        parts.append(
            f'<span style="color:{theme.ACCENT_RED};">{html_lib.escape(tok)}</span>'
        )
        last = m.end()
    parts.append(html_lib.escape(s[last:]))
    inner = "".join(parts)
    return (
        f'<span style="color:{theme.ACCENT_GREEN}; font-size:{theme.FONT_LG}px; '
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
        self.set_status_line("GPS: FIX  |  BAT: 85%  |  14:30")

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
