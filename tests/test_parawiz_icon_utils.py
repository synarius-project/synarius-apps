"""Tests for non-Qt parts of synarius_parawiz.app.icon_utils."""

from __future__ import annotations

import os
import struct
import tempfile
from pathlib import Path

from synarius_parawiz.app.icon_utils import (
    _write_ico_embedded_png,
    parawiz_icon_png_path,
)


class TestParawizIconPngPath:
    def test_returns_none_or_path(self) -> None:
        result = parawiz_icon_png_path()
        assert result is None or isinstance(result, Path)

    def test_return_value_is_file_if_not_none(self) -> None:
        result = parawiz_icon_png_path()
        if result is not None:
            assert result.is_file()


class TestWriteIcoEmbeddedPng:
    def _make_minimal_png(self, width: int = 8, height: int = 8) -> bytes:
        """Build the minimal bytes of a PNG header (IHDR chunk) for testing."""
        # PNG signature
        sig = b"\x89PNG\r\n\x1a\n"
        # IHDR chunk: 13 bytes of data
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        import zlib
        crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", crc)
        # Minimal IEND chunk
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
        return sig + ihdr + iend

    def test_nonexistent_file_returns_false(self) -> None:
        result = _write_ico_embedded_png(Path("/nonexistent/path/icon.png"), "out.ico")
        assert result is False

    def test_file_too_short_returns_false(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, b"\x89PNG\r\n\x1a\n")  # Only 8 bytes, need >= 24
            os.close(fd)
            fd = -1
            result = _write_ico_embedded_png(Path(path), path + ".ico")
            assert result is False
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_wrong_magic_bytes_returns_false(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, b"NOTPNG" + b"\x00" * 20)
            os.close(fd)
            fd = -1
            result = _write_ico_embedded_png(Path(path), path + ".ico")
            assert result is False
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_zero_width_returns_false(self) -> None:
        # PNG signature + IHDR with w=0
        sig = b"\x89PNG\r\n\x1a\n"
        # 16 bytes for signature + chunk length + type, then bytes 16-20 = width
        padding = b"\x00" * 8  # chunk length + type placeholder
        width_zero = b"\x00\x00\x00\x00"  # width = 0
        height_ok = b"\x00\x00\x00\x08"  # height = 8
        data = sig + padding + width_zero + height_ok
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, data)
            os.close(fd)
            fd = -1
            result = _write_ico_embedded_png(Path(path), path + ".ico")
            assert result is False
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_valid_png_writes_ico(self) -> None:
        png_bytes = self._make_minimal_png(8, 8)
        fd, png_path = tempfile.mkstemp(suffix=".png")
        fd_ico, ico_path = tempfile.mkstemp(suffix=".ico")
        try:
            os.write(fd, png_bytes)
            os.close(fd)
            fd = -1
            os.close(fd_ico)
            fd_ico = -1
            result = _write_ico_embedded_png(Path(png_path), ico_path)
            assert result is True
            assert Path(ico_path).stat().st_size > 0
        finally:
            if fd >= 0:
                os.close(fd)
            if fd_ico >= 0:
                os.close(fd_ico)
            for p in (png_path, ico_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_valid_png_large_dimension_uses_zero_in_ico(self) -> None:
        """Width/height >= 256 → stored as 0 in ICO entry (per spec)."""
        png_bytes = self._make_minimal_png(256, 256)
        fd, png_path = tempfile.mkstemp(suffix=".png")
        fd_ico, ico_path = tempfile.mkstemp(suffix=".ico")
        try:
            os.write(fd, png_bytes)
            os.close(fd)
            fd = -1
            os.close(fd_ico)
            fd_ico = -1
            result = _write_ico_embedded_png(Path(png_path), ico_path)
            assert result is True
        finally:
            if fd >= 0:
                os.close(fd)
            if fd_ico >= 0:
                os.close(fd_ico)
            for p in (png_path, ico_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_ico_output_unwritable_path_returns_false(self) -> None:
        png_bytes = self._make_minimal_png(8, 8)
        fd, png_path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, png_bytes)
            os.close(fd)
            fd = -1
            result = _write_ico_embedded_png(Path(png_path), "/nonexistent/dir/out.ico")
            assert result is False
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(png_path)
            except OSError:
                pass
