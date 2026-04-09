"""Unit tests for VDA5050 deep diagnostics parsing."""

from dataclasses import dataclass
from typing import Any, List, Optional

from core.sensor_diagnostics import (
    format_sensor_summary_line,
    format_vda_error_for_top_bar,
    parse_sensor_entries,
    primary_metric_label,
)


@dataclass
class _Ref:
    referenceKey: str
    referenceValue: str


@dataclass
class _Info:
    infoType: str
    infoDescription: str
    infoReferences: Optional[List[Any]] = None


@dataclass
class _Err:
    errorType: str
    errorDescription: str
    errorLevel: str
    errorReferences: Optional[List[Any]] = None


def test_parse_laser_error_with_refs_and_json() -> None:
    errors = [
        _Err(
            errorType="LASER_ERROR",
            errorDescription='{"last_update_sec": "0.10", "frequency_hz": "10.0", '
            '"blocked_points_percent": "35.5"}',
            errorLevel="WARNING",
            errorReferences=[_Ref("hardware_id", "LASER")],
        )
    ]
    out = parse_sensor_entries([], errors)
    assert "LASER" in out
    assert out["LASER"].level == "WARNING"
    assert out["LASER"].metrics["blocked_points_percent"] == "35.5"
    assert out["LASER"].metrics["frequency_hz"] == "10.0"


def test_parse_health_without_refs_uses_type_suffix() -> None:
    info = [
        _Info(
            infoType="GNSS_HEALTH",
            infoDescription='{"fix_type": "RTK_FIXED", "last_update_sec": "1.2"}',
        )
    ]
    out = parse_sensor_entries(info, [])
    assert "GNSS" in out
    assert out["GNSS"].level == "OK"
    assert out["GNSS"].metrics["fix_type"] == "RTK_FIXED"


def test_error_overrides_health_same_hardware() -> None:
    info = [
        _Info(
            infoType="IMU_HEALTH",
            infoDescription='{"shock_detected": "false"}',
        )
    ]
    errors = [
        _Err(
            errorType="IMU_ERROR",
            errorDescription='{"shock_detected": "true"}',
            errorLevel="FATAL",
            errorReferences=[_Ref("hardware_id", "IMU")],
        )
    ]
    out = parse_sensor_entries(info, errors)
    assert out["IMU"].level == "FATAL"
    assert out["IMU"].metrics["shock_detected"] == "true"


def test_format_sensor_summary_line_order() -> None:
    from core.sensor_diagnostics import SensorStatus

    d = {
        "GNSS": SensorStatus("GNSS", "OK", {}, "GNSS_HEALTH"),
        "LASER": SensorStatus("LASER", "WARNING", {}, "LASER_ERROR"),
    }
    s = format_sensor_summary_line(d)
    assert "LASER: WARN" in s
    assert "GNSS: OK" in s
    assert s.index("LASER") < s.index("GNSS")


def test_format_vda_error_for_top_bar_expands_sensor_json() -> None:
    msg = format_vda_error_for_top_bar(
        "LASER_ERROR",
        '{"last_update_sec": "never"}',
        [_Ref("hardware_id", "LASER")],
        "FATAL",
    )
    assert "{" not in msg
    assert "LASER" in msg
    assert "last_update_sec" in msg
    assert "never" in msg


def test_primary_metric_labels() -> None:
    from core.sensor_diagnostics import SensorStatus

    laser = SensorStatus(
        "LASER",
        "OK",
        {"frequency_hz": "12.5", "blocked_points_percent": "1"},
        "LASER_HEALTH",
    )
    assert "Hz" in primary_metric_label("LASER", laser)

    gnss = SensorStatus(
        "GNSS",
        "OK",
        {"fix_type": "FLOAT", "position_covariance": "0.5"},
        "GNSS_HEALTH",
    )
    assert primary_metric_label("GNSS", gnss) == "FLOAT"
