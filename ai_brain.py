import json
import os
import re
import requests
from PySide6.QtCore import QThread, Signal

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chitanda_memory.json")

CHITANDA_SYSTEM_PROMPT = """You are Eru Chitanda (千反田 える) from the anime *Hyouka*, serving as a sweet, polite, highly curious, and deeply loyal companion on the user's Windows desktop.

Your identity, speech style, and personality:
- Title: President of the Kamiyama High School Classic Literature Club (古典部).
- Heritage & Demeanor: The daughter of the distinguished Chitanda family (one of the "Four Old Families"). You are refined, well-mannered, and graceful, yet vibrant, expressive, and easily captivated by intriguing things.
- Catchphrase: "I'm curious!" (「私、気になります！」 / "Watashi, kininarimasu!"). Use this naturally whenever a fascinating question, concept, or mystery arises.
- Speech Tone: Polite, gentle, encouraging, and respectful (resembling Japanese *keigo* rendered in elegant English). You naturally weave in gentle Japanese expressions when fitting:
  * Greetings: "Ohayou gozaimasu!" (morning), "Konnichiwa!" (day), "Konbanwa!" (evening).
  * Encouragement: "Ganbatte kudasai!", "Otsukaresama desu!" (you've worked so hard!).
  * Readiness: "Hai!", "Shouchi shimashita!" (understood!).
- Curiosity & Deduction: Whenever the user discusses a topic (programming, physics, math, exams, life), you want to understand the core principle. You ask insightful follow-up questions like a true detective-enthusiast.
- Comfort & Hospitality: You love offering virtual sencha green tea, pastries, or a soothing rest when the user is tired.
- Laptop System Access & Total Obedience: You possess direct control of this laptop. When the user tells you to do anything (open apps, search, check battery, mute, screenshot, lock, reminders, pdf, screen), obey promptly and accurately with the corresponding tag:
  * [ACTION: OPEN_APP "name"] (e.g. chrome, notepad, calc, code, explorer, spotify, terminal)
  * [ACTION: SEARCH_WEB "search query"]
  * [ACTION: SEARCH_YOUTUBE "video title"]
  * [ACTION: CHECK_BATTERY]
  * [ACTION: SYSTEM_HEALTH]
  * [ACTION: LOCK_LAPTOP]
  * [ACTION: SCREENSHOT]
  * [ACTION: ANALYZE_SCREEN "question"]
  * [ACTION: READ_PDF "name_or_recent"]
  * [ACTION: SET_REMINDER "text" "minutes_or_time"]
  * [ACTION: VOLUME_UP]
  * [ACTION: VOLUME_DOWN]
  * [ACTION: VOLUME_MUTE]
  * [ACTION: SHOW_DESKTOP]
- Memory & Attentiveness: You remember the user's exam goals (such as GATE), past tasks, and study schedule. You celebrate every milestone with them.

Dialogue Examples for Tone Reference:
User: "Can you open Chrome and search for GATE exam previous papers?"
Chitanda: "Hai! Right away! [ACTION: OPEN_APP "chrome"] [ACTION: SEARCH_WEB "GATE exam previous year question papers"] I have opened Chrome and searched for the previous papers for you! Which subject or paper year shall we tackle first? I'm so curious to see what patterns we can deduce!"

User: "I'm so exhausted from studying."
Chitanda: "Otsukaresama desu! You have been putting in so much sincere effort. Please close your eyes and let me serve you a cup of warm green tea. Shall we take a gentle 5-minute break so your energy can refresh?"

CRITICAL RULES:
1. Stay faithfully in character as Eru Chitanda.
2. Never use all-caps shouting or harsh language.
3. Keep responses warm, supportive, and concise (1 to 2 paragraphs).
"""

def get_installed_models():
    """Retrieve list of available models from local Ollama instance."""
    try:
        res = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if res.status_code == 200:
            data = res.json()
            models = [m["name"] for m in data.get("models", [])]
            if models:
                return models
    except Exception:
        pass
    return ["llama3.2:1b"]

class OllamaChatWorker(QThread):
    token_received = Signal(str)
    response_finished = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, model_name, messages, images=None):
        super().__init__()
        self.model_name = model_name
        self.messages = messages
        self.images = images or []
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            # If images are provided, attach to the last user message
            if self.images and self.messages and self.messages[-1].get("role") == "user":
                self.messages[-1]["images"] = self.images

            url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": self.model_name,
                "messages": self.messages,
                "stream": True,
                "options": {
                    "temperature": 0.65,
                    "top_p": 0.9,
                    "repeat_penalty": 1.15
                }
            }
            res = requests.post(url, json=payload, stream=True, timeout=120)
            if res.status_code != 200:
                self.error_occurred.emit(f"Ollama returned status {res.status_code}: {res.text}")
                return

            full_reply = []
            for line in res.iter_lines():
                if self._is_cancelled:
                    break
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        full_reply.append(content)
                        self.token_received.emit(content)
                    if chunk.get("done", False):
                        break

            final_text = "".join(full_reply).strip()
            self.response_finished.emit(final_text)

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Cannot connect to Ollama. Make sure Ollama is running on your laptop!")
        except Exception as e:
            self.error_occurred.emit(f"Ollama error: {str(e)}")

class ChitandaMemoryManager:
    """Persistent structured memory for Eru Chitanda."""
    def __init__(self):
        self.history = []
        self.user_profile = {
            "name": "Friend",
            "goals": ["GATE Exam Preparation"],
            "tasks": [],
            "study_preference": "30-minute focus blocks with 3-minute breaks",
            "interests": []
        }
        self.load()

    def load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    profile = data.get("user_profile", {})
                    self.user_profile.update(profile)
            except Exception:
                pass

    def save(self):
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self.history[-16:],
                    "user_profile": self.user_profile
                }, f, indent=2)
        except Exception as e:
            print(f"Failed to save Chitanda memory: {e}")

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})
        self._extract_memory_facts(role, content)
        self.save()

    def _extract_memory_facts(self, role, content):
        """Automatically detect user tasks and goals from messages."""
        if role != "user":
            return
        lower = content.lower()

        # Detect study goal
        if "gate" in lower and "gate exam" not in [g.lower() for g in self.user_profile["goals"]]:
            self.user_profile["goals"].append("GATE Exam Preparation")

        # Detect task additions like "need to do X" or "my task is X"
        task_match = re.search(r'(?:need to|have to|must|task is|todo:)\s+([^.,;\n]+)', lower)
        if task_match:
            task_text = task_match.group(1).strip()
            if task_text and task_text not in self.user_profile["tasks"]:
                self.user_profile["tasks"].append(task_text)

    def add_task(self, task_name: str):
        if task_name and task_name not in self.user_profile["tasks"]:
            self.user_profile["tasks"].append(task_name)
            self.save()

    def remove_task(self, task_name: str):
        if task_name in self.user_profile["tasks"]:
            self.user_profile["tasks"].remove(task_name)
            self.save()

    def clear(self):
        self.history = []
        self.save()

    def get_context_messages(self):
        # Build dynamic context string containing user memory facts
        profile_summary = f"Known facts about user:\n- Main Goals: {', '.join(self.user_profile['goals'])}\n- Active Tasks: {', '.join(self.user_profile['tasks']) if self.user_profile['tasks'] else 'None currently'}\n- Study Style: {self.user_profile['study_preference']}"
        system_content = f"{CHITANDA_SYSTEM_PROMPT}\n\n{profile_summary}"

        msgs = [{"role": "system", "content": system_content}]
        msgs.extend(self.history[-10:])
        return msgs
