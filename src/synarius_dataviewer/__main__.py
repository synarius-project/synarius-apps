"""Entry: graphical Dataviewer (PySide6) or ``--version``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from synarius_apps_diagnostics import (
    configure_file_logging,
    install_qt_message_handler,
    log_session_start,
    main_log_path,
)
from synarius_dataviewer._version import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="Synarius Dataviewer")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args()
    if args.version:
        print(__version__)
        return 0

    configure_file_logging(
        user_log_appname="SynariusDataviewer",
        log_filename="synarius-dataviewer.log",
        uncaught_logger_name="synarius_dataviewer.uncaught",
        root_child_logger="synarius_dataviewer",
        debug_env_keys=("SYNARIUS_DATAVIEWER_LOG_DEBUG",),
    )
    log_session_start(logger_name="synarius_dataviewer.bootstrap", app_name="Synarius Dataviewer", version=__version__)
    _log_path = main_log_path()
    if _log_path is not None:
        print(
            f"Synarius Dataviewer {__version__} | log file: {_log_path.resolve()}",
            file=sys.stderr,
            flush=True,
        )

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from synarius_dataviewer.app.main_window import MainWindow

    if sys.platform.startswith("win"):
        # Ensure Windows taskbar uses Synarius identity/icon instead of python.exe.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
                "synarius.dataviewer"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    install_qt_message_handler()
    app.setApplicationName("Synarius Dataviewer")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(
        QIcon(str(Path(__file__).resolve().parent / "app" / "icons" / "synarius64.png"))
    )
    w = MainWindow()
    w.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
