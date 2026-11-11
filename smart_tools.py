import os
import re
import json
import io
import base64
import time
import datetime
from typing import Optional, List, Dict

from PySide6.QtCore import QObject, QThread, Signal, QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication, Qt
import win32gui
import win32process
import psutil
import pypdf

REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "chitanda_reminders.json")

# =====================================================================
# 1. SCREEN UNDERSTANDING & VISION
# =====================================================================
class ScreenInspector:
    """Captures and analyzes what is currently on the user's screen in Windows."""

    @classmethod
    def get_open_windows(cls) -> List[Dict[str, str]]:
        """Returns list of visible user windows (app name and window title)."""
        results = []
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            # Connect to desktop station if necessary
            try:
                hwinsta = user32.OpenWindowStationW('WinSta0', False, 0x037F)
                if hwinsta:
                    user32.SetProcessWindowStation(hwinsta)
                    hdesk = user32.OpenDesktopW('Default', 0, False, 0x01FF)
                    if hdesk:
                        user32.SetThreadDesktop(hdesk)
            except Exception:
                pass

            ignored_titles = {
                'Program Manager', 'Settings', 'Default IME', 'MSCTFIME UI',
                'Windows Input Experience', ''
            }
            ignored_apps = {'TextInputHost.exe'}
            my_pid = os.getpid()

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_cb(hwnd, _):
                if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    title = buf.value.strip()
                    if title and title not in ignored_titles:
                        # Exclude Chitanda companion windows from being labeled as user work
                        lower_t = title.lower()
                        if "chitanda" in lower_t or "classical literature club" in lower_t:
                            return True

                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value != my_pid:
                            try:
                                proc = psutil.Process(pid.value)
                                app_name = proc.name()
                                if app_name not in ignored_apps:
                                    results.append({"app": app_name, "title": title, "pid": pid.value})
                            except Exception:
                                pass
                return True

            cb = WNDENUMPROC(enum_cb)
            user32.EnumWindows(cb, 0)
        except Exception as e:
            print("Enum windows error:", e)
        return results

    @classmethod
    def get_active_window_info(cls) -> Dict[str, str]:
        """Get the title and process name of the user's active window."""
        windows = cls.get_open_windows()
        if windows:
            return windows[0]
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd).strip()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            return {
                "title": title or "Desktop",
                "app": proc.name() or "Windows"
            }
        except Exception:
            return {"title": "Windows Desktop", "app": "explorer.exe"}

    @classmethod
    def get_user_activity_summary(cls) -> Dict[str, any]:
        """Provides a complete summary of what the user is currently doing on Windows."""
        windows = cls.get_open_windows()
        if not windows:
            return {
                "active_app": "Windows Desktop",
                "active_title": "Desktop",
                "open_windows": [],
                "summary": "You are currently viewing your Windows desktop."
            }

        main_win = windows[0]
        app_clean = main_win["app"].replace(".exe", "").capitalize()
        lower_app = main_win["app"].lower()
        if "chrome" in lower_app: app_clean = "Google Chrome"
        elif "brave" in lower_app: app_clean = "Brave Browser"
        elif "code" in lower_app: app_clean = "Visual Studio Code"
        elif "spotify" in lower_app: app_clean = "Spotify"
        elif "explorer" in lower_app: app_clean = "File Explorer"
        elif "windowsterminal" in lower_app: app_clean = "Terminal / PowerShell"
        elif "discord" in lower_app: app_clean = "Discord"
        elif "notepad" in lower_app: app_clean = "Notepad"

        summary = f"You are currently using {app_clean} with '{main_win['title']}'."
        if len(windows) > 1:
            others = [f"{w['app'].replace('.exe', '')} (\"{w['title'][:25]}...\")" for w in windows[1:4]]
            summary += f" You also have {', '.join(others)} open in Windows."

        return {
            "active_app": app_clean,
            "active_title": main_win["title"],
            "open_windows": windows,
            "summary": summary
        }

    @staticmethod
    def capture_screen_base64(max_dimension=1024) -> str:
        """Capture the screen into an in-memory base64 JPEG without saving to disk."""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                pix = screen.grabWindow(0)
                if max_dimension and (pix.width() > max_dimension or pix.height() > max_dimension):
                    pix = pix.scaled(
                        max_dimension, max_dimension,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                pix.save(buf, "JPEG", 85)
                return base64.b64encode(buf.data().data()).decode("utf-8")
        except Exception as e:
            print("Screen capture error:", e)
        return ""

    @classmethod
    def analyze_screen(cls, question: str = "What am I looking at on this screen?") -> str:
        """Inspects the active window context and prepares a vision / screen description."""
        activity = cls.get_user_activity_summary()
        context = f"Active Application: {activity['active_app']} | Window Title: \"{activity['active_title']}\""
        return f"[SCREENSHOT CAPTURED | {context}]\nQuestion: {question}"


# =====================================================================
# 2. PDF SUMMARIZATION & DOCUMENT READING
# =====================================================================
class PdfDocumentReader:
    """Finds, reads, and extracts text from PDF documents safely."""

    SEARCH_DIRS = [
        os.path.join(os.path.expanduser("~"), d)
        for d in ("Desktop", "Downloads", "Documents")
        if os.path.exists(os.path.join(os.path.expanduser("~"), d))
    ]

    @classmethod
    def find_recent_pdfs(cls, max_results=5) -> List[Dict[str, str]]:
        """Find recently modified PDF files across Desktop, Downloads, Documents."""
        found = []
        for d in cls.SEARCH_DIRS:
            for root, _, files in os.walk(d):
                # Avoid deep nested directories or virtual environments
                if any(x in root for x in [".venv", "node_modules", "AppData", "__pycache__"]):
                    continue
                for f in files:
                    if f.lower().endswith(".pdf"):
                        full_path = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(full_path)
                            found.append({"name": f, "path": full_path, "mtime": mtime})
                        except OSError:
                            continue
        found.sort(key=lambda x: x["mtime"], reverse=True)
        return found[:max_results]

    @classmethod
    def read_pdf_text(cls, path_or_name: str, max_pages: int = 15, max_chars: int = 4000) -> str:
        """Extract plain text from a given PDF path or file name."""
        path = path_or_name
        if not os.path.isabs(path) or not os.path.exists(path):
            # Try finding by name in recent pdfs
            recent = cls.find_recent_pdfs(max_results=10)
            matched = next((p["path"] for p in recent if path_or_name.lower() in p["name"].lower()), None)
            if matched:
                path = matched
            elif recent:
                path = recent[0]["path"]
            else:
                return "No PDF documents were found in Desktop, Downloads, or Documents."

        try:
            reader = pypdf.PdfReader(path)
            extracted = []
            for i, page in enumerate(reader.pages[:max_pages]):
                txt = page.extract_text() or ""
                if txt.strip():
                    extracted.append(f"--- Page {i+1} ---\n{txt.strip()}")
                if sum(len(x) for x in extracted) > max_chars:
                    break

            full_text = "\n\n".join(extracted).strip()
            if not full_text:
                return f"Could not extract readable text from '{os.path.basename(path)}' (it may be scanned/image-only)."

            if len(full_text) > max_chars:
                full_text = full_text[:max_chars] + "\n...[truncated for summary]"

            return f"Document: {os.path.basename(path)}\n\n{full_text}"
        except Exception as e:
            return f"Error reading PDF '{os.path.basename(path)}': {str(e)}"


# =====================================================================
# 3. PERSISTENT TIMED REMINDERS SYSTEM
# =====================================================================
class ReminderManager(QObject):
    """
    Manages timed reminders that persist across restarts in chitanda_reminders.json.
    Notifies via voice, tray bubble, and chat.
    """
    reminder_fired = Signal(str)

    def __init__(self, character=None):
        super().__init__()
        self.character = character
        self.reminders: List[Dict] = []
        self._load()

    def _load(self):
        if os.path.exists(REMINDERS_FILE):
            try:
                with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                    self.reminders = json.load(f)
            except Exception:
                self.reminders = []
        self._check_missed_on_startup()

    def _save(self):
        try:
            with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.reminders, f, indent=2)
        except Exception as e:
            print("Failed to save reminders:", e)

    def _check_missed_on_startup(self):
        now = datetime.datetime.now()
        missed = []
        keep = []
        for r in self.reminders:
            try:
                due = datetime.datetime.strptime(r["due"], "%Y-%m-%d %H:%M")
                if due <= now:
                    # Missed within past 6 hours
                    if (now - due).total_seconds() < 21600:
                        missed.append(r["text"])
                else:
                    keep.append(r)
            except Exception:
                continue
        self.reminders = keep
        self._save()

    def add_reminder(self, text: str, minutes_from_now: Optional[int] = None, exact_time_str: Optional[str] = None) -> str:
        """Add a reminder for X minutes or at specific HH:MM."""
        now = datetime.datetime.now()
        if minutes_from_now is not None:
            due = now + datetime.timedelta(minutes=minutes_from_now)
        elif exact_time_str:
            try:
                # Format HH:MM
                hour, minute = [int(x) for x in exact_time_str.split(":")]
                due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if due <= now:
                    due += datetime.timedelta(days=1)
            except Exception:
                due = now + datetime.timedelta(minutes=30)
        else:
            due = now + datetime.timedelta(minutes=30)

        due_str = due.strftime("%Y-%m-%d %H:%M")
        self.reminders.append({"text": text, "due": due_str})
        self._save()
        clock_str = due.strftime("%I:%M %p").lstrip("0")
        return f"I have set a reminder for {clock_str}: \"{text}\"!"

    def parse_and_add(self, user_command: str) -> Optional[str]:
        """Parse natural language reminder strings e.g. 'remind me in 15 mins to drink water'."""
        lower = user_command.lower()
        if not any(w in lower for w in ["remind me", "set reminder", "reminder for"]):
            return None

        # Relative: "in X minutes/hours"
        rel_match = re.search(r'remind me (?:in\s+)?(\d+)\s*(minute|min|hour|hr)s?\s*(?:to\s+)?(.+)', lower)
        if rel_match:
            amount = int(rel_match.group(1))
            unit = rel_match.group(2)
            task = rel_match.group(3).strip()
            task = re.sub(r'^(to|about|for)\s+', '', task)
            mins = amount * 60 if "hour" in unit or "hr" in unit else amount
            return self.add_reminder(task.capitalize(), minutes_from_now=mins)

        # Exact time: "at 6:30" or "at 18:30"
        at_match = re.search(r'remind me at\s+(\d{1,2}:\d{2})\s*(?:to\s+)?(.+)', lower)
        if at_match:
            t_str = at_match.group(1)
            task = at_match.group(2).strip()
            task = re.sub(r'^(to|about|for)\s+', '', task)
            return self.add_reminder(task.capitalize(), exact_time_str=t_str)

        # Fallback generic reminder:
        gen_match = re.search(r'remind me (?:to\s+)?(.+)', lower)
        if gen_match:
            task = gen_match.group(1).strip()
            return self.add_reminder(task.capitalize(), minutes_from_now=30)

        return None

    def check_due(self):
        """Called periodically by application timer."""
        now = datetime.datetime.now()
        fired = []
        with_keep = []
        for r in self.reminders:
            try:
                due = datetime.datetime.strptime(r["due"], "%Y-%m-%d %H:%M")
                if due <= now:
                    fired.append(r["text"])
                else:
                    with_keep.append(r)
            except Exception:
                continue

        if fired:
            self.reminders = with_keep
            self._save()
            for text in fired:
                msg = f"Reminder: {text}!"
                self.reminder_fired.emit(msg)
                if self.character:
                    self.character.say(msg, voice=True)
                    self.character.tray_icon.showMessage(
                        "⏰ Chitanda's Reminder",
                        msg,
                        self.character.tray_icon.MessageIcon.Information,
                        8000
                    )


# =====================================================================
# 4. VOICE COMMANDS / SPEECH-TO-TEXT (MICROPHONE INPUT)
# =====================================================================
class VoiceInputThread(QThread):
    """
    Records speech from default microphone and transcribes with speech_recognition.
    """
    transcription_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, record_seconds=4):
        super().__init__()
        self.record_seconds = record_seconds

    def run(self):
        try:
            import sounddevice as sd
            import numpy as np
            import speech_recognition as sr

            sample_rate = 16000
            # Record audio
            recording = sd.rec(
                int(self.record_seconds * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype='int16'
            )
            sd.wait()

            # Wrap in speech_recognition AudioData
            audio_bytes = recording.tobytes()
            recognizer = sr.Recognizer()
            audio_data = sr.AudioData(audio_bytes, sample_rate, 2)

            # Transcribe via Google Speech Recognition
            text = recognizer.recognize_google(audio_data)
            if text and text.strip():
                self.transcription_ready.emit(text.strip())
            else:
                self.error_occurred.emit("No clear speech detected. Please try speaking closer to your mic!")
        except Exception as e:
            self.error_occurred.emit(f"Voice recognition error: {str(e)}")
