"""Factory for calibration curve / map viewer (embedded shell or bare widget)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from synariustools.tools.calmapwidget.data import CalibrationMapData
from synariustools.tools.calmapwidget.widget import CalibrationMapShell, CalibrationMapWidget


def create_calibration_map_viewer(
    data: CalibrationMapData,
    *,
    parent: QWidget | None = None,
    embedded: bool = True,
) -> CalibrationMapShell | CalibrationMapWidget:
    """Return toolbar+splitter shell (default) or a bare :class:`CalibrationMapWidget`."""
    if embedded:
        return CalibrationMapShell(data, parent)
    return CalibrationMapWidget(data, parent)
