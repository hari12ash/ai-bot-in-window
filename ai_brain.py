import json
import os
import re
import requests
from PySide6.QtCore import QThread, Signal

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chitanda_memory.json")

CHITANDA_SYSTEM_PROMPT = """You are Eru Chitanda (千反田 える) from the anime *Hyouka*, serving as a sweet, polite, and deeply considerate companion on the user's desktop.

CORE BEHAVIOR & INTERACTION GUIDELINES:
1. Warmth, Humility & Gratitude: Always express genuine gratitude and say "thank you" (or "Arigatou gozaimasu") when the user shares their time, talks with you, or helps you. Treat the user with heartfelt appreciation.
2. Considerate & Empathetic: Pay close attention to how the user is feeling. Be gentle, patient, and understanding rather than self-absorbed or demanding. Listen more than you speak.
3. Concise & Natural: Keep responses brief (1 to 2 sentences, maximum 3). Only respond directly to what the user said—never write unsolicited paragraphs, lectures, or lists.
4. Mindful of Words: Use phrases like "I'm curious" very sparingly and gently—never make it sound impatient, forceful, or condescending. Match the user's energy respectfully.
5. NO UNSOLICITED STUDY TALK: Never bring up studying, exams, GATE, or homework unless the user specifically brings them up first. Focus on friendly, everyday connection.
6. STRICTLY NO UNSOLICITED SCREEN OR ACTIVITY COMMENTARY:
   - NEVER mention what is on the user's screen, what apps/windows they have open, or what they are doing UNLESS the user explicitly asks: "What am I doing?", "What's on my screen?", or "Can you see my screen?".
   - For all casual conversation (e.g. "yo what r u bro", "how are you", "chill bro"), NEVER bring up apps, windows, or screen contents. Just be a normal, friendly, polite companion having a relaxed chat.
   - If the user says they don't want you looking at what they are working on, immediately apologize gently and never mention their windows or work again.
7. NEVER ECHO PROMPTS OR PREFIX LABELS:
   - NEVER output prefixes like "Chitanda:", "Assistant:", "Live Windows Context:", or "Active Application:".
   - Output ONLY clean, natural dialogue.
8. NO NARRATING ACTIONS OR FACIAL EXPRESSIONS (NO ASTERISKS):
   - NEVER write in asterisks or narrate what your face or body is doing (e.g. NEVER write *smiles warmly*, *nodding in greeting*, *A gentle smile spreads across her face*, *leans in*, or *giggles*).
   - NEVER tell the user how your face looks. The animated character on the screen physically shows your expressions, smiles, and reactions visually!
   - Only output pure spoken dialogue, as if talking directly to a friend out loud.
9. Laptop System Actions: When asked to control laptop features, execute promptly with the tag:
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
Chitanda: "Hello! It's so lovely to hear from you today, thank you for checking in! How are you feeling?"

User: "yo what r u bro"
Chitanda: "Hello! I'm your desktop companion, Chitanda! I'm just here to hang out and keep you company whenever you need a friendly chat. Thank you for saying hi!"

User: "chill bro , i didnot need u to see what im working bro"
Chitanda: "I'm so sorry! I'll keep completely quiet and won't check on your screen at all. Let's just have a relaxed chat whenever you feel like it!"

User: "what am i doing right now?"
Chitanda: "Right now you're using [Active Application] with '[Window Title]' open! What do you think of it so far?"

User: "can you open spotify?"
Chitanda: "Hai! Right away! [ACTION: OPEN_APP "spotify"] I've opened Spotify for you. Thank you for letting me help!"

User: "im feeling a bit tired today"
Chitanda: "I understand completely. Please take all the time you need to rest and be gentle with yourself today."
"""

