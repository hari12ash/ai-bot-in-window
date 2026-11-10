from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPainterPath, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class SpeechBubble(QWidget):
    def __init__(self, parent_character):
        super().__init__()
        self.character = parent_character

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setFixedWidth(240)
        self.setMinimumHeight(55)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)

        self.label = QLabel("I'm listening.")
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Segoe UI", 9))
        self.label.setStyleSheet("color: #f1f5f9; background: transparent;")
        layout.addWidget(self.label)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, duration_ms: int = 6500):
        if not text:
            return
        display_text = text if len(text) <= 200 else text[:197] + "..."
        self.label.setText(display_text)
        self.adjustSize()
        self.update_position()
        self.show()
        if duration_ms > 0:
            self.hide_timer.start(duration_ms)

    def set_streaming_text(self, text: str):
        display_text = text if len(text) <= 200 else text[-197:]
        self.label.setText(display_text)
        self.adjustSize()
        self.update_position()
        if not self.isVisible():
            self.show()
        self.hide_timer.stop()

    def finalize_stream(self, duration_ms: int = 6500):
        if duration_ms > 0:
            self.hide_timer.start(duration_ms)

    def update_position(self):
        if not self.character:
            return
        char_rect = self.character.geometry()
        bubble_x = char_rect.x() + (char_rect.width() - self.width()) // 2
        bubble_y = char_rect.y() - self.height() - 6

        if bubble_y < 10:
            bubble_y = char_rect.y() + char_rect.height() + 6

        self.move(bubble_x, bubble_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(rect.toRectF(), 10, 10)

        # Soft dark slate bubble with calming emerald border
        painter.setPen(QColor("#10b981"))
        painter.setBrush(QColor(15, 23, 42, 245))
        painter.drawPath(path)

    def mousePressEvent(self, event):
        self.character.open_chat()
        self.hide()
