"""Qt table model for ParaWiz parameter values."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QFont, QIcon


class ParaWizParameterTableModel(QAbstractTableModel):
    """Read-only model backed by callables owned by MainWindow."""

    def __init__(
        self,
        *,
        row_count_fn: Callable[[], int],
        column_count_fn: Callable[[], int],
        cell_payload_fn: Callable[[int, int], tuple[str, str, UUID] | None],
        row_style_fn: Callable[[int], tuple[bool, dict[int, QBrush] | None]],
        icon_fn: Callable[[str], QIcon],
    ) -> None:
        super().__init__()
        self._row_count_fn = row_count_fn
        self._column_count_fn = column_count_fn
        self._cell_payload_fn = cell_payload_fn
        self._row_style_fn = row_style_fn
        self._icon_fn = icon_fn

    def rowCount(self, _parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return int(self._row_count_fn())

    def columnCount(self, _parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return int(self._column_count_fn())

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = int(index.row())
        col = int(index.column())
        hit = self._cell_payload_fn(row, col)
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if hit is None else hit[1]
        if role == Qt.ItemDataRole.DecorationRole:
            if hit is None:
                return None
            return self._icon_fn(hit[0])
        if role == Qt.ItemDataRole.UserRole:
            if hit is None:
                return None
            return str(hit[2])
        if role == Qt.ItemDataRole.FontRole:
            bold, _fg_by_col = self._row_style_fn(row)
            if bold:
                f = QFont()
                f.setBold(True)
                return f
            return None
        if role == Qt.ItemDataRole.ForegroundRole:
            _bold, fg_by_col = self._row_style_fn(row)
            if fg_by_col is None:
                return None
            return fg_by_col.get(col)
        return None

    def flags(self, index: QModelIndex):  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()

