# actions/computer_settings.py — JARVIS: volume / brightness / window control
# Uses pyautogui media keys for volume and WMI/screen-brightness for brightness.

import sys

from ._common import user_name, log, say


def computer_settings(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    desc  = (params.get("description") or params.get("task") or "").strip().lower()
    value = params.get("value")
    u = user_name()

    try:
        import pyautogui
    except Exception:
        return f"System settings control needs pyautogui installed, {u}."

    try:
        # ── Volume ──────────────────────────────────────────────
        if "mute" in desc:
            pyautogui.press("volumemute")
            msg = f"Toggled mute, {u}."
        elif "volume" in desc or "sound" in desc:
            if "up" in desc or "increase" in desc or "raise" in desc:
                for _ in range(int(value or 5)):
                    pyautogui.press("volumeup")
                msg = f"Volume up, {u}."
            elif "down" in desc or "decrease" in desc or "lower" in desc:
                for _ in range(int(value or 5)):
                    pyautogui.press("volumedown")
                msg = f"Volume down, {u}."
            elif "max" in desc:
                for _ in range(50):
                    pyautogui.press("volumeup")
                msg = f"Volume at maximum, {u}."
            else:
                msg = f"Tell me whether to raise or lower the volume, {u}."

        # ── Brightness ──────────────────────────────────────────
        elif "brightness" in desc:
            msg = _set_brightness(desc, value, u)

        # ── Window management ───────────────────────────────────
        elif "minimize" in desc and "all" in desc:
            pyautogui.hotkey("win", "d")
            msg = f"Minimised everything, {u}."
        elif "maximize" in desc:
            pyautogui.hotkey("win", "up")
            msg = f"Maximised the window, {u}."
        elif "minimize" in desc:
            pyautogui.hotkey("win", "down")
            msg = f"Minimised the window, {u}."
        elif "lock" in desc:
            pyautogui.hotkey("win", "l")
            msg = f"Locking the screen, {u}."
        elif "switch" in desc or "alt tab" in desc:
            pyautogui.hotkey("alt", "tab")
            msg = f"Switched windows, {u}."
        else:
            msg = f"I'm not sure how to adjust that setting, {u}."

        log(f"[Settings] {desc}", player)
        say(speak, msg)
        return msg

    except Exception as e:
        msg = f"That setting change failed, {u}: {str(e)[:100]}"
        log(f"[Settings] error: {e}", player)
        return msg


def _set_brightness(desc: str, value, u: str) -> str:
    try:
        import screen_brightness_control as sbc
        current = sbc.get_brightness(display=0)
        current = current[0] if isinstance(current, list) else current
        if value is not None:
            level = int(value)
        elif "up" in desc or "increase" in desc:
            level = min(100, current + 20)
        elif "down" in desc or "decrease" in desc or "dim" in desc:
            level = max(0, current - 20)
        elif "max" in desc:
            level = 100
        else:
            level = current
        sbc.set_brightness(level)
        return f"Brightness set to {level}%, {u}."
    except Exception:
        return f"I couldn't adjust brightness — install screen-brightness-control, {u}."
