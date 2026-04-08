"""QTableView with a minimal QTableWidget-like API used by ParaWiz."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QTableView, QTableWidgetItem, QWidget


def _item_flags_to_int(flags: int | Qt.ItemFlags | Qt.ItemFlag) -> int:
    """PySide6: ``int(item.flags())`` can raise; normalize via ``Qt.ItemFlags``."""
    if isinstance(flags, int):
        return flags
    try:
        return int(Qt.ItemFlags(flags))
    except Exception:
        v = getattr(flags, "value", None)
        if isinstance(v, int):
            return v
        return int(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)


class _CompatItemModel(QStandardItemModel):
    def flags(self, index: QModelIndex):  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        raw = self.data(index, Qt.ItemDataRole.UserRole + 1)
        if raw is None:
            return super().flags(index)
        try:
            return Qt.ItemFlags(_item_flags_to_int(int(raw)))
        except Exception:
            return super().flags(index)


class CompatTableView(QTableView):
    """Bridge class so existing code can move from QTableWidget to QTableView."""

    cellClicked = Signal(int, int)
    cellDoubleClicked = Signal(int, int)
    itemSelectionChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = _CompatItemModel(self)
        self._items: dict[tuple[int, int], QTableWidgetItem] = {}
        self.setModel(self._model)
        self.clicked.connect(lambda ix: self.cellClicked.emit(int(ix.row()), int(ix.column())))
        self.doubleClicked.connect(lambda ix: self.cellDoubleClicked.emit(int(ix.row()), int(ix.column())))
        sm = self.selectionModel()
        if sm is not None:
            sm.selectionChanged.connect(lambda _sel, _desel: self.itemSelectionChanged.emit())

    def setRowCount(self, rows: int) -> None:
        self._model.setRowCount(max(0, int(rows)))
        self._prune_items()

    def setColumnCount(self, cols: int) -> None:
        self._model.setColumnCount(max(0, int(cols)))
        self._prune_items()

    def rowCount(self) -> int:
        return self._model.rowCount()

    def columnCount(self) -> int:
        return self._model.columnCount()

    def clear(self) -> None:
        self._items.clear()
        self._model.clear()

    def clearContents(self) -> None:
        self._items.clear()
        self._model.clear()
        self._model.setRowCount(self.rowCount())
        self._model.setColumnCount(self.columnCount())

    def setItem(self, row: int, column: int, item: QTableWidgetItem) -> None:
        r = int(row)
        c = int(column)
        if r < 0 or c < 0 or r >= self.rowCount() or c >= self.columnCount():
            return
        self._items[(r, c)] = item
        self._sync_item_to_model(r, c, item)

    def item(self, row: int, column: int) -> QTableWidgetItem | None:
        return self._items.get((int(row), int(column)))

    def setCellWidget(self, row: int, column: int, widget: QWidget) -> None:
        """QTableWidget compatibility: embed a widget in a cell (uses ``QTableView.setIndexWidget``)."""
        idx = self._model.index(int(row), int(column))
        self.setIndexWidget(idx, widget)

    def cellWidget(self, row: int, column: int) -> QWidget | None:
        idx = self._model.index(int(row), int(column))
        return self.indexWidget(idx)

    def removeCellWidget(self, row: int, column: int) -> None:
        idx = self._model.index(int(row), int(column))
        self.setIndexWidget(idx, None)

    def _prune_items(self) -> None:
        max_r = self.rowCount()
        max_c = self.columnCount()
        keep: dict[tuple[int, int], QTableWidgetItem] = {}
        for (r, c), it in self._items.items():
            if 0 <= r < max_r and 0 <= c < max_c:
                keep[(r, c)] = it
                self._sync_item_to_model(r, c, it)
        self._items = keep

    def _sync_item_to_model(self, row: int, col: int, item: QTableWidgetItem) -> None:
        idx = self._model.index(row, col)
        self._model.setData(idx, item.text(), Qt.ItemDataRole.DisplayRole)
        icon = item.icon()
        if not icon.isNull():
            self._model.setData(idx, icon, Qt.ItemDataRole.DecorationRole)
        self._model.setData(idx, item.data(Qt.ItemDataRole.UserRole), Qt.ItemDataRole.UserRole)
        self._model.setData(idx, item.font(), Qt.ItemDataRole.FontRole)
        self._model.setData(idx, item.foreground(), Qt.ItemDataRole.ForegroundRole)
        _br = item.background()
        if _br.style() != Qt.BrushStyle.NoBrush:
            self._model.setData(idx, _br, Qt.ItemDataRole.BackgroundRole)
        else:
            # PySide6: QVariant is not exported from QtCore; None clears the role for alternating rows.
            self._model.setData(idx, None, Qt.ItemDataRole.BackgroundRole)
        self._model.setData(idx, item.textAlignment(), Qt.ItemDataRole.TextAlignmentRole)
        self._model.setData(idx, _item_flags_to_int(item.flags()), Qt.ItemDataRole.UserRole + 1)

