import os
import re
import sys
import time
import ctypes
import psutil
import datetime
import subprocess
import webbrowser
from PySide6.QtGui import QGuiApplication

# Windows Virtual-Key Codes
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_LWIN = 0x5B
KEY_D = 0x44
KEYEVENTF_KEYUP = 0x0002

class LaptopController:
    """Provides safe, direct, and deterministic control over the Windows laptop."""

    @staticmethod
    def get_battery_info() -> str:
        """Returns battery percentage, power plugged status, and time remaining."""
        battery = psutil.sensors_battery()
        if not battery:
            return "Your laptop does not report a battery (it is running on direct AC power)."
        
        status = "charging" if battery.power_plugged else "discharging"
        msg = f"Your laptop battery is currently at {battery.percent}% and is {status}."
        if not battery.power_plugged and battery.secsleft and battery.secsleft > 0:
            hours = battery.secsleft // 3600
            mins = (battery.secsleft % 3600) // 60
            msg += f" (Approximately {hours} hours and {mins} minutes remaining)."
        if battery.percent <= 20 and not battery.power_plugged:
            msg += " Please consider plugging in your charger soon!"
        return msg

    @staticmethod
    def get_system_health() -> str:
        """Returns CPU, RAM, and disk usage."""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:")
        
        free_ram_gb = ram.available / (1024 ** 3)
        free_disk_gb = disk.free / (1024 ** 3)
        
        return (
            f"Laptop Health Report:\n"
            f"- CPU Load: {cpu}%\n"
            f"- RAM Usage: {ram.percent}% ({free_ram_gb:.1f} GB free)\n"
            f"- C: Drive Free: {free_disk_gb:.1f} GB ({100 - disk.percent:.1f}% free)"
        )

    @staticmethod
    def lock_laptop() -> str:
        """Immediately locks the Windows session."""
        ctypes.windll.user32.LockWorkStation()
        return "Laptop locked securely. See you when you return!"

    @staticmethod
    def volume_up(steps=3) -> str:
        """Increases volume."""
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)
        return "Volume increased!"

    @staticmethod
    def volume_down(steps=3) -> str:
        """Decreases volume."""
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)
        return "Volume decreased!"

    @staticmethod
    def volume_mute_toggle() -> str:
        """Toggles mute on/off."""
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
        return "Audio mute toggled!"

    @staticmethod
    def media_toggle() -> str:
        """Toggles media play/pause."""
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)
        return "Media playback toggled!"

    @staticmethod
    def show_desktop() -> str:
        """Minimizes all windows to show the desktop (Win+D)."""
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
        ctypes.windll.user32.keybd_event(KEY_D, 0, 0, 0)
        ctypes.windll.user32.keybd_event(KEY_D, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        return "Desktop shown!"

    @staticmethod
    def take_screenshot() -> str:
        """Captures primary screen and saves to Pictures/Chitanda_Screenshots."""
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                return "Could not capture screen."
            pix = screen.grabWindow(0)
            
            pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Chitanda_Screenshots")
            os.makedirs(pictures_dir, exist_ok=True)
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{ts}.png"
            full_path = os.path.join(pictures_dir, filename)
            
            pix.save(full_path, "PNG")
            return f"Screenshot captured and saved to: Pictures\\Chitanda_Screenshots\\{filename}!"
        except Exception as e:
            return f"Failed to take screenshot: {e}"

    @staticmethod
    def search_web(query: str) -> str:
        """Opens Google search for query."""
        clean_q = query.strip()
        if not clean_q:
            return "Please provide a search term."
        url = f"https://www.google.com/search?q={clean_q.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Searching Google for '{clean_q}' in your browser!"

    @staticmethod
    def search_youtube(query: str) -> str:
        """Opens YouTube search for query."""
        clean_q = query.strip()
        if not clean_q:
            return "Please provide a video or song to search."
        url = f"https://www.youtube.com/results?search_query={clean_q.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Searching YouTube for '{clean_q}'!"

    @staticmethod
    def open_url(url: str) -> str:
        """Opens a website URL in the default browser."""
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url
        webbrowser.open(clean_url)
        return f"Opening {clean_url} in your browser!"

    @staticmethod
    def open_application(app_name: str) -> str:
        """Launches requested Windows application or tool."""
        lower = app_name.lower().strip()

        # Application mapping
        app_commands = {
            "chrome": ["start", "chrome"],
            "google chrome": ["start", "chrome"],
            "browser": ["start", "https://google.com"],
            "notepad": ["notepad.exe"],
            "text editor": ["notepad.exe"],
            "calculator": ["calc.exe"],
            "calc": ["calc.exe"],
            "vs code": ["code"],
            "vscode": ["code"],
            "code": ["code"],
            "terminal": ["powershell.exe"],
            "powershell": ["powershell.exe"],
            "cmd": ["cmd.exe"],
            "command prompt": ["cmd.exe"],
            "task manager": ["taskmgr.exe"],
            "taskmgr": ["taskmgr.exe"],
            "task manager": ["taskmgr.exe"],
            "explorer": ["explorer.exe"],
            "file explorer": ["explorer.exe"],
            "my files": ["explorer.exe"],
            "downloads": ["explorer.exe", os.path.join(os.path.expanduser("~"), "Downloads")],
            "documents": ["explorer.exe", os.path.join(os.path.expanduser("~"), "Documents")],
            "pictures": ["explorer.exe", os.path.join(os.path.expanduser("~"), "Pictures")],
            "desktop": ["explorer.exe", os.path.join(os.path.expanduser("~"), "Desktop")],
            "settings": ["start", "ms-settings:"],
            "windows settings": ["start", "ms-settings:"],
            "spotify": ["start", "spotify:"],
            "paint": ["mspaint.exe"],
            "word": ["start", "winword"],
            "excel": ["start", "excel"]
        }

        # Check direct mapping
        for key, cmd in app_commands.items():
            if key == lower or lower in key or key in lower:
                try:
                    if cmd[0] == "start":
                        subprocess.Popen(f"start {' '.join(cmd[1:])}", shell=True)
                    else:
                        subprocess.Popen(cmd)
                    return f"Opening {key.title()} for you!"
                except Exception as e:
                    return f"I tried to launch {key.title()}, but encountered: {e}"

        # Fallback to shell start
        try:
            subprocess.Popen(f"start {lower}", shell=True)
            return f"Launching {app_name} for you!"
        except Exception as e:
            return f"Could not launch {app_name}: {e}"

    @staticmethod
    def execute_action_tag(action_str: str) -> str:
        """Executes a structured action tag generated by the AI or command pipeline."""
        # Examples: [ACTION: OPEN_APP "notepad"], [ACTION: CHECK_BATTERY], [ACTION: LOCK_LAPTOP]
        upper = action_str.upper()
        if "CHECK_BATTERY" in upper or "BATTERY" in upper:
            return LaptopController.get_battery_info()
        elif "SYSTEM_HEALTH" in upper or "HEALTH" in upper:
            return LaptopController.get_system_health()
        elif "LOCK_LAPTOP" in upper or "LOCK" in upper:
            return LaptopController.lock_laptop()
        elif "SCREENSHOT" in upper:
            return LaptopController.take_screenshot()
        elif "VOLUME_UP" in upper:
            return LaptopController.volume_up()
        elif "VOLUME_DOWN" in upper:
            return LaptopController.volume_down()
        elif "VOLUME_MUTE" in upper:
            return LaptopController.volume_mute_toggle()
        elif "SHOW_DESKTOP" in upper:
            return LaptopController.show_desktop()
        elif "SEARCH_WEB" in upper:
            m = re.search(r'SEARCH_WEB\s*["\']([^"\']+)["\']', action_str, re.IGNORECASE)
            if m:
                return LaptopController.search_web(m.group(1))
        elif "SEARCH_YOUTUBE" in upper:
            m = re.search(r'SEARCH_YOUTUBE\s*["\']([^"\']+)["\']', action_str, re.IGNORECASE)
            if m:
                return LaptopController.search_youtube(m.group(1))
        elif "OPEN_APP" in upper:
            m = re.search(r'OPEN_APP\s*["\']([^"\']+)["\']', action_str, re.IGNORECASE)
            if m:
                return LaptopController.open_application(m.group(1))
        elif "OPEN_URL" in upper:
            m = re.search(r'OPEN_URL\s*["\']([^"\']+)["\']', action_str, re.IGNORECASE)
            if m:
                return LaptopController.open_url(m.group(1))
        return "Action not recognized."
