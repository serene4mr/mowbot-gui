"""Map surface: WebEngine + JS bridge for robot marker / path rendering.

Supports two backends (selected via MBGUI_MAP_BACKEND env var):
  - "leaflet" (default): raster tiles, no WebGL required
  - "esri" / "maplibre"   : MapLibre GL JS, requires WebGL context
"""

from __future__ import annotations

import html
import json
import os
from typing import List, Optional, Tuple

from PySide6.QtCore import QUrl, Slot
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from utils.logger import logger


class MapView(QWebEngineView):
    """Owns map HTML/JS loading and JS calls for robot geometry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._teach_recording_poly: bool = False
        self._last_mission_preview: Optional[Tuple[str, List[Tuple[float, float]]]] = None
        self._last_poly_coverage: Optional[
            Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]
        ] = None
        settings = self.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        self.loadFinished.connect(self._on_load_finished)
        self.setup_map()

    # ── Map loading ───────────────────────────────────────────

    def _map_html_path(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.abspath(os.path.join(current_dir, "../../../assets"))

        override = os.environ.get("MBGUI_MAP_HTML", "").strip()
        if override:
            return os.path.join(assets_dir, override)

        backend = os.environ.get("MBGUI_MAP_BACKEND", "leaflet").strip().lower()
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
                "MBGUI_MAP_BACKEND=leaflet"
            )

        self.load(QUrl.fromLocalFile(html_path))

    @Slot(bool)
    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            self._push_teach_recording_poly_js()
            self._push_poly_coverage_js()
            self._push_mission_preview_js()

    def set_teach_recording_poly_mode(self, is_poly: bool) -> None:
        """PATH vs POLY: POLY shows live fill when there are ≥3 teach points."""
        self._teach_recording_poly = bool(is_poly)
        self._push_teach_recording_poly_js()

    def _push_teach_recording_poly_js(self) -> None:
        p = "true" if self._teach_recording_poly else "false"
        js = (
            "if (typeof setTeachRecordingMode === 'function') "
            f"{{ setTeachRecordingMode({p}); }}"
        )
        self.page().runJavaScript(js)

    def clear_mission_preview(self) -> None:
        """Remove RUN-tab mission overlay from the map."""
        self._last_mission_preview = None
        self._last_poly_coverage = None
        self.page().runJavaScript(
            "if (typeof clearMissionPreview === 'function') { clearMissionPreview(); }"
        )

    def update_mission_progress(
        self, last_node_index: int, mission_done: bool = False
    ) -> None:
        """Highlight waypoint markers by execution progress (Leaflet backend)."""
        md = "true" if mission_done else "false"
        js = (
            "if (typeof updateMissionProgress === 'function') "
            f"{{ updateMissionProgress({int(last_node_index)}, {md}); }}"
        )
        self.page().runJavaScript(js)

    def clear_mission_progress_highlight(self) -> None:
        """Reset mission markers to the default preview style."""
        self.update_mission_progress(-1, False)

    def load_mission_preview(
        self, mission_type: str, coordinates: List[Tuple[float, float]]
    ) -> None:
        """Draw saved PATH/POLY on map (orange); replaces any previous preview."""
        mt = str(mission_type).upper()
        self._last_poly_coverage = None
        self._last_mission_preview = (mt, list(coordinates))
        self._push_mission_preview_js()

    def load_poly_coverage_preview(
        self,
        polygon_latlon: List[Tuple[float, float]],
        path_latlon: List[Tuple[float, float]],
    ) -> None:
        """POLY boundary fill plus coverage path markers (progress uses path waypoints)."""
        self._last_mission_preview = None
        self._last_poly_coverage = (list(polygon_latlon), list(path_latlon))
        self._push_poly_coverage_js()

    def _push_poly_coverage_js(self) -> None:
        if self._last_poly_coverage is None:
            return
        poly, path = self._last_poly_coverage
        poly_js = json.dumps([[lat, lon] for lat, lon in poly])
        path_js = json.dumps([[lat, lon] for lat, lon in path])
        js = (
            "if (typeof setPolyCoveragePreview === 'function') "
            f"{{ setPolyCoveragePreview({poly_js}, {path_js}); }}"
        )
        self.page().runJavaScript(js)

    def _push_mission_preview_js(self) -> None:
        if self._last_poly_coverage is not None:
            return
        if self._last_mission_preview is None:
            return
        typ, coords = self._last_mission_preview
        typ_js = json.dumps(typ)
        coords_js = json.dumps([[lat, lon] for lat, lon in coords])
        js = (
            "if (typeof setMissionPreview === 'function') "
            f"{{ setMissionPreview({typ_js}, {coords_js}); }}"
        )
        self.page().runJavaScript(js)

    # ── JS bridge (Python → JavaScript) ──────────────────────
    #
    # Both leaflet_map.html and esri_map.html expose the same
    # global `updateRobotPosition(lat, lng, headingRad)` function,
    # so this single call works for either backend.
    #
    # TODO: Replace raw runJavaScript with QWebChannel for
    #       bidirectional communication when JS→Python callbacks
    #       are needed (e.g. click-to-waypoint).

    def update_robot_marker(
        self, lat: float, lon: float, heading_rad: float
    ) -> None:
        js = (
            "if (typeof updateRobotPosition === 'function') "
            f"{{ updateRobotPosition({lat}, {lon}, {heading_rad}); }}"
        )
        self.page().runJavaScript(js)

    def add_teach_point(self, lat: float, lon: float) -> None:
        js = (
            "if (typeof addTeachPoint === 'function') "
            f"{{ addTeachPoint({lat}, {lon}); }}"
        )
        self.page().runJavaScript(js)

    def undo_teach_point(self) -> None:
        js = (
            "if (typeof undoTeachPoint === 'function') { undoTeachPoint(); }"
        )
        self.page().runJavaScript(js)

    def clear_teach_layer(self) -> None:
        js = (
            "if (typeof clearTeachLayer === 'function') { clearTeachLayer(); }"
        )
        self.page().runJavaScript(js)

    def close_polygon(self) -> None:
        js = "if (typeof closePolygon === 'function') { closePolygon(); }"
        self.page().runJavaScript(js)
