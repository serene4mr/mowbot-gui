"""Map surface: WebEngine + JS bridge for robot marker / path rendering.

Supports two backends (selected via MOWBOT_MAP_BACKEND env var):
  - "leaflet" (default): raster tiles, no WebGL required
  - "esri" / "maplibre"   : MapLibre GL JS, requires WebGL context
"""

from __future__ import annotations

import html
import os

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from utils.logger import logger


class MapView(QWebEngineView):
    """Owns map HTML/JS loading and JS calls for robot geometry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        settings = self.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        self.setup_map()

    # ── Map loading ───────────────────────────────────────────

    def _map_html_path(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.abspath(os.path.join(current_dir, "../../../assets"))

        override = os.environ.get("MOWBOT_MAP_HTML", "").strip()
        if override:
            return os.path.join(assets_dir, override)

        backend = os.environ.get("MOWBOT_MAP_BACKEND", "leaflet").strip().lower()
        name = (
            "leaflet_map.html"
            if backend in ("leaflet", "raster", "no-webgl")
            else "esri_map.html"
        )
        return os.path.join(assets_dir, name)

    def setup_map(self) -> None:
        html_path = os.path.abspath(self._map_html_path())

        if not os.path.exists(html_path):
            logger.error(f"Cannot find map file at: {html_path}")
            safe = html.escape(html_path, quote=True)
            self.setHtml(
                "<body style='background:#500;color:white;font-family:sans-serif;"
                "display:flex;align-items:center;justify-content:center;"
                f"height:100vh;margin:0;'>"
                f"<div><h1>Map File Not Found!</h1><p>{safe}</p></div></body>"
            )
            return

        logger.info(f"Loading map from: {html_path}")
        if html_path.endswith("esri_map.html"):
            logger.info(
                "   (MapLibre/WebGL). If tiles stay blank, try: "
                "MOWBOT_MAP_BACKEND=leaflet"
            )

        self.load(QUrl.fromLocalFile(html_path))

    # ── JS bridge (Python → JavaScript) ──────────────────────
    #
    # Both leaflet_map.html and esri_map.html expose the same
    # global `updateRobotPosition(lat, lng, headingDeg)` function,
    # so this single call works for either backend.
    #
    # TODO: Replace raw runJavaScript with QWebChannel for
    #       bidirectional communication when JS→Python callbacks
    #       are needed (e.g. click-to-waypoint).

    def update_robot_marker(
        self, lat: float, lon: float, heading_deg: float
    ) -> None:
        js = (
            "if (typeof updateRobotPosition === 'function') "
            f"{{ updateRobotPosition({lat}, {lon}, {heading_deg}); }}"
        )
        self.page().runJavaScript(js)
