import os
import time
import math
import random
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QRadialGradient,
    QPen, QBrush, QFont, QPixmap, QImage, QGuiApplication,
    QIcon
)
from PySide6.QtWidgets import QWidget, QMenu, QApplication, QSystemTrayIcon

from bubble import SpeechBubble
from voice import VoiceSpeakerThread
from work_tools import StudySessionManager

UNIFORM_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_uniform.png")
CURIOUS_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_curious.png")
CASUAL_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_casual.png")
YUKATA_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_yukata.png")
OREKI_SPRITE = os.path.join(os.path.dirname(__file__), "oreki_crisp.png")

CHITANDA_QUOTES = [
    "I'm curious! (私、気になります！) Please tell me what you are working on!",
    "Let's do our very best today! I know you can accomplish all your goals!",
    "Don't worry, even difficult problems have an answer if we look closely together!",
    "Are we studying for your exams today? I'll be right here cheering you on!",
    "Remember to drink plenty of water and rest your eyes. Your health is so important!"
]

CHITANDA_AMBIENT_THOUGHTS = [
    "I'm curious... how is your study session progressing?",
    "You're working so hard today! Please remember to take a short break if you feel tired.",
    "The Classic Literature Club is always peaceful, but studying with you is so exciting!",
    "Would you like some warm tea? Staying refreshed helps keep your mind clear!",
    "Don't forget to check your daily task list! We can finish them one step at a time!"
]

