# actions/open_app.py — JARVIS: launch applications (cross-platform, Windows-first)

import os
import shutil
import subprocess
import sys
import webbrowser

from ._common import user_name, log, say

# Friendly name → how to launch it.
WINDOWS_APPS = {
    "chrome":      "chrome",
    "google chrome": "chrome",
    "edge":        "msedge",
    "firefox":     "firefox",
    "notepad":     "notepad",
    "calculator":  "calc",
    "calc":        "calc",
    "paint":       "mspaint",
    "explorer":    "explorer",
    "file explorer": "explorer",
    "cmd":         "cmd",
    "command prompt": "cmd",
    "powershell":  "powershell",
    "terminal":    "wt",
    "vscode":      "code",
    "vs code":     "code",
    "visual studio code": "code",
    "spotify":     "spotify",
    "word":        "winword",
    "excel":       "excel",
    "powerpoint":  "powerpnt",
    "outlook":     "outlook",
    "settings":    "ms-settings:",
    "task manager": "taskmgr",
    "snipping tool": "snippingtool",
}

# Apps that are really websites.
WEB_APPS = {
    "youtube":  "https://youtube.com",
    "gmail":    "https://mail.google.com",
    "maps":     "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "github":   "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "chatgpt":  "https://chat.openai.com",
    "netflix":  "https://netflix.com",
    "twitter":  "https://twitter.com",
    "x":        "https://x.com",
    "reddit":   "https://reddit.com",
}


def open_app(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    app = (params.get("app_name") or params.get("name") or params.get("app") or "").strip().lower()

    if not app:
        msg = f"Which application would you like me to open, {user_name()}?"
        log(f"[OpenApp] {msg}", player)
        return msg

    # Website "apps"
    if app in WEB_APPS:
        webbrowser.open(WEB_APPS[app])
        msg = f"Opening {app}, {user_name()}."
        log(f"[OpenApp] web → {WEB_APPS[app]}", player)
        say(speak, msg)
        return msg

    target = WINDOWS_APPS.get(app, app)

    try:
        if sys.platform.startswith("win"):
            if target.startswith("ms-settings:"):
                os.startfile(target)  # type: ignore[attr-defined]
            else:
                # `start` resolves apps on PATH and registered app paths.
                subprocess.Popen(f'start "" "{target}"', shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", target])
        else:
            launcher = shutil.which(target) or target
            subprocess.Popen([launcher])

        msg = f"Opening {app}, {user_name()}."
        log(f"[OpenApp] launched → {target}", player)
        say(speak, msg)
        return msg

    except Exception as e:
        # Last resort: maybe it's a URL or a misnamed site.
        if "." in app:
            webbrowser.open(app if app.startswith("http") else f"https://{app}")
            return f"Opening {app} in your browser, {user_name()}."
        msg = f"I couldn't open {app}, {user_name()}: {str(e)[:80]}"
        log(f"[OpenApp] error: {e}", player)
        return msg
