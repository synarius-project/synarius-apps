"""Tint monochrome SVG icons for dark toolbars."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_HEX_DARK_1 = re.compile(r"#232629", re.IGNORECASE)
_HEX_DARK_2 = re.compile(r"#1c1c1c", re.IGNORECASE)
_HEX_DARK_3 = re.compile(r"#000000", re.IGNORECASE)


def _tint_svg_markup(svg_text: str, foreground: QColor) -> str:
    hx = foreground.name(QColor.NameFormat.HexRgb)
    s = _HEX_DARK_1.sub(hx, svg_text)
    s = _HEX_DARK_2.sub(hx, s)
    s = _HEX_DARK_3.sub(hx, s)
    return s


def icon_from_tinted_svg_file(
    svg_path: Path,
    foreground: QColor,
    *,
    logical_side: int = 20,
) -> QIcon:
    raw = svg_path.read_text(encoding="utf-8")
    tinted = _tint_svg_markup(raw, foreground)
    renderer = QSvgRenderer(QByteArray(tinted.encode("utf-8")))
    if not renderer.isValid():
        return QIcon(str(svg_path))

    app = QGuiApplication.instance()
    dpr = 1.0
    if app is not None:
        screen = app.primaryScreen()
        if screen is not None:
            dpr = max(1.0, float(screen.devicePixelRatio()))

    px = max(1, int(round(logical_side * dpr)))
    img = QImage(px, px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p, QRectF(0.0, 0.0, float(px), float(px)))
    p.end()

    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icon_from_tinted_svg_file_fit_height(
    svg_path: Path,
    foreground: QColor,
    *,
    logical_height: int = 18,
) -> tuple[QIcon, QSize]:
    """Tint + render SVG mit erhaltener Seitenproportion (Höhe = ``logical_height`` px, Breite skaliert)."""
    raw = svg_path.read_text(encoding="utf-8")
    tinted = _tint_svg_markup(raw, foreground)
    renderer = QSvgRenderer(QByteArray(tinted.encode("utf-8")))
    if not renderer.isValid():
        return QIcon(str(svg_path)), QSize(max(1, logical_height), max(1, logical_height))

    ds = renderer.defaultSize()
    if ds.width() <= 0 or ds.height() <= 0:
        lw = lh = max(1, logical_height)
    else:
        lh = max(1, int(logical_height))
        lw = max(1, int(round(lh * ds.width() / float(ds.height()))))

    app = QGuiApplication.instance()
    dpr = 1.0
    if app is not None:
        screen = app.primaryScreen()
        if screen is not None:
            dpr = max(1.0, float(screen.devicePixelRatio()))

    w_px = max(1, int(round(lw * dpr)))
    h_px = max(1, int(round(lh * dpr)))
    img = QImage(w_px, h_px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p, QRectF(0.0, 0.0, float(w_px), float(h_px)))
    p.end()

    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm), QSize(lw, lh)


def icon_from_svg_file(
    svg_path: Path,
    *,
    logical_side: int = 20,
) -> QIcon:
    """SVG wie in der Datei gerendert (ohne Farb-Ersetzung); für farbige oder fest gestaltete Symbole."""
    raw = svg_path.read_text(encoding="utf-8")
    renderer = QSvgRenderer(QByteArray(raw.encode("utf-8")))
    if not renderer.isValid():
        return QIcon(str(svg_path))

    app = QGuiApplication.instance()
    dpr = 1.0
    if app is not None:
        screen = app.primaryScreen()
        if screen is not None:
            dpr = max(1.0, float(screen.devicePixelRatio()))

    px = max(1, int(round(logical_side * dpr)))
    img = QImage(px, px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p, QRectF(0.0, 0.0, float(px), float(px)))
    p.end()

    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)
