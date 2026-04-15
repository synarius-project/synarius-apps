"""Session-wide pytest fixtures for synarius-apps tests."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication for the whole test session."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
