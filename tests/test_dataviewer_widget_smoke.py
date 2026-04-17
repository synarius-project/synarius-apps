"""Smoke: DataViewerWidget constructs without raising.

Guards against the PySide6-Enum regression where ``Qt.ToolButtonStyle.ToolButtonIconOnly``
was incorrectly cast with ``int()``, causing a ``TypeError`` at widget construction time
and preventing the DataViewer from opening on canvas double-click.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def _empty_series(name: str) -> tuple[np.ndarray, np.ndarray]:
    return np.array([0.0]), np.array([0.0])


class DataViewerWidgetSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    # ------------------------------------------------------------------
    # Test 1a — core construction guard
    # ------------------------------------------------------------------

    def test_init_static_mode_no_exception(self) -> None:
        """DataViewerWidget.__init__ must complete without raising in static mode.

        Regression: ToolButtonStyle Enum cast to int() raised TypeError on PySide6 6.x.
        """
        from synariustools.tools.plotwidget.widget import DataViewerWidget

        w = DataViewerWidget(_empty_series)
        self.assertIsNotNone(w)
        w.close()

    def test_toolbar_button_style_is_icon_only(self) -> None:
        """Toolbar style must be ToolButtonIconOnly — not an int, not zero.

        An ``int()`` cast returns 0 (TextOnly), masking the icon-only layout.
        """
        from synariustools.tools.plotwidget.widget import DataViewerWidget

        w = DataViewerWidget(_empty_series)
        actual = w._toolbar.toolButtonStyle()
        self.assertEqual(actual, Qt.ToolButtonStyle.ToolButtonIconOnly)
        w.close()

    def test_init_dynamic_mode_walking_axis_no_exception(self) -> None:
        """dynamic mode + enable_walking_axis=True must also construct cleanly."""
        from synariustools.tools.plotwidget.widget import DataViewerWidget

        w = DataViewerWidget(_empty_series, mode="dynamic", enable_walking_axis=True)
        self.assertIsNotNone(w)
        w.close()

    # ------------------------------------------------------------------
    # Test 1b — DataViewerShell wrapper
    # ------------------------------------------------------------------

    def test_shell_exposes_viewer(self) -> None:
        """DataViewerShell.viewer must be the wrapped DataViewerWidget."""
        from synariustools.tools.plotwidget.widget import DataViewerShell, DataViewerWidget

        shell = DataViewerShell(_empty_series)
        self.assertIsInstance(shell.viewer, DataViewerWidget)
        shell.close()

    def test_shell_dynamic_mode_no_exception(self) -> None:
        """DataViewerShell in dynamic mode (as Studio uses it) must construct cleanly."""
        from synariustools.tools.plotwidget.widget import DataViewerShell

        shell = DataViewerShell(
            _empty_series,
            enable_walking_axis=True,
            mode="dynamic",
            legend_visible_at_start=True,
        )
        self.assertIsNotNone(shell.viewer)
        shell.close()


if __name__ == "__main__":
    unittest.main()
