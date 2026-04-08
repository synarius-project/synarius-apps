from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit, QWidget


@dataclass
class TerminalCommandHistory:
    entries: list[str] = field(default_factory=list)
    index: int = 0

    def push(self, line: str) -> None:
        if line.strip() == "":
            return
        self.entries.append(line)
        self.index = len(self.entries)

    def prev(self) -> str | None:
        if not self.entries:
            return None
        self.index = max(0, self.index - 1)
        return self.entries[self.index]

    def next(self) -> str:
        if not self.entries:
            return ""
        self.index = min(len(self.entries), self.index + 1)
        if self.index >= len(self.entries):
            return ""
        return self.entries[self.index]


class TerminalConsoleWidget(QTextEdit):
    """Terminal-like QTextEdit with prompt/input on same widget."""

    def __init__(
        self,
        on_submit: Callable[[str], None],
        on_prev: Callable[[], None],
        on_next: Callable[[], None],
        parent: QWidget | None = None,
        *,
        input_color: str = "#FFFFFF",
        output_color: str = "#ADD8E6",
    ) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        self._on_prev = on_prev
        self._on_next = on_next
        self._input_color = input_color
        self._output_color = output_color
        self._input_start = 0
        self._prompt_line_start = 0
        self.setAcceptRichText(False)

    def _insert_colored(self, text: str, color: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.mergeCharFormat(fmt)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_output(self, text: str, color: str) -> None:
        self._insert_colored(f"{text}\n", color)

    def show_prompt(self, prompt: str, color: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self._prompt_line_start = cursor.position()
        self._insert_colored(prompt, color)
        self._input_start = self.textCursor().position()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._input_color))
        self.setCurrentCharFormat(fmt)

    def insert_log_before_current_prompt(self, text: str, color: str) -> None:
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        cursor.setPosition(self._prompt_line_start)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"{text}\n")
        cursor.endEditBlock()
        delta = len(text) + 1
        self._prompt_line_start += delta
        self._input_start += delta
        end = self.textCursor()
        end.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(end)

    def current_input(self) -> str:
        return self.toPlainText()[self._input_start :]

    def replace_current_input(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        cursor = self.textCursor()

        if key == Qt.Key.Key_Up:
            self._on_prev()
            return
        if key == Qt.Key.Key_Down:
            self._on_next()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            line = self.current_input()
            self._insert_colored("\n", self._output_color)
            self._on_submit(line)
            return
        if key == Qt.Key.Key_Backspace and cursor.position() <= self._input_start:
            return
        if key == Qt.Key.Key_Left and cursor.position() <= self._input_start:
            return
        if key == Qt.Key.Key_Home:
            cursor.setPosition(self._input_start)
            self.setTextCursor(cursor)
            return
        if cursor.position() < self._input_start:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)

        super().keyPressEvent(event)
