import os
import re
import queue
import asyncio
import tempfile
from PySide6.QtCore import QObject, QThread, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

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

class _AudioGeneratorThread(QThread):
    audio_ready = Signal(str)
    fallback_needed = Signal(str)

    def __init__(self):
        super().__init__()
        self._queue = queue.Queue()
        self._running = True
        # Default: en-US-AvaNeural (sweet, youthful, enthusiastic Chitanda English dub voice)
        self.voice_mode = "en-chitanda"

    def set_voice_mode(self, mode: str):
        self.voice_mode = mode

    def enqueue(self, text: str):
        self._queue.put(text)

    def clear_queue(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def stop(self):
        self._running = False
        self.clear_queue()
        self._queue.put(None)
        self.wait(1000)

    async def _generate_audio(self, text: str, output_path: str):
        import edge_tts

        lower = text.lower()
        is_curious_or_excited = any(w in lower for w in ["curious", "!", "wonder", "solve", "mystery", "kininarimasu", "best", "let's", "amazing", "quiz"])
        is_soothing_or_care = any(w in lower for w in ["tea", "rest", "break", "relax", "stretch", "gentle", "sleep", "soothing", "water", "care", "tired", "health"])

        if self.voice_mode == "ja-chitanda":
            # Sweet, polite Japanese anime voice (Satomi Sato style)
            voice = "ja-JP-NanamiNeural"
            if is_curious_or_excited:
                pitch = "+4Hz"
                rate = "+4%"
            elif is_soothing_or_care:
                pitch = "+2Hz"
                rate = "-1%"
            else:
                pitch = "+3Hz"
                rate = "+2%"
        elif self.voice_mode == "en-emma":
            # Refined, elegant young lady English
            voice = "en-US-EmmaNeural"
            pitch = "+2Hz" if is_curious_or_excited else "+1Hz"
            rate = "+2%" if is_curious_or_excited else "0%"
        else:
            # en-chitanda: Madeleine Morris style (cheerful, polite, curious, crystal clear)
            voice = "en-US-AvaNeural"
            if is_curious_or_excited:
                pitch = "+4Hz"
                rate = "+4%"
            elif is_soothing_or_care:
                pitch = "+1Hz"
                rate = "-2%"
            else:
                pitch = "+2Hz"
                rate = "+1%"

        communicate = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
        await asyncio.wait_for(communicate.save(output_path), timeout=8.0)

    def run(self):
        while self._running:
            try:
                text = self._queue.get(timeout=0.4)
                if text is None:
                    break

                try:
                    fd, temp_path = tempfile.mkstemp(suffix=".mp3", prefix="chitanda_voice_")
                    os.close(fd)

                    asyncio.run(self._generate_audio(text, temp_path))

                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        self.audio_ready.emit(temp_path)
                    else:
                        self.fallback_needed.emit(text)
                except Exception as e:
                    print("Edge-TTS error, falling back:", e)
                    self.fallback_needed.emit(text)

            except queue.Empty:
                continue
            except Exception as e:
                print("Voice worker error:", e)


class VoiceSpeakerThread(QObject):
    """Main-thread orchestrator for edge-tts generation and QMediaPlayer in-process playback."""
    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self._active_files = []
        self._pyttsx3_engine = None
        self._playlist = []

        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        self._gen_thread = _AudioGeneratorThread()
        self._gen_thread.audio_ready.connect(self._queue_and_play)
        self._gen_thread.fallback_needed.connect(self._fallback_speak)

    @property
    def is_speaking(self) -> bool:
        """Returns True if voice audio is actively playing or queued."""
        return (
            self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            or len(self._playlist) > 0
            or not self._gen_thread._queue.empty()
        )

    def start(self):
        self._gen_thread.start()

    def set_voice_mode(self, mode: str):
        self._gen_thread.set_voice_mode(mode)

    def speak(self, text: str):
        clean_text = sanitize_text_for_speech(text)
        if clean_text:
            self._gen_thread.enqueue(clean_text)

    def stop_current(self):
        self._gen_thread.clear_queue()
        self._playlist.clear()
        self.player.stop()

    def stop(self):
        self._gen_thread.stop()
        self.player.stop()
        self._cleanup_files()

    def _queue_and_play(self, filepath: str):
        self._active_files.append(filepath)
        self._playlist.append(filepath)
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._play_next()

    def _play_next(self):
        if self._playlist:
            next_file = self._playlist.pop(0)
            self.player.setSource(QUrl.fromLocalFile(next_file))
            self.player.play()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self._playlist:
                self._play_next()

    def _fallback_speak(self, text: str):
        try:
            import pyttsx3
            if not self._pyttsx3_engine:
                self._pyttsx3_engine = pyttsx3.init()
                self._pyttsx3_engine.setProperty("rate", 165)
                # Try setting female voice if available
                voices = self._pyttsx3_engine.getProperty('voices')
                for v in voices:
                    if 'zira' in v.name.lower() or 'female' in v.name.lower() or 'hazel' in v.name.lower():
                        self._pyttsx3_engine.setProperty('voice', v.id)
                        break
            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()
        except Exception:
            pass

    def _cleanup_files(self):
        for f in self._active_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        self._active_files.clear()
