"""Calibration curve / map viewer (tabular + matplotlib, for ParaWiz and Studio)."""

from synariustools.tools.calmapwidget.data import CalibrationMapData, supports_calibration_plot
from synariustools.tools.calmapwidget.factory import create_calibration_map_viewer
from synariustools.tools.calmapwidget.widget import CalibrationMapShell, CalibrationMapWidget

__all__ = [
    "CalibrationMapData",
    "CalibrationMapShell",
    "CalibrationMapWidget",
    "create_calibration_map_viewer",
    "supports_calibration_plot",
]
