# 📜 Eru Chitanda Desktop AI - Project Improvements, Bug Fixes & Architectural Rules

> **CRITICAL DIRECTIVE**: This document records all past architectural errors, mistakes, user feedback, and enforced solutions across the lifecycle of this project. **None of the mistakes documented here must ever be reintroduced.** Future contributors, agents, and developers must follow these rules without exception.

---

## 📑 Table of Contents
1. [Personality & Conversation Guidelines](#1-personality--conversation-guidelines)
2. [Visual Expression vs. Dialogue Rules (No Asterisks)](#2-visual-expression-vs-dialogue-rules-no-asterisks)
3. [Voice & Audio Architecture (Eliminating Lag)](#3-voice--audio-architecture-eliminating-lag)
4. [Chat Window UI & Interaction Rules](#4-chat-window-ui--interaction-rules)
5. [3D WebGL Mascot & Mouse Event Pass-Through](#5-3d-webgl-mascot--mouse-event-pass-through)
6. [JavaScript & Python Bridge Race Condition Prevention](#6-javascript--python-bridge-race-condition-prevention)
7. [Live Windows Screen & Activity Awareness](#7-live-windows-screen--activity-awareness)
8. [Process Management & Memory State Integrity](#8-process-management--memory-state-integrity)
9. [Summary Checklist for Future Changes](#9-summary-checklist-for-future-changes)

---

## 1. Personality & Conversation Guidelines

### ❌ The Mistake:
- The AI was previously hardcoded with study/exam assumptions (`"GATE Exam Preparation"`), causing Chitanda to aimlessly lecture the user about study schedules, revision, and exams even when the user just said `"yo whats up"`.
- The bot wrote long, multi-paragraph essays instead of having a natural, friendly chat.
- The background question timer (`_ask_proactive_question`) was shouting unprompted voice queries every 2–4 minutes.

### ✅ The Enforced Rules & Solutions:
1. **Short & Sweet Policy**: Responses must be **1 to 2 sentences** (maximum 3). Only respond directly to what the user said. Never talk aimlessly, give long lectures, or output essays.
2. **Strictly NO Unsolicited Study Talk**: Never mention studying, exams, GATE, tests, revision, or homework unless the user explicitly brings it up first.
3. **Warm, Considerate & Humble**: Chitanda expresses sincere gratitude (*"Thank you so much!"* / *"Arigatou gozaimasu"*). Her catchphrase *"I'm curious!"* (私、気になります！) is used gently and sparingly so it never sounds impatient or overbearing.
4. **Zero Unprompted Audio**: Chitanda must **never** speak audio through the speakers unprompted in the background. Background check-ins are silent text bubbles only, firing at relaxed, non-intrusive intervals (10–18 minutes).
5. **Clean Memory Defaults**: `chitanda_memory.json` defaults to empty goals and tasks. Facts are only injected into context if the user explicitly states them.

---

## 2. Visual Expression vs. Dialogue Rules (No Asterisks)

### ❌ The Mistake:
- The AI generated roleplay narration and stage directions in asterisks, e.g.:
  `*Chitanda smiles warmly, nodding in greeting.* "Hello!" *A gentle smile spreads across her face*`
- The user explicitly requested: **do not let her say how her face looks; make the physical character show it instead!**

### ✅ The Enforced Rules & Solutions:
1. **Never Output Asterisks or Stage Directions**:
   - The LLM prompt in `ai_brain.py` strictly forbids writing in asterisks or narrating facial expressions.
   - Text output and speech synthesis pipelines enforce automated regex scrubbing:
     ```python
     clean_dialogue = re.sub(r'\*[^*]*\*', '', raw_text).strip()
     clean_dialogue = re.sub(r'\[ACTION:[^\]]+\]', '', clean_dialogue).strip()
     clean_dialogue = re.sub(r'\s+', ' ', clean_dialogue).strip()
     ```
2. **Physical Visual Rendering of Facial Expressions**:
   - Instead of narrating her smile in text, `KingCharacter.trigger_friendly_reaction()` visually renders:
     - **Smiling Eyes (`^ ^`)**: Animated happy crescent arcs overlaid on her eyes.
     - **Anime Cheek Blush**: Soft pink blush ovals (`#f472b6`) drawn on both cheeks.
     - **Gentle Smile Curve**: Dynamic smiling mouth curve rendered in 2D and 3D.
     - **Floating Sakura Blossoms**: Drifting petals that bloom during energetic or curious states.

---

## 3. Voice & Audio Architecture (Eliminating Lag)

### ❌ The Mistake:
- Cloud-based Edge-TTS required online WebSocket connections to Microsoft servers for every phrase, taking **2.5 to 5.0 seconds** per sentence. This created unacceptable speech lag.
- Fallback `pyttsx3.runAndWait()` on the main Qt GUI thread caused total UI freezing during speech synthesis.

### ✅ The Enforced Rules & Solutions:
1. **Native Asynchronous Windows SAPI COM Engine**:
   - `voice.py` uses native Windows COM `SAPI.SpVoice` (`Microsoft Zira` / `Hazel`).
   - Latency dropped from ~2.6s to **~0.05 seconds** (50x faster, zero internet lag).
2. **Immediate Interruption & Non-Blocking**:
   - When a new phrase is spoken, old speech is purged instantly (`sapi.Speak("", 2)`).
   - Audio is dispatched asynchronously with flag `1` (`SVSFlagsAsync`) without blocking the Qt event loop.
3. **Accurate Lip-Sync Talking Animation**:
   - `voice_worker.is_speaking` directly reads `sapi.Status.RunningState == 2`, perfectly synchronizing mouth movement with active audio output.

---

## 4. Chat Window UI & Interaction Rules

### ❌ The Mistake:
- Chat box was oversized (`360×480`), covering too much desktop space.
- There was no way to minimize the chat window without closing it completely.

### ✅ The Enforced Rules & Solutions:
1. **Compact Half-Size Footprint**:
   - Dimensions reduced to **`230×255` px** (minimum size `200×210` px).
   - Padding, scrollbars, and font sizes (11px) are scaled proportionally for crisp readability.
2. **Dedicated Minimize Button (`🗕`)**:
   - Added `🗕` in the header bar next to close (`✕`).
   - Clicking `🗕` calls `self.showMinimized()`.
3. **Double-Click Summoning**:
   - Double-clicking or double-tapping the desktop avatar immediately calls `self.show()`, `self.showNormal()`, `self.raise_()`, and `self.activateWindow()` to restore and position the chat box beside Chitanda.

---

## 5. 3D WebGL Mascot & Mouse Event Pass-Through

### ❌ The Mistake:
- When 3D mode was enabled, double-clicking the avatar **did not open the chat box** because `QWebEngineView` sat on top of the widget and Chromium's internal RenderWidget swallowed all mouse events.

### ✅ The Enforced Rules & Solutions:
1. **Transparent Mouse Events on WebEngineView**:
   - In `character.py`:
     ```python
     self.web_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
     ```
   - In `mascot_3d.html`:
     ```css
     html, body, #canvas-container {
         pointer-events: none;
     }
     ```
   - Result: 100% of mouse presses, releases, drags, double-clicks, and right-clicks pass straight through the 3D layer into `KingCharacter`.
2. **Dual Double-Click Handling**:
   - Supports native OS `mouseDoubleClickEvent`.
   - Also tracks rapid consecutive clicks (`< 450ms` in `mouseReleaseEvent`) to ensure touchscreens and trackpads trigger reliably.

---

## 6. JavaScript & Python Bridge Race Condition Prevention

### ❌ The Mistake:
- When starting `main.py`, Python's 30 FPS animation loop immediately fired `window.setTargetLook(...)` and `window.setMascotState(...)` within the first 10ms—before Three.js had finished parsing.
- Result: `Uncaught TypeError: window.setMascotState is not a function` spammed the console 30 times per second.

### ✅ The Enforced Rules & Solutions:
1. **Instant Global Stubs in `<head>`**:
   - `mascot_3d.html` defines stubs at the very top of `<head>`:
     ```javascript
     window._pendingState = 'STAND';
     window._pendingLook = { dx: 0, dy: 0 };
     window.setMascotState = function(state) {
         window._pendingState = state;
         if (window._applyMascotState) window._applyMascotState(state);
     };
     window.setTargetLook = function(dx, dy) {
         window._pendingLook = { dx, dy };
         if (window._applyTargetLook) window._applyTargetLook(dx, dy);
     };
     ```
2. **Python Readiness Gate**:
   - `character.py` maintains `self.is_3d_ready = False`.
   - Set to `True` only in `loadFinished`.
   - All Python JavaScript evaluations use defensive guards:
     ```python
     if self.render_mode == "3D" and getattr(self, "is_3d_ready", False):
         self.web_view.page().runJavaScript(
             f"if (typeof window.setTargetLook === 'function') window.setTargetLook({target_dx:.2f}, {target_dy:.2f});"
         )
     ```

---

## 7. Live Windows Screen & Activity Awareness

### ❌ The Mistake:
- The bot previously responded: *"I don't actually have direct access to viewing your Windows desktop..."* when the user asked what they were doing.

### ✅ The Enforced Rules & Solutions:
1. **Native Windows Desktop Station Inspection**:
   - `ScreenInspector.get_open_windows()` connects to `WinSta0\Default` and uses `User32.EnumWindows` to enumerate all active top-level user windows.
   - Automatically filters out internal OS elements (IME, taskbar, system trays) and ignores Chitanda's own companion window.
2. **Real-Time Context Injection**:
   - In `ai_brain.py`, every prompt evaluation automatically pulls the live summary:
     ```python
     act = ScreenInspector.get_user_activity_summary()
     # e.g.: "You are currently using Brave Browser on '(293) How to Throw Punches That Actually Hurt - YouTube'"
     ```
   - When asked *"what am I doing?"*, Chitanda immediately recognizes the exact active application, YouTube video, browser tab, or code document.
3. **Multi-Phrase Vision Intent Routing**:
   - All variants (*"what am I doing"*, *"see what I'm seeing"*, *"what's on my screen"*, *"inspect screen"*) automatically capture the screen and analyze the active window.

---

## 8. Process Management & Memory State Integrity

### ❌ The Mistake:
- Multiple instances of `main.py` were running in the background simultaneously. An old background instance held stale memory in RAM and overwrote `chitanda_memory.json` on disk, restoring old GATE exam prompts.

### ✅ The Enforced Rules & Solutions:
1. **Single Instance Hygiene**:
   - Before launching or testing `main.py`, always terminate old python processes:
     `Stop-Process -Id <PIDs> -Force`
2. **Strict Regex for Profile Extraction**:
   - Do NOT use loose trigger words like `"have to"` or `"must"` to add user tasks, as casual chat (e.g. *"I must tell you something"*) contaminated user profiles.
   - Restrict automatic fact extraction strictly to explicit phrases:
     `r'(?:my goal is|aiming to achieve)\s+([^.,;\n]+)'` and `r'(?:my task is|todo:)\s+([^.,;\n]+)'`.

---

## 9. Multimodal / Vision Fallback for Text-Only Models

### ❌ The Mistake:
- When using local text-only Ollama models like `llama3.2:1b`, clicking the `🔍 [Screen Vision]` button or asking *"What am I looking at right now?"* caused Ollama to fail with HTTP 400:
  ```json
  {"error":"Multimodal data provided, but model does not support multimodal requests."}
  ```
- Because `llama3.2:1b` has no CLIP vision encoder, passing `images: [base64_data]` to `/api/chat` causes Ollama to reject the entire query.

### ✅ The Enforced Rules & Solutions:
1. **Model Vision Capability Detection (`is_vision_capable_model`)**:
   - In `ai_brain.py`:
     ```python
     def is_vision_capable_model(model_name: str) -> bool:
         lower = (model_name or "").lower()
         vision_keywords = ["vision", "llava", "moondream", "bakllava", "minicpm", "qwen-vl", "qwen2-vl", "cogvlm"]
         return any(k in lower for k in vision_keywords)
     ```
2. **Selective Image Attachment**:
   - In `chat_window.py`, only attach base64 screenshot images if `is_vision_capable_model(active_model)` is `True`.
   - In `OllamaChatWorker`, never attach images to the Ollama payload if the model lacks multimodal support.
3. **Rich Context Text Fallback**:
   - Windows desktop context already provides 100% accurate information via `ScreenInspector.get_user_activity_summary()`:
     ```python
     prompt = (
         f"The user asks: \"{question}\"\n"
         f"Live Windows Context: {act['summary']}\n"
         f"Active Application: {act['active_app']} | Window Title: \"{act['active_title']}\"\n"
         f"Please respond kindly, concisely (1-2 sentences), and accurately stating what application and page/window the user currently has open."
     )
     ```
   - Text models (`llama3.2:1b`, etc.) answer with complete accuracy without throwing 400 errors.
4. **Transparent Auto-Recovery in `OllamaChatWorker`**:
   - If Ollama ever returns HTTP 400 containing `"multimodal"`, `OllamaChatWorker` automatically strips all `"images"` keys from the message history and resends the request instantly so the user never sees an error.

---

## 10. 3D Slime Avatar Loading & Transparent Desktop Isolation

### ❌ Potential Issues:
- GLB models exported from Blender often contain ground/floor planes (e.g. `Plane.002`), which would block the desktop background with an opaque green sheet.
- Local `file://` fetch/XHR loading of binary assets in Qt Chromium web engines can trigger CORS/local origin security blocks.

### ✅ The Enforced Rules & Solutions:
1. **Self-Contained Base64 Model Injection (`slime_model_data.js`)**:
   - `slime.glb` (~294 KB) is encoded into `window.SLIME_GLB_BASE64` and parsed via `THREE.GLTFLoader.parse(arrayBuffer, ...)`.
   - Bypasses all `file://` security/CORS restrictions; loads synchronously with 0 network latency.
2. **Floor Plane Filtering**:
   - In `mascot_3d.html`, traverse the scene and set `child.visible = false` for `Plane.002`, keeping the desktop 100% transparent.
   - Bounding box auto-centering calculates dimensions strictly from character meshes.
3. **Squash, Stretch & Jelly Physics**:
   - Slime idle: gentle jelly breathing & soft ambient float.
   - Walk: dynamic squash on contact, stretch in mid-air with hop kinematics.
   - Interaction: happy spring bounce for clicks and bows, cute wobble lean for curious state.
   - Global bridge stubs (`window.setMascotState`, `window.setTargetLook`) maintained in `<head>` to guarantee 0 TypeError console exceptions.

---

## 11. Elimination of Unsolicited Screen Commentary & Prompt Leakage Loops

### ❌ The Mistake:
- In `ai_brain.py`, `ScreenInspector.get_user_activity_summary()` was unconditionally injected into the system prompt facts on EVERY single chat message, even when the user just said *"yo what r u bro"* or *"chill bro"*.
- In `chat_window.py`, when screen analysis was triggered, the full formatted prompt template containing `"Live Windows Context: ... Active Application: ..."` was stored directly in `chitanda_memory.json` as the user's message.
- The small 1B model saw `Live Windows Context: ...` in previous turns, started echoing the words verbatim in its responses, and kept talking about open tabs/windows even when the user begged her to stop.

### ✅ The Enforced Rules & Solutions:
1. **STRICTLY No Unsolicited Screen Commentary**:
   - `ScreenInspector.get_user_activity_summary()` is NEVER injected into default system prompt facts for general chit-chat.
   - Screen/window activity is ONLY provided when the user explicitly triggers Screen Vision or asks *"What am I looking at?"* / *"What am I doing?"*.
2. **Clean Memory Storage (`memory_text`)**:
   - In `chat_window.py`, `process_user_prompt(prompt, memory_text=question)` records only the clean, original question in `chitanda_memory.json`.
   - The formatted prompt template is used strictly for the single ephemeral Ollama request payload and NEVER pollutes the permanent dialogue history.
3. **Response Sanitization (`clean_llm_response`)**:
   - `clean_llm_response` defensively strips:
     - Echoed metadata headers (`Live Windows Context:`, `Active Application:`, `Window Title:`).
     - Model name prefixes (`Chitanda:`, `Eru Chitanda:`, `Assistant:`).
     - Unnecessary outer quotes.
     - Roleplay asterisks (`*...*`).
4. **Sanitized Dialogue History**:
   - `chitanda_memory.json` was purged of all contaminated echoed messages, restoring a relaxed, respectful companion persona.

---

## 12. Ollama Model Power Optimization & Multi-Model Selection

### ❌ The Issue:
- The default setup ran `llama3.2:1b` (1.2 billion parameters) with a high temperature (`0.65`) and default unexpanded context window (`2048`).
- Small 1B models with high temperature hallucinate factual details, dates, science, and math.
- Hardcoded `models[0]` prevented users from selecting or taking advantage of smarter models installed in Ollama.

### ✅ The Enforced Rules & Solutions:
1. **Inference Power Optimization**:
   - `temperature: 0.45`: Significantly reduces hallucinations and grounds responses in factual accuracy.
   - `num_ctx: 4096`: Expands context buffer from default 2048 to 4096 so conversation and system instructions are never truncated.
   - `top_k: 40`, `top_p: 0.9`, `repeat_penalty: 1.15`, `num_predict: 350`.
2. **Dynamic Capability Sorting**:
   - `get_installed_models()` ranks available models by capability (8b/7b > 3b > 1b), automatically giving the user the smartest model available.
3. **Model Selection UI**:
   - Added an `"🤖 Ollama AI Model"` submenu to the character's right-click context menu.
   - The chat box status header dynamically displays the active model name (e.g. `● Ready • llama3.2:1b`).
   - Supports seamless switching between any models pulled in Ollama (`llama3.2:3b`, `qwen2.5:3b`, `llama3:8b`, etc.).

---

## 13. Summary Checklist for Future Changes

Before committing any future changes, verify:
- [ ] Is Chitanda's response concise (1–2 sentences) and free of unprompted study/exam references?
- [ ] Are all roleplay asterisks (`*...*`) stripped from both displayed text and voice audio?
- [ ] Does double-clicking the avatar open the chat window immediately?
- [ ] Does the 3D model load cleanly with 0 console errors in `QWebEngineView`?
- [ ] Does speech start instantly (~0.05s) via native SAPI without lagging the UI?
- [ ] Does the chat box fit the compact `230×255` size and have a working `🗕` minimize button?
- [ ] Does Chitanda refrain from mentioning screens/windows unless explicitly asked?
- [ ] Are Screen Vision queries safe from Ollama 400 multimodal errors on text-only models?
- [ ] Are Ollama inference parameters optimized for accuracy (`temperature: 0.45`, `num_ctx: 4096`)?
- [ ] Does the 3D Slime avatar render transparently without opaque Blender ground planes?
- [ ] Are all background processes cleanly terminated so only 1 instance of `main.py` runs?
- [ ] Does the 3D Slime avatar render transparently without opaque Blender ground planes?
- [ ] Are all background processes cleanly terminated so only 1 instance of `main.py` runs?
