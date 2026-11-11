import os
import re
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QFont, QGuiApplication, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QFrame, QScrollArea, QFileDialog
)

from ai_brain import get_installed_models, OllamaChatWorker, ChitandaMemoryManager
from laptop_control import LaptopController
from smart_tools import ScreenInspector, PdfDocumentReader, VoiceInputThread

class ChatWindow(QWidget):
    """
    Compact, comfortable, and intelligent desktop chat box for Eru Chitanda.
    - Voice commands with push-to-talk microphone recording.
    - Screen understanding / vision analysis of active windows.
    - PDF document extraction & summarization via pypdf.
    - Persistent reminders & timers that survive restarts.
    - Complete Windows automation & local AI via Ollama.
    """
    message_sent_to_king = Signal(str)

    def __init__(self, character):
        super().__init__()
        self.character = character
        self.memory = ChitandaMemoryManager()
        self.active_worker = None
        self.voice_rec_thread = None
        self._current_reply_accum = []
        self._drag_pos = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(360, 480)
        self.setMinimumSize(320, 390)

        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

        # Main background container with rounded borders and anime glow
        self.container = QFrame(self)
        self.container.setObjectName("Container")
        self.container.setStyleSheet("""
            QFrame#Container {
                background-color: #0f0b1e;
                border: 1.5px solid #ec4899;
                border-radius: 14px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 12)
        container_layout.setSpacing(8)

        # --- HEADER BAR ---
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        # Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_lbl = QLabel("🌸 Eru Chitanda")
        self.title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #ec4899; background: transparent;")

        self.status_lbl = QLabel("● Ready • Classical Literature Club")
        self.status_lbl.setFont(QFont("Segoe UI", 8))
        self.status_lbl.setStyleSheet("color: #a78bfa; background: transparent;")

        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.status_lbl)
        header.addLayout(title_box)

        header.addStretch()

        # Voice Toggle Button (Speaker Output)
        self.voice_btn = QPushButton("🔊")
        self.voice_btn.setToolTip("Toggle Voice Speech Output")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setChecked(True)
        self.voice_btn.setFixedSize(28, 28)
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: #24163b;
                color: #fdf2f8;
                border: 1px solid #4a2d6b;
                border-radius: 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #ec4899;
            }
        """)
        self.voice_btn.clicked.connect(self._toggle_voice)
        header.addWidget(self.voice_btn)

        # Close / Minimize button
        close_btn = QPushButton("✕")
        close_btn.setToolTip("Hide Chat")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #24163b;
                color: #a78bfa;
                border: 1px solid #4a2d6b;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e11d48;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)

        container_layout.addLayout(header)

        # --- CHAT DISPLAY ---
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #150f28;
                color: #fdf2f8;
                border: 1px solid #2d1d49;
                border-radius: 10px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.45;
            }
            QScrollBar:vertical {
                background: #150f28;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4a2d6b;
                min-height: 16px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #ec4899;
            }
        """)
        greeting = self.character.get_time_appropriate_greeting()
        self.chat_display.append(
            f"<div style='margin-bottom: 6px;'>"
            f"<b style='color: #ec4899;'>🌸 Chitanda:</b> {greeting} "
            f"<span style='color: #f472b6;'>(私、気になります！)</span>"
            f"</div>"
        )
        container_layout.addWidget(self.chat_display)

        # --- QUICK ACTION CHIPS ---
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(4)

        chip_style = """
            QPushButton {
                background-color: #1f1438;
                color: #e9d5ff;
                border: 1px solid #3d2363;
                border-radius: 10px;
                padding: 3px 7px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ec4899;
                color: white;
                border: 1px solid #ec4899;
            }
        """

        chips = [
            ("🎙️ Voice", self._chip_mic),
            ("🔍 Vision", self._chip_vision),
            ("📄 PDF", self._chip_pdf),
            ("⏰ Remind", self._chip_reminder),
            ("⏱️ Study", self._chip_study),
            ("🔋 Battery", self._chip_battery),
        ]

        for label, callback in chips:
            btn = QPushButton(label)
            btn.setStyleSheet(chip_style)
            btn.clicked.connect(callback)
            chips_layout.addWidget(btn)

        container_layout.addLayout(chips_layout)

        # --- INPUT ROW WITH MICROPHONE ---
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        # Voice Input Push-to-Talk Button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setToolTip("Click to speak your command (Voice Input)")
        self.mic_btn.setFixedSize(36, 34)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #24163b;
                color: #ec4899;
                border: 1px solid #4a2d6b;
                border-radius: 10px;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #ec4899;
                color: white;
            }
        """)
        self.mic_btn.clicked.connect(self._toggle_mic_recording)
        input_row.addWidget(self.mic_btn)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Message, ask screen, or give voice/command...")
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: #170f2d;
                color: #fdf2f8;
                border: 1px solid #3d2363;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #ec4899;
            }
        """)
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_row.addWidget(self.chat_input)

        send_btn = QPushButton("Send")
        send_btn.setFixedHeight(34)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #db2777, stop:1 #be185d);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #ec4899;
            }
            QPushButton:pressed {
                background: #9d174d;
            }
        """)
        send_btn.clicked.connect(self.send_chat_message)
        input_row.addWidget(send_btn)

        container_layout.addLayout(input_row)
        root_layout.addWidget(self.container)

    # -------------------------------------------------------------
    # WINDOW DRAGGING & POSITIONING
    # -------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < 55:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def show_near_mascot(self, mascot):
        """Intelligently position this compact chat box right beside the desktop mascot."""
        screen = QGuiApplication.primaryScreen().availableGeometry()
        target_x = mascot.x() - self.width() - 10
        target_y = mascot.y() + mascot.height() - self.height()

        if target_x < 10:
            target_x = mascot.x() + mascot.width() + 10

        target_x = max(10, min(target_x, screen.width() - self.width() - 10))
        target_y = max(10, min(target_y, screen.height() - self.height() - 40))

        self.move(target_x, target_y)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.chat_input.setFocus()

    def _toggle_voice(self):
        enabled = self.voice_btn.isChecked()
        self.voice_btn.setText("🔊" if enabled else "🔇")
        if not enabled:
            self.character.voice_worker.stop_current()

    # -------------------------------------------------------------
    # VOICE INPUT (MICROPHONE RECORDING)
    # -------------------------------------------------------------
    def _toggle_mic_recording(self):
        if self.voice_rec_thread and self.voice_rec_thread.isRunning():
            return

        self.mic_btn.setText("🔴")
        self.mic_btn.setStyleSheet("background-color: #e11d48; color: white; border-radius: 10px;")
        self.status_lbl.setText("🎙️ Listening to you now...")
        self.character.set_thinking(True)
        self.character.bubble.show_message("Listening to your voice...", duration_ms=4000)

        self.voice_rec_thread = VoiceInputThread(record_seconds=4)
        self.voice_rec_thread.transcription_ready.connect(self._on_voice_transcribed)
        self.voice_rec_thread.error_occurred.connect(self._on_voice_error)
        self.voice_rec_thread.start()

    def _on_voice_transcribed(self, text):
        self.mic_btn.setText("🎙️")
        self.mic_btn.setStyleSheet("background-color: #24163b; color: #ec4899; border-radius: 10px;")
        self.status_lbl.setText("● Ready • Classical Literature Club")
        self.character.set_thinking(False)

        # Place recognized text and process immediately
        self.chat_input.setText(text)
        self.send_chat_message()

    def _on_voice_error(self, err_msg):
        self.mic_btn.setText("🎙️")
        self.mic_btn.setStyleSheet("background-color: #24163b; color: #ec4899; border-radius: 10px;")
        self.status_lbl.setText("● Ready • Classical Literature Club")
        self.character.set_thinking(False)
        self.chat_display.append(f"<div style='color: #ef4444; font-size: 11px;'>[Mic Notice]: {err_msg}</div>")

    # -------------------------------------------------------------
    # QUICK CHIP ACTIONS
    # -------------------------------------------------------------
    def _chip_mic(self):
        self._toggle_mic_recording()

    def _chip_vision(self):
        self.trigger_screen_analysis("What am I looking at right now? Please summarize what is on my screen!")

    def _chip_pdf(self):
        self.trigger_pdf_summary()

    def _chip_reminder(self):
        self.chat_input.setText("Remind me in 30 minutes to ")
        self.chat_input.setFocus()

    def _chip_study(self):
        self._start_custom_study(30, 3, hide=True)

    def _chip_battery(self):
        self._exec_laptop_cmd("battery")

    # -------------------------------------------------------------
    # SCREEN UNDERSTANDING & PDF SUMMARIZATION
    # -------------------------------------------------------------
    def trigger_screen_analysis(self, question="What am I looking at on this screen?"):
        """Captures active screen and sends it for vision analysis."""
        win_info = ScreenInspector.get_active_window_info()
        b64_img = ScreenInspector.capture_screen_base64()

        self.chat_display.append(
            f"<div style='margin-bottom: 6px; text-align: right;'>"
            f"<span style='background-color: #24163b; border: 1px solid #4a2d6b; border-radius: 8px; padding: 4px 8px; color: #38bdf8;'>"
            f"<b>You:</b> 🔍 [Screen Vision] {question}"
            f"</span></div>"
        )
        self.chat_display.append(
            f"<div style='color: #a78bfa; font-size: 11px;'>Captured screen of <i>{win_info['app']}</i> (\"{win_info['title']}\")</div>"
        )

        prompt = (
            f"The user asks about their Windows screen: \"{question}\"\n"
            f"Active Application: {win_info['app']} | Window Title: \"{win_info['title']}\"\n"
            f"Please explain clearly what is on the screen, identify any errors or key details, and give sweet, practical guidance!"
        )
        self.process_user_prompt(prompt, images=[b64_img])

    def trigger_pdf_summary(self, target_query=""):
        """Finds recent PDF documents and extracts text for Chitanda to summarize."""
        recent = PdfDocumentReader.find_recent_pdfs(max_results=5)
        if not recent:
            self.chat_display.append("<div style='color: #ef4444;'>[Chitanda]: No PDF files found in Desktop, Downloads, or Documents.</div>")
            return

        selected = recent[0]
        if target_query:
            matched = next((p for p in recent if target_query.lower() in p["name"].lower()), None)
            if matched:
                selected = matched

        self.chat_display.append(
            f"<div style='margin-bottom: 6px; text-align: right;'>"
            f"<span style='background-color: #24163b; border: 1px solid #4a2d6b; border-radius: 8px; padding: 4px 8px; color: #38bdf8;'>"
            f"<b>You:</b> 📄 Read and summarize '{selected['name']}'"
            f"</span></div>"
        )

        doc_text = PdfDocumentReader.read_pdf_text(selected["path"])
        prompt = (
            f"As Eru Chitanda, I'm so curious! Please provide a sweet, well-structured summary of this PDF document, "
            f"highlighting the main concepts, key takeaways, and conclusions:\n\n{doc_text}"
        )
        self.process_user_prompt(prompt)

    # -------------------------------------------------------------
    # COMPATIBILITY HOOKS (CALLED BY CHARACTER / TIMERS)
    # -------------------------------------------------------------
    def _start_custom_study(self, study_mins=30, break_mins=3, hide=True):
        self.character.start_study_cycle(study_mins, break_mins, hide=hide)
        reply = (
            f"Study session started! We will focus diligently for {study_mins} minutes, "
            f"followed by a relaxing {break_mins}-minute break. "
            f"{'I will quietly hide now so you have zero distractions!' if hide else 'I will cheer you on quietly right here!'}"
        )
        self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
        if hide:
            QTimer.singleShot(2200, self.hide)

    def _update_study_timer_display(self, time_str, remaining_secs, phase):
        phase_name = "Study Focus" if phase == "study" else "Break Time"
        self.status_lbl.setText(f"⏱️ {time_str} ({phase_name})")

    def run_clipboard_action(self, action_type="summarize"):
        clip = QGuiApplication.clipboard().text().strip()
        if not clip:
            self.chat_display.append("<div style='color: #ef4444;'>[Chitanda]: Clipboard is empty. Copy some text first!</div>")
            return
        prompt = f"Please provide a sweet, elegant summary of this text highlighting the main takeaways:\n\n{clip}"
        self.process_user_prompt(prompt)

    # -------------------------------------------------------------
    # MESSAGE & COMMAND PROCESSING
    # -------------------------------------------------------------
    def send_chat_message(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()

        lower = text.lower()

        # Display User message
        self.chat_display.append(
            f"<div style='margin-bottom: 6px; text-align: right;'>"
            f"<span style='background-color: #24163b; border: 1px solid #4a2d6b; border-radius: 8px; padding: 4px 8px; color: #38bdf8;'>"
            f"<b>You:</b> {text}"
            f"</span></div>"
        )

        # 1. SCREEN UNDERSTANDING INTENT
        if any(w in lower for w in ["what's on my screen", "what is on my screen", "look at my screen", "summarize screen", "what am i looking at", "explain this error", "screen vision"]):
            self.trigger_screen_analysis(text)
            return

        # 2. PDF SUMMARIZATION INTENT
        if any(w in lower for w in ["read pdf", "summarize pdf", "read that pdf", "latest pdf", "summarize document"]):
            self.trigger_pdf_summary(text)
            return

        # 3. TIMED REMINDERS INTENT
        reminder_conf = self.character.reminder_manager.parse_and_add(text)
        if reminder_conf:
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reminder_conf}</div>")
            self.character.say(reminder_conf, voice=self.voice_btn.isChecked())
            return

        # 4. EXIT / DISMISS INTENT
        exit_phrases = ["you can go", "go away", "leave", "goodbye", "bye", "exit", "quit", "shut down", "dismiss"]
        if any(p == lower or lower.startswith(p + " ") or lower.endswith(" " + p) for p in exit_phrases):
            farewell = "Understood! You've worked so hard today. Please rest well, and call me back anytime! See you soon!"
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {farewell}</div>")
            self.character.say(farewell, voice=self.voice_btn.isChecked())
            QTimer.singleShot(3000, self.character.dismiss_companion)
            return

        # 5. HIDE COMMAND
        if any(h in lower for h in ["hide now", "hide", "go invisible", "disappear"]):
            reply = "Understood! Going invisible now so nothing distracts you! I'll pop right back up for your break. Do your best!"
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            QTimer.singleShot(2500, self.character.hide_character)
            QTimer.singleShot(2500, self.hide)
            return

        # 6. SHOW / UNHIDE
        if any(s in lower for s in ["show yourself", "unhide", "where are you", "come back", "show now"]):
            self.character.show_character()
            reply = "I'm right here! How is your study coming along? I'm so curious!"
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 7. STUDY & BREAK TIMER COMMAND
        is_study = any(w in lower for w in ["study", "gate", "exam", "focus"])
        has_time = any(w in lower for w in ["minute", "min", "hour"])
        if is_study and has_time:
            study_match = re.search(r'(\d+)\s*(?:minute|min)', lower)
            study_mins = int(study_match.group(1)) if study_match else 30
            break_match = re.search(r'break(?:\s+of)?\s*(?:(\d+)\s*to\s*)?(\d+)\s*(?:minute|min)?', lower)
            break_mins = int(break_match.group(2)) if break_match and break_match.group(2) else 3
            should_hide = "hide" in lower
            self._start_custom_study(study_mins, break_mins, hide=should_hide)
            return

        # 8. TIMER STATUS
        if any(q in lower for q in ["how much time left", "time remaining", "timer status"]):
            if self.character.study_manager.is_running:
                mins = self.character.study_manager.remaining_seconds // 60
                secs = self.character.study_manager.remaining_seconds % 60
                phase = "study session" if self.character.study_manager.phase == "study" else "break"
                reply = f"You have {mins}m {secs}s remaining in your {phase}."
            else:
                reply = "No study timer is active right now. Tell me whenever you would like to begin!"
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 9. STOP TIMER
        if any(s in lower for s in ["stop timer", "cancel timer", "stop study"]):
            self.character.study_manager.stop_session()
            self.status_lbl.setText("● Ready • Classical Literature Club")
            reply = "Study timer stopped. Please remember to rest whenever you feel tired!"
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 10. DIRECT LAPTOP ACTIONS
        if any(b in lower for b in ["battery", "charge level", "power status"]):
            self._exec_laptop_cmd("battery")
            return
        if any(h in lower for h in ["system health", "laptop health", "cpu usage", "ram usage", "disk space"]):
            self._exec_laptop_cmd("health")
            return
        if any(l in lower for l in ["lock laptop", "lock pc", "lock computer", "lock screen"]):
            self._exec_laptop_cmd("lock")
            return
        if any(s in lower for s in ["take a screenshot", "screenshot", "screen capture"]):
            self._exec_laptop_cmd("screenshot")
            return
        if any(v in lower for v in ["mute sound", "mute volume", "mute audio", "unmute"]):
            self._exec_laptop_cmd("mute")
            return
        if any(v in lower for v in ["volume up", "louder", "turn up volume"]):
            self._exec_laptop_cmd("vol_up")
            return
        if any(v in lower for v in ["volume down", "quieter", "turn down volume"]):
            self._exec_laptop_cmd("vol_down")
            return
        if any(d in lower for d in ["show desktop", "minimize all"]):
            self._exec_laptop_cmd("desktop")
            return

        # 11. WEB SEARCH (GOOGLE / YOUTUBE)
        search_yt = re.search(r'(?:search youtube for|play on youtube|youtube)\s+([^.,;\n]+)', lower)
        if search_yt:
            q = search_yt.group(1).strip()
            reply = LaptopController.search_youtube(q)
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        search_google = re.search(r'(?:search google for|google|look up)\s+([^.,;\n]+)', lower)
        if search_google:
            q = search_google.group(1).strip()
            reply = LaptopController.search_web(q)
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 12. OPEN APPS
        open_match = re.search(r'^(?:please\s+)?open\s+(?:the\s+)?([a-zA-Z0-9_\s\.\:\-]+)', lower)
        if open_match:
            target = open_match.group(1).strip()
            if "." in target and not target.endswith((".exe", ".txt", ".py", ".json")):
                reply = LaptopController.open_url(target)
            else:
                reply = LaptopController.open_application(target)
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # Regular AI query through Ollama
        self.process_user_prompt(text)

    def _exec_laptop_cmd(self, cmd_key):
        if cmd_key == "battery":
            reply = LaptopController.get_battery_info()
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
            self.character.say(reply, voice=self.voice_btn.isChecked())
        elif cmd_key == "health":
            reply = LaptopController.get_system_health()
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b><pre style='color: #e9d5ff;'>{reply}</pre></div>")
            self.character.say("Here is your laptop health report!", voice=self.voice_btn.isChecked())
        elif cmd_key == "lock":
            reply = LaptopController.lock_laptop()
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
        elif cmd_key == "screenshot":
            self.hide()
            QTimer.singleShot(400, self._finish_screenshot)
        elif cmd_key == "mute":
            reply = LaptopController.volume_mute_toggle()
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
        elif cmd_key == "vol_up":
            reply = LaptopController.volume_up()
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
        elif cmd_key == "vol_down":
            reply = LaptopController.volume_down()
            self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
        elif cmd_key == "desktop":
            LaptopController.show_desktop()

    def _finish_screenshot(self):
        reply = LaptopController.take_screenshot()
        self.show()
        self.chat_display.append(f"<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> {reply}</div>")
        self.character.say("Screenshot captured and saved to your Pictures folder!", voice=self.voice_btn.isChecked())

    # -------------------------------------------------------------
    # OLLAMA AI STREAMING & MEMORY PERSISTENCE
    # -------------------------------------------------------------
    def process_user_prompt(self, user_text, images=None):
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.cancel()

        # Add to persistent memory silently
        self.memory.add_message("user", user_text)

        self.status_lbl.setText("● Thinking... (私、気になります！)")
        self.character.set_thinking(True)
        self.character.bubble.set_streaming_text("I'm curious...")

        models = get_installed_models()
        model = models[0] if models else "llama3.2:1b"
        messages = self.memory.get_context_messages()

        self.active_worker = OllamaChatWorker(model, messages, images=images)
        self.active_worker.token_received.connect(self._on_token)
        self.active_worker.response_finished.connect(self._on_finished)
        self.active_worker.error_occurred.connect(self._on_error)
        self.active_worker.start()

        self._current_reply_accum = []
        self.chat_display.append("<div style='margin-bottom: 6px;'><b style='color: #ec4899;'>🌸 Chitanda:</b> ")

    def _on_token(self, token):
        self._current_reply_accum.append(token)
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
        self.character.bubble.set_streaming_text("".join(self._current_reply_accum))

    def _on_finished(self, full_text):
        self.status_lbl.setText("● Ready • Classical Literature Club")
        self.character.set_thinking(False)
        self.memory.add_message("assistant", full_text)
        self.character.bubble.finalize_stream(duration_ms=7000)

        # Check for [ACTION: ...] tags
        action_matches = re.findall(r'\[ACTION:\s*([^\]]+)\]', full_text, re.IGNORECASE)
        for act in action_matches:
            res = LaptopController.execute_action_tag(act)
            self.chat_display.append(f"<div style='color: #c084fc; font-size: 11px;'>[Laptop Executed]: {res}</div>")

        if self.voice_btn.isChecked() and full_text:
            clean_speech = re.sub(r'\[ACTION:[^\]]+\]', '', full_text).strip()
            if clean_speech:
                self.character.voice_worker.speak(clean_speech)

    def _on_error(self, err):
        self.status_lbl.setText("● Offline / Error")
        self.character.set_thinking(False)
        self.chat_display.append(f"<div style='color: #ef4444;'>[Notice]: {err}</div>")
        self.character.say("I couldn't reach Ollama on your laptop. Please check that Ollama is running!", voice=False)
