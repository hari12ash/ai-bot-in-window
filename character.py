import os
import time
import math
import random
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, QUrl, QEvent
from PySide6.QtGui import (
    QColor, QPainter, QRadialGradient,
    QPen, QBrush, QFont, QPixmap, QImage, QGuiApplication,
    QIcon, QCursor, QPainterPath
)
from PySide6.QtWidgets import QWidget, QMenu, QApplication, QSystemTrayIcon
from PySide6.QtWebEngineWidgets import QWebEngineView

from bubble import SpeechBubble
from voice import VoiceSpeakerThread
from work_tools import StudySessionManager
from laptop_control import LaptopController
from smart_tools import ReminderManager

UNIFORM_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_uniform.png")
CURIOUS_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_curious.png")
CASUAL_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_casual.png")
WINTER_SPRITE = os.path.join(os.path.dirname(__file__), "chitanda_winter.png")
OREKI_SPRITE = os.path.join(os.path.dirname(__file__), "oreki_crisp.png")

CHITANDA_QUOTES = [
    "I'm curious! (私、気になります！) Tell me whatever is on your mind!",
    "I hope you're having a wonderful and peaceful day!",
    "I'm always right here by your side whenever you need a hand or want to chat!",
    "Remember to stay hydrated and take a nice deep breath!",
    "It's really nice spending time with you on your desktop!"
]

CHITANDA_PROACTIVE_QUESTIONS = [
    "I'm curious! (私、気になります！) How is your day going so far?",
    "Is there anything interesting happening today? I'd love to hear about it!",
    "Just checking in to say hi! How are you feeling right now?",
    "If you need anything or just want to chat, I'm always right here!",
    "I hope everything is going smoothly with whatever you're doing!",
    "Would you like to take a quick pause and enjoy a warm drink?",
    "What's your favorite thing to do when you want to relax?",
    "I'm curious—have you seen any fun or interesting things lately?",
    "Remember to take good care of yourself and rest your eyes whenever you need to!",
    "I'm really glad to be here keeping you company!"
]

