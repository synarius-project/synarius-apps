"""Smoke tests for shared GUI diagnostics (no second configure_file_logging in same process)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from synarius_apps_diagnostics import (
    configure_file_logging,
    install_qt_message_handler,
    log_directory_for_app,
    log_session_start,
    main_log_path,
)
from synarius_apps_diagnostics.core import (
    _debug_from_env,
    _fault_handler_disabled_by_env,
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


class DebugFromEnvTest(unittest.TestCase):

    def _call(self, env: dict, keys: list[str] | None = None) -> bool:
        with patch.dict(os.environ, env, clear=True):
            return _debug_from_env(keys or [])

    def test_returns_false_when_env_empty(self) -> None:
        self.assertFalse(self._call({}))

    def test_key_with_value_1_returns_true(self) -> None:
        self.assertTrue(self._call({"MY_DEBUG": "1"}, ["MY_DEBUG"]))

    def test_key_with_value_true_returns_true(self) -> None:
        self.assertTrue(self._call({"MY_DEBUG": "true"}, ["MY_DEBUG"]))

    def test_key_with_value_yes_returns_true(self) -> None:
        self.assertTrue(self._call({"MY_DEBUG": "yes"}, ["MY_DEBUG"]))

    def test_key_with_value_on_returns_true(self) -> None:
        self.assertTrue(self._call({"MY_DEBUG": "on"}, ["MY_DEBUG"]))

    def test_key_with_value_0_returns_false(self) -> None:
        self.assertFalse(self._call({"MY_DEBUG": "0"}, ["MY_DEBUG"]))

    def test_key_with_empty_value_returns_false(self) -> None:
        self.assertFalse(self._call({"MY_DEBUG": ""}, ["MY_DEBUG"]))

    def test_fallback_synarius_log_debug_true(self) -> None:
        self.assertTrue(self._call({"SYNARIUS_LOG_DEBUG": "1"}))

    def test_fallback_synarius_log_debug_false(self) -> None:
        self.assertFalse(self._call({"SYNARIUS_LOG_DEBUG": "0"}))

    def test_case_insensitive(self) -> None:
        self.assertTrue(self._call({"MY_DEBUG": "TRUE"}, ["MY_DEBUG"]))


class FaultHandlerDisabledByEnvTest(unittest.TestCase):

    def _call(self, value: str) -> bool:
        with patch.dict(os.environ, {"SYNARIUS_FAULT_HANDLER": value}, clear=False):
            return _fault_handler_disabled_by_env()

    def test_empty_string_not_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_fault_handler_disabled_by_env())

    def test_value_0_is_disabled(self) -> None:
        self.assertTrue(self._call("0"))

    def test_value_false_is_disabled(self) -> None:
        self.assertTrue(self._call("false"))

    def test_value_no_is_disabled(self) -> None:
        self.assertTrue(self._call("no"))

    def test_value_off_is_disabled(self) -> None:
        self.assertTrue(self._call("off"))

    def test_value_1_not_disabled(self) -> None:
        self.assertFalse(self._call("1"))

    def test_value_true_not_disabled(self) -> None:
        self.assertFalse(self._call("true"))

    def test_case_insensitive(self) -> None:
        self.assertTrue(self._call("FALSE"))
