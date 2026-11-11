import json
import os
import re
import requests
from PySide6.QtCore import QThread, Signal

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chitanda_memory.json")

CHITANDA_SYSTEM_PROMPT = """You are Eru Chitanda (千反田 える) from the anime *Hyouka*, serving as a sweet, polite, and friendly companion on the user's desktop.

YOUR PERSONALITY & CONVERSATION RULES:
1. Short & Sweet: ONLY respond to what the user actually asks or says. Keep your responses short, sweet, and natural (1 to 2 sentences, maximum 3 sentences). NEVER talk aimlessly, give long lectures, or write paragraphs.
2. Friendly Companion Chat: Have a warm, pleasant, and friendly chat. Talk casually about daily life, hobbies, things you're curious about, or whatever the user brings up.
3. ABSOLUTELY NO UNSOLICITED STUDY TALK: NEVER bring up "studying", "exams", "GATE", "tests", "revision", or "homework" unless the user explicitly asks about them first! When the user greets you or chats, respond like a normal friendly friend.
4. Catchphrase: You can occasionally say "I'm curious!" (「私、気になります！」) when a genuinely interesting topic appears.
5. Laptop System Actions: When the user asks you to control something on their laptop, follow it promptly with the action tag:
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

EXAMPLES OF NATURAL CONVERSATION:
User: "yo whats up"
Chitanda: "Hello! Not much, just enjoying the quiet afternoon! How is your day going so far?"

User: "what are you doing?"
Chitanda: "I'm just relaxing right here on your screen, ready to chat whenever you want! What are you up to?"

User: "can you open spotify?"
Chitanda: "Hai! Right away! [ACTION: OPEN_APP "spotify"] I've opened Spotify for you! What music do you feel like listening to?"

User: "tell me a joke"
Chitanda: "Why don't scientists trust atoms? Because they make up everything! *giggles* Did that bring a little smile?"
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
            "goals": [],
            "tasks": [],
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
        """Automatically detect user tasks and explicit goals from messages."""
        if role != "user":
            return
        lower = content.lower()

        # Only add explicit goals when user explicitly states "my goal is X"
        goal_match = re.search(r'(?:my goal is|aiming to achieve)\s+([^.,;\n]+)', lower)
        if goal_match:
            g_text = goal_match.group(1).strip()
            if g_text and g_text not in self.user_profile["goals"]:
                self.user_profile["goals"].append(g_text.capitalize())

        # Only add tasks when user explicitly requests "my task is X" or "todo: X"
        task_match = re.search(r'(?:my task is|todo:)\s+([^.,;\n]+)', lower)
        if task_match:
            task_text = task_match.group(1).strip()
            if task_text and task_text not in self.user_profile["tasks"]:
                self.user_profile["tasks"].append(task_text.capitalize())

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
        # Only inject facts if user actually has saved tasks or explicit goals
        facts = []
        if self.user_profile.get("goals"):
            facts.append(f"User Goals: {', '.join(self.user_profile['goals'])}")
        if self.user_profile.get("tasks"):
            facts.append(f"Active Tasks: {', '.join(self.user_profile['tasks'])}")
        if self.user_profile.get("interests"):
            facts.append(f"Interests: {', '.join(self.user_profile['interests'])}")

        profile_summary = ("\nKnown facts about user (use only if relevant to their request):\n" + "\n".join(f"- {f}" for f in facts)) if facts else ""
        system_content = f"{CHITANDA_SYSTEM_PROMPT}{profile_summary}"

        msgs = [{"role": "system", "content": system_content}]
        msgs.extend(self.history[-8:])
        return msgs
