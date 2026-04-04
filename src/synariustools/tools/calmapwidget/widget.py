"""Split-view widget: HoloViews (matplotlib backend) plot + matrix table (axes + heatmap cells)."""

from __future__ import annotations

import types
from pathlib import Path
from typing import cast

import matplotlib

matplotlib.use("qtagg")

import holoviews as hv
import numpy as np
from holoviews import opts
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QAction, QColor, QShowEvent, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from synariustools.tools.calmapwidget.data import CalibrationMapData
from synariustools.tools.plotwidget.plot_theme import STUDIO_TOOLBAR_FOREGROUND, studio_toolbar_stylesheet
from synariustools.tools.plotwidget.svg_icons import icon_from_tinted_svg_file

hv.extension("matplotlib")

_ICONS_DIR = Path(__file__).resolve().parent.parent / "plotwidget" / "icons" / "toolbar"

_TABLE_MATRIX_COL_W = 52
_TABLE_MATRIX_ROW_H = 22
_TABLE_FRAME_PAD = 8
_TABLE_VIEWPORT_MAX_CELLS = 12
_SCALAR_TABLE_MAX_W = 420

_HV_2D_CURVE_FIG_INCHES = (8.0, 4.5)
_HV_2D_MAP_FIG_INCHES = (8.0, 5.0)
_HV_3D_FIG_INCHES = (8.0, 6.5)
_3D_SCROLL_ZOOM_STEP = 1.12
_3D_DIST_MIN = 2.8
_3D_DIST_MAX = 48.0
_PLOT_VIEWPORT_MAX_H = 360

# Marken für diskrete Stützstellen (gut sichtbar auf Kurve / Fläche / Heatmap)
_SUPPORT_MARKER_COLOR = "orangered"
_SUPPORT_MARKER_EDGE = "white"
_SUPPORT_SCATTER_OPTS = opts.Scatter(
    s=42, color=_SUPPORT_MARKER_COLOR, edgecolor=_SUPPORT_MARKER_EDGE, linewidth=1.2
)
_SUPPORT_POINTS_OPTS = opts.Points(
    s=52, color=_SUPPORT_MARKER_COLOR, edgecolor=_SUPPORT_MARKER_EDGE, linewidth=1.2
)
_SUPPORT_SCATTER3D_OPTS = opts.Scatter3D(
    s=38, color=_SUPPORT_MARKER_COLOR, edgecolor=_SUPPORT_MARKER_EDGE, linewidth=1.0
)


def _extent_1d(ax_arr: np.ndarray, n: int) -> tuple[float, float]:
    a = np.asarray(ax_arr, dtype=np.float64).reshape(-1)
    if a.size >= 2:
        return float(a[0]), float(a[-1])
    if a.size == 1:
        return float(a[0]) - 0.5, float(a[0]) + 0.5
    return -0.5, float(max(1, n)) - 0.5


def _heatmap_qcolor(value: float, vmin: float, vmax: float, cmap) -> tuple[QColor, QColor]:
    """Return (background, foreground) for a numeric cell."""
    if not np.isfinite(value) or not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        bg = QColor(240, 240, 240)
        return bg, QColor(30, 30, 30)
    t = (float(value) - float(vmin)) / (float(vmax) - float(vmin))
    t = max(0.0, min(1.0, t))
    rgba = cmap(t)
    r, g, b = int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
    bg = QColor(r, g, b)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    fg = QColor(255, 255, 255) if lum < 140 else QColor(20, 20, 20)
    return bg, fg


def _enable_3d_mouse_rotation(fig: Figure) -> None:
    for ax in fig.axes:
        if isinstance(ax, Axes3D):
            ax.mouse_init(rotate_btn=1, pan_btn=2, zoom_btn=3)


