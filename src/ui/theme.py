"""Centralized UI theme: colors, layout constants, and reusable style fragments.

Every component imports from here instead of hard-coding colors/sizes,
so a brand refresh is a single-file change.
"""

# ── Core palette ───────────────────────────────────────────────
BG_DARK = "#121212"
PANEL_BG = "rgba(20, 25, 30, 210)"
TOPBAR_BG = "rgba(20, 25, 30, 230)"
TOPBAR_BORDER = "#333"

ACCENT_GREEN = "#00E676"
ACCENT_BLUE = "#00B0FF"
ACCENT_RED = "#D50000"
ACCENT_RED_PRESSED = "#9b0000"
ACCENT_ORANGE = "#FF6D00"
ACCENT_YELLOW = "#FFD600"

TEXT_PRIMARY = "#E0E0E0"
TEXT_WHITE = "white"
TEXT_MUTED = "#8a8a8a"

BUTTON_BG = "#333"
BUTTON_BG_DARK = "#424242"
BUTTON_START = "#2962FF"
BUTTON_EXECUTE = "#00C853"

# ── Layout constants (logical pixels, Qt handles DPI scaling) ─
TOPBAR_HEIGHT = 50
OVERLAY_MARGIN = 20
HUD_WIDTH = 320
HUD_HEIGHT = 340
SIDEBAR_WIDTH = 350

# ── Font sizes (px) ──────────────────────────────────────────
FONT_XL = 18
FONT_LG = 16
FONT_MD = 15
FONT_SM = 14
FONT_XS = 13

# ── Reusable stylesheet fragments ────────────────────────────
MAIN_WINDOW_STYLE = f"QMainWindow {{ background-color: {BG_DARK}; }}"

TOPBAR_STYLE = (
    f"background-color: {TOPBAR_BG}; border-bottom: 2px solid {TOPBAR_BORDER};"
)

PANEL_STYLE = (
    f"background-color: {PANEL_BG}; border-radius: 10px; color: {TEXT_WHITE};"
)

TAB_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {BUTTON_BG}; color: {TEXT_WHITE};
        border-radius: 5px; padding: 10px; font-weight: bold;
    }}
    QPushButton:checked {{ background-color: {ACCENT_BLUE}; }}
    QPushButton:disabled {{
        background-color: #252525;
        color: #5c5c5c;
    }}
"""

ESTOP_STYLE = f"""
    QPushButton {{
        background-color: {ACCENT_RED}; color: {TEXT_WHITE};
        font-size: {FONT_XL}px; font-weight: bold;
        padding: 25px; border-radius: 8px;
    }}
    QPushButton:pressed {{ background-color: {ACCENT_RED_PRESSED}; }}
"""


def action_button_style(bg: str = BUTTON_BG_DARK, bold: bool = False) -> str:
    """Generic action button (sidebar buttons, LOG POINT, etc.)."""
    weight = "font-weight: bold; " if bold else ""
    return (
        f"QPushButton {{ background-color: {bg}; color: {TEXT_WHITE}; padding: 15px; "
        f"border-radius: 8px; margin-bottom: 5px; {weight}}}"
        f"QPushButton:disabled {{ background-color: #2e2e2e; color: #5a5a5a; }}"
    )


def primary_button_style(bg: str = BUTTON_START) -> str:
    """Large call-to-action button (START SYSTEM, EXECUTE MISSION)."""
    return (
        f"QPushButton {{ background-color: {bg}; color: {TEXT_WHITE}; font-size: {FONT_LG}px; "
        f"font-weight: bold; padding: 20px; border-radius: 8px; }}"
        f"QPushButton:disabled {{ background-color: #2e2e2e; color: #5a5a5a; }}"
    )
