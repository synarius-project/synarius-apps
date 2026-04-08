"""Shared file logging, uncaught-exception hooks, and Qt message routing for Synarius GUIs."""

from __future__ import annotations

from synarius_apps_diagnostics.core import (
    configure_file_logging,
    install_qt_message_handler,
    log_directory_for_app,
    log_session_start,
    main_log_path,
)

__all__ = [
    "configure_file_logging",
    "install_qt_message_handler",
    "log_directory_for_app",
    "log_session_start",
    "main_log_path",
]
