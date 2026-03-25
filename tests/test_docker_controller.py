"""Unit tests for DockerController (docker-py client mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from docker import errors as docker_errors

from core.app_state import AppState
from core.docker_controller import DockerController, DockerSequenceWorker, SequenceStep

# Single container per key
CONFIG_SINGLE = {
    "docker_containers": {
        "localization": {"container_name": "mowbot_localization"},
        "navigation": {"container_name": "mowbot_navigation"},
        "app": {"container_name": "mowbot_app"},
    }
}

# Mixed: one key has multiple containers
CONFIG_MULTI = {
    "docker_containers": {
        "bringup_and_sensing": {
            "container_name": ["mowbot_uros_agent", "mowbot_bringup_and_sensing"],
        },
        "localization": {"container_name": "mowbot_localization"},
        "navigation": {"container_name": "mowbot_navigation"},
        "app": {"container_name": "mowbot_app"},
    }
}


def _mock_container(status: str = "running") -> MagicMock:
    c = MagicMock()
    c.status = status
    c.reload = MagicMock()
    return c


@pytest.fixture
def app_state(qapp):
    return AppState(qapp)


# ── Registry / keys ──────────────────────────────────────────────


def test_keys_from_config(app_state):
    dc = DockerController(CONFIG_MULTI, app_state, client=MagicMock())
    assert set(dc.keys()) == {
        "bringup_and_sensing",
        "localization",
        "navigation",
        "app",
    }


def test_container_names_single(app_state):
    dc = DockerController(CONFIG_SINGLE, app_state, client=MagicMock())
    assert dc.container_names("localization") == ["mowbot_localization"]


def test_container_names_multi(app_state):
    dc = DockerController(CONFIG_MULTI, app_state, client=MagicMock())
    assert dc.container_names("bringup_and_sensing") == [
        "mowbot_uros_agent",
        "mowbot_bringup_and_sensing",
    ]


def test_container_names_unknown_key(app_state):
    dc = DockerController(CONFIG_SINGLE, app_state, client=MagicMock())
    with pytest.raises(KeyError, match="Unknown docker container key"):
        dc.container_names("nonexistent")


# ── Status ───────────────────────────────────────────────────────


def test_status_single_running(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("running")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.status(["localization"])
    assert out == {"localization": "running"}


def test_status_single_missing(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = docker_errors.NotFound("gone")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.status(["navigation"])
    assert out == {"navigation": "missing"}


def test_status_multi_all_running(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("running")

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.status(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "running"}


def test_status_multi_one_exited(app_state):
    """If one of two containers is exited, worst status wins."""
    mock_client = MagicMock()
    containers = {
        "mowbot_uros_agent": _mock_container("running"),
        "mowbot_bringup_and_sensing": _mock_container("exited"),
    }
    mock_client.containers.get.side_effect = lambda n: containers[n]

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.status(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "exited"}


def test_status_multi_one_missing(app_state):
    mock_client = MagicMock()

    def _get(name):
        if name == "mowbot_uros_agent":
            raise docker_errors.NotFound("gone")
        return _mock_container("running")

    mock_client.containers.get.side_effect = _get

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.status(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "missing"}


def test_status_all_default_keys(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("created")

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.status()
    assert len(out) == 4
    assert all(v == "created" for v in out.values())


# ── Start (single container) ────────────────────────────────────


def test_start_stopped_container(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("exited")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.start(["app"])
    assert out == {"app": "started"}
    mock_client.containers.get.return_value.start.assert_called_once()


def test_start_already_running(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("running")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.start(["app"])
    assert out == {"app": "already_running"}
    mock_client.containers.get.return_value.start.assert_not_called()


def test_start_missing_container(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = docker_errors.NotFound("missing")

    errors: list[tuple[str, str]] = []
    app_state.docker_error.connect(lambda key, msg: errors.append((key, msg)))

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.start(["localization"])
    assert out == {"localization": "error"}
    assert len(errors) == 1
    assert "not found" in errors[0][1].lower()


# ── Start (multi container, all-or-nothing) ─────────────────────


def test_start_multi_all_stopped(app_state):
    mock_client = MagicMock()
    containers = {
        "mowbot_uros_agent": _mock_container("exited"),
        "mowbot_bringup_and_sensing": _mock_container("exited"),
    }
    mock_client.containers.get.side_effect = lambda n: containers[n]

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.start(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "started"}
    containers["mowbot_uros_agent"].start.assert_called_once()
    containers["mowbot_bringup_and_sensing"].start.assert_called_once()


def test_start_multi_all_running(app_state):
    mock_client = MagicMock()
    containers = {
        "mowbot_uros_agent": _mock_container("running"),
        "mowbot_bringup_and_sensing": _mock_container("running"),
    }
    mock_client.containers.get.side_effect = lambda n: containers[n]

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.start(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "already_running"}
    containers["mowbot_uros_agent"].start.assert_not_called()
    containers["mowbot_bringup_and_sensing"].start.assert_not_called()


def test_start_multi_second_missing_rollback(app_state):
    """First container starts OK, second is missing → rollback first."""
    mock_client = MagicMock()
    c_agent = _mock_container("exited")

    def _get(name):
        if name == "mowbot_uros_agent":
            return c_agent
        raise docker_errors.NotFound("missing")

    mock_client.containers.get.side_effect = _get

    errors: list[tuple[str, str]] = []
    app_state.docker_error.connect(lambda key, msg: errors.append((key, msg)))

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.start(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "error"}
    c_agent.start.assert_called_once()
    assert len(errors) == 1
    assert "not found" in errors[0][1].lower()


def test_start_multi_first_fails_no_rollback_needed(app_state):
    """First container missing → error immediately, nothing to roll back."""
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = docker_errors.NotFound("missing")

    errors: list[tuple[str, str]] = []
    app_state.docker_error.connect(lambda key, msg: errors.append((key, msg)))

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.start(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "error"}
    assert len(errors) == 1


# ── Stop (single container) ─────────────────────────────────────


def test_stop_running_container(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("running")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.stop(["navigation"])
    assert out == {"navigation": "stopped"}
    mock_client.containers.get.return_value.stop.assert_called_once_with(timeout=10)


def test_stop_already_stopped(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("exited")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.stop(["navigation"])
    assert out == {"navigation": "already_stopped"}


def test_stop_missing_container(app_state):
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = docker_errors.NotFound("missing")

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.stop(["navigation"])
    assert out == {"navigation": "missing_ok"}


def test_stop_kill_fallback(app_state):
    """If graceful stop raises APIError, kill() is used as fallback."""
    mock_client = MagicMock()
    c = _mock_container("running")
    c.stop.side_effect = docker_errors.APIError("timeout")
    mock_client.containers.get.return_value = c

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.stop(["navigation"])
    assert out == {"navigation": "stopped"}
    c.stop.assert_called_once_with(timeout=10)
    c.kill.assert_called_once()


def test_stop_kill_fallback_also_fails(app_state):
    """If both stop and kill fail, report error."""
    mock_client = MagicMock()
    c = _mock_container("running")
    c.stop.side_effect = docker_errors.APIError("timeout")
    c.kill.side_effect = docker_errors.APIError("kill failed")
    mock_client.containers.get.return_value = c

    errors: list[tuple[str, str]] = []
    app_state.docker_error.connect(lambda key, msg: errors.append((key, msg)))

    dc = DockerController(CONFIG_SINGLE, app_state, client=mock_client)
    out = dc.stop(["navigation"])
    assert out == {"navigation": "error"}
    assert len(errors) == 1
    assert "kill failed" in errors[0][1].lower()


# ── Stop (multi container, best-effort) ─────────────────────────


def test_stop_multi_all_running(app_state):
    mock_client = MagicMock()
    containers = {
        "mowbot_uros_agent": _mock_container("running"),
        "mowbot_bringup_and_sensing": _mock_container("running"),
    }
    mock_client.containers.get.side_effect = lambda n: containers[n]

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.stop(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "stopped"}
    containers["mowbot_uros_agent"].stop.assert_called_once()
    containers["mowbot_bringup_and_sensing"].stop.assert_called_once()


def test_stop_multi_one_missing(app_state):
    """One container missing, one running → still stops the running one."""
    mock_client = MagicMock()
    c_sensing = _mock_container("running")

    def _get(name):
        if name == "mowbot_uros_agent":
            raise docker_errors.NotFound("missing")
        return c_sensing

    mock_client.containers.get.side_effect = _get

    dc = DockerController(CONFIG_MULTI, app_state, client=mock_client)
    out = dc.stop(["bringup_and_sensing"])
    assert out == {"bringup_and_sensing": "stopped"}
    c_sensing.stop.assert_called_once()


# ── Docker unavailable ──────────────────────────────────────────


def test_docker_unavailable(app_state):
    with patch("core.docker_controller.docker.from_env") as mock_from_env:
        mock_from_env.side_effect = docker_errors.DockerException("no daemon")

        errors: list[tuple[str, str]] = []
        app_state.docker_error.connect(lambda key, msg: errors.append((key, msg)))

        dc = DockerController(CONFIG_SINGLE, app_state)
        out = dc.start(["app"])
        assert out == {"app": "unavailable"}
        assert errors[0][0] == "app"
        assert "not available" in errors[0][1].lower()


# ── Sequence config parsing ──────────────────────────────────────

CONFIG_SEQ = {
    "docker_containers": {
        "sensing": {"container_name": "mowbot_sensing"},
        "localization": {"container_name": "mowbot_localization"},
        "app": {"container_name": "mowbot_app"},
    },
    "docker_startup_sequence": [
        {"key": "sensing", "settle_time_s": 2},
        {"key": "localization", "settle_time_s": 3},
        {"key": "app", "settle_time_s": 1},
    ],
}

CONFIG_SEQ_BAD_KEY = {
    "docker_containers": {
        "sensing": {"container_name": "mowbot_sensing"},
    },
    "docker_startup_sequence": [
        {"key": "sensing", "settle_time_s": 2},
        {"key": "nonexistent", "settle_time_s": 1},
    ],
}


def test_parse_startup_sequence(app_state):
    dc = DockerController(CONFIG_SEQ, app_state, client=MagicMock())
    assert dc.startup_sequence_keys() == ["sensing", "localization", "app"]


def test_parse_startup_sequence_skips_bad_key(app_state):
    dc = DockerController(CONFIG_SEQ_BAD_KEY, app_state, client=MagicMock())
    assert dc.startup_sequence_keys() == ["sensing"]


def test_is_sequence_running_false_initially(app_state):
    dc = DockerController(CONFIG_SEQ, app_state, client=MagicMock())
    assert dc.is_sequence_running is False


# ── Sequence worker tests ────────────────────────────────────────


def test_start_sequence_all_succeed(app_state, qapp):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("exited")

    dc = DockerController(CONFIG_SEQ, app_state, client=mock_client)

    steps: list[tuple[int, str, str]] = []
    finished: list[tuple[bool, str]] = []
    app_state.docker_sequence_step.connect(
        lambda i, k, p: steps.append((i, k, p))
    )
    app_state.docker_sequence_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )

    seq = [SequenceStep("sensing", 0), SequenceStep("localization", 0), SequenceStep("app", 0)]
    worker = DockerSequenceWorker(dc, seq, direction="start")
    worker.step_progress.connect(app_state.docker_sequence_step.emit)
    worker.finished_signal.connect(app_state.docker_sequence_finished.emit)
    worker.run()

    assert len(finished) == 1
    assert finished[0][0] is True
    step_keys = [s[1] for s in steps if s[2] == "ready"]
    assert step_keys == ["sensing", "localization", "app"]


def test_start_sequence_mid_step_failure(app_state, qapp):
    """sensing starts OK, localization fails → rollback sensing."""
    mock_client = MagicMock()

    def _get(name):
        if name == "mowbot_sensing":
            return _mock_container("exited")
        raise docker_errors.NotFound("missing")

    mock_client.containers.get.side_effect = _get

    dc = DockerController(CONFIG_SEQ, app_state, client=mock_client)

    finished: list[tuple[bool, str]] = []
    app_state.docker_sequence_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )

    seq = [SequenceStep("sensing", 0), SequenceStep("localization", 0)]
    worker = DockerSequenceWorker(dc, seq, direction="start")
    worker.step_progress.connect(app_state.docker_sequence_step.emit)
    worker.finished_signal.connect(app_state.docker_sequence_finished.emit)
    worker.run()

    assert len(finished) == 1
    assert finished[0][0] is False
    assert "localization" in finished[0][1].lower()


def test_start_sequence_crash_during_settle(app_state, qapp):
    """Container starts but crashes during settle time."""
    mock_client = MagicMock()

    call_count = {"n": 0}

    def _get(name):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            return _mock_container("exited")
        return _mock_container("exited")

    mock_client.containers.get.side_effect = _get

    dc = DockerController(CONFIG_SEQ, app_state, client=mock_client)

    finished: list[tuple[bool, str]] = []
    app_state.docker_sequence_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )

    seq = [SequenceStep("sensing", 0.1)]
    worker = DockerSequenceWorker(dc, seq, direction="start")
    worker.step_progress.connect(app_state.docker_sequence_step.emit)
    worker.finished_signal.connect(app_state.docker_sequence_finished.emit)
    worker.run()

    assert len(finished) == 1
    assert finished[0][0] is False
    assert "exited" in finished[0][1].lower() or "settle" in finished[0][1].lower()


def test_stop_sequence_reverse_order(app_state, qapp):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("running")

    dc = DockerController(CONFIG_SEQ, app_state, client=mock_client)

    steps: list[tuple[int, str, str]] = []
    finished: list[tuple[bool, str]] = []
    app_state.docker_sequence_step.connect(
        lambda i, k, p: steps.append((i, k, p))
    )
    app_state.docker_sequence_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )

    reversed_seq = list(reversed([
        SequenceStep("sensing", 0), SequenceStep("localization", 0), SequenceStep("app", 0)
    ]))
    worker = DockerSequenceWorker(dc, reversed_seq, direction="stop")
    worker.step_progress.connect(app_state.docker_sequence_step.emit)
    worker.finished_signal.connect(app_state.docker_sequence_finished.emit)
    worker.run()

    assert len(finished) == 1
    assert finished[0][0] is True
    stopped_keys = [s[1] for s in steps if s[2] == "stopped"]
    assert stopped_keys == ["app", "localization", "sensing"]


def test_start_sequence_cancel(app_state, qapp):
    mock_client = MagicMock()
    mock_client.containers.get.return_value = _mock_container("exited")

    dc = DockerController(CONFIG_SEQ, app_state, client=mock_client)

    finished: list[tuple[bool, str]] = []
    app_state.docker_sequence_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )

    seq = [SequenceStep("sensing", 0), SequenceStep("localization", 0)]
    worker = DockerSequenceWorker(dc, seq, direction="start")
    worker.step_progress.connect(app_state.docker_sequence_step.emit)
    worker.finished_signal.connect(app_state.docker_sequence_finished.emit)
    worker.cancel()
    worker.run()

    assert len(finished) == 1
    assert finished[0][0] is False
    assert "cancelled" in finished[0][1].lower()


def test_no_sequence_configured(app_state):
    """start_sequence with empty config emits finished(False)."""
    config_no_seq = {
        "docker_containers": {"app": {"container_name": "mowbot_app"}},
    }
    dc = DockerController(config_no_seq, app_state, client=MagicMock())

    finished: list[tuple[bool, str]] = []
    app_state.docker_sequence_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )

    dc.start_sequence()
    assert len(finished) == 1
    assert finished[0][0] is False
