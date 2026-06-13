# actions/desktop_control.py — JARVIS: desktop wallpaper / organisation / stats

import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from ._common import user_name, log, say

DESKTOP = Path.home() / "Desktop"

CATEGORIES = {
    "Images":    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"},
    "Spreadsheets": {".xls", ".xlsx", ".csv"},
    "Videos":    {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    "Audio":     {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Installers":{".exe", ".msi", ".dmg"},
    "Code":      {".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".cpp"},
}


def desktop_control(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "stats").strip().lower()
    u = user_name()

    try:
        if action == "organize" or action == "clean":
            return _organize(u, player, speak)
        if action == "wallpaper":
            return _wallpaper(params.get("task") or params.get("path"), u)
        if action == "list":
            items = sorted(os.listdir(DESKTOP))[:60]
            return f"Your desktop has {len(items)} items: {', '.join(items)}"
        # stats
        return _stats(u)
    except Exception as e:
        msg = f"That desktop action failed, {u}: {str(e)[:100]}"
        log(f"[Desktop] error: {e}", player)
        return msg


def _organize(u, player, speak) -> str:
    moved = 0
    for entry in list(DESKTOP.iterdir()):
        if entry.is_dir() or entry.name.startswith("."):
            continue
        ext = entry.suffix.lower()
        category = next((c for c, exts in CATEGORIES.items() if ext in exts), "Other")
        dest_dir = DESKTOP / category
        dest_dir.mkdir(exist_ok=True)
        try:
            shutil.move(str(entry), str(dest_dir / entry.name))
            moved += 1
        except Exception:
            pass
    log(f"[Desktop] organised {moved} files", player)
    msg = f"I tidied your desktop, {u} — sorted {moved} files into category folders."
    say(speak, msg)
    return msg


def _stats(u) -> str:
    counts = defaultdict(int)
    total = 0
    for entry in DESKTOP.iterdir():
        if entry.is_file():
            ext = entry.suffix.lower()
            category = next((c for c, exts in CATEGORIES.items() if ext in exts), "Other")
            counts[category] += 1
            total += 1
    if not total:
        return f"Your desktop is spotless, {u}."
    breakdown = ", ".join(f"{n} {c.lower()}" for c, n in sorted(counts.items(), key=lambda x: -x[1]))
    return f"Your desktop has {total} loose files, {u}: {breakdown}."


def _wallpaper(path, u) -> str:
    if not path:
        return f"Point me at an image to set as wallpaper, {u}."
    img = Path(os.path.expanduser(str(path)))
    if not img.exists():
        return f"I couldn't find that image, {u}: {img}"
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(img.resolve()), 3)
            return f"Wallpaper updated, {u}."
        return f"Wallpaper setting is Windows-only in this build, {u}."
    except Exception as e:
        return f"I couldn't set the wallpaper, {u}: {str(e)[:80]}"