class KingCharacter(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Proportions: width 130, height 220
        self.size_mode = "medium"
        self.widget_width = 130
        self.widget_height = 220
        self.resize(self.widget_width, self.widget_height)

        # Sprites dictionary
        self.sprites = {}
        self.active_outfit = "uniform"  # "uniform", "curious", "casual", "yukata"
        self.load_all_sprites()

        # Voice & Speech Bubble
        self.voice_worker = VoiceSpeakerThread()
        self.voice_worker.start()

        self.bubble = SpeechBubble(self)

        # Study Session Manager
        self.study_manager = StudySessionManager()
        self.study_manager.tick.connect(self._on_study_tick)
        self.study_manager.study_completed.connect(self._on_study_completed)
        self.study_manager.break_completed.connect(self._on_break_completed)

        # Interactive & Animation States
        self.animation_step = 0.0
        self.drag_position = None
        self.is_thinking = False
        self.is_active_reaction = False
        self.is_hidden_by_user = False

        # States: "STAND", "WALK", "CURIOUS", "SLEEP"
        self.current_state = "STAND"
        self.walk_direction = 1
        self.walk_speed = 1.0
        self.walk_ticks_remaining = 0
        self.walk_footstep = 0.0
        self.last_interaction_time = time.time()
        self.sleep_zzz_timer = 0.0
        self.ambient_enabled = True

        # State decision timer
        self.idle_decision_timer = QTimer(self)
        self.idle_decision_timer.timeout.connect(self._decide_next_idle_action)
        self.idle_decision_timer.start(5000)

        # Ambient thoughts timer (every 10 minutes)
        self.ambient_timer = QTimer(self)
        self.ambient_timer.timeout.connect(self._pop_ambient_thought)
        self.ambient_timer.start(10 * 60 * 1000)

        # Reaction reset timer
        self.reaction_reset_timer = QTimer(self)
        self.reaction_reset_timer.setSingleShot(True)
        self.reaction_reset_timer.timeout.connect(self._end_reaction)

        # Animation loop
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(33)

        self.chat_window = None

        # Setup System Tray Icon
        self.tray_icon = QSystemTrayIcon(self)
        if "uniform" in self.sprites and self.sprites["uniform"][0]:
            self.tray_icon.setIcon(QIcon(self.sprites["uniform"][0]))
        self.tray_icon.setToolTip("Eru Chitanda - Study Companion")
        self._setup_tray_menu()
        self.tray_icon.show()

    def load_all_sprites(self):
        target_h = self.widget_height - 35
        target_w = self.widget_width - 16

        paths = {
            "uniform": UNIFORM_SPRITE,
            "curious": CURIOUS_SPRITE,
            "casual": CASUAL_SPRITE,
            "yukata": YUKATA_SPRITE,
            "oreki": OREKI_SPRITE
        }

        for outfit_name, path in paths.items():
            if os.path.exists(path):
                img = QImage(path)
                if not img.isNull():
                    scaled = img.scaled(
                        target_w, target_h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    pix_right = QPixmap.fromImage(scaled)
                    pix_left = QPixmap.fromImage(scaled.mirrored(True, False))
                    self.sprites[outfit_name] = (pix_right, pix_left)

    def set_outfit(self, outfit_name: str):
        if outfit_name in self.sprites:
            self.active_outfit = outfit_name
            self.update()

    def set_size_mode(self, mode: str):
        self.size_mode = mode
        if mode == "compact":
            self.widget_width, self.widget_height = 100, 180
        elif mode == "large":
            self.widget_width, self.widget_height = 160, 280
        else:  # medium
            self.widget_width, self.widget_height = 130, 220

        self.resize(self.widget_width, self.widget_height)
        self.load_all_sprites()
        self.bubble.update_position()
        self.update()

    def _setup_tray_menu(self):
        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #1e1b4b;
                color: #fdf2f8;
                border: 1px solid #ec4899;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ec4899;
                color: white;
                font-weight: bold;
            }
        """)

        action_show = tray_menu.addAction("🌸 Show Chitanda")
        action_chat = tray_menu.addAction("💬 Open Conversation")
        action_study_status = tray_menu.addAction("⏱️ Study Session Info")
        tray_menu.addSeparator()
        action_quit = tray_menu.addAction("👋 Say Goodbye (Exit)")

        action_show.triggered.connect(self.show_character)
        action_chat.triggered.connect(self.open_chat)
        action_study_status.triggered.connect(self._show_study_status)
        action_quit.triggered.connect(self.dismiss_companion)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible():
                self.open_chat()
            else:
                self.show_character()

    def _show_study_status(self):
        if self.study_manager.is_running:
            mins = self.study_manager.remaining_seconds // 60
            secs = self.study_manager.remaining_seconds % 60
            phase = "Study Focus" if self.study_manager.phase == "study" else "Break Time"
            msg = f"{phase}: {mins:02d}m {secs:02d}s remaining."
        else:
            msg = "No active study session right now. Tell me whenever you want to begin!"
        self.tray_icon.showMessage("Study Status", msg, QSystemTrayIcon.MessageIcon.Information, 4000)

    def hide_character(self):
        self.is_hidden_by_user = True
        self.bubble.hide()
        self.hide()
        self.tray_icon.showMessage(
            "Chitanda is quiet",
            "I'm keeping quiet so you can focus completely! I will pop back up with your break reminder!",
            QSystemTrayIcon.MessageIcon.Information,
            3500
        )

    def show_character(self):
        self.is_hidden_by_user = False
        self.wake_up()
        self.show()
        self.raise_()
        self.activateWindow()

    def start_study_cycle(self, study_minutes=30, break_minutes=3, hide=True):
        self.study_manager.start_session(
            study_minutes=study_minutes,
            break_minutes=break_minutes,
            hide_character=hide
        )
        if hide:
            QTimer.singleShot(3200, self.hide_character)

    def _on_study_tick(self, time_str, remaining_secs, phase):
        status = f"Chitanda | {'Studying' if phase == 'study' else 'Break'}: {time_str}"
        self.tray_icon.setToolTip(status)
        if self.chat_window:
            self.chat_window._update_study_timer_display(time_str, remaining_secs, phase)

    def _on_study_completed(self):
        self.show_character()
        alert_msg = "30 minutes of study are finished! You worked so hard! Please take your 3-minute break now and stretch!"
        self.say(alert_msg, voice=True)
        self.trigger_friendly_reaction(5000)
        self.tray_icon.showMessage(
            "🎉 Break Time!",
            "30 minutes of deep study completed! Take 3 minutes to relax!",
            QSystemTrayIcon.MessageIcon.Information,
            8000
        )

    def _on_break_completed(self):
        self.show_character()
        msg = "Your break has ended! Are you ready for another 30-minute study session, or should we rest for today?"
        self.say(msg, voice=True)
        self.tray_icon.showMessage(
            "☕ Break Completed",
            "Break time is finished! Ready to begin the next study block?",
            QSystemTrayIcon.MessageIcon.Information,
            6000
        )

    def get_time_appropriate_greeting(self):
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Good morning! It's a brand new day! I'm so curious to see what we will learn together today!"
        elif 12 <= hour < 17:
            return "Good afternoon! How is your day going? Let me know if you'd like to study or check on your tasks!"
        elif 17 <= hour < 23:
            return "Good evening! You've done wonderful work today! Shall we wrap up our remaining goals?"
        else:
            return "It's getting very late! Please make sure not to push yourself too hard. Resting well is so important!"

    def _pop_ambient_thought(self):
        if not self.ambient_enabled or self.is_thinking or not self.isVisible():
            return
        idle_seconds = time.time() - self.last_interaction_time
        if idle_seconds < 120 and (not self.chat_window or not self.chat_window.isVisible()):
            thought = random.choice(CHITANDA_AMBIENT_THOUGHTS)
            self.bubble.show_message(thought, duration_ms=6500)

    def _decide_next_idle_action(self):
        if self.drag_position is not None or self.is_thinking or not self.isVisible():
            return

        idle_seconds = time.time() - self.last_interaction_time

        if idle_seconds > 60:
            self.current_state = "SLEEP"
            self.idle_decision_timer.setInterval(8000)
            return

        choices = ["STAND", "WALK", "CURIOUS"]
        weights = [0.35, 0.40, 0.25]
        new_state = random.choices(choices, weights=weights)[0]

        if new_state == "WALK":
            self.current_state = "WALK"
            self.walk_direction = random.choice([-1, 1])
            self.walk_ticks_remaining = random.randint(60, 140)
            self.idle_decision_timer.setInterval(random.randint(4000, 7000))
        elif new_state == "CURIOUS":
            self.current_state = "CURIOUS"
            self.idle_decision_timer.setInterval(random.randint(6000, 12000))
        else:
            self.current_state = "STAND"
            self.idle_decision_timer.setInterval(random.randint(5000, 9000))

    def _tick(self):
        self.animation_step += 0.06
        self.sleep_zzz_timer += 0.05

        if self.current_state == "WALK" and self.drag_position is None and not self.is_thinking and self.isVisible():
            self.walk_ticks_remaining -= 1
            self.walk_footstep += 0.25

            screen = QGuiApplication.primaryScreen().availableGeometry()
            new_x = self.x() + int(self.walk_direction * self.walk_speed)

            if new_x < 15:
                new_x = 15
                self.walk_direction = 1
            elif new_x > screen.width() - self.widget_width - 15:
                new_x = screen.width() - self.widget_width - 15
                self.walk_direction = -1

            self.move(new_x, self.y())

            if self.walk_ticks_remaining <= 0:
                self.current_state = "STAND"

        if self.isVisible():
            self.bubble.update_position()
            self.update()

    def _end_reaction(self):
        self.is_active_reaction = False
        self.update()

    def wake_up(self):
        self.last_interaction_time = time.time()
        self.current_state = "STAND"
        self.update()

    def set_thinking(self, thinking: bool):
        self.is_thinking = thinking
        if thinking:
            self.wake_up()
        self.update()

    def trigger_friendly_reaction(self, duration_ms=2500):
        self.wake_up()
        self.is_active_reaction = True
        self.reaction_reset_timer.start(duration_ms)
        self.update()

    def say(self, message: str, voice=True):
        self.wake_up()
        self.bubble.show_message(message, duration_ms=6500)
        if voice:
            self.voice_worker.speak(message)

    def open_chat(self):
        self.wake_up()
        if self.chat_window:
            self.chat_window.show()
            self.chat_window.raise_()
            self.chat_window.activateWindow()

    def dismiss_companion(self):
        self.voice_worker.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self.current_state == "WALK":
            float_y = math.sin(self.walk_footstep) * 2.0
        elif self.current_state in ["CURIOUS", "SLEEP"]:
            float_y = math.sin(self.animation_step * 0.8) * 1.8
        else:
            float_y = math.sin(self.animation_step) * 2.8

        # --- SPARKLING CURIOSITY AURA (Blooming pink/purple gradient) ---
        if self.is_thinking or self.is_active_reaction or self.current_state == "CURIOUS":
            pulse = (math.sin(self.animation_step * 2.5) + 1.0) / 2.0
            radius = (self.widget_width // 2) + pulse * 14
            glow_grad = QRadialGradient(self.widget_width // 2, 95 + float_y, radius)
            glow_grad.setColorAt(0.0, QColor(236, 72, 153, int(90 + pulse * 60)))  # Pink
            glow_grad.setColorAt(0.6, QColor(168, 85, 247, int(35 + pulse * 35)))  # Purple
            glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

            painter.setBrush(QBrush(glow_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(self.widget_width // 2 - radius),
                int(95 + float_y - radius),
                int(radius * 2),
                int(radius * 2)
            )

        # Floor shadow
        shadow_w = int(self.widget_width * 0.65) - int(float_y * 1.0)
        shadow_h = 10
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int((self.widget_width - shadow_w) / 2),
            int(self.widget_height - 24 + float_y * 0.3),
            shadow_w,
            shadow_h
        )

        # Sprite Selection
        outfit_key = self.active_outfit
        if self.current_state == "CURIOUS" and "curious" in self.sprites:
            outfit_key = "curious"

        sprite_pair = self.sprites.get(outfit_key, self.sprites.get("uniform"))
        if sprite_pair:
            pix = sprite_pair[1] if (self.current_state == "WALK" and self.walk_direction < 0) else sprite_pair[0]
            if pix and not pix.isNull():
                draw_x = (self.widget_width - pix.width()) // 2
                draw_y = int(8 + float_y)
                painter.drawPixmap(draw_x, draw_y, pix)

        # Sleeping Zzz
        if self.current_state == "SLEEP":
            painter.setPen(QColor(236, 72, 153, 230))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            zzz_y1 = int(24 - (self.sleep_zzz_timer * 12) % 24)
            zzz_y2 = int(14 - ((self.sleep_zzz_timer + 0.5) * 12) % 24)
            painter.drawText(self.widget_width - 34, zzz_y1, "z")
            painter.drawText(self.widget_width - 24, zzz_y2, "Z")

        # Name badge
        badge_y = int(self.widget_height - 20 + float_y * 0.3)
        painter.setBrush(QColor(24, 18, 43, 235))
        painter.setPen(QPen(QColor("#ec4899"), 1.0))
        badge_rect = QRectF(self.widget_width // 2 - 44, badge_y, 88, 16)
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(QColor("#fdf2f8"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        status_text = "💤 SLEEP" if self.current_state == "SLEEP" else ("✨ CURIOUS" if self.current_state == "CURIOUS" else "🌸 CHITANDA")
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, status_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.trigger_friendly_reaction(2000)

    def mouseMoveEvent(self, event):
        if self.drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            self.bubble.update_position()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_chat()

    def contextMenuEvent(self, event):
        self.wake_up()
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1b4b;
                color: #fdf2f8;
                border: 1px solid #ec4899;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ec4899;
                color: white;
                font-weight: bold;
            }
        """)

        action_chat = menu.addAction("💬 Talk with Chitanda")
        action_pomo = menu.addAction("⏱️ 30m Study & Break Session")
        action_clip = menu.addAction("🔍 Ask Chitanda About Clipboard")
        action_curious = menu.addAction("✨ 「私、気になります！」 (I'm Curious!)")
        action_hide = menu.addAction("🙈 Hide Chitanda (Quiet Study)")

        # Outfit & Character submenu
        outfit_menu = menu.addMenu("👗 Change Outfit / Character")
        act_unif = outfit_menu.addAction("🌸 School Sailor Uniform (Chitanda)")
        act_cur = outfit_menu.addAction("✨ Curious Leaning Pose (Chitanda)")
        act_cas = outfit_menu.addAction("👒 Summer Casual Sundress (Chitanda)")
        act_yuk = outfit_menu.addAction("🎆 Festival Yukata (Chitanda)")
        outfit_menu.addSeparator()
        act_oreki = outfit_menu.addAction("🍵 Houtarou Oreki (Energy Saver)")

        # Size submenu
        size_menu = menu.addMenu("📏 Character Size")
        action_compact = size_menu.addAction("Compact (100px)")
        action_medium = size_menu.addAction("Medium (130px - Recommended)")
        action_large = size_menu.addAction("Large (160px)")

        ambient_label = "🔔 Ambient Thoughts: ON" if self.ambient_enabled else "🔕 Ambient Thoughts: OFF"
        action_ambient = menu.addAction(ambient_label)

        menu.addSeparator()
        action_exit = menu.addAction("👋 Say Goodbye (Exit)")

        action = menu.exec(event.globalPos())

        if action == action_chat:
            self.open_chat()
        elif action == action_pomo:
            if self.chat_window:
                self.chat_window._start_custom_study(30, 3, hide=True)
        elif action == action_clip:
            if self.chat_window:
                self.open_chat()
                self.chat_window.run_clipboard_action("summarize")
        elif action == action_curious:
            self.say("私、気になります！ (I'm curious! Please tell me what you are working on!)", voice=True)
            self.trigger_friendly_reaction(3000)
        elif action == action_hide:
            self.hide_character()
        elif action == act_unif:
            self.set_outfit("uniform")
        elif action == act_cur:
            self.set_outfit("curious")
        elif action == act_cas:
            self.set_outfit("casual")
        elif action == act_yuk:
            self.set_outfit("yukata")
        elif action == act_oreki:
            self.set_outfit("oreki")
        elif action == action_compact:
            self.set_size_mode("compact")
        elif action == action_medium:
            self.set_size_mode("medium")
        elif action == action_large:
            self.set_size_mode("large")
        elif action == action_ambient:
            self.ambient_enabled = not self.ambient_enabled
        elif action == action_exit:
            self.say("Goodbye! Let's do our best again tomorrow! See you soon!", voice=True)
            QTimer.singleShot(2500, self.dismiss_companion)

    def closeEvent(self, event):
        self.voice_worker.stop()
        super().closeEvent(event)
