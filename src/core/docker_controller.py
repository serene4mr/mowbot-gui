"""Docker lifecycle: start/stop containers by name (allowlist from config).

Containers are expected to be created beforehand (e.g. ``docker compose create``).
This module only calls Docker API start/stop/status on configured container names.

Each config key can map to one *or more* container names.  Start uses
**all-or-nothing** semantics: if any container in a group fails, the ones
already started are rolled back (stopped).

Sequential startup/shutdown is handled by ``DockerSequenceWorker`` which runs
in a ``QThread`` so the GUI stays responsive.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

import docker
from docker import errors as docker_errors
from PySide6.QtCore import QObject, QThread, Signal

from core.app_state import AppState
from utils.logger import logger

_STATUS_PRIORITY = ["error", "missing", "exited", "created", "running"]

_DEFAULT_SETTLE_TIME_S = 3.0
_POLL_INTERVAL_S = 0.5


def _worst_status(statuses: Iterable[str]) -> str:
    """Return the most severe status from a collection (lower index = worse)."""
    worst_idx = len(_STATUS_PRIORITY)
    worst = "unknown"
    for s in statuses:
        try:
            idx = _STATUS_PRIORITY.index(s)
        except ValueError:
            idx = len(_STATUS_PRIORITY) - 1
        if idx < worst_idx:
            worst_idx = idx
            worst = s
    return worst


@dataclass(frozen=True)
class SequenceStep:
    key: str
    settle_time_s: float


# ── Sequence worker (QThread) ────────────────────────────────────


class DockerSequenceWorker(QThread):
    """Run a startup or shutdown sequence off the main thread."""

    step_progress = Signal(int, str, str)  # step_index, key, phase
    finished_signal = Signal(bool, str)  # success, detail

    def __init__(
        self,
        controller: DockerController,
        sequence: List[SequenceStep],
        direction: str,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._ctrl = controller
        self._sequence = sequence
        self._direction = direction  # "start" or "stop"
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        if self._direction == "start":
            self._run_start()
        else:
            self._run_stop()

    # ── Start sequence ───────────────────────────────────────

    def _run_start(self) -> None:
        keys_started: List[str] = []

        for i, step in enumerate(self._sequence):
            if self._cancelled:
                self._rollback_sequence(keys_started)
                self.finished_signal.emit(False, "Startup cancelled by operator.")
                return

            self.step_progress.emit(i, step.key, "starting")
            result = self._ctrl.start([step.key])
            outcome = result.get(step.key, "error")

            if outcome not in ("started", "already_running"):
                self._rollback_sequence(keys_started)
                self.step_progress.emit(i, step.key, "failed")
                self.finished_signal.emit(
                    False, f"Failed to start {step.key}: {outcome}"
                )
                return

            keys_started.append(step.key)

            if step.settle_time_s > 0 and outcome != "already_running":
                self.step_progress.emit(i, step.key, "settling")
                if not self._wait_settle(step):
                    self._rollback_sequence(keys_started)
                    self.step_progress.emit(i, step.key, "failed")
                    self.finished_signal.emit(
                        False,
                        f"{step.key} exited during settle time.",
                    )
                    return

            self.step_progress.emit(i, step.key, "ready")

        self.finished_signal.emit(True, "All services running.")

    def _wait_settle(self, step: SequenceStep) -> bool:
        """Sleep in small increments; verify containers stay running."""
        elapsed = 0.0
        while elapsed < step.settle_time_s:
            if self._cancelled:
                return False
            time.sleep(_POLL_INTERVAL_S)
            elapsed += _POLL_INTERVAL_S
            st = self._ctrl.status([step.key])
            if st.get(step.key) not in ("running",):
                return False
        return True

    def _rollback_sequence(self, keys_started: List[str]) -> None:
        """Stop previously started keys in reverse order (best-effort)."""
        for key in reversed(keys_started):
            try:
                self._ctrl.stop([key])
                logger.info("[Docker] Sequence rollback: stopped %s", key)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "[Docker] Sequence rollback failed for %s", key, exc_info=True
                )

    # ── Stop sequence ────────────────────────────────────────

    def _run_stop(self) -> None:
        for i, step in enumerate(self._sequence):
            if self._cancelled:
                self.finished_signal.emit(False, "Shutdown cancelled by operator.")
                return

            self.step_progress.emit(i, step.key, "stopping")
            self._ctrl.stop([step.key])
            self.step_progress.emit(i, step.key, "stopped")

        self.finished_signal.emit(True, "All services stopped.")


# ── Docker controller ────────────────────────────────────────────


class DockerController(QObject):
    """Resolve config keys to container names and run start/stop/status via docker-py."""

    def __init__(
        self,
        config: Mapping[str, Any],
        app_state: AppState,
        *,
        parent: Optional[QObject] = None,
        client: Optional[docker.DockerClient] = None,
    ):
        super().__init__(parent)
        self._config = config
        self._state = app_state
        self._registry: Dict[str, List[str]] = self._parse_docker_containers(
            config.get("docker_containers") or {}
        )
        self._startup_sequence: List[SequenceStep] = self._parse_startup_sequence(
            config.get("docker_startup_sequence") or []
        )
        self._client: Optional[docker.DockerClient] = None
        self._available = False
        self._worker: Optional[DockerSequenceWorker] = None

        if client is not None:
            self._client = client
            self._available = True
        else:
            try:
                self._client = docker.from_env()
                self._client.ping()
                self._available = True
            except docker_errors.DockerException as exc:
                logger.warning("[Docker] Could not connect to Docker daemon: %s", exc)
                self._client = None
                self._available = False

    # ── Config parsing ───────────────────────────────────────

    @staticmethod
    def _parse_docker_containers(raw: Any) -> Dict[str, List[str]]:
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, List[str]] = {}
        for key, spec in raw.items():
            if not isinstance(spec, dict):
                continue
            name = spec.get("container_name")
            if name is None:
                continue
            if isinstance(name, list):
                names = [str(n) for n in name if n]
            else:
                names = [str(name)]
            if names:
                out[str(key)] = names
        return out

    def _parse_startup_sequence(self, raw: Any) -> List[SequenceStep]:
        if not isinstance(raw, list):
            return []
        steps: List[SequenceStep] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            if not key or key not in self._registry:
                logger.warning(
                    "[Docker] Startup sequence references unknown key %r, skipping", key
                )
                continue
            settle = item.get("settle_time_s", _DEFAULT_SETTLE_TIME_S)
            try:
                settle = float(settle)
            except (TypeError, ValueError):
                settle = _DEFAULT_SETTLE_TIME_S
            steps.append(SequenceStep(key=key, settle_time_s=settle))
        return steps

    # ── Public accessors ─────────────────────────────────────

    def keys(self) -> List[str]:
        return list(self._registry.keys())

    def container_names(self, key: str) -> List[str]:
        if key not in self._registry:
            raise KeyError(f"Unknown docker container key: {key!r}")
        return list(self._registry[key])

    def startup_sequence_keys(self) -> List[str]:
        return [s.key for s in self._startup_sequence]

    @property
    def is_sequence_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    # ── Sequence operations ──────────────────────────────────

    def start_sequence(self) -> None:
        """Launch sequential startup in a background thread."""
        if self.is_sequence_running:
            logger.warning("[Docker] Sequence already running, ignoring start request")
            return
        if not self._startup_sequence:
            self._state.docker_sequence_finished.emit(False, "No startup sequence configured.")
            return
        self._worker = DockerSequenceWorker(
            self, self._startup_sequence, direction="start", parent=self
        )
        self._wire_worker()
        self._worker.start()

    def stop_sequence(self) -> None:
        """Launch sequential shutdown (reverse order) in a background thread."""
        if self.is_sequence_running:
            logger.warning("[Docker] Sequence already running, ignoring stop request")
            return
        if not self._startup_sequence:
            self._state.docker_sequence_finished.emit(False, "No startup sequence configured.")
            return
        reversed_seq = list(reversed(self._startup_sequence))
        self._worker = DockerSequenceWorker(
            self, reversed_seq, direction="stop", parent=self
        )
        self._wire_worker()
        self._worker.start()

    def cancel_sequence(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _wire_worker(self) -> None:
        assert self._worker is not None
        self._worker.step_progress.connect(self._state.docker_sequence_step.emit)
        self._worker.finished_signal.connect(self._state.docker_sequence_finished.emit)

    # ── Single-key operations (unchanged) ────────────────────

    def _emit_unavailable(self, keys: Iterable[str], msg: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key in keys:
            out[key] = "unavailable"
            self._state.docker_error.emit(key, msg)
        return out

    def _get_container_status(self, name: str) -> str:
        assert self._client is not None
        c = self._client.containers.get(name)
        c.reload()
        return str(c.status or "unknown")

    def status(self, keys: Optional[Iterable[str]] = None) -> Dict[str, str]:
        """Return aggregated status per key.

        Only reports ``"running"`` when *all* containers for that key are
        running.  Otherwise returns the worst individual status.
        """
        ks = list(keys) if keys is not None else self.keys()
        if not self._available or self._client is None:
            return self._emit_unavailable(
                ks,
                "Docker daemon not available (check socket / install Docker).",
            )

        out: Dict[str, str] = {}
        for key in ks:
            names = self.container_names(key)
            per_container: List[str] = []
            for name in names:
                try:
                    per_container.append(self._get_container_status(name))
                except docker_errors.NotFound:
                    per_container.append("missing")
                except docker_errors.APIError as exc:
                    per_container.append("error")
                    self._state.docker_error.emit(key, f"{name}: {exc}")

            agg = _worst_status(per_container) if per_container else "unknown"
            out[key] = agg
            self._state.docker_status_changed.emit(key, agg)
        return out

    def start(self, keys: Iterable[str]) -> Dict[str, str]:
        """Start containers by config key (all-or-nothing per key).

        If any container in a group fails to start, the ones that were just
        started are rolled back (stopped).
        """
        ks = list(keys)
        if not self._available or self._client is None:
            return self._emit_unavailable(
                ks,
                "Docker daemon not available (check socket / install Docker).",
            )

        out: Dict[str, str] = {}
        for key in ks:
            names = self.container_names(key)
            started_in_this_call: List[str] = []
            all_already_running = True
            failed = False
            fail_msg = ""

            for name in names:
                try:
                    c = self._client.containers.get(name)
                    c.reload()
                    if c.status == "running":
                        continue
                    all_already_running = False
                    c.start()
                    started_in_this_call.append(name)
                except docker_errors.NotFound:
                    failed = True
                    fail_msg = (
                        f"Container {name!r} not found. "
                        "Create it first (e.g. docker compose create)."
                    )
                    break
                except docker_errors.APIError as exc:
                    failed = True
                    fail_msg = f"Failed to start {name!r}: {exc}"
                    break

            if failed:
                self._rollback_started(started_in_this_call)
                out[key] = "error"
                self._state.docker_error.emit(key, fail_msg)
            elif all_already_running and not started_in_this_call:
                out[key] = "already_running"
                self._state.docker_status_changed.emit(key, "running")
            else:
                out[key] = "started"
                self._state.docker_status_changed.emit(key, "running")

        return out

    def _rollback_started(self, names: List[str]) -> None:
        """Best-effort stop of containers that were started during a failed group start."""
        for name in names:
            try:
                c = self._client.containers.get(name)  # type: ignore[union-attr]
                c.stop(timeout=5)
                logger.info("[Docker] Rolled back container %s", name)
            except Exception:  # noqa: BLE001
                logger.warning("[Docker] Rollback failed for %s", name, exc_info=True)

    def stop(self, keys: Iterable[str], *, timeout: int = 10) -> Dict[str, str]:
        """Stop all containers for each key (best-effort: attempt all even if one fails)."""
        ks = list(keys)
        if not self._available or self._client is None:
            return self._emit_unavailable(
                ks,
                "Docker daemon not available (check socket / install Docker).",
            )

        out: Dict[str, str] = {}
        for key in ks:
            names = self.container_names(key)
            any_error = False
            any_stopped = False
            all_missing = True

            for name in names:
                try:
                    c = self._client.containers.get(name)
                    c.reload()
                    all_missing = False
                    if c.status == "running":
                        try:
                            c.stop(timeout=timeout)
                        except docker_errors.APIError:
                            logger.warning(
                                "[Docker] Graceful stop failed for %s, sending kill", name
                            )
                            c.kill()
                        any_stopped = True
                except docker_errors.NotFound:
                    pass
                except docker_errors.APIError as exc:
                    any_error = True
                    all_missing = False
                    self._state.docker_error.emit(key, f"Failed to stop {name!r}: {exc}")

            if any_error:
                out[key] = "error"
            elif all_missing:
                out[key] = "missing_ok"
                self._state.docker_status_changed.emit(key, "missing")
            elif any_stopped:
                out[key] = "stopped"
                self._state.docker_status_changed.emit(key, "stopped")
            else:
                out[key] = "already_stopped"
                self._state.docker_status_changed.emit(key, "stopped")

        return out