def _patch_axes3d_preserve_dist(ax: Axes3D) -> None:
    """Axes3D.view_init setzt _dist fest auf 10; die Rotation ruft view_init pro Bewegung auf."""
    if getattr(ax, "_synarius_dist_preserve", False):
        return

    def view_init_preserve(
        self: Axes3D,
        elev=None,
        azim=None,
        roll=None,
        vertical_axis: str = "z",
        share: bool = False,
    ) -> None:
        saved = self._dist
        Axes3D.view_init(self, elev=elev, azim=azim, roll=roll, vertical_axis=vertical_axis, share=share)
        self._dist = max(_3D_DIST_MIN, min(_3D_DIST_MAX, float(saved)))

    ax.view_init = types.MethodType(view_init_preserve, ax)
    ax._synarius_dist_preserve = True


def _relax_3d_plot_clipping(fig: Figure) -> None:
    """Ohne das clippt Matplotlib 3D an der Achsen-Bounding-Box — starkes Reinzoomen schneidet die Fläche ab."""
    for ax in fig.axes:
        if not isinstance(ax, Axes3D):
            continue
        try:
            ax.patch.set_clip_on(False)
        except Exception:
            pass
        for ch in ax.get_children():
            try:
                if hasattr(ch, "set_clip_on"):
                    ch.set_clip_on(False)
            except Exception:
                pass


