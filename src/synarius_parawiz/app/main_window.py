"""Main window for Synarius ParaWiz."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout
from synarius_core.controller import MinimalController
from synarius_core.model.data_model import ComplexInstance
from synarius_core.parameters.repository import ParameterRecord

from synarius_dataviewer.app import theme
from synarius_parawiz._version import __version__
from synarius_parawiz.app.console_window import ConsoleWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Synarius Apps - ParaWiz {__version__}")
        self.resize(1100, 720)
        icon_path = Path(__file__).resolve().parents[2] / "synarius_dataviewer" / "app" / "icons" / "synarius64.png"
        try:
            import synarius_dataviewer as sdv

            p_pkg = Path(sdv.__file__).resolve().parent / "app" / "icons" / "synarius64.png"
            if p_pkg.is_file():
                icon_path = p_pkg
        except Exception:
            pass
        self.setWindowIcon(QIcon(str(icon_path)))

        self._controller = MinimalController()
        self._console_window: ConsoleWindow | None = None

        self._table = QTableWidget(self)
        self._table.setObjectName("ParameterTable")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Value / Shape"])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._table.setColumnWidth(0, 340)
        self._table.setColumnWidth(1, 120)
        self.setCentralWidget(self._table)
        self._table.setStyleSheet(self._table_stylesheet())
        self._table.cellDoubleClicked.connect(self._on_parameter_table_double_clicked)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self.statusBar().showMessage("Ready")
        self._refresh_table()
        self.statusBar().showMessage(
            'Doppelklick auf die Spalte „Value / Shape“ öffnet Plot und Tabelle (Kennlinie / Kennfeld / Vektor).',
            10000,
        )
        # Preload HoloViews + calmapwidget after the first event-loop tick so startup stays responsive
        # but the first double-click on a parameter is not blocked by a multi-second HoloViews/calmap import.
        QTimer.singleShot(0, self._warm_calibration_plot_stack)

    def _warm_calibration_plot_stack(self) -> None:
        try:
            import synariustools.tools.calmapwidget  # noqa: F401
        except Exception:
            pass

    def _table_stylesheet(self) -> str:
        return (
            "QTableWidget {"
            f" background-color: {theme.RESOURCES_PANEL_BACKGROUND};"
            f" alternate-background-color: {theme.RESOURCES_PANEL_ALTERNATE_ROW};"
            " color: #1a1a1a;"
            " gridline-color: transparent;"
            " border: none;"
            " font-size: 11px;"
            "}"
            "QTableWidget::item { padding: 0px 2px; }"
            "QTableWidget::item:selected {"
            " background-color: #586cd4;"
            " color: #ffffff;"
            "}"
            "QHeaderView::section {"
            " background-color: #353535;"
            " color: #ffffff;"
            " padding: 2px 4px;"
            " border: none;"
            " font-size: 11px;"
            "}"
        )

    def _create_actions(self) -> None:
        self._act_open_script = QAction("Open Parameter Script...", self)
        self._act_open_script.triggered.connect(self._open_script)
        self._act_open_source = QAction("Register DataSet Source...", self)
        self._act_open_source.triggered.connect(self._register_data_set_source)
        self._act_refresh = QAction("Refresh", self)
        self._act_refresh.triggered.connect(self._refresh_table)
        self._act_console = QAction("CLI Console", self)
        self._act_console.triggered.connect(self._open_console)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self._act_open_script)
        file_menu.addAction(self._act_open_source)
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self._act_refresh)
        view_menu.addAction(self._act_console)

    def _create_toolbar(self) -> None:
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setStyleSheet(theme.studio_toolbar_stylesheet())
        tb.addAction(self._act_open_script)
        tb.addAction(self._act_open_source)
        tb.addAction(self._act_refresh)
        tb.addSeparator()
        tb.addAction(self._act_console)

    def _open_console(self) -> None:
        if self._console_window is None:
            self._console_window = ConsoleWindow(self._controller, on_command_executed=self._refresh_table)
        self._console_window.show_and_raise()

    def _open_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open parameter script",
            "",
            "Synarius scripts (*.syn *.txt *.cli);;All files (*)",
        )
        if not path:
            return
        cli_path = path.replace("\\", "/")
        try:
            self._controller.execute(f'load "{cli_path}"')
            self._refresh_table()
            self.statusBar().showMessage(f"Loaded script: {Path(path).name}", 6000)
        except Exception as exc:
            QMessageBox.critical(self, "Load script failed", str(exc))

    def _register_data_set_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Register DataSet source",
            "",
            "Parameter files (*.dcm *.cdfx *.a2l);;All files (*)",
        )
        if not path:
            return
        fmt = (Path(path).suffix or "").lstrip(".").lower() or "unknown"
        name = self._next_dataset_name(Path(path).stem)
        cli_path = path.replace("\\", "/")
        try:
            self._controller.execute("cd @main/parameters/data_sets")
            ds_ref = (self._controller.execute(f'new DataSet {name} source_path="{cli_path}" source_format={fmt}') or "").strip()
            if fmt == "dcm":
                from synarius_core.parameters.dcm_io import import_dcm_for_dataset

                n = import_dcm_for_dataset(self._controller, ds_ref, str(Path(path).resolve()))
                self._refresh_table()
                self.statusBar().showMessage(f"DCM: {n} parameters in DataSet '{name}'", 8000)
            else:
                self._refresh_table()
                self.statusBar().showMessage(f"Registered source for DataSet '{name}'", 6000)
        except Exception as exc:
            QMessageBox.critical(self, "Register DataSet failed", str(exc))

    def _next_dataset_name(self, raw: str) -> str:
        base = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in raw).strip("_")
        if not base:
            base = "DataSet"
        used: set[str] = set()
        root = self._controller.model.parameter_runtime().data_sets_root()
        for child in root.children:
            if isinstance(child, ComplexInstance):
                used.add(child.name)
        if base not in used:
            return base
        idx = 2
        while f"{base}_{idx}" in used:
            idx += 1
        return f"{base}_{idx}"

    def _collect_rows(self) -> list[tuple[str, str, str, UUID]]:
        rows: list[tuple[str, str, str, UUID]] = []
        model = self._controller.model
        repo = model.parameter_runtime().repo
        for node in model.iter_objects():
            if not isinstance(node, ComplexInstance):
                continue
            if model.is_in_trash_subtree(node):
                continue
            try:
                if str(node.get("type")) != "MODEL.CAL_PARAM":
                    continue
            except KeyError:
                continue
            if node.id is None:
                continue
            try:
                rec = repo.get_record(node.id)
            except Exception:
                continue
            rows.append((rec.name, rec.category, self._value_or_shape_label(rec), rec.parameter_id))
        rows.sort(key=lambda row: row[0].lower())
        return rows

    def _value_or_shape_label(self, rec: ParameterRecord) -> str:
        if rec.is_text:
            return rec.text_value
        arr = rec.values
        if arr.ndim == 0:
            return repr(float(arr.item()))
        if arr.ndim == 1:
            return f"{arr.shape[0]} Values"
        return f"{'X'.join(str(dim) for dim in arr.shape)} Values"

    def _refresh_table(self) -> None:
        try:
            rows = self._collect_rows()
        except ModuleNotFoundError as exc:
            QMessageBox.critical(
                self,
                "Missing dependency",
                f"{exc}\n\nInstall dependencies for synarius-apps, then restart ParaWiz.",
            )
            return

        self._table.setRowCount(len(rows))
        for row_idx, (name, ptype, value_repr, param_id) in enumerate(rows):
            it0 = QTableWidgetItem(name)
            it1 = QTableWidgetItem(ptype)
            it2 = QTableWidgetItem(value_repr)
            pid_s = str(param_id)
            for it in (it0, it1, it2):
                it.setData(Qt.ItemDataRole.UserRole, pid_s)
            self._table.setItem(row_idx, 0, it0)
            self._table.setItem(row_idx, 1, it1)
            self._table.setItem(row_idx, 2, it2)
        self.statusBar().showMessage(f"{len(rows)} parameters loaded", 3000)

    def _on_parameter_table_double_clicked(self, row: int, col: int) -> None:
        if col != 2:
            return
        it = self._table.item(row, 0)
        if it is None:
            return
        pid_raw = it.data(Qt.ItemDataRole.UserRole)
        if not pid_raw:
            return
        try:
            pid = UUID(str(pid_raw))
        except ValueError:
            return
        try:
            rec = self._controller.model.parameter_runtime().repo.get_record(pid)
        except Exception:
            return
        from synariustools.tools.calmapwidget import (
            CalibrationMapData,
            create_calibration_map_viewer,
            supports_calibration_plot,
        )

        if not supports_calibration_plot(rec):
            QMessageBox.information(
                self,
                "ParaWiz",
                "Nur numerische Kenngrößen mit mindestens einer Dimension (Kennlinie, Kennfeld, Vektor) können geplottet werden.",
            )
            return
        data = CalibrationMapData.from_parameter_record(rec)
        shell = create_calibration_map_viewer(data, parent=self, embedded=True)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"ParaWiz — {rec.name}")
        dlg.setWindowIcon(self.windowIcon())
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(shell)
        sh = shell.sizeHint()
        dlg.resize(sh.width(), sh.height())
        dlg.exec()
