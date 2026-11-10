import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt

from character import KingCharacter
from chat_window import ChatWindow

def main():
    # Enable crisp High-DPI rendering
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Eru Chitanda - AI Desktop Companion")

    # CRITICAL: Do NOT quit when the chat window or any dialog is closed!
    # The companion stays floating on the desktop until the user explicitly tells her to go.
    app.setQuitOnLastWindowClosed(False)

    chitanda = KingCharacter()
    chat_win = ChatWindow(character=chitanda)
    chitanda.chat_window = chat_win

    # Position in bottom-right corner above Windows taskbar
    screen = QGuiApplication.primaryScreen().availableGeometry()
    default_x = screen.width() - 170
    default_y = screen.height() - 270
    chitanda.move(default_x, default_y)

    chitanda.show()

    # Living friend greeting
    chitanda.say("Hello! I'm Eru Chitanda. I'm so curious to see what we'll achieve together today! Let's do our best!", voice=True)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