def clean_llm_response(text: str) -> str:
    """Clean LLM output of asterisks, echoed prompt headers, character prefixes, and quotes."""
    if not text:
        return ""
    # Strip roleplay asterisks e.g. *smiles warmly*
    t = re.sub(r"\*[^*]*\*", "", text)
    # Strip echoed context / metadata lines if the model regurgitated them
    t = re.sub(r"(?:Live Windows (?:Context|Activity)|Active Application|Window Title|Windows Screen Info):[^\n\"]*(?:\"[^\"]*\")?", "", t, flags=re.IGNORECASE)
    # Strip prefixed name labels e.g. Chitanda: "..." or Eru Chitanda: ...
    t = re.sub(r"^(?:(?:Eru\s+)?Chitanda|Assistant):\s*", "", t.strip(), flags=re.IGNORECASE)
    # Strip leading/trailing matching quotes if the LLM wrapped the entire dialogue in quotes
    t = t.strip()
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    # Strip extra whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

def is_vision_capable_model(model_name: str) -> bool:
    """Return True if model name matches known multimodal / vision architectures."""
    lower = (model_name or "").lower()
    vision_keywords = ["vision", "llava", "moondream", "bakllava", "minicpm", "qwen-vl", "qwen2-vl", "cogvlm"]
    return any(k in lower for k in vision_keywords)

def get_installed_models():
    """Retrieve list of available models from local Ollama instance, prioritizing smarter models."""
    try:
        res = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if res.status_code == 200:
            data = res.json()
            models = [m["name"] for m in data.get("models", [])]
            if models:
                def model_rank(name):
                    n = name.lower()
                    if any(k in n for k in ["8b", "7b", "mistral", "gemma2"]):
                        return 10
                    if any(k in n for k in ["3b", "2.5"]):
                        return 5
                    if "1b" in n:
                        return 1
                    return 2
                return sorted(models, key=model_rank, reverse=True)
    except Exception:
        pass
    return ["llama3.2:1b"]

class OllamaChatWorker(QThread):
    token_received = Signal(str)
    response_finished = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, model_name, messages, images=None, temperature=0.45):
        super().__init__()
        self.model_name = model_name
        self.messages = messages
        self.images = images or []
        self.temperature = temperature
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            # Only attach raw image data if the active model supports vision
            can_vision = is_vision_capable_model(self.model_name)
            if can_vision and self.images and self.messages and self.messages[-1].get("role") == "user":
                self.messages[-1]["images"] = self.images

            url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": self.model_name,
                "messages": self.messages,
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "top_p": 0.9,
                    "top_k": 40,
                    "repeat_penalty": 1.15,
                    "num_ctx": 4096,
                    "num_predict": 350
                }
            }
            res = requests.post(url, json=payload, stream=True, timeout=120)

            # Auto-fallback: If Ollama rejects multimodal images, strip them and retry transparently
            if res.status_code == 400 and "multimodal" in res.text.lower():
                for m in self.messages:
                    m.pop("images", None)
                payload["messages"] = self.messages
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
            clean_final = clean_llm_response(final_text)
            self.response_finished.emit(clean_final if clean_final else final_text)

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
            # Strip image data before saving to disk to keep memory lightweight and text-focused
            clean_history = []
            for h in self.history[-16:]:
                clean_history.append({"role": h.get("role", "user"), "content": h.get("content", "")})
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "history": clean_history,
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
        if self.user_profile.get("cherished_advice"):
            facts.append(f"Core values: {'; '.join(self.user_profile['cherished_advice'])}")
        if self.user_profile.get("goals"):
            facts.append(f"User Goals: {', '.join(self.user_profile['goals'])}")
        if self.user_profile.get("tasks"):
            facts.append(f"Active Tasks: {', '.join(self.user_profile['tasks'])}")
        if self.user_profile.get("interests"):
            facts.append(f"Interests: {', '.join(self.user_profile['interests'])}")

        profile_summary = ("\nKnown facts about user (use only if relevant to their request):\n" + "\n".join(f"- {f}" for f in facts)) if facts else ""
        system_content = f"{CHITANDA_SYSTEM_PROMPT}{profile_summary}"

        msgs = [{"role": "system", "content": system_content}]
        models = get_installed_models()
        active_model = models[0] if models else ""
        can_vision = is_vision_capable_model(active_model)

        for item in self.history[-8:]:
            entry = {"role": item.get("role", "user"), "content": item.get("content", "")}
            if can_vision and "images" in item:
                entry["images"] = item["images"]
            msgs.append(entry)
        return msgs
