"""Tests for synarius_parawiz Qt widgets (requires QApplication / Windows display)."""

from __future__ import annotations

from uuid import UUID

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QWidget

# ---------------------------------------------------------------------------
# windows_app_id
# ---------------------------------------------------------------------------

class TestWindowsAppId:
    def test_constant_value(self) -> None:
        from synarius_parawiz.app.windows_app_id import PARAWIZ_APP_USER_MODEL_ID

        assert PARAWIZ_APP_USER_MODEL_ID == "Synarius.SynariusApps.ParaWiz.1.0"


# ---------------------------------------------------------------------------
# _item_flags_to_int  (compat_table_view helper)
# ---------------------------------------------------------------------------

class TestItemFlagsToInt:
    def test_plain_int_is_returned_unchanged(self) -> None:
        from synarius_parawiz.app.compat_table_view import _item_flags_to_int

        assert _item_flags_to_int(7) == 7

    def test_qt_item_flag_converts_to_int(self) -> None:
        from synarius_parawiz.app.compat_table_view import _item_flags_to_int

        flag = Qt.ItemFlag.ItemIsEnabled
        result = _item_flags_to_int(flag)
        assert isinstance(result, int)
        assert result > 0

    def test_qt_item_flags_combination(self) -> None:
        from synarius_parawiz.app.compat_table_view import _item_flags_to_int

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        result = _item_flags_to_int(flags)
        assert isinstance(result, int)

    def test_object_with_value_attribute(self) -> None:
        from synarius_parawiz.app.compat_table_view import _item_flags_to_int

        class _FakeFlags:
            # Triggers the `getattr(flags, "value", None)` branch
            # We need int(Qt.ItemFlags(flags)) to fail first.
            # Simplest: pass something Qt.ItemFlags() cannot accept.
            pass

        obj = _FakeFlags()
        obj.value = 3  # type: ignore[attr-defined]
        result = _item_flags_to_int(obj)  # type: ignore[arg-type]
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# ParaWizParameterTableModel
# ---------------------------------------------------------------------------

@pytest.fixture
def table_model(qapp):
    from synarius_parawiz.app.parameter_table_model import ParaWizParameterTableModel

    row_data: list[tuple[str, str, UUID]] = [
        ("icon_a", "1.0", UUID("00000000-0000-0000-0000-000000000001")),
        ("icon_b", "2.0", UUID("00000000-0000-0000-0000-000000000002")),
    ]

    def row_count_fn() -> int:
        return len(row_data)

    def col_count_fn() -> int:
        return 3

    def cell_payload_fn(row: int, col: int) -> tuple[str, str, UUID] | None:
        if 0 <= row < len(row_data):
            return row_data[row]
        return None

    def row_style_fn(row: int) -> tuple[bool, dict[int, QBrush] | None]:
        if row == 0:
            return (True, {0: QBrush(QColor("#ff0000"))})
        return (False, None)

    def icon_fn(name: str) -> QIcon:
        return QIcon()

    return ParaWizParameterTableModel(
        row_count_fn=row_count_fn,
        column_count_fn=col_count_fn,
        cell_payload_fn=cell_payload_fn,
        row_style_fn=row_style_fn,
        icon_fn=icon_fn,
    )


