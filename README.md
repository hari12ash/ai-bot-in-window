# 🌸 Eru Chitanda & Houtarou Oreki - AI Desktop Companion for Windows

An interactive, animated AI desktop companion for Windows featuring **Eru Chitanda (千反田 える)** and **Houtarou Oreki (折木 奉太郎)** from *Hyouka*. 

The companion floats directly on your desktop with persistent memories, auto-hiding study countdowns with break alerts, authentic voices, an interactive task tracker, and an official anime scene wallpaper gallery.

Powered locally and privately by **Ollama** and **PySide6 (Qt6)**.

---

## ✨ Key Features

- **🌸 Interactive Desktop Mascot (Floating Interface)**:
  - Frameless, translucent floating desktop character that strolls, breathes, naps (Zzz), and blinks naturally every 3-5 seconds.
  - **Speech Lip-Sync Animation**: Mouth animates in sync with spoken syllables when she speaks.
  - **Interactive Cursor Look-At**: Her eyes and head softly track your mouse cursor across the screen.
  - **4 Outfits / Character Modes**: School Uniform, Inquisitive Knit Vest, Casual Blouse, Winter Coat & Scarf, and Houtarou Oreki.
  - Double-tap or double-click to immediately open the compact, comfortable chat box!

- **🎙️ Voice Commands (Microphone Speech-to-Text)**:
  - Push-to-talk microphone button (`🎙️`) in the chat box or right-click menu.
  - Speak your command naturally, and Chitanda transcribes, processes, and responds with full voice!

- **🔍 Screen Understanding & Vision Analysis**:
  - Ask *"What am I looking at?"*, *"Explain this error"*, or *"Summarize what's on my screen"*.
  - Chitanda captures the active screen in-memory, detects active application & window context, and provides intelligent explanations!

- **📄 PDF Reading & Summarization**:
  - Automatically scans recent documents or accepts PDF names.
  - Extracts text via `pypdf` and provides sweet, insightful, well-structured summaries.

- **⏰ Persistent Reminders & Timers**:
  - Natural commands like *"Remind me in 20 minutes to stretch"* or *"Remind me at 18:30 to call home"*.
  - Survives computer reboots in `chitanda_reminders.json` with voice notifications and Windows alerts.

- **💻 PC Automation & Windows Control**:
  - Open applications (Chrome, VS Code, Notepad, Spotify, Calc, Downloads).
  - Audio control (Volume Up, Down, Mute toggle).
  - Security & Screen (Lock Laptop, Show Desktop, Take Screenshot, Battery & System Health report).

- **🧠 Persistent Memory & Local AI**:
  - Runs 100% locally and privately via **Ollama**.
  - Silently retains personal interests, custom tasks, and preferences with heartfelt friendship values.

- **📜 Project Rules & Architectural Guidelines**:
  - All bug fixes, design decisions, and strict guidelines are documented in [**`IMPROVEMENTS_AND_RULES.md`**](file:///c:/Users/eruma/Desktop/KING_AI/IMPROVEMENTS_AND_RULES.md) to prevent past issues from recurring.

---

## 🚀 Quick Start Guide

### 1. Requirements
- Windows 10 / 11
- Python 3.10+
- [Ollama](https://ollama.ai) installed with `llama3.2:1b` (or your preferred local model):
  ```bash
  ollama run llama3.2:1b
  ```

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/hari12ash/ai-bot-in-window.git
cd ai-bot-in-window

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### 3. Launching
- Double-click **`run_king.bat`** (or **`run_king_silent.vbs`** for quiet background mode without a console window).
- Or run in terminal:
  ```powershell
  python main.py
  ```

---

## 📁 Repository Structure
```
ai-bot-in-window/
├── ai_brain.py             # Ollama chat worker & Chitanda persistent memory manager
├── bubble.py               # Streaming speech bubble widget
├── character.py            # Floating desktop mascot, animations & context menu
├── chat_window.py          # Tabbed companion interface, study timers & soundboard
├── main.py                 # Application entry point & tray lifecycle
├── voice.py                # Edge-TTS & offline voice engine
├── work_tools.py           # Study session manager & Pomodoro timer
├── requirements.txt        # Python package dependencies
├── run_king.bat            # Windows batch launcher
├── run_king_silent.vbs     # Silent background launcher
├── chitanda_*.png          # Official high-resolution transparent sprites
├── oreki_crisp.png         # Houtarou Oreki character sprite
└── wallpapers/             # Curated Kyoto Animation scene wallpapers
```

---

## 📜 License
MIT License. Created for anime fans and focused learners!
