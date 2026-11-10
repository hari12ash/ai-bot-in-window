import os
import re
import ctypes
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QIcon, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QTabWidget,
    QWidget, QListWidget, QListWidgetItem,
    QComboBox, QFrame, QGridLayout
)

from ai_brain import get_installed_models, OllamaChatWorker, ChitandaMemoryManager
from work_tools import PomodoroTimer, TaskManager

WALLPAPER_DIR = os.path.join(os.path.dirname(__file__), "wallpapers")

class ChatWindow(QDialog):
    message_sent_to_king = Signal(str)

    def __init__(self, character):
        super().__init__()
        self.character = character
        self.memory = ChitandaMemoryManager()
        self.task_manager = TaskManager()
        self.pomodoro = PomodoroTimer()
        self.active_worker = None

        # Synchronize task manager with persistent memory tasks
        for task in self.memory.user_profile.get("tasks", []):
            if not any(t["text"].lower() == task.lower() for t in self.task_manager.tasks):
                self.task_manager.add_task(task)

        self.setWindowTitle("🌸 Eru Chitanda - Living Study Companion")
        self.resize(540, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f0b1e;
                color: #fdf2f8;
            }
            QTabWidget::pane {
                border: 1px solid #3b2656;
                background: #17112c;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #0f0b1e;
                color: #a78bfa;
                padding: 9px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #17112c;
                color: #ec4899;
                border: 1px solid #3b2656;
                border-bottom: none;
            }
            QTextEdit, QListWidget {
                background-color: #0d091a;
                color: #fdf2f8;
                border: 1px solid #3b2656;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.4;
            }
            QLineEdit {
                background-color: #0d091a;
                color: #fdf2f8;
                border: 1px solid #3b2656;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #ec4899;
            }
            QPushButton {
                background-color: #db2777;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #ec4899;
            }
            QPushButton:pressed {
                background-color: #be185d;
            }
            QPushButton.secondary {
                background-color: #261b40;
                color: #e9d5ff;
            }
            QPushButton.secondary:hover {
                background-color: #3b285f;
            }
            QComboBox {
                background-color: #1a1333;
                color: #fdf2f8;
                border: 1px solid #3b2656;
                border-radius: 6px;
                padding: 5px 10px;
            }
            QScrollBar:vertical {
                background: #0d091a;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3b2656;
                min-height: 20px;
                border-radius: 4px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # Header bar
        header = QHBoxLayout()
        title = QLabel("🌸 Eru Chitanda  |  Your Curious Friend")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #ec4899;")
        header.addWidget(title)

        header.addStretch()

        # Model Selector
        self.model_combo = QComboBox()
        models = get_installed_models()
        self.model_combo.addItems(models)
        header.addWidget(self.model_combo)

        # Voice Selector
        self.voice_mode_combo = QComboBox()
        self.voice_mode_combo.addItem("🌸 English Dub (Madeleine Morris)", "en-chitanda")
        self.voice_mode_combo.addItem("🎀 Elegant English (Emma)", "en-emma")
        self.voice_mode_combo.addItem("🇯🇵 Anime Japanese (Satomi Sato)", "ja-chitanda")
        self.voice_mode_combo.currentIndexChanged.connect(self._on_voice_mode_changed)
        header.addWidget(self.voice_mode_combo)

        # Voice toggle
        self.voice_btn = QPushButton("🔊 ON")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setChecked(True)
        self.voice_btn.clicked.connect(self.toggle_voice)
        header.addWidget(self.voice_btn)

        main_layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.setup_chat_tab()
        self.setup_tools_tab()
        self.setup_quick_actions_tab()
        self.setup_wallpapers_tab()
        main_layout.addWidget(self.tabs)

        # Pomodoro notifications
        self.pomodoro.tick.connect(self._update_pomo_display)
        self.pomodoro.session_completed.connect(self._on_pomo_done)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def reject(self):
        self.hide()

    def _on_voice_mode_changed(self):
        mode = self.voice_mode_combo.currentData()
        self.character.voice_worker.set_voice_mode(mode)

    def setup_chat_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        # Scenic Kyoto Animation banner
        banner_path = os.path.join(WALLPAPER_DIR, "01_chitanda_sweet_smile.png")
        if not os.path.exists(banner_path):
            banner_path = os.path.join(WALLPAPER_DIR, "04_chitanda_classic_literature.jpg")
        if os.path.exists(banner_path):
            banner_lbl = QLabel()
            banner_lbl.setFixedHeight(95)
            banner_lbl.setScaledContents(True)
            banner_pix = QPixmap(banner_path).scaled(
                500, 95,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            banner_lbl.setPixmap(banner_pix)
            banner_lbl.setStyleSheet("border-radius: 8px; border: 1px solid #3b2656;")
            layout.addWidget(banner_lbl)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        greeting = self.character.get_time_appropriate_greeting()
        self.chat_display.append(
            f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {greeting}"
        )
        layout.addWidget(self.chat_display)

        # Input row
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Talk to Chitanda (e.g. 'I am studying now, remind me in 30 mins to take a break')...")
        self.chat_input.returnPressed.connect(self.send_chat_message)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_chat_message)

        input_row.addWidget(self.chat_input)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

        # Footer actions
        actions_row = QHBoxLayout()
        clear_btn = QPushButton("Reset Memory")
        clear_btn.setStyleSheet("background-color: #261b40; color: #a78bfa; font-size: 11px;")
        clear_btn.clicked.connect(self.clear_chat_history)
        actions_row.addWidget(clear_btn)

        hide_btn = QPushButton("🙈 Hide Chitanda (Study Mode)")
        hide_btn.setStyleSheet("background-color: #261b40; color: #ec4899; font-size: 11px;")
        hide_btn.clicked.connect(self._on_click_hide)
        actions_row.addWidget(hide_btn)

        actions_row.addStretch()

        self.status_label = QLabel("Listening")
        self.status_label.setStyleSheet("color: #a78bfa; font-size: 11px;")
        actions_row.addWidget(self.status_label)

        layout.addLayout(actions_row)
        self.tabs.addTab(tab, "💬 Conversation")

    def _on_click_hide(self):
        self.chat_display.append("<span style='color: #ec4899;'>[Chitanda]: Going invisible now. Focus on your study! I'll pop back up for your break!</span>")
        self.character.say("Going invisible now. Focus with all your heart! See you at break time!", voice=self.voice_btn.isChecked())
        QTimer.singleShot(1500, self.character.hide_character)
        self.hide()

    def setup_tools_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        # Study Session Frame
        study_frame = QFrame()
        study_frame.setStyleSheet("background: #130d24; border-radius: 8px; padding: 10px; border: 1px solid #ec4899;")
        study_layout = QVBoxLayout(study_frame)

        study_title = QLabel("⏱️ Active Study & Break Session (Custom Timers)")
        study_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        study_title.setStyleSheet("color: #ec4899;")
        study_layout.addWidget(study_title)

        study_row = QHBoxLayout()
        self.study_time_label = QLabel("30:00 (Idle)")
        self.study_time_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.study_time_label.setStyleSheet("color: #fdf2f8;")
        study_row.addWidget(self.study_time_label)

        study_row.addStretch()

        btn_start_30 = QPushButton("Start 30m Study (Auto-Hide)")
        btn_start_30.clicked.connect(lambda: self._start_custom_study(30, 3, hide=True))
        study_row.addWidget(btn_start_30)

        btn_stop = QPushButton("Stop")
        btn_stop.setStyleSheet("background-color: #ef4444;")
        btn_stop.clicked.connect(self._stop_study_session)
        study_row.addWidget(btn_stop)

        study_layout.addLayout(study_row)
        layout.addWidget(study_frame)

        # Pomodoro Frame
        pomo_frame = QFrame()
        pomo_frame.setStyleSheet("background: #130d24; border-radius: 8px; padding: 10px; margin-top: 6px; border: 1px solid #3b2656;")
        pomo_layout = QVBoxLayout(pomo_frame)

        pomo_title = QLabel("🍵 Quick Focus (Pomodoro)")
        pomo_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        pomo_title.setStyleSheet("color: #c084fc;")
        pomo_layout.addWidget(pomo_title)

        pomo_row = QHBoxLayout()
        self.pomo_time_label = QLabel("25:00")
        self.pomo_time_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.pomo_time_label.setStyleSheet("color: #fdf2f8;")
        pomo_row.addWidget(self.pomo_time_label)

        pomo_row.addStretch()

        start_25_btn = QPushButton("Focus (25m)")
        start_25_btn.clicked.connect(lambda: self.start_pomodoro(25))
        pomo_row.addWidget(start_25_btn)

        break_5_btn = QPushButton("Tea Break (5m)")
        break_5_btn.setStyleSheet("background-color: #261b40;")
        break_5_btn.clicked.connect(lambda: self.start_pomodoro_break(5))
        pomo_row.addWidget(break_5_btn)

        pomo_layout.addLayout(pomo_row)
        layout.addWidget(pomo_frame)

        # Persistent Memory Tasks Frame
        tasks_label = QLabel("📝 Chitanda's Memory & Daily Tasks (Saved across sessions)")
        tasks_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        tasks_label.setStyleSheet("color: #ec4899; margin-top: 6px;")
        layout.addWidget(tasks_label)

        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(self._on_task_clicked)
        self.refresh_task_list()
        layout.addWidget(self.task_list)

        task_input_row = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Add a task to Chitanda's memory (e.g. GATE Revision)...")
        self.task_input.returnPressed.connect(self.add_task)

        add_task_btn = QPushButton("Add Task")
        add_task_btn.clicked.connect(self.add_task)

        clear_done_btn = QPushButton("Clear Done")
        clear_done_btn.setStyleSheet("background-color: #261b40;")
        clear_done_btn.clicked.connect(self.clear_completed_tasks)

        task_input_row.addWidget(self.task_input)
        task_input_row.addWidget(add_task_btn)
        task_input_row.addWidget(clear_done_btn)
        layout.addLayout(task_input_row)

        self.tabs.addTab(tab, "🎯 Focus & Tasks")

    def _start_custom_study(self, study_mins, break_mins, hide=True):
        self.character.start_study_cycle(study_mins, break_mins, hide=hide)
        self.chat_display.append(
            f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> "
            f"Study session started! We will focus for {study_mins} minutes, followed by a sweet {break_mins}-minute break! "
            f"{'I will hide quietly so you have complete focus. See you at break time!' if hide else 'I will cheer you on quietly right here!'}"
        )
        if hide:
            QTimer.singleShot(2500, self.hide)

    def _stop_study_session(self):
        self.character.study_manager.stop_session()
        self.study_time_label.setText("30:00 (Idle)")
        self.chat_display.append("<span style='color: #ef4444;'>[Chitanda]: Study session paused. Remember to rest if you feel tired!</span>")

    def _update_study_timer_display(self, time_str, remaining_secs, phase):
        phase_name = "Study Focus" if phase == "study" else "Break Time"
        self.study_time_label.setText(f"{time_str} ({phase_name})")

    def setup_quick_actions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        quotes_title = QLabel("🌸 Eru Chitanda's Soundboard & Catchphrases")
        quotes_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        quotes_title.setStyleSheet("color: #ec4899;")
        layout.addWidget(quotes_title)

        grid = QGridLayout()
        grid.setSpacing(8)

        btn_curious = QPushButton("✨ 「私、気になります！」\n(I'm Curious!)")
        btn_curious.clicked.connect(lambda: self.play_chitanda_line(
            "私、気になります！詳しく教えていただけませんか？",
            "I'm curious! Could you please tell me more about it?"
        ))
        grid.addWidget(btn_curious, 0, 0)

        btn_tea = QPushButton("🍵 「お茶を淹れましょうか？」\n(Offer Warm Tea)")
        btn_tea.clicked.connect(lambda: self.play_chitanda_line(
            "お茶を淹れましたよ。温かいお茶を飲んで、少し休んでくださいね。",
            "I've brewed some fresh warm tea. Please take a gentle sip and rest your mind."
        ))
        grid.addWidget(btn_tea, 0, 1)

        btn_cheer = QPushButton("📚 「古典部で一緒に！」\n(Study Encouragement)")
        btn_cheer.clicked.connect(lambda: self.play_chitanda_line(
            "古典部で一緒に頑張りましょう！あなたの努力、ずっと応援しています！",
            "Let's study hard together in the Classics Club! I believe in your success with all my heart!"
        ))
        grid.addWidget(btn_cheer, 1, 0)

        btn_mystery = QPushButton("💡 「きっと答えが見つかります」\n(Solve Any Puzzle)")
        btn_mystery.clicked.connect(lambda: self.play_chitanda_line(
            "どんなに難しい問題でも、一緒に考えればきっと答えが見つかります！",
            "No matter how difficult the problem seems, if we think about it together, we will find the answer!"
        ))
        grid.addWidget(btn_mystery, 1, 1)

        layout.addLayout(grid)
        layout.addSpacing(10)

        clip_title = QLabel("🔍 Chitanda's Curious Clipboard Assistant")
        clip_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        clip_title.setStyleSheet("color: #ec4899;")
        layout.addWidget(clip_title)

        clip_desc = QLabel("Copy any text or question to your clipboard, then click below:")
        clip_desc.setStyleSheet("color: #a78bfa; font-size: 11px;")
        layout.addWidget(clip_desc)

        btn_investigate = QPushButton("✨ Deeply Explore & Explain (Curiosity Mode)")
        btn_investigate.clicked.connect(lambda: self.run_clipboard_action("investigate"))
        layout.addWidget(btn_investigate)

        btn_summarize = QPushButton("📄 Sweet & Clear Summary")
        btn_summarize.clicked.connect(lambda: self.run_clipboard_action("summarize"))
        layout.addWidget(btn_summarize)

        btn_polish = QPushButton("✍️ Clean Up & Polish Writing")
        btn_polish.clicked.connect(lambda: self.run_clipboard_action("polish"))
        layout.addWidget(btn_polish)

        layout.addStretch()
        self.tabs.addTab(tab, "💡 Quick Assist")

    def setup_wallpapers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        intro_lbl = QLabel("🖼️ Hyouka & Chitanda Scene Gallery")
        intro_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        intro_lbl.setStyleSheet("color: #ec4899;")
        layout.addWidget(intro_lbl)

        sub_lbl = QLabel("Click any scene to preview or set as your Windows Desktop Wallpaper:")
        sub_lbl.setStyleSheet("color: #a78bfa; font-size: 11px;")
        layout.addWidget(sub_lbl)

        self.wp_preview_lbl = QLabel("Select an image below")
        self.wp_preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wp_preview_lbl.setFixedHeight(160)
        self.wp_preview_lbl.setStyleSheet("background: #0d091a; border: 1px solid #3b2656; border-radius: 8px;")
        layout.addWidget(self.wp_preview_lbl)

        btn_row = QHBoxLayout()
        self.selected_wp_path = None
        self.set_wp_btn = QPushButton("🖥️ Set as My Desktop Wallpaper")
        self.set_wp_btn.setEnabled(False)
        self.set_wp_btn.clicked.connect(self._set_current_wallpaper)
        btn_row.addWidget(self.set_wp_btn)
        layout.addLayout(btn_row)

        self.wp_list = QListWidget()
        self.wp_list.itemClicked.connect(self._on_wallpaper_selected)

        if os.path.exists(WALLPAPER_DIR):
            files = sorted(os.listdir(WALLPAPER_DIR))
            for f in files:
                if f.endswith(('.jpg', '.png')):
                    clean_name = f.replace('.jpg', '').replace('.png', '').replace('_', ' ').title()
                    item = QListWidgetItem(f"🌸 {clean_name}")
                    item.setData(Qt.ItemDataRole.UserRole, os.path.join(WALLPAPER_DIR, f))
                    self.wp_list.addItem(item)

        layout.addWidget(self.wp_list)
        self.tabs.addTab(tab, "🖼️ Wallpapers")

    def _on_wallpaper_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self.selected_wp_path = path
            pix = QPixmap(path).scaled(
                450, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.wp_preview_lbl.setPixmap(pix)
            self.set_wp_btn.setEnabled(True)

    def _set_current_wallpaper(self):
        if self.selected_wp_path and os.path.exists(self.selected_wp_path):
            abs_path = os.path.abspath(self.selected_wp_path)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
            self.character.say("Your desktop wallpaper is set! It looks so wonderful!", voice=self.voice_btn.isChecked())

    def play_chitanda_line(self, ja_text: str, en_text: str):
        is_ja = (self.voice_mode_combo.currentData() == "ja-chitanda")
        spoken = ja_text if is_ja else en_text
        self.character.say(spoken, voice=self.voice_btn.isChecked())
        self.character.trigger_friendly_reaction(3000)

    def toggle_voice(self):
        enabled = self.voice_btn.isChecked()
        self.voice_btn.setText("🔊 ON" if enabled else "🔇 OFF")
        if not enabled:
            self.character.voice_worker.stop_current()

    def clear_chat_history(self):
        self.memory.clear()
        self.chat_display.clear()
        self.chat_display.append(
            "<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> "
            "I've refreshed our conversation history! What are you working on now? I'm so curious!"
        )

    def refresh_task_list(self):
        self.task_list.clear()
        for idx, item in enumerate(self.task_manager.tasks):
            text = item["text"]
            done = item.get("done", False)
            prefix = "✔ " if done else "◻ "
            list_item = QListWidgetItem(f"{prefix}{text}")
            if done:
                list_item.setForeground(Qt.GlobalColor.gray)
            self.task_list.addItem(list_item)

    def add_task(self):
        text = self.task_input.text().strip()
        if text:
            self.task_manager.add_task(text)
            self.memory.add_task(text)
            self.task_input.clear()
            self.refresh_task_list()

    def _on_task_clicked(self, item):
        row = self.task_list.row(item)
        self.task_manager.toggle_task(row)
        self.refresh_task_list()

    def clear_completed_tasks(self):
        # Remove from memory as well
        completed = [t["text"] for t in self.task_manager.tasks if t.get("done", False)]
        for t_text in completed:
            self.memory.remove_task(t_text)
        self.task_manager.clear_completed()
        self.refresh_task_list()

    def start_pomodoro(self, minutes):
        self.pomodoro.start_focus(minutes)
        msg = "25分間、集中して頑張りましょう！応援しています！" if self.voice_mode_combo.currentData() == "ja-chitanda" else "Let's focus with all our energy for 25 minutes! I'm cheering for you!"
        self.character.say(msg, voice=self.voice_btn.isChecked())
        self.character.trigger_friendly_reaction()

    def start_pomodoro_break(self, minutes):
        self.pomodoro.start_break(minutes)
        msg = "休憩の時間ですよ。温かいお茶でも飲んでゆっくりしてくださいね。" if self.voice_mode_combo.currentData() == "ja-chitanda" else "It's break time! Please stretch, relax, and have some warm tea."
        self.character.say(msg, voice=self.voice_btn.isChecked())

    def _update_pomo_display(self, formatted_str, remaining):
        self.pomo_time_label.setText(formatted_str)

    def _on_pomo_done(self, mode):
        if mode == "focus":
            msg = "Focus session completed! You did fantastic work! Please take a 5-minute break now!"
        else:
            msg = "Break is over! Are you ready to continue our goals together?"
        self.character.say(msg, voice=self.voice_btn.isChecked())

    def run_clipboard_action(self, action_type):
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            self.chat_display.append("<span style='color: #ef4444;'>[Chitanda]: Your clipboard is empty. Please copy some text first!</span>")
            self.tabs.setCurrentIndex(0)
            return

        prompts = {
            "investigate": f"I'm very curious about this! Please explore and explain the core ideas and significance clearly:\n\n{text}",
            "summarize": f"Please provide a sweet, elegant, and concise summary of this text highlighting the main takeaways:\n\n{text}",
            "polish": f"Please help me review and polish this writing so that it sounds natural, clear, and well-structured:\n\n{text}"
        }
        self.ask_predefined(prompts[action_type])

    def ask_predefined(self, prompt):
        self.tabs.setCurrentIndex(0)
        self.process_user_prompt(prompt)

    # -------------------------------------------------------------
    # REAL INTENT & COMMAND EXECUTION PARSER
    # -------------------------------------------------------------
    def send_chat_message(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()

        lower = text.lower()

        # 1. EXIT / DISMISS INTENT
        exit_phrases = ["you can go", "go away", "leave", "goodbye", "bye", "exit", "quit", "shut down", "dismiss"]
        if any(p == lower or lower.startswith(p + " ") or lower.endswith(" " + p) for p in exit_phrases):
            self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {text}")
            farewell = "Understood! You've done wonderful work today. Please rest well, and call me back anytime! See you soon!"
            self.chat_display.append(f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {farewell}")
            self.character.say(farewell, voice=self.voice_btn.isChecked())
            QTimer.singleShot(3500, self.character.dismiss_companion)
            return

        # 2. HIDE COMMAND ("hide now", "hide", "only show when it is break time")
        if any(h in lower for h in ["hide now", "only show when it is break", "hide until break", "go invisible", "disappear"]):
            self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {text}")
            reply = "Understood! Going invisible now so nothing distracts you! I'll pop right back up the moment it's break time. Do your best!"
            self.chat_display.append(f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {reply}")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            # Hide both character and chat window
            QTimer.singleShot(3000, self.character.hide_character)
            QTimer.singleShot(3000, self.hide)
            return

        # 3. SHOW / UNHIDE COMMAND
        if any(s in lower for s in ["show yourself", "unhide", "where are you", "come back", "show now"]):
            self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {text}")
            self.character.show_character()
            reply = "I'm right here! How is your study coming along? I'm so curious!"
            self.chat_display.append(f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {reply}")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 4. STUDY / EXAM / TIMER COMMAND WITH BREAK REMINDERS
        is_study_intent = any(w in lower for w in ["study", "gate", "exam", "focus", "remind me"])
        has_time = any(w in lower for w in ["minute", "min", "hour"])
        
        if is_study_intent and has_time:
            # Extract study minutes (default 30)
            study_match = re.search(r'(\d+)\s*(?:minute|min)', lower)
            study_mins = int(study_match.group(1)) if study_match else 30

            # Extract break minutes (default 3)
            break_match = re.search(r'break(?:\s+of)?\s*(?:(\d+)\s*to\s*)?(\d+)\s*(?:minute|min)?', lower)
            if break_match:
                break_mins = int(break_match.group(2)) if break_match.group(2) else 3
            else:
                break_mins = 3

            # Check if user also asked to hide in this message
            should_hide = "hide" in lower

            self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {text}")
            self.character.start_study_cycle(study_minutes=study_mins, break_minutes=break_mins, hide=should_hide)

            if should_hide:
                reply = (f"Understood! I've set a {study_mins}-minute focus session for your preparation with a {break_mins}-minute break. "
                         f"I will quietly hide now so you have zero distractions, and pop back up the second break time arrives! Let's do our best!")
                QTimer.singleShot(3500, self.hide)
            else:
                reply = (f"Understood! I've started your {study_mins}-minute study session with a {break_mins}-minute break. "
                         f"Stay focused, and I will alert you with your break reminder the moment time is up!")

            self.chat_display.append(f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {reply}")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 5. TIMER STATUS QUERY
        if any(q in lower for q in ["how much time left", "time remaining", "timer status"]):
            self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {text}")
            if self.character.study_manager.is_running:
                mins = self.character.study_manager.remaining_seconds // 60
                secs = self.character.study_manager.remaining_seconds % 60
                phase = "study session" if self.character.study_manager.phase == "study" else "break"
                reply = f"You have {mins} minutes and {secs} seconds remaining in your {phase}."
            else:
                reply = "No study timer is currently active. Tell me whenever you would like to start one!"
            self.chat_display.append(f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {reply}")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # 6. STOP TIMER
        if any(s in lower for s in ["stop timer", "cancel timer", "stop study"]):
            self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {text}")
            self.character.study_manager.stop_session()
            reply = "Study timer stopped. Please remember to take a nice rest whenever you need it!"
            self.chat_display.append(f"<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> {reply}")
            self.character.say(reply, voice=self.voice_btn.isChecked())
            return

        # Regular AI query to Ollama
        self.process_user_prompt(text)

    def process_user_prompt(self, user_text):
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.cancel()

        self.chat_display.append(f"<span style='color: #38bdf8; font-weight: bold;'>You:</span> {user_text}")
        self.memory.add_message("user", user_text)

        # Refresh tasks if newly detected in memory
        self.refresh_task_list()

        self.status_label.setText("Curious...")
        self.character.set_thinking(True)
        self.character.bubble.set_streaming_text("I'm curious...")

        model = self.model_combo.currentText()
        messages = self.memory.get_context_messages()

        self.active_worker = OllamaChatWorker(model, messages)
        self.active_worker.token_received.connect(self._on_token)
        self.active_worker.response_finished.connect(self._on_finished)
        self.active_worker.error_occurred.connect(self._on_error)
        self.active_worker.start()

        self._current_reply_accum = []
        self.chat_display.append("<span style='color: #ec4899; font-weight: bold;'>Chitanda:</span> ")

    def _on_token(self, token):
        self._current_reply_accum.append(token)
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_display.setTextCursor(cursor)
        self.character.bubble.set_streaming_text("".join(self._current_reply_accum))

    def _on_finished(self, full_text):
        self.status_label.setText("Listening")
        self.character.set_thinking(False)
        self.memory.add_message("assistant", full_text)
        self.character.bubble.finalize_stream(duration_ms=7000)

        if self.voice_btn.isChecked() and full_text:
            self.character.voice_worker.speak(full_text)

    def _on_error(self, err):
        self.status_label.setText("Error")
        self.character.set_thinking(False)
        self.chat_display.append(f"<span style='color: #ef4444;'>[Error]: {err}</span>")
        self.character.say("I'm sorry, I couldn't reach Ollama. Please make sure Ollama is running!", voice=False)