class TestParameterTableModel:
    def test_row_count(self, table_model) -> None:
        assert table_model.rowCount() == 2

    def test_column_count(self, table_model) -> None:
        assert table_model.columnCount() == 3

    def test_row_count_with_parent(self, table_model) -> None:
        assert table_model.rowCount(QModelIndex()) == 2

    def test_data_display_role_present(self, table_model) -> None:
        idx = table_model.index(0, 0)
        val = table_model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert val == "1.0"

    def test_data_display_role_out_of_range(self, table_model) -> None:
        # index(99, 0) is out-of-range → Qt returns invalid QModelIndex → data() returns None
        idx = table_model.index(99, 0)
        val = table_model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert val is None

    def test_data_invalid_index_returns_none(self, table_model) -> None:
        val = table_model.data(QModelIndex())
        assert val is None

    def test_data_decoration_role_present(self, table_model) -> None:
        idx = table_model.index(0, 0)
        val = table_model.data(idx, Qt.ItemDataRole.DecorationRole)
        assert isinstance(val, QIcon)

    def test_data_decoration_role_out_of_range(self, table_model) -> None:
        idx = table_model.index(99, 0)
        val = table_model.data(idx, Qt.ItemDataRole.DecorationRole)
        assert val is None

    def test_data_user_role_present(self, table_model) -> None:
        idx = table_model.index(0, 0)
        val = table_model.data(idx, Qt.ItemDataRole.UserRole)
        assert val == "00000000-0000-0000-0000-000000000001"

    def test_data_user_role_out_of_range(self, table_model) -> None:
        idx = table_model.index(99, 0)
        val = table_model.data(idx, Qt.ItemDataRole.UserRole)
        assert val is None

    def test_data_font_role_bold_row(self, table_model) -> None:
        idx = table_model.index(0, 0)
        val = table_model.data(idx, Qt.ItemDataRole.FontRole)
        assert isinstance(val, QFont)
        assert val.bold()

    def test_data_font_role_non_bold_row(self, table_model) -> None:
        idx = table_model.index(1, 0)
        val = table_model.data(idx, Qt.ItemDataRole.FontRole)
        assert val is None

    def test_data_foreground_role_with_brush(self, table_model) -> None:
        idx = table_model.index(0, 0)
        val = table_model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert val is not None  # brush for col 0

    def test_data_foreground_role_no_brush(self, table_model) -> None:
        idx = table_model.index(1, 0)
        val = table_model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert val is None

    def test_data_unknown_role_returns_none(self, table_model) -> None:
        idx = table_model.index(0, 0)
        val = table_model.data(idx, 9999)
        assert val is None

    def test_flags_valid_index(self, table_model) -> None:
        idx = table_model.index(0, 0)
        flags = table_model.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsEnabled
        assert flags & Qt.ItemFlag.ItemIsSelectable

    def test_flags_invalid_index(self, table_model) -> None:
        flags = table_model.flags(QModelIndex())
        assert flags == Qt.ItemFlag.NoItemFlags

    def test_refresh_does_not_raise(self, table_model) -> None:
        table_model.refresh()


# ---------------------------------------------------------------------------
# StatusMessageProgressBar
# ---------------------------------------------------------------------------

@pytest.fixture
def progress_bar(qapp):
    from synarius_parawiz.app.status_progress_widget import StatusMessageProgressBar

    return StatusMessageProgressBar(accent_color="#0078d4")


class TestStatusMessageProgressBar:
    def test_initial_value_is_zero(self, progress_bar) -> None:
        assert progress_bar.value() == 0

    def test_set_range_and_value(self, progress_bar) -> None:
        progress_bar.set_range(0, 100)
        progress_bar.set_value(50)
        assert progress_bar.value() == 50

    def test_set_message_short(self, progress_bar) -> None:
        progress_bar.set_message("Loading…")

    def test_set_message_empty(self, progress_bar) -> None:
        progress_bar.set_message("")

    def test_set_message_then_clear(self, progress_bar) -> None:
        progress_bar.set_message("Step 1 of 3")
        progress_bar.set_message("")

    def test_set_accent_color_same_is_noop(self, progress_bar) -> None:
        progress_bar.set_accent_color("#0078d4")

    def test_set_accent_color_different_updates(self, progress_bar) -> None:
        progress_bar.set_accent_color("#ff0000")
        progress_bar.set_accent_color("#00aa00")

    def test_resize_event_triggers_layout(self, progress_bar) -> None:
        progress_bar.resize(500, 18)

    def test_custom_bar_dimensions(self, qapp) -> None:
        from synarius_parawiz.app.status_progress_widget import StatusMessageProgressBar

        w = StatusMessageProgressBar(accent_color="#aabbcc", bar_width=200, bar_height=20)
        w.set_message("test")
        w.set_range(0, 10)
        w.set_value(5)
        assert w.value() == 5


