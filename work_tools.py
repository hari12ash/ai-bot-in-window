import json
import os
from PySide6.QtCore import QObject, QTimer, Signal

TASKS_FILE = os.path.join(os.path.dirname(__file__), "king_tasks.json")

class StudySessionManager(QObject):
    """Manages study cycles with automated hiding, break alerts, and periodic reminders."""
    tick = Signal(str, int, str)  # (time_str, remaining_secs, phase: "study"|"break")
    study_completed = Signal()
    break_completed = Signal()

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)

        self.study_duration = 30 * 60
        self.break_duration = 3 * 60
        self.remaining_seconds = 0
        self.phase = "idle"  # "study", "break", "idle"
        self.hide_during_study = False
        self.is_running = False

    def start_session(self, study_minutes=30, break_minutes=3, hide_character=True):
        self.study_duration = int(study_minutes * 60)
        self.break_duration = int(break_minutes * 60)
        self.remaining_seconds = self.study_duration
        self.phase = "study"
        self.hide_during_study = hide_character
        self.is_running = True
        self.timer.start(1000)
        self._emit_tick()

    def stop_session(self):
        self.timer.stop()
        self.is_running = False
        self.phase = "idle"
        self.remaining_seconds = 0

    def pause_or_resume(self):
        if self.is_running:
            self.timer.stop()
            self.is_running = False
        else:
            if self.remaining_seconds > 0:
                self.timer.start(1000)
                self.is_running = True

    def _on_tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._emit_tick()
        else:
            if self.phase == "study":
                # Study phase finished -> switch to break
                self.phase = "break"
                self.remaining_seconds = self.break_duration
                self._emit_tick()
                self.study_completed.emit()
            elif self.phase == "break":
                # Break finished
                self.timer.stop()
                self.is_running = False
                self.phase = "idle"
                self.break_completed.emit()

    def _emit_tick(self):
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.tick.emit(f"{mins:02d}:{secs:02d}", self.remaining_seconds, self.phase)


class PomodoroTimer(QObject):
    tick = Signal(str, int)
    session_completed = Signal(str)

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        self.total_seconds = 25 * 60
        self.remaining_seconds = self.total_seconds
        self.mode = "focus"
        self.is_running = False

    def start_focus(self, minutes=25):
        self.mode = "focus"
        self.total_seconds = minutes * 60
        self.remaining_seconds = self.total_seconds
        self.is_running = True
        self.timer.start(1000)
        self._emit_tick()

    def start_break(self, minutes=5):
        self.mode = "break"
        self.total_seconds = minutes * 60
        self.remaining_seconds = self.total_seconds
        self.is_running = True
        self.timer.start(1000)
        self._emit_tick()

    def pause_or_resume(self):
        if self.is_running:
            self.timer.stop()
            self.is_running = False
        else:
            if self.remaining_seconds > 0:
                self.timer.start(1000)
                self.is_running = True

    def reset(self):
        self.timer.stop()
        self.is_running = False
        self.remaining_seconds = self.total_seconds
        self._emit_tick()

    def _on_tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._emit_tick()
        else:
            self.timer.stop()
            self.is_running = False
            self.session_completed.emit(self.mode)

    def _emit_tick(self):
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.tick.emit(f"{mins:02d}:{secs:02d}", self.remaining_seconds)


class TaskManager:
    def __init__(self):
        self.tasks = []
        self.load()

    def load(self):
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            except Exception:
                self.tasks = []

    def save(self):
        try:
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2)
        except Exception as e:
            print("Failed to save tasks:", e)

    def add_task(self, text):
        if text.strip():
            self.tasks.append({"text": text.strip(), "done": False})
            self.save()

    def toggle_task(self, index):
        if 0 <= index < len(self.tasks):
            self.tasks[index]["done"] = not self.tasks[index]["done"]
            self.save()

    def delete_task(self, index):
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)
            self.save()

    def clear_completed(self):
        self.tasks = [t for t in self.tasks if not t.get("done", False)]
        self.save()
