"""VDA5050 deep diagnostics: parse sensor health from state information/errors."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# Hardware IDs from bridge spec (LiDAR, IMU, GNSS, NTRIP client).
KNOWN_HARDWARE_IDS = frozenset({"LASER", "IMU", "GNSS", "RTCM"})


@dataclass
class SensorStatus:
    """One sensor's diagnostic snapshot from a VDA5050 state message."""

    hardware_id: str
    level: str  # OK, WARNING, FATAL
    metrics: Dict[str, str] = field(default_factory=dict)
    raw_type: str = ""
    description_fallback: str = ""

    def to_payload(self) -> Dict[str, Any]:
        """Plain dict for Qt signals / UI."""
        d = asdict(self)
        return d


def sensor_health_to_payload(data: Dict[str, SensorStatus]) -> Dict[str, Dict[str, Any]]:
    return {k: v.to_payload() for k, v in data.items()}


def sensor_status_from_payload(payload: Dict[str, Any]) -> SensorStatus:
    """Reconstruct from bridge/AppState wire format."""
    metrics = payload.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    return SensorStatus(
        hardware_id=str(payload.get("hardware_id") or "").strip().upper() or "UNKNOWN",
        level=str(payload.get("level") or "OK").strip().upper() or "OK",
        metrics={str(k): str(v) for k, v in metrics.items()},
        raw_type=str(payload.get("raw_type") or ""),
        description_fallback=str(payload.get("description_fallback") or ""),
    )


def _norm_enum_name(value: object) -> str:
    return str(getattr(value, "value", value) or "").strip().upper()


def _hardware_id_from_references(refs: Any) -> Optional[str]:
    if not refs:
        return None
    for ref in refs:
        if ref is None:
            continue
        if isinstance(ref, dict):
            key = str(ref.get("referenceKey") or "").strip()
            val = ref.get("referenceValue")
        else:
            key = str(getattr(ref, "referenceKey", "") or "").strip()
            val = getattr(ref, "referenceValue", None)
        if key == "hardware_id" and val is not None:
            hid = str(val).strip().upper()
            if hid:
                return hid
    return None


def _hardware_id_from_type(type_str: str) -> Optional[str]:
    s = (type_str or "").strip().upper()
    if s.endswith("_ERROR") and len(s) > 6:
        base = s[: -len("_ERROR")]
    elif s.endswith("_HEALTH") and len(s) > 7:
        base = s[: -len("_HEALTH")]
    else:
        return None
    if base in KNOWN_HARDWARE_IDS:
        return base
    return None


def _parse_description_json(description: Optional[str]) -> tuple[Dict[str, str], str]:
    """Return (metrics dict, fallback plain text if JSON parse fails)."""
    raw = str(description or "").strip()
    if not raw:
        return {}, ""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}, raw
    if not isinstance(obj, dict):
        return {}, raw
    out: Dict[str, str] = {}
    for k, v in obj.items():
        out[str(k)] = str(v) if v is not None else ""
    return out, ""


def format_vda_error_for_top_bar(
    error_type: str,
    error_description: Optional[str],
    error_references: Any,
    prefix: str,
) -> str:
    """Short top-bar text for VDA ``errors[]`` entries.

    Sensor deep diagnostics use JSON in ``errorDescription``; show hardware id
    and ``key: value`` pairs instead of a raw JSON blob.
    """
    et = str(error_type or "").strip()
    desc = str(error_description or "").strip()
    pref = (prefix or "ERROR").strip().upper()
    if not desc:
        return pref

    if et.upper().endswith("_ERROR"):
        metrics, plain = _parse_description_json(desc)
        hid = _hardware_id_from_references(error_references) or _hardware_id_from_type(et)
        if metrics:
            parts = [f"{k}: {v}" for k, v in metrics.items()]
            tail = ", ".join(parts[:6])
            if len(parts) > 6:
                tail += ", …"
            if hid:
                return f"{pref}: {hid} — {tail}"
            return f"{pref}: {tail}"
        if hid:
            if plain:
                return f"{pref}: {hid} — {plain}"
            return f"{pref}: {hid}"
        if plain:
            return f"{pref}: {plain}"

    return f"{pref}: {desc}"


def _error_level_to_sensor_level(error_level: object) -> str:
    name = _norm_enum_name(error_level)
    if name == "FATAL":
        return "FATAL"
    if name in {"WARNING", "WARN"}:
        return "WARNING"
    return "WARNING"


