"""Entry point for Synarius ParaWiz."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from synarius_parawiz._version import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description="Synarius ParaWiz")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args()
    if args.version:
        print(__version__)
        return 0

    # Windows: set AppUserModelID before any Qt import so the taskbar can group this process
    # under synarius.parawiz instead of generic python.exe.
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
                "synarius.parawiz"
            )
        except Exception:
            pass

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from synarius_parawiz.app.main_window import MainWindow

    p_via_file = Path(__file__).resolve().parents[1] / "synarius_dataviewer" / "app" / "icons" / "synarius64.png"
    icon_path = p_via_file
    try:
        import synarius_dataviewer as sdv

        p_via_pkg = Path(sdv.__file__).resolve().parent / "app" / "icons" / "synarius64.png"
        if p_via_pkg.is_file():
            icon_path = p_via_pkg
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Synarius ParaWiz")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(icon_path)))
    w = MainWindow()
    w.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