CHITANDA_AMBIENT_THOUGHTS = [
    "I hope you're having a lovely day!",
    "Take a breath and relax your shoulders for a moment~",
    "It's so peaceful hanging out together on your desktop.",
    "Remember to stay hydrated with some water or warm tea!",
    "I'm right here whenever you want to talk!"
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

        # Proportions: width 145, height 240 (crisp high-DPI anime presentation)
        self.size_mode = "medium"
        self.widget_width = 145
        self.widget_height = 240
        self.resize(self.widget_width, self.widget_height)

        # Sprites dictionary
        self.sprites = {}
        self.active_outfit = "uniform"  # "uniform", "curious", "casual", "winter", "oreki"
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

        # Persistent Reminders Manager (Survives Restarts)
        self.reminder_manager = ReminderManager(character=self)

        # Interactive & Animation States
        self.animation_step = 0.0
        self.drag_position = None
        self.press_global_pos = None
        self.is_dragging = False
        self.last_release_time = 0.0
        self.is_thinking = False
        self.is_active_reaction = False
        self.is_hidden_by_user = False

        # Facial & Eye Animation State
        self.talk_step = 0.0
        self.blink_timer = 0
        self.blink_duration = 0
        self.is_blinking = False
        self.blink_phase = 0.0
        self.next_blink_in = random.randint(90, 160)

        # Interactive cursor look-at
        self.look_offset_x = 0.0
        self.look_offset_y = 0.0
        self.head_tilt = 0.0

        # Dynamic Particles (Sakura petals & star sparkles)
        self.particles = []

        # States: "STAND", "WALK", "CURIOUS", "SLEEP"
        self.current_state = "WALK"
        self.walk_direction = random.choice([-1, 1])
        self.walk_speed = 1.8
        self.walk_pos_accumulator = 0.0
        self.walk_ticks_remaining = random.randint(120, 240)
        self.walk_footstep = 0.0
        self.last_interaction_time = time.time()
        self.sleep_zzz_timer = 0.0
        self.ambient_enabled = True

        # State decision timer (evaluates every 3.5 seconds)
        self.idle_decision_timer = QTimer(self)
        self.idle_decision_timer.timeout.connect(self._decide_next_idle_action)
        self.idle_decision_timer.start(3500)

        # Proactive Friendly Check-in Timer (occasional, non-intrusive, silent bubble)
        self.question_timer = QTimer(self)
        self.question_timer.timeout.connect(self._ask_proactive_question)
        self.question_timer.start(600 * 1000)  # Gentle check-in after 10 minutes

        # Reaction reset timer
        self.reaction_reset_timer = QTimer(self)
        self.reaction_reset_timer.setSingleShot(True)
        self.reaction_reset_timer.timeout.connect(self._end_reaction)

        # Animation loop (30 FPS smooth rendering)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(33)

        self.chat_window = None

        # Render Mode: "2D" (Authentic Kyoto Animation Sprites) by default
        self.render_mode = "2D"

        # Embedded WebGL 3D Mascot View (Optional secondary mode)
        self.web_view = QWebEngineView(self)
        self.web_view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mascot_3d.html"))
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))
        self.web_view.resize(self.widget_width, self.widget_height)
        self.web_view.installEventFilter(self)
        self.web_view.hide()

        # Setup System Tray Icon
        self.tray_icon = QSystemTrayIcon(self)
        if "uniform" in self.sprites and self.sprites["uniform"][0]:
            self.tray_icon.setIcon(QIcon(self.sprites["uniform"][0]))
        self.tray_icon.setToolTip("Eru Chitanda - Desktop AI Companion")
        self._setup_tray_menu()
        self.tray_icon.show()

    def load_all_sprites(self):
        target_h = self.widget_height - 35
        target_w = self.widget_width - 16

        paths = {
            "uniform": UNIFORM_SPRITE,
            "curious": CURIOUS_SPRITE,
            "casual": CASUAL_SPRITE,
            "winter": WINTER_SPRITE,
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
        if hasattr(self, "web_view"):
            self.web_view.resize(self.widget_width, self.widget_height)
        self.load_all_sprites()
        self.bubble.update_position()
        self.update()

    def set_render_mode(self, mode: str):
        self.render_mode = mode
        if mode == "3D":
            self.web_view.show()
            self._sync_3d_state()
        else:
            self.web_view.hide()
        self.update()

    def _sync_3d_state(self):
        if self.render_mode == "3D" and hasattr(self, "web_view"):
            state_to_send = self.current_state
            if self.is_thinking or self.is_active_reaction:
                state_to_send = "CURIOUS"
            self.web_view.page().runJavaScript(f"window.setMascotState('{state_to_send}')")

    def eventFilter(self, obj, event):
        if hasattr(self, "web_view") and obj == self.web_view:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.press_global_pos = event.globalPosition().toPoint()
                    self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    self.is_dragging = False
                    self.trigger_friendly_reaction(1500)
                    return True
                elif event.button() == Qt.MouseButton.RightButton:
                    self.contextMenuEvent(event)
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if self.press_global_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
                    delta = (event.globalPosition().toPoint() - self.press_global_pos).manhattanLength()
                    if delta > 7:
                        self.is_dragging = True
                        new_pos = event.globalPosition().toPoint() - self.drag_position
                        self.move(new_pos)
                        self.bubble.update_position()
                        return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    now = time.time()
                    if not self.is_dragging:
                        if now - self.last_release_time < 0.42:
                            self.open_chat()
                            self.last_release_time = 0.0
                        else:
                            self.last_release_time = now
                    else:
                        self.last_release_time = 0.0
                    self.press_global_pos = None
                    self.drag_position = None
                    self.is_dragging = False
                    return True
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.open_chat()
                    return True
        return super().eventFilter(obj, event)

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
            return "Good morning! I hope you have a wonderful and pleasant day!"
        elif 12 <= hour < 17:
            return "Good afternoon! How is your day going? I'm here if you'd like to chat!"
        elif 17 <= hour < 23:
            return "Good evening! It was lovely spending time today. How are you feeling?"
        else:
            return "It's getting late! Please make sure to get plenty of rest tonight!"

    def _pop_ambient_thought(self):
        if not self.ambient_enabled or self.is_thinking or not self.isVisible():
            return
        idle_seconds = time.time() - self.last_interaction_time
        if idle_seconds < 120 and (not self.chat_window or not self.chat_window.isVisible()):
            thought = random.choice(CHITANDA_AMBIENT_THOUGHTS)
            self.bubble.show_message(thought, duration_ms=6500)

    def _ask_proactive_question(self):
        # Do not talk unprompted or speak out loud aimlessly
        if not self.ambient_enabled or self.is_thinking or not self.isVisible():
            return
        # If quiet study mode is active, don't interrupt
        if self.study_manager.is_running and self.study_manager.phase == "study":
            return
        # If chat window is open, let the user chat uninterrupted
        if self.chat_window and self.chat_window.isVisible():
            return

        # Do NOT speak out loud unsolicited (voice=False). Only show a brief, gentle silent bubble.
        self.wake_up()
        self.current_state = "CURIOUS"
        self.walk_ticks_remaining = 0
        question = random.choice(CHITANDA_PROACTIVE_QUESTIONS)
        self.say(question, voice=False)
        self.trigger_friendly_reaction(4000)

        # Re-arm question timer with very relaxed delay (10 to 18 minutes)
        next_delay = random.randint(600, 1080) * 1000
        self.question_timer.setInterval(next_delay)

    def _decide_next_idle_action(self):
        if self.drag_position is not None or self.is_thinking or not self.isVisible():
            return

        idle_seconds = time.time() - self.last_interaction_time

        # Only sleep if idle for over 20 minutes with high probability of waking up
        if idle_seconds > 1200:
            if random.random() < 0.5:
                self.current_state = "SLEEP"
                self.idle_decision_timer.setInterval(8000)
                return

        # High probability to WALK (she is lively and explores your screen!)
        choices = ["WALK", "WALK", "CURIOUS", "STAND"]
        weights = [0.55, 0.20, 0.15, 0.10]
        new_state = random.choices(choices, weights=weights)[0]

        if new_state == "WALK":
            self.current_state = "WALK"
            screen = QGuiApplication.primaryScreen().availableGeometry()
            # Turn toward center if getting too close to edges
            if self.x() < 100:
                self.walk_direction = 1
            elif self.x() > screen.width() - self.widget_width - 100:
                self.walk_direction = -1
            else:
                self.walk_direction = random.choice([-1, 1])

            self.walk_ticks_remaining = random.randint(120, 260)  # 4 to 8.5 seconds of smooth walking
            self.idle_decision_timer.setInterval(random.randint(4500, 9000))
        elif new_state == "CURIOUS":
            self.current_state = "CURIOUS"
            self.idle_decision_timer.setInterval(random.randint(4000, 7500))
        else:
            self.current_state = "STAND"
            self.idle_decision_timer.setInterval(random.randint(3000, 6000))

        self._sync_3d_state()

    def _tick(self):
        self.animation_step += 0.06
        self.sleep_zzz_timer += 0.05

        # Update Talk animation when voice is playing
        if self.voice_worker.is_speaking:
            self.talk_step += 0.28
        else:
            self.talk_step = 0.0

        # Update Blinking logic
        if self.current_state != "SLEEP":
            self.blink_timer += 1
            if not self.is_blinking and self.blink_timer >= self.next_blink_in:
                self.is_blinking = True
                self.blink_duration = 6  # 6 frames (~180 ms)
                self.blink_timer = 0
                self.next_blink_in = random.randint(85, 155)

            if self.is_blinking:
                self.blink_duration -= 1
                t = 1.0 - (self.blink_duration / 6.0)
                self.blink_phase = 1.0 - abs(t - 0.5) * 2.0
                if self.blink_duration <= 0:
                    self.is_blinking = False
                    self.blink_phase = 0.0
        else:
            self.is_blinking = True
            self.blink_phase = 1.0

        # Check due reminders periodically (~every 3 seconds)
        if int(self.animation_step * 10) % 30 == 0:
            self.reminder_manager.check_due()

        # Interactive Mouse Cursor tracking (Gaze & Head Tilt)
        cursor_pos = QCursor.pos()
        center_x = self.x() + self.widget_width / 2
        center_y = self.y() + self.widget_height * 0.25
        target_dx = max(-1.0, min(1.0, (cursor_pos.x() - center_x) / 380.0))
        target_dy = max(-1.0, min(1.0, (cursor_pos.y() - center_y) / 300.0))
        self.look_offset_x += (target_dx * 3.2 - self.look_offset_x) * 0.12
        self.look_offset_y += (target_dy * 2.2 - self.look_offset_y) * 0.12
        self.head_tilt += (target_dx * 2.5 - self.head_tilt) * 0.10

        # 3D Head and Eye Tracking toward cursor (if in 3D mode)
        if self.render_mode == "3D" and hasattr(self, "web_view") and self.isVisible():
            self.web_view.page().runJavaScript(f"window.setTargetLook({target_dx:.2f}, {target_dy:.2f})")

        # Particle System (Sakura petals & star sparkles)
        is_energetic = (self.is_thinking or self.is_active_reaction or self.current_state == "CURIOUS")
        if is_energetic and random.random() < 0.38 and len(self.particles) < 22:
            self.particles.append({
                "x": random.uniform(15, self.widget_width - 15),
                "y": self.widget_height - random.uniform(25, 55),
                "vx": random.uniform(-0.6, 0.6),
                "vy": -random.uniform(1.2, 2.2),
                "rot": random.uniform(0, 360),
                "vrot": random.uniform(-4, 4),
                "size": random.uniform(7, 12),
                "alpha": 1.0,
                "type": random.choice(["sakura", "sparkle", "star"])
            })

        # Walking footstep sparkle puffs
        if self.current_state == "WALK" and abs(math.sin(self.walk_footstep * 2.0)) < 0.15 and len(self.particles) < 22:
            self.particles.append({
                "x": (self.widget_width // 2) - self.walk_direction * 12 + random.uniform(-5, 5),
                "y": self.widget_height - 24,
                "vx": -self.walk_direction * random.uniform(0.3, 0.8),
                "vy": -random.uniform(0.4, 0.9),
                "rot": random.uniform(0, 360),
                "vrot": random.uniform(-3, 3),
                "size": random.uniform(5, 8),
                "alpha": 0.85,
                "type": "sparkle"
            })

        for p in self.particles[:]:
            p["x"] += p["vx"] + math.sin(self.animation_step + p["rot"]) * 0.3
            p["y"] += p["vy"]
            p["rot"] += p["vrot"]
            p["alpha"] -= 0.02
            if p["alpha"] <= 0 or p["y"] < 0:
                self.particles.remove(p)

        if self.current_state == "WALK" and self.drag_position is None and not self.is_thinking and self.isVisible():
            self.walk_ticks_remaining -= 1
            self.walk_footstep += 0.22

            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.walk_pos_accumulator += self.walk_direction * self.walk_speed
            step = int(self.walk_pos_accumulator)

            if step != 0:
                self.walk_pos_accumulator -= step
                new_x = self.x() + step

                if new_x < 20:
                    new_x = 20
                    self.walk_direction = 1
                elif new_x > screen.width() - self.widget_width - 20:
                    new_x = screen.width() - self.widget_width - 20
                    self.walk_direction = -1

                self.move(new_x, self.y())

            if self.walk_ticks_remaining <= 0:
                self.current_state = "STAND"
                self._sync_3d_state()

        if self.isVisible():
            self.bubble.update_position()
            self.update()

    def _end_reaction(self):
        self.is_active_reaction = False
        self._sync_3d_state()
        self.update()

    def wake_up(self):
        self.last_interaction_time = time.time()
        self.current_state = "STAND"
        self._sync_3d_state()
        self.update()

    def set_thinking(self, thinking: bool):
        self.is_thinking = thinking
        if thinking:
            self.wake_up()
        self._sync_3d_state()
        self.update()

    def trigger_friendly_reaction(self, duration_ms=2500):
        self.wake_up()
        self.is_active_reaction = True
        self.reaction_reset_timer.start(duration_ms)
        self._sync_3d_state()
        self.update()

    def say(self, message: str, voice=True):
        self.wake_up()
        self.bubble.show_message(message, duration_ms=6500)
        if voice:
            self.voice_worker.speak(message)

    def open_chat(self):
        self.wake_up()
        if self.chat_window:
            if hasattr(self.chat_window, "show_near_mascot"):
                self.chat_window.show_near_mascot(self)
            else:
                self.chat_window.showNormal()
                self.chat_window.raise_()
                self.chat_window.activateWindow()

    def dismiss_companion(self):
        self.voice_worker.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def paintEvent(self, event):
        # When in 3D WebGL mode, Three.js handles the full rendering inside web_view
        if self.render_mode == "3D":
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Walk gait bounce, curiosity lean, and breathing physics
        squash_x, squash_y = 1.0, 1.0
        if self.current_state == "WALK":
            float_y = -abs(math.sin(self.walk_footstep * 2.0)) * 6.0
            tilt_deg = math.sin(self.walk_footstep) * 3.5 * (1 if self.walk_direction > 0 else -1)
            squash_x = 1.0 - math.sin(self.walk_footstep * 2.0) * 0.03
            squash_y = 1.0 + math.sin(self.walk_footstep * 2.0) * 0.03
        elif self.current_state == "CURIOUS":
            float_y = -3.5 + math.sin(self.animation_step * 1.5) * 1.6
            tilt_deg = math.sin(self.animation_step) * 1.2
            squash_x = 1.02
            squash_y = 0.98
        elif self.current_state == "SLEEP":
            float_y = math.sin(self.animation_step * 0.6) * 1.8
            tilt_deg = 2.8
        else: # STAND
            float_y = math.sin(self.animation_step * 1.4) * 2.4
            tilt_deg = self.head_tilt
            squash_x = 1.0 - math.sin(self.animation_step * 1.4) * 0.015
            squash_y = 1.0 + math.sin(self.animation_step * 1.4) * 0.015

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
        shadow_w = int(self.widget_width * 0.65) - int(float_y * 1.5)
        shadow_h = 10
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int((self.widget_width - shadow_w) / 2),
            int(self.widget_height - 24 + float_y * 0.25),
            shadow_w,
            shadow_h
        )

        # Sprite Selection
        outfit_key = self.active_outfit
        if self.current_state == "CURIOUS" and "curious" in self.sprites:
            outfit_key = "curious"

        sprite_pair = self.sprites.get(outfit_key, self.sprites.get("uniform"))
        if sprite_pair:
            facing_left = (self.current_state == "WALK" and self.walk_direction < 0)
            pix = sprite_pair[1] if facing_left else sprite_pair[0]
            if pix and not pix.isNull():
                painter.save()
                pivot_x = self.widget_width / 2
                pivot_y = self.widget_height - 20
                painter.translate(pivot_x, pivot_y)
                painter.rotate(tilt_deg)
                painter.scale(squash_x, squash_y)
                painter.translate(-pivot_x, -pivot_y)

                draw_x = (self.widget_width - pix.width()) // 2
                draw_y = int(8 + float_y)
                painter.drawPixmap(draw_x, draw_y, pix)

                # --- ANIMATED FACIAL FEATURES OVERLAY ---
                norm_eye_x = (1.0 - 0.55) if facing_left else 0.55
                eye_center_x = draw_x + pix.width() * norm_eye_x + self.look_offset_x
                eye_center_y = draw_y + pix.height() * 0.175 + self.look_offset_y

                # Eye Blinking & Sleep Eyes
                if self.blink_phase > 0.05 or self.current_state == "SLEEP":
                    eyelid_h = max(2, int(8 * (1.0 if self.current_state == "SLEEP" else self.blink_phase)))
                    painter.setPen(QPen(QColor(38, 30, 26), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    # Left lash arc
                    painter.drawArc(int(eye_center_x - 9), int(eye_center_y - 2), 8, eyelid_h, 25 * 16, 130 * 16)
                    # Right lash arc
                    painter.drawArc(int(eye_center_x + 1), int(eye_center_y - 2), 8, eyelid_h, 25 * 16, 130 * 16)

                # Curiosity Eye Sparkles
                if (self.current_state == "CURIOUS" or self.is_thinking) and not self.is_blinking:
                    sp_rot = self.animation_step * 1.8
                    for ox in [-5, 5]:
                        painter.save()
                        painter.translate(eye_center_x + ox, eye_center_y)
                        painter.rotate(sp_rot * (1 if ox > 0 else -1))
                        painter.setBrush(QColor(255, 255, 255, 220))
                        painter.setPen(Qt.PenStyle.NoPen)
                        # Diamond star
                        painter.drawPolygon([QPoint(-1, 0), QPoint(0, -3), QPoint(1, 0), QPoint(0, 3)])
                        painter.drawPolygon([QPoint(0, -1), QPoint(3, 0), QPoint(0, 1), QPoint(-3, 0)])
                        painter.restore()

                # Lip-Sync Talking Mouth Animation (syncs with speech audio)
                if self.voice_worker.is_speaking:
                    mouth_center_x = draw_x + pix.width() * norm_eye_x + self.look_offset_x * 0.5
                    mouth_center_y = draw_y + pix.height() * 0.285 + self.look_offset_y * 0.5
                    mouth_open = abs(math.sin(self.talk_step * 14.0)) * 3.5
                    if mouth_open > 0.8:
                        painter.setPen(QPen(QColor(219, 39, 119), 1.2))
                        painter.setBrush(QColor(244, 114, 182, 230))
                        painter.drawEllipse(QRectF(mouth_center_x - 2.5, mouth_center_y - mouth_open / 2, 5.0, mouth_open))

                painter.restore()

        # Sakura & Star Floating Particles
        for p in self.particles:
            painter.save()
            painter.translate(p["x"], p["y"])
            painter.rotate(p["rot"])
            alpha_int = int(max(0, min(255, p["alpha"] * 255)))
            if p["type"] == "sakura":
                painter.setBrush(QColor(244, 114, 182, alpha_int))
                painter.setPen(Qt.PenStyle.NoPen)
                path = QPainterPath()
                sz = p["size"]
                path.moveTo(0, -sz)
                path.cubicTo(sz * 0.7, -sz * 0.5, sz * 0.5, sz * 0.5, 0, sz)
                path.cubicTo(-sz * 0.5, sz * 0.5, -sz * 0.7, -sz * 0.5, 0, -sz)
                painter.drawPath(path)
            elif p["type"] == "star":
                painter.setBrush(QColor(253, 224, 71, alpha_int))
                painter.setPen(Qt.PenStyle.NoPen)
                sz = p["size"] * 0.5
                painter.drawPolygon([
                    QPoint(0, int(-sz)), QPoint(int(sz*0.3), int(-sz*0.3)),
                    QPoint(int(sz), 0), QPoint(int(sz*0.3), int(sz*0.3)),
                    QPoint(0, int(sz)), QPoint(int(-sz*0.3), int(sz*0.3)),
                    QPoint(int(-sz), 0), QPoint(int(-sz*0.3), int(-sz*0.3))
                ])
            else: # sparkle
                painter.setBrush(QColor(255, 255, 255, alpha_int))
                painter.setPen(Qt.PenStyle.NoPen)
                sz = p["size"]
                painter.drawEllipse(QRectF(-sz/2, -sz/2, sz, sz))
            painter.restore()

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
            self.press_global_pos = event.globalPosition().toPoint()
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.is_dragging = False
            self.trigger_friendly_reaction(1500)

    def mouseMoveEvent(self, event):
        if self.press_global_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = (event.globalPosition().toPoint() - self.press_global_pos).manhattanLength()
            if delta > 7:
                self.is_dragging = True
                new_pos = event.globalPosition().toPoint() - self.drag_position
                self.move(new_pos)
                self.bubble.update_position()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            now = time.time()
            if not self.is_dragging:
                # Double tap / click detected within 420ms
                if now - self.last_release_time < 0.42:
                    self.open_chat()
                    self.last_release_time = 0.0
                else:
                    self.last_release_time = now
            else:
                self.last_release_time = 0.0

            self.press_global_pos = None
            self.drag_position = None
            self.is_dragging = False

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
        action_ask = menu.addAction("❓ Ask Me a Curious Question")
        action_walk = menu.addAction("🚶 Stroll Around Desktop" if self.current_state != "WALK" else "🧍 Stand Still Here")
        action_pomo = menu.addAction("⏱️ 30m Study & Break Session")
        action_clip = menu.addAction("🔍 Ask Chitanda About Clipboard")
        action_curious = menu.addAction("✨ 「私、気になります！」 (I'm Curious!)")
        action_hide = menu.addAction("🙈 Hide Chitanda (Quiet Study)")

        # Smart Jarvis Tools
        smart_menu = menu.addMenu("🧠 Smart Jarvis Tools")
        action_mic = smart_menu.addAction("🎙️ Voice Command (Microphone)")
        action_vision = smart_menu.addAction("🔍 What am I looking at? (Screen Vision)")
        action_pdf = smart_menu.addAction("📄 Read & Summarize Latest PDF")
        action_remind = smart_menu.addAction("⏰ Set a Timed Reminder...")

        # 3D / 2D Mascot Mode
        render_menu = menu.addMenu("✨ 3D / 2D Mascot Mode")
        act_3d = render_menu.addAction("✨ 3D Anime Model (WebGL)" + ("  ✔" if self.render_mode == "3D" else ""))
        act_2d = render_menu.addAction("🌸 2D Sprite" + ("  ✔" if self.render_mode == "2D" else ""))

        # Laptop Quick Tools submenu
        laptop_menu = menu.addMenu("💻 Laptop Controls")
        act_battery = laptop_menu.addAction("🔋 Check Battery Status")
        act_shot = laptop_menu.addAction("📸 Take Screenshot")
        act_desk = laptop_menu.addAction("🖥️ Show Desktop (Win+D)")
        act_lock = laptop_menu.addAction("🔒 Lock Laptop (LockWorkstation)")

        # Outfit & Character submenu
        outfit_menu = menu.addMenu("👗 Change Outfit / Character")
        act_unif = outfit_menu.addAction("🌸 School Sailor Uniform (Chitanda)")
        act_cur = outfit_menu.addAction("✨ Inquisitive School Uniform (Chitanda)")
        act_cas = outfit_menu.addAction("🍃 Knit Vest & Blouse (Chitanda)")
        act_win = outfit_menu.addAction("🧥 Winter Coat & Scarf (Chitanda)")
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

        action = menu.exec(QCursor.pos())

        if action == action_chat:
            self.open_chat()
        elif action == action_mic:
            self.open_chat()
            if self.chat_window:
                self.chat_window._chip_mic()
        elif action == action_vision:
            self.open_chat()
            if self.chat_window:
                self.chat_window._chip_vision()
        elif action == action_pdf:
            self.open_chat()
            if self.chat_window:
                self.chat_window._chip_pdf()
        elif action == action_remind:
            self.open_chat()
            if self.chat_window:
                self.chat_window._chip_reminder()
        elif action == act_3d:
            self.set_render_mode("3D")
        elif action == act_2d:
            self.set_render_mode("2D")
        elif action == action_ask:
            self._ask_proactive_question()
        elif action == act_battery:
            info = LaptopController.get_battery_info()
            self.say(info, voice=True)
        elif action == act_shot:
            reply = LaptopController.take_screenshot()
            self.say(reply, voice=True)
        elif action == act_desk:
            LaptopController.show_desktop()
        elif action == act_lock:
            LaptopController.lock_laptop()
        elif action == action_walk:
            if self.current_state == "WALK":
                self.current_state = "STAND"
                self.walk_ticks_remaining = 0
            else:
                self.wake_up()
                self.current_state = "WALK"
                self.walk_ticks_remaining = 350
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
        elif action == act_win:
            self.set_outfit("winter")
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
