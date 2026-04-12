import synarius_dataviewer
import synarius_parawiz
import synariustools.tools.calmapwidget as calmapwidget


def test_package_importable() -> None:
    assert synarius_dataviewer is not None
    assert synarius_parawiz is not None
    assert calmapwidget.CalibrationMapData is not None


def test_pyside6_qtcore_importable() -> None:
    """Guards against missing/wrong-environment PySide6 (see README developer setup)."""
    from PySide6.QtCore import Qt, QTimer

    assert Qt is not None
    assert QTimer is not None
