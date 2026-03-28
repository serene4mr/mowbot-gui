"""Pytest fixtures shared across tests."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Single Qt core application for signal delivery in unit tests."""
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app