def parse_sensor_entries(
    information: Optional[List[Any]],
    errors: Optional[List[Any]],
) -> Dict[str, SensorStatus]:
    """Build per-hardware_id status from VDA5050 state information[] and errors[]."""
    error_by_id: Dict[str, SensorStatus] = {}
    health_by_id: Dict[str, SensorStatus] = {}

    # Errors: last wins per hardware_id.
    for err in errors or []:
        et = str(getattr(err, "errorType", "") or "").strip()
        if not et.upper().endswith("_ERROR"):
            continue
        hid = _hardware_id_from_references(getattr(err, "errorReferences", None))
        if not hid:
            hid = _hardware_id_from_type(et)
        if not hid or hid not in KNOWN_HARDWARE_IDS:
            continue
        desc = getattr(err, "errorDescription", None)
        metrics, fallback = _parse_description_json(desc)
        level = _error_level_to_sensor_level(getattr(err, "errorLevel", None))
        error_by_id[hid] = SensorStatus(
            hardware_id=hid,
            level=level,
            metrics=metrics,
            raw_type=et,
            description_fallback=fallback,
        )

    # OK health: last wins per hardware_id (information[] order).
    for info in information or []:
        it = str(getattr(info, "infoType", "") or "").strip()
        if not it.upper().endswith("_HEALTH"):
            continue
        hid = _hardware_id_from_references(getattr(info, "infoReferences", None))
        if not hid:
            hid = _hardware_id_from_type(it)
        if not hid or hid not in KNOWN_HARDWARE_IDS:
            continue
        desc = getattr(info, "infoDescription", None)
        metrics, fallback = _parse_description_json(desc)
        health_by_id[hid] = SensorStatus(
            hardware_id=hid,
            level="OK",
            metrics=metrics,
            raw_type=it,
            description_fallback=fallback,
        )

    out: Dict[str, SensorStatus] = dict(health_by_id)
    out.update(error_by_id)  # errors override OK health for same id
    return out


def format_sensor_summary_line(sensor_health: Dict[str, SensorStatus]) -> str:
    """Compact status for top bar: LASER: OK | IMU: WARN | …"""
    order = ("LASER", "IMU", "GNSS", "RTCM")
    parts: List[str] = []
    for hid in order:
        st = sensor_health.get(hid)
        if st is None:
            continue
        lvl = (st.level or "OK").strip().upper()
        if lvl == "OK":
            short = "OK"
        elif lvl == "WARNING":
            short = "WARN"
        elif lvl == "FATAL":
            short = "FATAL"
        else:
            short = lvl[:4]
        parts.append(f"{hid}: {short}")
    return " | ".join(parts) if parts else ""


def primary_metric_label(hardware_id: str, status: SensorStatus) -> str:
    """One short right-column string for LeftHUD."""
    m = status.metrics
    hid = (hardware_id or "").upper()

    if hid == "LASER":
        hz = m.get("frequency_hz", "")
        if hz:
            try:
                return f"{float(hz):.1f} Hz"
            except (TypeError, ValueError):
                return f"{hz} Hz"
        bp = m.get("blocked_points_percent", "")
        return f"blk {bp}%" if bp else (status.description_fallback or "—")

    if hid == "IMU":
        shock = (m.get("shock_detected") or "").lower()
        if shock in {"true", "1", "yes"}:
            return "SHOCK"
        yv = m.get("yaw_variance", "")
        if yv:
            try:
                return f"var: {float(yv):.3g}"
            except (TypeError, ValueError):
                return f"var: {yv}"
        return status.description_fallback or "—"

    if hid == "GNSS":
        fix = m.get("fix_type", "")
        if fix:
            return str(fix)
        cov = m.get("position_covariance", "")
        if cov:
            try:
                return f"cov: {float(cov):.3g}"
            except (TypeError, ValueError):
                return f"cov: {cov}"
        return status.description_fallback or "—"

    if hid == "RTCM":
        last = m.get("last_update_sec", "")
        if last:
            return f"last: {last}s" if str(last).replace(".", "", 1).isdigit() else f"last: {last}"
        lat = m.get("rtcm_latency_sec", "")
        if lat:
            try:
                return f"lat: {float(lat):.2f}s"
            except (TypeError, ValueError):
                return f"lat: {lat}s"
        sz = m.get("msg_size_bytes", "")
        if sz:
            return f"{sz} B"
        return status.description_fallback or "—"

    return status.description_fallback or "—"
