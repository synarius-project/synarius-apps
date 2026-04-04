"""Data carrier for calibration curve / map visualization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from synarius_core.parameters.repository import ParameterRecord


@dataclass(frozen=True, slots=True)
class CalibrationMapData:
    """Snapshot of one numeric calibration parameter (curve or map)."""

    title: str
    category: str
    values: np.ndarray
    axes: dict[int, np.ndarray]

    @classmethod
    def from_parameter_record(cls, rec: ParameterRecord) -> CalibrationMapData:
        vals = np.squeeze(np.asarray(rec.values, dtype=np.float64))
        ax_copy = {int(k): np.asarray(v, dtype=np.float64).copy() for k, v in rec.axes.items()}
        return cls(title=rec.name, category=str(rec.category).upper(), values=vals, axes=ax_copy)

    def axis_values(self, axis_idx: int) -> np.ndarray:
        if axis_idx in self.axes:
            return np.asarray(self.axes[axis_idx], dtype=np.float64).reshape(-1)
        if axis_idx >= self.values.ndim:
            return np.array([], dtype=np.float64)
        n = int(self.values.shape[axis_idx])
        return np.arange(n, dtype=np.float64)


def supports_calibration_plot(rec: ParameterRecord) -> bool:
    """True if the record is numeric and at least one-dimensional (curve / map / vector)."""
    if rec.is_text:
        return False
    return int(rec.values.ndim) >= 1
