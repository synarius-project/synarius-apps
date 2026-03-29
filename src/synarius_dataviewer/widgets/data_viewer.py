"""Multi-channel time-series plot: PyLinX-style black scope (QPixmap + QPainter, no pyqtgraph)."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import numpy as np
from PySide6.QtCore import QEvent, QMimeData, QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMdiSubWindow,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from synarius_dataviewer.app import theme
from synarius_dataviewer.widgets.channel_sidebar import MIME_CHANNEL
from synarius_dataviewer.widgets.pixmap_scope import PixmapScopeWidget


def _find_mdi_subwindow(widget: QWidget) -> QMdiSubWindow | None:
    w: QWidget | None = widget
    while w is not None:
        if isinstance(w, QMdiSubWindow):
            return w
        w = w.parentWidget()
    return None


_COLOR_CYCLE = [
    "#00ff99",
    "#00c8ff",
    "#ffaa00",
    "#ff6699",
    "#cc77ff",
    "#eeff44",
    "#66ffcc",
    "#ff8844",
]


class DataViewerWidget(QWidget):
    """Plot widget with toolbar (Adjust, optional walking X window, side legend table, clear).

    Scope rendering uses :class:`PixmapScopeWidget` (single pixmap repaint per frame). Slider drags
    update the legend immediately via :signal:`PixmapScopeWidget.slider_positions_changed`.

    Real-time: call :meth:`set_channel_data` or :meth:`append_samples` from any thread only via Qt
    signals — for in-process Studio integration, call from the GUI thread or use
    ``QMetaObject.invokeMethod`` / a queued signal.
    """

    channel_drop_requested = Signal(str)
    _color_index: int

    def __init__(
        self,
        resolve_series: Callable[[str], tuple[np.ndarray, np.ndarray]],
        parent: QWidget | None = None,
        *,
        enable_walking_axis: bool = False,
        resolve_channel_unit: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._resolve_series = resolve_series
        self._resolve_channel_unit = resolve_channel_unit
        self._color_index = 0
        self._channel_pens: dict[str, QPen] = {}
        self._walk_span = 10.0
        self._legend_visible = True
        self._channel_legend_row: dict[str, int] = {}
        self._legend_split_saved = 380

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        plot_column = QWidget()
        plot_column_lay = QVBoxLayout(plot_column)
        plot_column_lay.setContentsMargins(0, 0, 0, 0)
        plot_column_lay.setSpacing(0)

        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setStyleSheet(theme.studio_toolbar_stylesheet())

        act_adjust = self._toolbar.addAction("Adjust")
        act_adjust.setToolTip("Autoscale X/Y (PyLinX-style Ctrl+A)")
        act_adjust.triggered.connect(self._on_adjust)

        self._walk_action = None
        if enable_walking_axis:
            self._walk_action = self._toolbar.addAction("Walking axis")
            self._walk_action.setCheckable(True)
            self._walk_action.setToolTip("Keep a rolling time window on the X axis")
            self._walk_action.toggled.connect(self._on_walk_toggled)

        self._legend_action = self._toolbar.addAction("Legend")
        self._legend_action.setCheckable(True)
        self._legend_action.setChecked(True)
        self._legend_action.setToolTip("Show or hide the signal list (adjusts window width)")
        self._legend_action.toggled.connect(self._on_legend_panel_toggled)

        self._slider_action = self._toolbar.addAction("Slider")
        self._slider_action.setCheckable(True)
        self._slider_action.setToolTip("Show two vertical cursors (A/B); values appear in the legend columns")
        self._slider_action.toggled.connect(self._on_slider_toggled)

        act_clear = self._toolbar.addAction("Clear")
        act_clear.triggered.connect(self.clear_channels)

        plot_column_lay.addWidget(self._toolbar)

        self._scope = PixmapScopeWidget()
        self._scope.slider_positions_changed.connect(self._refresh_slider_legend_values)
        plot_column_lay.addWidget(self._scope, 1)

        self._legend_panel = QWidget()
        self._legend_panel.setObjectName("LegendPanel")
        self._legend_panel.setMinimumWidth(260)
        self._legend_panel.setStyleSheet(theme.data_viewer_legend_panel_stylesheet())
        legend_lay = QVBoxLayout(self._legend_panel)
        legend_lay.setContentsMargins(0, 0, 0, 0)
        legend_lay.setSpacing(0)
        self._legend_table = QTableWidget(0, 6)
        self._legend_table.setHorizontalHeaderLabels(
            ["Color", "Signal Name", "Unit", "Slider A", "Slider B", "Difference"]
        )
        self._legend_table.setAlternatingRowColors(True)
        self._legend_table.verticalHeader().setVisible(False)
        self._legend_table.setShowGrid(True)
        self._legend_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._legend_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = self._legend_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._legend_table.verticalHeader().setDefaultSectionSize(18)
        legend_lay.addWidget(self._legend_table)

        self._splitter.addWidget(plot_column)
        self._splitter.addWidget(self._legend_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([900, 400])

        layout.addWidget(self._splitter, 1)

        self.setAcceptDrops(True)
        self._scope.setAcceptDrops(True)
        self._scope.installEventFilter(self)

        self._empty_hint = QLabel(
            "Drag channel names here or use Plot selected in the sidebar.",
            self._scope,
        )
        self._empty_hint.setStyleSheet("color: #888; background: transparent;")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._position_hint()

    def _position_hint(self) -> None:
        if self._empty_hint.isVisible():
            r = self._scope.rect()
            self._empty_hint.setGeometry(r.adjusted(20, 60, -20, -20))

    def _next_pen(self) -> QPen:
        c = QColor(_COLOR_CYCLE[self._color_index % len(_COLOR_CYCLE)])
        self._color_index += 1
        p = QPen(c)
        p.setWidthF(1.5)
        p.setCosmetic(True)
        return p

    def _on_legend_panel_toggled(self, checked: bool) -> None:
        self._legend_visible = bool(checked)
        host = _find_mdi_subwindow(self)
        if host is not None:
            if checked:
                lw = max(200, self._legend_split_saved)
                self._legend_panel.setVisible(True)
                geo = host.geometry()
                host.setGeometry(geo.x(), geo.y(), geo.width() + lw, geo.height())
                tw = self._splitter.width()
                if tw <= 0:
                    tw = max(400, host.width())
                self._splitter.setSizes([max(120, tw - lw), lw])
            else:
                sizes = self._splitter.sizes()
                lw = sizes[1] if len(sizes) > 1 and sizes[1] > 0 else self._legend_split_saved
                self._legend_split_saved = max(200, lw)
                self._legend_panel.setVisible(False)
                geo = host.geometry()
                nw = max(host.minimumWidth(), geo.width() - self._legend_split_saved)
                host.setGeometry(geo.x(), geo.y(), nw, geo.height())
            return
        self._legend_panel.setVisible(self._legend_visible)

    def _on_slider_toggled(self, on: bool) -> None:
        self._scope.set_sliders_visible(on)
        if not on:
            self._clear_slider_legend_cells()
        else:
            self._refresh_slider_legend_values()

    def _slider_x_positions(self) -> tuple[float | None, float | None]:
        return self._scope.slider_data_x_positions()

    @staticmethod
    def _fmt_measure(v: float | None) -> str:
        if v is None or not np.isfinite(v):
            return "—"
        return f"{v:.6g}"

    def _interp_channel_at(self, name: str, xq: float) -> float | None:
        pair = self._scope.get_series(name)
        if pair is None:
            return None
        txa, tya = pair
        if len(txa) == 0:
            return None
        txa = np.asarray(txa, dtype=np.float64).ravel()
        tya = np.asarray(tya, dtype=np.float64).ravel()
        if txa.size != tya.size:
            return None
        if not np.all(np.diff(txa) >= 0):
            order = np.argsort(txa)
            txa = txa[order]
            tya = tya[order]
        if xq < txa[0] or xq > txa[-1]:
            return None
        return float(np.interp(xq, txa, tya))

    def _set_legend_slider_cells(self, row: int, ya: float | None, yb: float | None, diff: float | None) -> None:
        for col, val in zip((3, 4, 5), (ya, yb, diff), strict=True):
            it = self._legend_table.item(row, col)
            if it is None:
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._legend_table.setItem(row, col, it)
            it.setText(self._fmt_measure(val))

    def _clear_slider_legend_cells(self) -> None:
        for row in range(self._legend_table.rowCount()):
            self._set_legend_slider_cells(row, None, None, None)

    def _refresh_slider_legend_values(self) -> None:
        if not self._slider_action.isChecked():
            self._clear_slider_legend_cells()
            return
        xa, xb = self._slider_x_positions()
        if xa is None or xb is None:
            self._clear_slider_legend_cells()
            return
        for name, row in self._channel_legend_row.items():
            ya = self._interp_channel_at(name, xa)
            yb = self._interp_channel_at(name, xb)
            diff: float | None = None
            if ya is not None and yb is not None:
                diff = float(yb - ya)
            self._set_legend_slider_cells(row, ya, yb, diff)

    def _register_legend_row(self, name: str, pen: QPen) -> None:
        if name in self._channel_legend_row:
            return
        row = self._legend_table.rowCount()
        self._legend_table.insertRow(row)
        c = pen.color()
        sw = QTableWidgetItem()
        sw.setFlags(Qt.ItemFlag.ItemIsEnabled)
        sw.setBackground(QBrush(c))
        sw.setToolTip(c.name(QColor.NameFormat.HexRgb))
        self._legend_table.setItem(row, 0, sw)
        nm = QTableWidgetItem(name)
        nm.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._legend_table.setItem(row, 1, nm)
        unit_text = ""
        if self._resolve_channel_unit is not None:
            try:
                unit_text = self._resolve_channel_unit(name) or ""
            except Exception:
                unit_text = ""
        u_item = QTableWidgetItem(unit_text)
        u_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._legend_table.setItem(row, 2, u_item)
        for col in (3, 4, 5):
            s_item = QTableWidgetItem("—")
            s_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._legend_table.setItem(row, col, s_item)
        self._channel_legend_row[name] = row
        if self._slider_action.isChecked():
            self._refresh_slider_legend_values()

    def _remove_legend_row(self, name: str) -> None:
        row = self._channel_legend_row.pop(name, None)
        if row is None:
            return
        self._legend_table.removeRow(row)
        for key, r in list(self._channel_legend_row.items()):
            if r > row:
                self._channel_legend_row[key] = r - 1

    def _clear_legend_rows(self) -> None:
        self._legend_table.setRowCount(0)
        self._channel_legend_row.clear()

    def add_channel(self, name: str) -> None:
        if name in self._channel_pens:
            return
        tx, ty = self._resolve_series(name)
        if len(tx) == 0:
            return
        pen = self._next_pen()
        self._channel_pens[name] = pen
        self._scope.set_series(name, tx, ty, pen)
        self._register_legend_row(name, pen)
        self._empty_hint.hide()

    def remove_channel(self, name: str) -> None:
        if name not in self._channel_pens:
            return
        self._channel_pens.pop(name, None)
        self._scope.remove_series(name)
        self._remove_legend_row(name)
        if self._slider_action.isChecked():
            self._refresh_slider_legend_values()
        if not self._channel_pens:
            self._empty_hint.show()
            self._position_hint()

    def clear_channels(self) -> None:
        self._channel_pens.clear()
        self._scope.clear_series()
        self._color_index = 0
        self._clear_legend_rows()
        self._empty_hint.show()
        self._position_hint()
        if self._slider_action.isChecked():
            self._refresh_slider_legend_values()

    def set_channel_data(self, name: str, t: np.ndarray, y: np.ndarray) -> None:
        """Replace curve arrays (full redraw; preferred for simulation ticks)."""
        t = np.asarray(t, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if name not in self._channel_pens:
            pen = self._next_pen()
            self._channel_pens[name] = pen
            self._register_legend_row(name, pen)
            self._empty_hint.hide()
        pen = self._channel_pens[name]
        self._scope.set_series(name, t, y, pen)
        if self._slider_action.isChecked():
            self._refresh_slider_legend_values()

    def append_samples(
        self,
        name: str,
        t_new: np.ndarray,
        y_new: np.ndarray,
        max_points: int = 200_000,
    ) -> None:
        """Append samples in O(n) by rebuilding a bounded buffer (GUI thread)."""
        t_new = np.asarray(t_new, dtype=np.float64).ravel()
        y_new = np.asarray(y_new, dtype=np.float64).ravel()
        if len(t_new) == 0:
            return
        if name in self._channel_pens:
            pair = self._scope.get_series(name)
            pen = self._channel_pens[name]
            if pair is None or len(pair[0]) == 0:
                t_all, y_all = t_new, y_new
            else:
                tx, ty = pair
                t_all = np.concatenate([tx, t_new])
                y_all = np.concatenate([ty, y_new])
            if len(t_all) > max_points:
                cut = len(t_all) - max_points
                t_all = t_all[cut:]
                y_all = y_all[cut:]
            self._scope.set_series(name, t_all, y_all, pen)
            if self._slider_action.isChecked():
                self._refresh_slider_legend_values()
        else:
            self.set_channel_data(name, t_new, y_new)

    def _on_adjust(self) -> None:
        self._scope.auto_range()

    def _on_walk_toggled(self, on: bool) -> None:
        if self._walk_action is None:
            return
        self._scope.set_walking_axis(on, self._walk_span)

    def _mime_names(self, md: QMimeData) -> list[str]:
        names: list[str] = []
        if md.hasFormat(MIME_CHANNEL):
            raw = bytes(md.data(MIME_CHANNEL)).decode("utf-8")
            names = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if not names and raw.strip():
                names = [raw.strip()]
        elif md.hasText():
            names = [ln.strip() for ln in md.text().splitlines() if ln.strip()]
            if not names and md.text().strip():
                names = [md.text().strip()]
        return names

    def _can_accept_mime(self, md: QMimeData) -> bool:
        return md.hasFormat(MIME_CHANNEL) or md.hasText()

    def _apply_drop(self, md: QMimeData) -> None:
        for n in self._mime_names(md):
            try:
                self.add_channel(n)
            except KeyError:
                self.channel_drop_requested.emit(n)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self._scope:
            return super().eventFilter(watched, event)
        et = event.type()
        if et == QEvent.Type.DragEnter:
            ev = cast(QDragEnterEvent, event)
            if self._can_accept_mime(ev.mimeData()):
                ev.acceptProposedAction()
            else:
                ev.ignore()
            return True
        if et == QEvent.Type.DragMove:
            ev = cast(QDragMoveEvent, event)
            if self._can_accept_mime(ev.mimeData()):
                ev.acceptProposedAction()
            else:
                ev.ignore()
            return True
        if et == QEvent.Type.Drop:
            ev = cast(QDropEvent, event)
            self._apply_drop(ev.mimeData())
            ev.acceptProposedAction()
            return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._can_accept_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._can_accept_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        self._apply_drop(event.mimeData())
        event.acceptProposedAction()


class DataViewerShell(QWidget):
    """Toolbar + :class:`DataViewerWidget` for embedding in an ``QMdiSubWindow``."""

    def __init__(
        self,
        resolve_series: Callable[[str], tuple[np.ndarray, np.ndarray]],
        parent: QWidget | None = None,
        *,
        enable_walking_axis: bool = False,
        resolve_channel_unit: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._viewer = DataViewerWidget(
            resolve_series,
            self,
            enable_walking_axis=enable_walking_axis,
            resolve_channel_unit=resolve_channel_unit,
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._viewer)

    @property
    def viewer(self) -> DataViewerWidget:
        return self._viewer
