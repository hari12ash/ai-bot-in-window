import os
import re
import queue
import threading
from PySide6.QtCore import QObject, Signal

def sanitize_text_for_speech(text: str) -> str:
    """Clean markdown, code blocks, html tags, and symbols for crisp audio speech."""
    text = re.sub(r"```[\s\S]*?```", " Code snippet provided. ", text)
    text = re.sub(r"`.*?`", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^[#*->]+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[\*_~\[\]\(\)\{\}\^]", "", text)
    text = text.replace("“", '"').replace("”", '"').replace("—", ", ").replace("–", ", ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

class VoiceSpeakerThread(QObject):
    """
    Ultra-low latency Windows speech engine for Eru Chitanda.
    Uses asynchronous native SAPI COM (Microsoft Zira) for instant 0.05s speech with zero lag.
    """
    speech_started = Signal()
    speech_finished = Signal()

    def __init__(self):
        super().__init__()
        self._sapi = None
        self._init_sapi()

    def _init_sapi(self):
        try:
            import win32com.client
            self._sapi = win32com.client.Dispatch("SAPI.SpVoice")
            # Select friendly female voice (Zira or Hazel)
            for v in self._sapi.GetVoices():
                desc = v.GetDescription().lower()
                if "zira" in desc or "female" in desc or "hazel" in desc:
                    self._sapi.Voice = v
                    break
            self._sapi.Rate = 1  # Natural, conversational pace
            self._sapi.Volume = 100
        except Exception as e:
            print("Failed to initialize SAPI voice:", e)
            self._sapi = None

    @property
    def is_speaking(self) -> bool:
        """Returns True if audio is actively coming out of speakers."""
        if self._sapi:
            try:
                # RunningState 2 = SRSEIsSpeaking
                return self._sapi.Status.RunningState == 2
            except Exception:
                pass
        return False

    def start(self):
        # Ready on creation
        pass

    def set_voice_mode(self, mode: str):
        pass

    def speak(self, text: str):
        clean_text = sanitize_text_for_speech(text)
        if not clean_text:
            return

        if self._sapi:
            try:
                # SVSFlagsAsync = 1, SVSFPurgeBeforeSpeak = 2 (Purge cancels previous audio and speaks immediately)
                self._sapi.Speak("", 2)
                self._sapi.Speak(clean_text, 1)
                return
            except Exception as e:
                print("SAPI speak error, reinitializing:", e)
                self._init_sapi()
                if self._sapi:
                    try:
                        self._sapi.Speak(clean_text, 1)
                        return
                    except Exception:
                        pass

        # Fallback to background pyttsx3 thread
        threading.Thread(target=self._fallback_speak, args=(clean_text,), daemon=True).start()

    def stop_current(self):
        if self._sapi:
            try:
                self._sapi.Speak("", 2)
            except Exception:
                pass

    def stop(self):
        self.stop_current()

    def _fallback_speak(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