# ---------------------------------------------------------------------------
# CompatTableView  +  _CompatItemModel
# ---------------------------------------------------------------------------

@pytest.fixture
def compat_view(qapp):
    from synarius_parawiz.app.compat_table_view import CompatTableView

    return CompatTableView()


class TestCompatTableView:
    def test_initial_dimensions_are_zero(self, compat_view) -> None:
        assert compat_view.rowCount() == 0
        assert compat_view.columnCount() == 0

    def test_set_row_column_count(self, compat_view) -> None:
        compat_view.setRowCount(4)
        compat_view.setColumnCount(3)
        assert compat_view.rowCount() == 4
        assert compat_view.columnCount() == 3

    def test_set_item_and_retrieve(self, compat_view) -> None:
        compat_view.setRowCount(3)
        compat_view.setColumnCount(3)
        item = QTableWidgetItem("hello")
        compat_view.setItem(0, 0, item)
        assert compat_view.item(0, 0) is item

    def test_item_missing_returns_none(self, compat_view) -> None:
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        assert compat_view.item(0, 0) is None

    def test_set_item_out_of_bounds_is_noop(self, compat_view) -> None:
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        compat_view.setItem(99, 0, QTableWidgetItem("x"))
        assert compat_view.item(99, 0) is None

    def test_set_item_negative_is_noop(self, compat_view) -> None:
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        compat_view.setItem(-1, 0, QTableWidgetItem("x"))

    def test_clear_removes_all_items(self, compat_view) -> None:
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        compat_view.setItem(0, 0, QTableWidgetItem("x"))
        compat_view.clear()
        assert compat_view.item(0, 0) is None

    def test_clear_contents(self, compat_view) -> None:
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        compat_view.setItem(0, 0, QTableWidgetItem("x"))
        compat_view.clearContents()
        assert compat_view.item(0, 0) is None

    def test_set_row_count_prunes_out_of_range_items(self, compat_view) -> None:
        compat_view.setRowCount(5)
        compat_view.setColumnCount(2)
        compat_view.setItem(4, 0, QTableWidgetItem("deep"))
        compat_view.setRowCount(2)
        assert compat_view.item(4, 0) is None

    def test_set_cell_widget_and_retrieve(self, compat_view) -> None:
        from PySide6.QtWidgets import QLabel

        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        label = QLabel("cell widget")
        compat_view.setCellWidget(0, 0, label)
        retrieved = compat_view.cellWidget(0, 0)
        assert retrieved is label

    def test_remove_cell_widget(self, compat_view) -> None:
        from PySide6.QtWidgets import QLabel

        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        compat_view.setCellWidget(0, 0, QLabel("x"))
        compat_view.removeCellWidget(0, 0)

    def test_item_with_icon_branch(self, compat_view) -> None:
        """Covers the non-null icon branch in _sync_item_to_model."""
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        pm = QPixmap(16, 16)
        pm.fill(QColor("#ff0000"))
        item = QTableWidgetItem()
        item.setIcon(QIcon(pm))
        item.setText("icon-item")
        compat_view.setItem(0, 0, item)
        assert compat_view.item(0, 0) is item

    def test_item_with_background_brush(self, compat_view) -> None:
        """Covers the non-NoBrush background branch in _sync_item_to_model."""
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        item = QTableWidgetItem("bg")
        item.setBackground(QBrush(QColor("#0000ff")))
        compat_view.setItem(0, 0, item)
        assert compat_view.item(0, 0) is item

    def test_compat_model_flags_valid_with_userdata(self, compat_view) -> None:
        """Covers _CompatItemModel.flags() with UserRole+1 data set."""
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        item = QTableWidgetItem("x")
        compat_view.setItem(0, 0, item)
        idx = compat_view._model.index(0, 0)
        flags = compat_view._model.flags(idx)
        assert flags is not None

    def test_compat_model_flags_invalid_index(self, compat_view) -> None:
        flags = compat_view._model.flags(QModelIndex())
        assert flags == Qt.ItemFlag.NoItemFlags

    def test_compat_model_flags_no_userdata(self, compat_view) -> None:
        """Covers _CompatItemModel.flags() where raw is None (no UserRole+1 data)."""
        compat_view.setRowCount(2)
        compat_view.setColumnCount(2)
        idx = compat_view._model.index(0, 0)
        # No UserRole+1 data → falls through to super().flags()
        flags = compat_view._model.flags(idx)
        assert flags is not None


