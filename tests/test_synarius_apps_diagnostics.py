"""Smoke tests for shared GUI diagnostics (no second configure_file_logging in same process)."""

from __future__ import annotations

from synarius_apps_diagnostics import (
    configure_file_logging,
    install_qt_message_handler,
    log_directory_for_app,
    log_session_start,
    main_log_path,
)


def test_log_directory_for_app_creates_dir() -> None:
    d = log_directory_for_app(appname="SynariusDiagSmokeTest")
    assert d.is_dir()
    assert "SynariusDiagSmokeTest" in str(d) or "synariusdiagsmoketest" in str(d).lower()


def test_public_api_callable() -> None:
    assert callable(configure_file_logging)
    assert callable(install_qt_message_handler)
    assert callable(log_session_start)
    assert callable(main_log_path)
