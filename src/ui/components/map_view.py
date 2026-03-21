"""Map surface: WebEngine + future ESRI / QWebChannel bridge."""

from __future__ import annotations

import html
import os
from typing import Sequence

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


class MapView(QWebEngineView):
    """Owns map HTML/JS loading and JS calls for robot geometry (markers, paths, polygons)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Local file:// HTML must load remote tiles/scripts; WebGL only needed for MapLibre.
        settings = self.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        self.setup_map()

    def _map_html_path(self) -> str:
        """Pick MapLibre (WebGL) or Leaflet (raster / no WebGL) from MOWBOT_MAP_BACKEND."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.abspath(os.path.join(current_dir, "../../../assets"))
        override = os.environ.get("MOWBOT_MAP_HTML", "").strip()
        if override:
            name = override
        else:
            backend = os.environ.get("MOWBOT_MAP_BACKEND", "leaflet").strip().lower()
            if backend in ("leaflet", "raster", "no-webgl"):
                name = "leaflet_map.html"
            else:
                name = "esri_map.html"
        return os.path.join(assets_dir, name)

    def setup_map(self) -> None:
        html_path = os.path.abspath(self._map_html_path())

        if not os.path.exists(html_path):
            print(f"\u274c ERROR: Cannot find map file at: {html_path}")
            safe = html.escape(html_path, quote=True)
            self.setHtml(
                f"<body style='background: #500; color: white; font-family: sans-serif; "
                f"display:flex; align-items:center; justify-content:center; height:100vh; margin:0;'>"
                f"<div><h1>Map File Not Found!</h1><p>Looked in: {safe}</p></div></body>"
            )
            return

        print(f"\u2705 SUCCESS: Loading map from: {html_path}")
        if html_path.endswith("esri_map.html"):
            print(
                "   (MapLibre/WebGL). If tiles stay blank, try: "
                "MOWBOT_MAP_BACKEND=leaflet"
            )

        local_url = QUrl.fromLocalFile(html_path)
        self.load(local_url)

    def update_robot_marker(self, x: float, y: float, theta: float) -> None:
        """Send coordinates to JS to move the robot graphic (QWebChannel / runJavaScript)."""
        # Example:
        # js_code = f"moveRobotMarker({x}, {y}, {theta});"
        # self.page().runJavaScript(js_code)
        pass

    def draw_polygon(self, points: Sequence[tuple[float, float]]) -> None:
        """Send vertices to JS to render a mowing/teach-in area."""
        pass