class CalibrationMapWidget(QWidget):
    """Toolbar, darunter Tabelle; Plot optional (initial ausgeblendet). Feste Außenmaße = Summe sichtbarer Teile."""

    def __init__(self, data: CalibrationMapData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        try:
            self._cmap = matplotlib.colormaps["viridis"]
        except Exception:
            from matplotlib import cm

            self._cmap = cm.get_cmap("viridis")
        self._table_visible = True
        self._plot_visible = False
        self._plot_rendered = False
        # Kennfeld (2D): Standard = 3D-Oberfläche; optional 2D-Heatmap. Kennlinie (1D) = 2D-Funktionsgraph.
        self._use_heatmap = False
        self._3d_interaction_active = False
        self._hv_plot: object | None = None
        self._graph_plot_active = True
        self._last_plot_block = QSize(0, 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)

        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setStyleSheet(studio_toolbar_stylesheet())
        icon_fg = QColor(STUDIO_TOOLBAR_FOREGROUND)

        self._act_plot = QAction("Plot", self)
        self._act_plot.setIcon(icon_from_tinted_svg_file(_ICONS_DIR / "labplot-xy-plot-four-axes.svg", icon_fg))
        self._act_plot.setCheckable(True)
        self._act_plot.setChecked(False)
        self._act_plot.setToolTip("Show or hide the plot area")
        self._act_plot.toggled.connect(self._on_plot_toggled)

        self._act_table = QAction("Table", self)
        self._act_table.setIcon(icon_from_tinted_svg_file(_ICONS_DIR / "legend.svg", icon_fg))
        self._act_table.setCheckable(True)
        self._act_table.setChecked(True)
        self._act_table.setToolTip("Show or hide the data table")
        self._act_table.toggled.connect(self._on_table_toggled)

        self._act_heatmap = QAction("Heatmap", self)
        self._act_heatmap.setIcon(icon_from_tinted_svg_file(_ICONS_DIR / "slider.svg", icon_fg))
        self._act_heatmap.setCheckable(True)
        self._act_heatmap.setChecked(self._use_heatmap)
        self._act_heatmap.setToolTip(
            "Kennfeld: aus = 3D-Oberfläche; ein = 2D-Heatmap (Farbtafel)"
        )
        self._act_heatmap.setEnabled(data.values.ndim == 2)
        self._act_heatmap.toggled.connect(self._on_heatmap_toggled)

        self._toolbar.addAction(self._act_plot)
        self._toolbar.addAction(self._act_table)
        self._toolbar.addAction(self._act_heatmap)
        root.addWidget(self._toolbar)

        self._table = QTableWidget(self)
        self._table.setAlternatingRowColors(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(True)

        self._plot_column = QWidget()
        plot_lay = QVBoxLayout(self._plot_column)
        plot_lay.setContentsMargins(0, 0, 0, 0)
        plot_lay.setSpacing(0)

        self._figure = Figure(figsize=(6.5, 5.5), layout="tight")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._canvas.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self._plot_scroll = QScrollArea(self._plot_column)
        self._plot_scroll.setWidget(self._canvas)
        self._plot_scroll.setWidgetResizable(False)
        self._plot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._plot_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._plot_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._plot_scroll.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._plot_scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._plot_scroll.installEventFilter(self)
        self._plot_scroll.viewport().installEventFilter(self)
        self._canvas.installEventFilter(self)

        self._nav = NavigationToolbar2QT(self._canvas, self._plot_column)
        plot_lay.addWidget(self._plot_scroll)
        plot_lay.addWidget(self._nav)
        self._nav.hide()

        self._hint = QLabel("", self._plot_column)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("color: #666; padding: 24px;")
        plot_lay.addWidget(self._hint)

        root.addWidget(self._table)
        root.addWidget(self._plot_column)

        self._hint.hide()
        self._plot_column.hide()

        self._build_table()
        vals = np.asarray(self._data.values, dtype=np.float64)
        if vals.ndim == 0 or not self._graph_plot_active:
            self._draw_plot()
            self._plot_rendered = vals.ndim != 0 and self._graph_plot_active
        self._apply_outer_geometry()

    def _plot_wheel_targets(self) -> tuple[QObject, ...]:
        return (self._plot_scroll, self._plot_scroll.viewport(), self._canvas)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Wheel trifft Viewport/Canvas, selten die QScrollArea — alle Ziele abdecken."""
        if watched in self._plot_wheel_targets() and event.type() == QEvent.Type.Wheel:
            wheel = cast(QWheelEvent, event)
            dy = wheel.angleDelta().y()
            if dy == 0:
                return False
            if wheel.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                hbar = self._plot_scroll.horizontalScrollBar()
                hbar.setValue(hbar.value() - dy // 12)
                return True
            if self._3d_interaction_active:
                self._qt_apply_3d_wheel_zoom(dy)
                return True
            return False
        return super().eventFilter(watched, event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Beim ersten Show sitzt der Viewer erst im QDialog; vorher war die Shell ggf. unter dem MainWindow.
        # Zudem liefert die Toolbar ihre finale Höhe oft erst nach Polish/Layout — wie nach Plot-Toggle, wo
        # _maybe_adjust_host_dialog ohnehin läuft und den Dialog per adjustSize() an den Inhalt anpasst.
        if getattr(self, "_calmap_did_sync_host_on_show", False):
            return
        self._calmap_did_sync_host_on_show = True
        self._apply_outer_geometry()
        self._maybe_adjust_host_dialog()

    def sizeHint(self) -> QSize:
        return self._compute_outer_size_from_children()

    def minimumSizeHint(self) -> QSize:
        return self._compute_outer_size_from_children()

    def _table_matrix_viewport_px(self) -> tuple[int, int]:
        """Sichtbare Zellen max. 12×12; größere Tabellen intern scrollbar. -> (width_px, height_px)."""
        vals = np.asarray(self._data.values, dtype=np.float64)
        cap = _TABLE_VIEWPORT_MAX_CELLS
        if vals.ndim == 2:
            nx, ny = int(vals.shape[0]), int(vals.shape[1])
            nrows, ncols = nx + 1, ny + 1
            vr = min(nrows, cap)
            vc = min(ncols, cap)
            return vc * _TABLE_MATRIX_COL_W + _TABLE_FRAME_PAD, vr * _TABLE_MATRIX_ROW_H + _TABLE_FRAME_PAD
        if vals.ndim == 1:
            n = int(vals.shape[0])
            vc = min(n + 1, cap)
            vr = 2
            return vc * _TABLE_MATRIX_COL_W + _TABLE_FRAME_PAD, vr * _TABLE_MATRIX_ROW_H + _TABLE_FRAME_PAD
        return 280, _TABLE_MATRIX_ROW_H * 2 + _TABLE_FRAME_PAD

    def _matrix_table_target_wh(self) -> tuple[int, int] | None:
        """Pixel size matching :meth:`_apply_table_viewport_fixed_size` (for geometry before first layout)."""
        vals = np.asarray(self._data.values, dtype=np.float64)
        if vals.ndim not in (1, 2):
            return None
        cap = _TABLE_VIEWPORT_MAX_CELLS
        nrows = self._table.rowCount()
        ncols = self._table.columnCount()
        cw_sum = sum(self._table.columnWidth(i) for i in range(ncols))
        rh_sum = sum(self._table.rowHeight(i) for i in range(nrows))
        # Before the first layout/polish, Qt often reports 0 widths/heights → clipped rows / wrong dialog size.
        if cw_sum < ncols * _TABLE_MATRIX_COL_W // 2:
            cw_sum = ncols * _TABLE_MATRIX_COL_W
        if rh_sum < nrows * _TABLE_MATRIX_ROW_H // 2:
            rh_sum = nrows * _TABLE_MATRIX_ROW_H
        vh = self._table.verticalHeader().width() if self._table.verticalHeader().isVisible() else 0
        hh = self._table.horizontalHeader().height() if self._table.horizontalHeader().isVisible() else 0
        intrinsic_w = cw_sum + vh + _TABLE_FRAME_PAD
        intrinsic_h = rh_sum + hh + _TABLE_FRAME_PAD
        tw_cap, th_cap = self._table_matrix_viewport_px()
        if nrows <= cap and ncols <= cap:
            return intrinsic_w, intrinsic_h
        return tw_cap, th_cap

    def _apply_table_viewport_fixed_size(self) -> None:
        vals = np.asarray(self._data.values, dtype=np.float64)
        if vals.ndim in (1, 2):
            m = self._matrix_table_target_wh()
            if m is None:
                return
            tw, th = m
            self._table.setFixedSize(tw, th)
            self._table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        elif vals.ndim == 0:
            self._table.setMinimumHeight(_TABLE_MATRIX_ROW_H + 8)
            self._table.setMaximumHeight(_TABLE_MATRIX_ROW_H * 3)
            self._table.setMinimumWidth(200)
            self._table.setMaximumWidth(_SCALAR_TABLE_MAX_W)
            self._table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        else:
            self._table.setFixedHeight(_TABLE_MATRIX_ROW_H * 2 + _TABLE_FRAME_PAD)
            self._table.setMinimumWidth(200)
            self._table.setMaximumWidth(_SCALAR_TABLE_MAX_W)
            self._table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _sync_plot_scroll_outer_size(self) -> None:
        if not self._graph_plot_active:
            return
        fig = self._canvas.figure
        if fig is None:
            return
        w_in, h_in = fig.get_size_inches()
        dpi = float(fig.dpi)
        nat_ch = int(max(220, np.ceil(h_in * dpi)))
        view_h = min(nat_ch, _PLOT_VIEWPORT_MAX_H)
        table_w = max(1, self._table.width())
        cw = max(200, table_w)
        win_new = cw / dpi
        hin_new = view_h / dpi
        try:
            fig.set_size_inches(win_new, hin_new, forward=True)
        except TypeError:
            fig.set_size_inches(win_new, hin_new)
        self._canvas.setMinimumSize(cw, view_h)
        self._canvas.resize(cw, view_h)
        self._plot_scroll.setFixedSize(table_w, view_h)
        self._plot_column.setFixedSize(table_w, view_h)
        self._last_plot_block = QSize(table_w, view_h)
        self._canvas.draw()
        if fig.axes and any(isinstance(a, Axes3D) for a in fig.axes):
            _relax_3d_plot_clipping(fig)
            self._canvas.draw()
        self._plot_scroll.verticalScrollBar().setValue(0)
        self._plot_scroll.horizontalScrollBar().setValue(0)

    def _apply_outer_geometry(self) -> None:
        """Höhe/Breite = exakt Toolbar + sichtbare Kinder; Breite nicht breiter als breitestes Kind."""
        self._apply_table_viewport_fixed_size()
        if self._plot_visible and self._graph_plot_active and self._plot_rendered:
            self._sync_plot_scroll_outer_size()
        mw = 0
        if self._table_visible:
            mw = max(mw, self._table.width())
        if self._plot_visible and self._graph_plot_active and self._plot_rendered and self._last_plot_block.width() > 0:
            mw = max(mw, self._last_plot_block.width())
        if mw > 0:
            self._toolbar.setMinimumWidth(max(self._toolbar.sizeHint().width(), mw))
        else:
            self._toolbar.setMinimumWidth(0)
        root_ly = self.layout()
        if root_ly is not None:
            root_ly.activate()
        sz = self._compute_outer_size_from_children()
        self.setFixedSize(sz)
        self.updateGeometry()

    def _maybe_adjust_host_dialog(self) -> None:
        shell = self.parentWidget()
        if shell is not None:
            shell.setFixedSize(self.size())
            sly = shell.layout()
            if sly is not None:
                sly.activate()
            shell.updateGeometry()
        win = self.window()
        if isinstance(win, QDialog):
            dly = win.layout()
            if dly is not None:
                dly.activate()
            win.adjustSize()

    def _compute_outer_size_from_children(self) -> QSize:
        # Toolbar: sizeHint until first layout (height() often 0 on first pass).
        tb = self._toolbar
        w = max(tb.sizeHint().width(), tb.width() if tb.width() > 0 else 0)
        h = tb.height() if tb.height() > 0 else tb.sizeHint().height()
        if self._table_visible:
            # Matrix tables: never use QTableWidget.sizeHint() for height — before the event loop
            # height()/width() can be 0; sizeHint() is ~192px tall and leaves a black gap until replot.
            m = self._matrix_table_target_wh()
            if m is not None:
                tw, th = m
            else:
                tw = self._table.width() if self._table.width() > 0 else self._table.sizeHint().width()
                th = self._table.height() if self._table.height() > 0 else self._table.sizeHint().height()
            w = max(w, tw)
            h += th
        if self._plot_visible:
            if self._graph_plot_active and self._plot_rendered and self._last_plot_block.height() > 0:
                w = max(w, self._last_plot_block.width())
                h += self._last_plot_block.height()
            elif self._graph_plot_active and self._plot_rendered:
                pc_w = self._plot_column.width() if self._plot_column.width() > 0 else self._plot_column.sizeHint().width()
                pc_h = self._plot_column.height() if self._plot_column.height() > 0 else self._plot_column.sizeHint().height()
                w = max(w, pc_w)
                h += pc_h
            else:
                w = max(w, 220)
                h += 48
        return QSize(max(1, w), max(1, h))

    def _qt_apply_3d_wheel_zoom(self, dy: int) -> None:
        fig = self._canvas.figure
        if fig is None:
            return
        step = 1 if dy > 0 else -1
        for ax in fig.axes:
            if not isinstance(ax, Axes3D):
                continue
            if step > 0:
                ax._dist /= _3D_SCROLL_ZOOM_STEP
            else:
                ax._dist *= _3D_SCROLL_ZOOM_STEP
            ax._dist = max(_3D_DIST_MIN, min(_3D_DIST_MAX, ax._dist))
            ax.stale = True
        _relax_3d_plot_clipping(fig)
        self._canvas.draw()

    def _cleanup_hv_plot(self) -> None:
        self._3d_interaction_active = False
        if self._hv_plot is None:
            return
        try:
            cleanup = getattr(self._hv_plot, "cleanup", None)
            if callable(cleanup):
                cleanup()
        except Exception:
            pass
        self._hv_plot = None

    def _vmin_vmax(self) -> tuple[float, float]:
        v = np.asarray(self._data.values, dtype=np.float64).ravel()
        v = v[np.isfinite(v)]
        if v.size == 0:
            return 0.0, 1.0
        return float(np.min(v)), float(np.max(v))

    def _build_table(self) -> None:
        d = self._data
        vals = np.asarray(d.values, dtype=np.float64)
        vmin, vmax = self._vmin_vmax()

        self._table.horizontalHeader().setVisible(True)
        self._table.verticalHeader().setVisible(True)

        if vals.ndim == 0:
            self._table.setColumnCount(2)
            self._table.setRowCount(1)
            self._table.setHorizontalHeaderLabels(["Field", "Value"])
            self._set_heatmap_item(0, 0, QTableWidgetItem(d.title), None, None)
            v0 = float(vals.item())
            itv = QTableWidgetItem(f"{v0:g}")
            self._set_heatmap_item(0, 1, itv, v0, (vmin, vmax))
            self._hint.setText("Scalar — no plot")
            self._graph_plot_active = False
            self._act_plot.setEnabled(False)
            self._act_heatmap.setEnabled(False)
            self._canvas.hide()
            self._plot_scroll.hide()
            self._nav.hide()
            self._hint.show()
            self._apply_labeled_table_sizing()
            self._apply_outer_geometry()
            return

        if vals.ndim == 1:
            n = int(vals.shape[0])
            ax_x = d.axis_values(0)
            self._table.horizontalHeader().setVisible(False)
            self._table.verticalHeader().setVisible(False)
            self._table.setRowCount(2)
            self._table.setColumnCount(n + 1)
            self._table.setItem(0, 0, QTableWidgetItem(""))
            for j in range(n):
                xj = float(ax_x[j]) if j < len(ax_x) else float(j)
                self._table.setItem(0, j + 1, QTableWidgetItem(f"{xj:g}"))
            self._table.setItem(1, 0, QTableWidgetItem(""))
            for j in range(n):
                vj = float(vals[j])
                it = QTableWidgetItem(f"{vj:g}")
                self._set_heatmap_item(1, j + 1, it, vj, (vmin, vmax))
            self._graph_plot_active = True
            self._apply_matrix_table_sizing()
            self._apply_outer_geometry()
            return

        if vals.ndim == 2:
            nx, ny = int(vals.shape[0]), int(vals.shape[1])
            ax_y = d.axis_values(0)
            ax_x = d.axis_values(1)
            self._table.horizontalHeader().setVisible(False)
            self._table.verticalHeader().setVisible(False)
            self._table.setRowCount(nx + 1)
            self._table.setColumnCount(ny + 1)
            self._table.setItem(0, 0, QTableWidgetItem(""))
            for j in range(ny):
                xj = float(ax_x[j]) if j < len(ax_x) else float(j)
                self._table.setItem(0, j + 1, QTableWidgetItem(f"{xj:g}"))
            for i in range(nx):
                yi = float(ax_y[i]) if i < len(ax_y) else float(i)
                self._table.setItem(i + 1, 0, QTableWidgetItem(f"{yi:g}"))
                for j in range(ny):
                    vij = float(vals[i, j])
                    it = QTableWidgetItem(f"{vij:g}")
                    self._set_heatmap_item(i + 1, j + 1, it, vij, (vmin, vmax))
            self._graph_plot_active = True
            self._apply_matrix_table_sizing()
            self._apply_outer_geometry()
            return

        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Info", "Value"])
        self._table.setRowCount(1)
        self._table.setItem(0, 0, QTableWidgetItem("Shape"))
        self._table.setItem(0, 1, QTableWidgetItem(str(vals.shape)))
        self._hint.setText(f"Unsupported rank ({vals.ndim}D) for this viewer")
        self._graph_plot_active = False
        self._hint.show()
        self._canvas.hide()
        self._plot_scroll.hide()
        self._nav.hide()
        self._apply_labeled_table_sizing()
        self._apply_outer_geometry()

    def _apply_matrix_table_sizing(self) -> None:
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setWordWrap(False)
        vh = self._table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for r in range(self._table.rowCount()):
            self._table.setRowHeight(r, _TABLE_MATRIX_ROW_H)
        for c in range(self._table.columnCount()):
            self._table.setColumnWidth(c, _TABLE_MATRIX_COL_W)
        for r in range(self._table.rowCount()):
            for c in range(self._table.columnCount()):
                it = self._table.item(r, c)
                if it is not None:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _apply_labeled_table_sizing(self) -> None:
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        vh = self._table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(_TABLE_MATRIX_ROW_H)
        self._table.resizeRowsToContents()

    def _set_heatmap_item(
        self,
        r: int,
        c: int,
        item: QTableWidgetItem,
        value: float | None,
        mm: tuple[float, float] | None,
    ) -> None:
        if value is None or mm is None:
            self._table.setItem(r, c, item)
            return
        bg, fg = _heatmap_qcolor(value, mm[0], mm[1], self._cmap)
        item.setBackground(bg)
        item.setForeground(fg)
        self._table.setItem(r, c, item)

    def _build_holoviews_element(self):
        d = self._data
        vals = np.asarray(d.values, dtype=np.float64)
        title = f"{d.title} ({d.category})"

        if vals.ndim == 1:
            xs = d.axis_values(0)
            if len(xs) != len(vals):
                xs = np.arange(len(vals), dtype=np.float64)
            curve = hv.Curve((xs, vals), ["x"], ["Value"]).opts(
                opts.Curve(
                    title=title,
                    color="steelblue",
                    linewidth=2,
                    xlabel="x",
                    ylabel="Value",
                    show_grid=True,
                    fig_inches=_HV_2D_CURVE_FIG_INCHES,
                )
            )
            m = np.isfinite(xs) & np.isfinite(vals)
            if not m.any():
                return curve
            support = hv.Scatter((xs[m], vals[m]), ["x"], ["Value"]).opts(_SUPPORT_SCATTER_OPTS)
            return curve * support

        if vals.ndim == 2:
            n0, n1 = int(vals.shape[0]), int(vals.shape[1])
            a0 = d.axis_values(0)
            a1 = d.axis_values(1)
            if len(a0) != n0:
                a0 = np.arange(n0, dtype=np.float64)
            if len(a1) != n1:
                a1 = np.arange(n1, dtype=np.float64)
            e1_lo, e1_hi = _extent_1d(a1, n1)
            e0_lo, e0_hi = _extent_1d(a0, n0)

            L, K = np.meshgrid(np.arange(n0, dtype=np.intp), np.arange(n1, dtype=np.intp), indexing="ij")
            px = a1[K].ravel()
            py = a0[L].ravel()
            z_flat = vals[L, K].ravel()
            fin = np.isfinite(px) & np.isfinite(py) & np.isfinite(z_flat)

            if self._use_heatmap:
                img = hv.Image(vals, bounds=(e1_lo, e0_lo, e1_hi, e0_hi), kdims=["x", "y"]).opts(
                    opts.Image(
                        title=title,
                        cmap="viridis",
                        colorbar=True,
                        xlabel="Sweep (axis 1)",
                        ylabel="Sweep (axis 0)",
                        fig_inches=_HV_2D_MAP_FIG_INCHES,
                    )
                )
                if not fin.any():
                    return img
                pts = hv.Points((px[fin], py[fin]), kdims=["x", "y"]).opts(_SUPPORT_POINTS_OPTS)
                return img * pts

            surf = hv.Surface((a0, a1, vals.T), kdims=["x1", "x2"], vdims=["Value"])
            surf = surf.opts(
                opts.Surface(
                    title=title,
                    cmap="viridis",
                    colorbar=True,
                    projection="3d",
                    fig_inches=_HV_3D_FIG_INCHES,
                    # kdim x1 ist erstes Array (a0 = Achse 0), x2 zweites (a1 = Achse 1)
                    xlabel="Sweep (axis 0)",
                    ylabel="Sweep (axis 1)",
                    zlabel="Value",
                    azimuth=40,
                    elevation=30,
                )
            )
            if not fin.any():
                return surf
            # Surface-Tupel (a0, a1, Z) bindet kdims[0]=x1 an a0, kdims[1]=x2 an a1 (ImageInterface).
            # Scatter3D muss dieselbe Zuordnung nutzen — nicht (a1,a0) wie bei der 2D-Heatmap (x=Achse1, y=Achse0).
            x1_s = a0[L].ravel()
            x2_s = a1[K].ravel()
            support = hv.Scatter3D(
                (x1_s[fin], x2_s[fin], z_flat[fin]), kdims=["x1", "x2", "Value"]
            ).opts(_SUPPORT_SCATTER3D_OPTS)
            return surf * support

        return None

    def _draw_plot(self) -> None:
        d = self._data
        vals = np.asarray(d.values, dtype=np.float64)

        if vals.ndim == 0:
            self._canvas.draw_idle()
            return

        self._plot_rendered = False
        self._cleanup_hv_plot()
        element = self._build_holoviews_element()
        if element is None:
            self._plot_scroll.hide()
            self._canvas.draw_idle()
            return

        renderer = hv.renderer("matplotlib")
        self._hv_plot = renderer.get_plot(element)
        self._hv_plot.initialize_plot()
        fig = self._hv_plot.state
        fig.set_canvas(self._canvas)
        self._canvas.figure = fig

        self._3d_interaction_active = False
        if vals.ndim == 2 and not self._use_heatmap:
            self._3d_interaction_active = True
            _enable_3d_mouse_rotation(fig)
            for ax in fig.axes:
                if isinstance(ax, Axes3D):
                    _patch_axes3d_preserve_dist(ax)
                if hasattr(ax, "set_navigate_mode"):
                    ax.set_navigate_mode(None)
            self._canvas.draw()
            _relax_3d_plot_clipping(fig)
            self._canvas.draw()
        else:
            self._canvas.draw_idle()
        if self._plot_visible:
            self._plot_scroll.show()
            self._sync_plot_scroll_outer_size()
        else:
            self._plot_scroll.hide()
        self._plot_rendered = True
        self._apply_outer_geometry()
        self._maybe_adjust_host_dialog()

    def _on_plot_toggled(self, checked: bool) -> None:
        if not checked and not self._act_table.isChecked():
            self._act_plot.blockSignals(True)
            self._act_plot.setChecked(True)
            self._act_plot.blockSignals(False)
            return
        self._plot_visible = bool(checked)
        self._plot_column.setVisible(self._plot_visible)
        if self._plot_visible and self._graph_plot_active and (
            not self._plot_rendered or self._canvas.figure is None
        ):
            self._draw_plot()
        elif self._plot_visible and self._graph_plot_active:
            self._plot_scroll.show()
            self._sync_plot_scroll_outer_size()
        if not self._plot_visible:
            self._plot_scroll.hide()
        self._apply_outer_geometry()
        self._maybe_adjust_host_dialog()

    def _on_table_toggled(self, checked: bool) -> None:
        if not checked and not self._act_plot.isChecked():
            self._act_table.blockSignals(True)
            self._act_table.setChecked(True)
            self._act_table.blockSignals(False)
            return
        self._table_visible = bool(checked)
        self._table.setVisible(self._table_visible)
        self._apply_outer_geometry()
        self._maybe_adjust_host_dialog()

    def _on_heatmap_toggled(self, checked: bool) -> None:
        self._use_heatmap = bool(checked)
        self._draw_plot()
        if self._plot_visible:
            self._apply_outer_geometry()
        self._maybe_adjust_host_dialog()


class CalibrationMapShell(QWidget):
    """Thin host embedding :class:`CalibrationMapWidget` (same pattern as :class:`DataViewerShell`)."""

    def __init__(self, data: CalibrationMapData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._viewer = CalibrationMapWidget(data, self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)
        lay.addWidget(self._viewer)
        pref = self.sizeHint()
        if pref.width() >= 1 and pref.height() >= 1:
            self.setFixedSize(pref)

    def sizeHint(self) -> QSize:
        # Do not use _viewer.size(): before show/layout it can be the default (e.g. 640×480), so the
        # ParaWiz dialog gets the wrong height and the table clips until a later geometry refresh.
        return self._viewer.sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self._viewer.minimumSizeHint()

    @property
    def viewer(self) -> CalibrationMapWidget:
        return self._viewer
