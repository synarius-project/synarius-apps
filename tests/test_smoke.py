import synarius_dataviewer
import synarius_parawiz
import synariustools.tools.calmapwidget as calmapwidget


def test_package_importable() -> None:
    assert synarius_dataviewer is not None
    assert synarius_parawiz is not None
    assert calmapwidget.CalibrationMapData is not None
