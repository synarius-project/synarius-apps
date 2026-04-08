"""Split wrapper for ParaWiz parameter table views."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt
from PySide6.QtWidgets import QHBoxLayout, QTableWidget, QVBoxLayout, QWidget


class ParameterTableSplitView(QWidget):
    """Hosts the scrollable main table and the fixed right target column."""

    def __init__(
        self,
        parent: QWidget,
        *,
        table_factory: Callable[[str], QTableWidget],
        main_column_supplier: Callable[[], int] | None = None,
    ) -> None:
        super().__init__(parent)
        self._sync_vscroll_guard = False
        self._sync_sel_guard = False
        self._frozen_body: QTableWidget | None = None
        self._main_column_supplier = main_column_supplier

        self._main_header = table_factory("ParameterTableHeader")
        self._main_body = table_factory("ParameterTable")
        self._target_header = table_factory("ParameterTableTargetHeader")
        self._target_body = table_factory("ParameterTableTarget")

        self._main_header.setRowCount(0)
        self._target_header.setRowCount(0)
        self._main_body.setRowCount(0)
        self._target_body.setRowCount(0)

        self._target_header.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._target_header.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._target_body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._target_body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._target_header.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._target_body.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._target_body.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        self._main_block = QWidget(self)
        self._target_block = QWidget(self)

        main_lay = QVBoxLayout(self._main_block)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(self._main_header, 0)
        main_lay.addWidget(self._main_body, 1)

        target_lay = QVBoxLayout(self._target_block)
        target_lay.setContentsMargins(0, 0, 0, 0)
        target_lay.setSpacing(0)
        target_lay.addWidget(self._target_header, 0)
        target_lay.addWidget(self._target_body, 1)

        self._outer_layout = QHBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)
        self._outer_layout.addWidget(self._main_block, 1)
        self._outer_layout.addWidget(self._target_block, 0)

        self._main_body.verticalScrollBar().valueChanged.connect(self._on_main_vscroll)
        self._target_body.verticalScrollBar().valueChanged.connect(self._on_target_vscroll)
        self._main_body.itemSelectionChanged.connect(self._on_main_selection_changed)
        self._target_body.itemSelectionChanged.connect(self._on_target_selection_changed)

    @property
    def main_header(self) -> QTableWidget:
        return self._main_header

    @property
    def main_body(self) -> QTableWidget:
        return self._main_body

    @property
    def target_header(self) -> QTableWidget:
        return self._target_header

    @property
    def target_body(self) -> QTableWidget:
        return self._target_body

    def set_target_visible(self, visible: bool) -> None:
        self._target_block.setVisible(visible)

    def set_target_fixed_width(self, width: int) -> None:
        w = max(1, int(width))
        self._target_header.setFixedWidth(w)
        self._target_body.setFixedWidth(w)
        self._target_block.setFixedWidth(w)

    def take_target_block(self) -> QWidget:
        """Entfernt die Target-Spalte aus diesem Widget.

        Der Aufrufer platziert ``_target_block`` fest rechts neben der horizontalen ScrollArea,
        damit sie beim Schmalwerden des Fensters nicht mit weggescrollt wird.
        """
        self._outer_layout.removeWidget(self._target_block)
        self._target_block.setParent(None)
        return self._target_block

    def bind_frozen_body(self, frozen_body: QTableWidget) -> None:
        self._frozen_body = frozen_body
        frozen_body.verticalScrollBar().valueChanged.connect(self._on_frozen_vscroll)
        frozen_body.itemSelectionChanged.connect(self._on_frozen_selection_changed)

    def _sync_vscroll(self, value: int, *, source: str) -> None:
        if self._sync_vscroll_guard:
            return
        self._sync_vscroll_guard = True
        try:
            if source != "main":
                self._main_body.verticalScrollBar().setValue(value)
            if source != "target":
                self._target_body.verticalScrollBar().setValue(value)
            if source != "frozen" and self._frozen_body is not None:
                self._frozen_body.verticalScrollBar().setValue(value)
        finally:
            self._sync_vscroll_guard = False

    @staticmethod
    def _selected_rows_for_sync(table: QTableWidget) -> set[int]:
        sm = table.selectionModel()
        if sm is None:
            return set()
        idxs = sm.selectedIndexes()
        if idxs:
            return {int(ix.row()) for ix in idxs}
        cur = sm.currentIndex()
        if cur.isValid():
            return {cur.row()}
        return set()

    def _set_row_selection(self, table: QTableWidget, rows: set[int]) -> None:
        sm = table.selectionModel()
        if sm is None:
            return
        sm.clearSelection()
        if not rows or table.columnCount() <= 0:
            return
        ncol = table.columnCount() - 1
        model = table.model()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for r in sorted(rows):
            if r < 0 or r >= table.rowCount():
                continue
            top_left = model.index(r, 0)
            bot_right = model.index(r, ncol)
            sm.select(QItemSelection(top_left, bot_right), flags)

    def _set_main_body_cell_rows_selection(self, rows: set[int]) -> None:
        tw = self._main_body
        sm = tw.selectionModel()
        if sm is None:
            return
        ncol = tw.columnCount()
        if ncol <= 0:
            return
        col = 0
        if self._main_column_supplier is not None:
            col = int(self._main_column_supplier())
        col = min(max(0, col), ncol - 1)
        # Kein eigenes _sync_sel_guard: sonst wird es vor Ende von _sync_row_selection_from
        # zurückgesetzt und Target→Main→Target feuert rekursiv (siehe itemSelectionChanged).
        sm.clearSelection()
        model = tw.model()
        for r in sorted(rows):
            if r < 0 or r >= tw.rowCount():
                continue
            ix = model.index(r, col)
            sm.select(ix, QItemSelectionModel.SelectionFlag.Select)
        if rows:
            r0 = min(r for r in rows if 0 <= r < tw.rowCount())
            sm.setCurrentIndex(
                model.index(r0, col),
                QItemSelectionModel.SelectionFlag(0),
            )

    def _sync_row_selection_from(self, source: str) -> None:
        if self._sync_sel_guard:
            return
        if source == "main":
            rows = self._selected_rows_for_sync(self._main_body)
        elif source == "target":
            rows = self._selected_rows_for_sync(self._target_body)
        elif source == "frozen":
            if self._frozen_body is None:
                return
            rows = self._selected_rows_for_sync(self._frozen_body)
        else:
            return
        self._sync_sel_guard = True
        try:
            if source != "main":
                self._set_main_body_cell_rows_selection(rows)
            if source != "target":
                self._set_row_selection(self._target_body, rows)
            if source != "frozen" and self._frozen_body is not None:
                self._set_row_selection(self._frozen_body, rows)
        finally:
            self._sync_sel_guard = False

    def _on_main_vscroll(self, value: int) -> None:
        self._sync_vscroll(value, source="main")

    def _on_target_vscroll(self, value: int) -> None:
        self._sync_vscroll(value, source="target")

    def _on_frozen_vscroll(self, value: int) -> None:
        self._sync_vscroll(value, source="frozen")

    def _on_main_selection_changed(self) -> None:
        if self._sync_sel_guard:
            return
        self._sync_row_selection_from("main")

    def _on_target_selection_changed(self) -> None:
        if self._sync_sel_guard:
            return
        self._sync_row_selection_from("target")

    def _on_frozen_selection_changed(self) -> None:
        if self._sync_sel_guard:
            return
        self._sync_row_selection_from("frozen")
