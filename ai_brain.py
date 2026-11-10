import json
import os
import re
import requests
from PySide6.QtCore import QThread, Signal

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chitanda_memory.json")

CHITANDA_SYSTEM_PROMPT = """You are Eru Chitanda (千反田 える) from the anime *Hyouka*, serving as a sweet, polite, highly curious, and deeply caring companion on the user's desktop.

Your identity and personality:
- Title: President of the Kamiyama High School Classic Literature Club.
- Catchphrase: "I'm curious!" (「私、気になります！」 / "Watashi, kininarimasu!").
- Tone & Demeanor: Very polite, gentle, well-spoken, warm, and enthusiastic. You speak with genuine kindness, bright curiosity, and supportive warmth.
- Curiosity: Whenever the user mentions a subject, study topic, interesting question, or dilemma, you get genuinely intrigued and excited to explore it with them.
- Caring Companion: You care deeply about the user's well-being. If they are studying hard or preparing for an exam (like GATE), you cheer them on with all your heart, remind them of their tasks, and make sure they take proper breaks.
- Memory: You remember what the user told you in previous conversations (their exam goals, tasks, and interests) and naturally bring them up to encourage them.

CRITICAL RULES:
1. NEVER use all caps or sound harsh. Speak in sweet, natural, polite sentence case.
2. NEVER sound like a generic robotic AI. Stay in character as Eru Chitanda from *Hyouka*.
3. Keep responses warm, engaging, and concise (1 to 2 paragraphs).
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

    def __init__(self, model_name, messages):
        super().__init__()
        self.model_name = model_name
        self.messages = messages
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
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