# ---------------------------------------------------------------------------
# ParameterTableSplitView
# ---------------------------------------------------------------------------

def _make_table_widget(name: str) -> QTableWidget:
    tw = QTableWidget()
    tw.setObjectName(name)
    return tw


@pytest.fixture
def split_view(qapp):
    from synarius_parawiz.app.parameter_table_split_view import ParameterTableSplitView

    parent = QWidget()
    view = ParameterTableSplitView(parent, table_factory=_make_table_widget)
    # Keep parent alive via a Python attribute so Qt doesn't delete child widgets early.
    view._test_parent_ref = parent  # type: ignore[attr-defined]
    yield view


@pytest.fixture
def split_view_with_supplier(qapp):
    from synarius_parawiz.app.parameter_table_split_view import ParameterTableSplitView

    parent = QWidget()
    col_idx = [0]
    view = ParameterTableSplitView(
        parent,
        table_factory=_make_table_widget,
        main_column_supplier=lambda: col_idx[0],
    )
    view._test_parent_ref = parent  # type: ignore[attr-defined]
    yield view


class TestParameterTableSplitView:
    def test_properties_accessible(self, split_view) -> None:
        assert split_view.main_header is not None
        assert split_view.main_body is not None
        assert split_view.target_header is not None
        assert split_view.target_body is not None

    def test_is_syncing_initially_false(self, split_view) -> None:
        assert not split_view.is_syncing_row_selection

    def test_set_target_visible_false(self, split_view) -> None:
        split_view.set_target_visible(False)

    def test_set_target_visible_true(self, split_view) -> None:
        split_view.set_target_visible(True)

    def test_set_target_fixed_width(self, split_view) -> None:
        split_view.set_target_fixed_width(120)

    def test_set_target_fixed_width_minimum(self, split_view) -> None:
        split_view.set_target_fixed_width(0)  # clamped to 1

    def test_take_target_block_returns_widget(self, split_view) -> None:
        block = split_view.take_target_block()
        assert isinstance(block, QWidget)

    def test_bind_frozen_body(self, split_view) -> None:
        frozen = _make_table_widget("Frozen")
        split_view.bind_frozen_body(frozen)

    def test_sync_vscroll_from_main(self, split_view) -> None:
        split_view._on_main_vscroll(0)

    def test_sync_vscroll_from_target(self, split_view) -> None:
        split_view._on_target_vscroll(0)

    def test_sync_vscroll_from_frozen_without_frozen_body(self, split_view) -> None:
        split_view._on_frozen_vscroll(0)

    def test_sync_vscroll_from_frozen_with_frozen_body(self, split_view) -> None:
        frozen = _make_table_widget("Frozen")
        split_view.bind_frozen_body(frozen)
        split_view._on_frozen_vscroll(0)

    def test_sync_vscroll_guard_prevents_reentry(self, split_view) -> None:
        split_view._sync_vscroll_guard = True
        split_view._sync_vscroll(0, source="main")  # should return immediately
        split_view._sync_vscroll_guard = False

    def test_selected_rows_for_sync_empty_table(self, split_view) -> None:
        from synarius_parawiz.app.parameter_table_split_view import ParameterTableSplitView

        rows = ParameterTableSplitView._selected_rows_for_sync(split_view.main_body)
        assert isinstance(rows, set)

    def test_selected_rows_for_sync_with_selection(self, split_view) -> None:
        from synarius_parawiz.app.parameter_table_split_view import ParameterTableSplitView

        tw = split_view.main_body
        tw.setRowCount(3)
        tw.setColumnCount(2)
        tw.setCurrentCell(1, 0)
        rows = ParameterTableSplitView._selected_rows_for_sync(tw)
        assert isinstance(rows, set)

    def test_set_row_selection_empty_rows(self, split_view) -> None:
        tw = split_view.main_body
        tw.setRowCount(3)
        tw.setColumnCount(2)
        split_view._set_row_selection(tw, set())

    def test_set_row_selection_no_columns(self, split_view) -> None:
        tw = split_view.main_body
        tw.setRowCount(3)
        tw.setColumnCount(0)
        split_view._set_row_selection(tw, {0, 1})

    def test_set_row_selection_valid_rows(self, split_view) -> None:
        tw = split_view.main_body
        tw.setRowCount(3)
        tw.setColumnCount(2)
        split_view._set_row_selection(tw, {0, 2})

    def test_set_row_selection_out_of_range_rows(self, split_view) -> None:
        tw = split_view.main_body
        tw.setRowCount(3)
        tw.setColumnCount(2)
        split_view._set_row_selection(tw, {99})

    def test_sync_row_selection_from_main(self, split_view) -> None:
        split_view.main_body.setRowCount(2)
        split_view.main_body.setColumnCount(2)
        split_view.target_body.setRowCount(2)
        split_view.target_body.setColumnCount(1)
        split_view._sync_row_selection_from("main")

    def test_sync_row_selection_from_target(self, split_view) -> None:
        split_view.main_body.setRowCount(2)
        split_view.main_body.setColumnCount(2)
        split_view.target_body.setRowCount(2)
        split_view.target_body.setColumnCount(1)
        split_view._sync_row_selection_from("target")

    def test_sync_row_selection_from_frozen_without_body(self, split_view) -> None:
        split_view._sync_row_selection_from("frozen")

    def test_sync_row_selection_from_frozen_with_body(self, split_view) -> None:
        frozen = _make_table_widget("Frozen")
        frozen.setRowCount(2)
        frozen.setColumnCount(1)
        split_view.bind_frozen_body(frozen)
        split_view.main_body.setRowCount(2)
        split_view.main_body.setColumnCount(2)
        split_view.target_body.setRowCount(2)
        split_view.target_body.setColumnCount(1)
        split_view._sync_row_selection_from("frozen")

    def test_sync_row_selection_unknown_source_is_noop(self, split_view) -> None:
        split_view._sync_row_selection_from("unknown")

    def test_sync_sel_guard_prevents_reentry(self, split_view) -> None:
        split_view._sync_sel_guard = True
        split_view._on_main_selection_changed()
        split_view._on_target_selection_changed()
        split_view._on_frozen_selection_changed()
        split_view._sync_sel_guard = False

    def test_set_main_body_cell_rows_selection_no_columns(self, split_view) -> None:
        split_view.main_body.setRowCount(3)
        split_view.main_body.setColumnCount(0)
        split_view._set_main_body_cell_rows_selection({0})

    def test_set_main_body_cell_rows_selection_valid(self, split_view) -> None:
        split_view.main_body.setRowCount(3)
        split_view.main_body.setColumnCount(2)
        split_view._set_main_body_cell_rows_selection({0, 2})

    def test_set_main_body_cell_rows_selection_with_supplier(self, split_view_with_supplier) -> None:
        v = split_view_with_supplier
        v.main_body.setRowCount(3)
        v.main_body.setColumnCount(2)
        v._set_main_body_cell_rows_selection({1})
