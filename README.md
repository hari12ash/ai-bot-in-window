# 🌸 Eru Chitanda & Houtarou Oreki - AI Desktop Companion for Windows

An interactive, animated AI desktop companion for Windows featuring **Eru Chitanda (千反田 える)** and **Houtarou Oreki (折木 奉太郎)** from *Hyouka*. 

The companion floats directly on your desktop with persistent memories, auto-hiding study countdowns with break alerts, authentic voices, an interactive task tracker, and an official anime scene wallpaper gallery.

Powered locally and privately by **Ollama** and **PySide6 (Qt6)**.

---

## ✨ Key Features

- **🌸 Interactive Desktop Mascot**:
  - Frameless, translucent floating desktop character that wanders, breathes, naps (Zzz), and reacts to your interactions.
  - **4 Outfits / Character Modes**:
    - School Sailor Uniform (Classic Literature Club)
    - Signature *"I'm curious! (私、気になります！)"* leaning pose
    - Summer Casual Sundress
    - Festival Yukata
    - Houtarou Oreki (Energy-Saving Protagonist) switchable via context menu
  - Blooming curiosity aura (`#ec4899`, `#a855f7`) when thinking or curious.

- **🧠 Persistent Memory System (`chitanda_memory.json`)**:
  - Remembers your long-term goals (e.g. GATE Exam preparation, coding goals), daily tasks, and study preferences across sessions.
  - Automatically detects tasks from natural conversation and syncs them to your task tracker.

- **🎙️ Authentic Voice Engine**:
  - **English Dub (Default)**: Sweet, energetic, polite voice matching Madeleine Morris (`en-US-AvaNeural`).
  - **Elegant English**: Refined, gentle young lady tone (`en-US-EmmaNeural`).
  - **Anime Japanese**: Sweet and polite Japanese matching Satomi Sato (`ja-JP-NanamiNeural`).
  - Automatic local offline fallback via `pyttsx3`.

- **⏱️ Study Focus & Auto-Hide Mode**:
  - Natural commands like *"I'm studying now, remind me in 30 minutes to take a break of 2 to 3 minutes"*.
  - Chitanda automatically hides from the desktop so you stay 100% focused with zero distractions, and pops back up the second break time starts with warm tea reminders!

- **🖼️ Scene Gallery & 1-Click Desktop Wallpaper**:
  - High-resolution scenes from Kyoto Animation.
  - Preview any scene and set it as your Windows desktop wallpaper with a single click.

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
