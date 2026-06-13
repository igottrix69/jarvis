# actions/computer_control.py — JARVIS: low-level mouse / keyboard / clipboard
# Requires pyautogui (and pyperclip for clipboard). Degrades gracefully.

from ._common import user_name, log, say


def computer_control(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "").strip().lower()
    text   = params.get("text", "")
    u = user_name()

    try:
        import pyautogui
        pyautogui.FAILSAFE = True
    except Exception:
        return f"Mouse and keyboard control needs pyautogui installed, {u}. Run setup.py."

    try:
        if action == "type":
            pyautogui.typewrite(str(text), interval=0.02)
            msg = f"Typed it, {u}."

        elif action == "press":
            pyautogui.press(str(text or "enter"))
            msg = f"Pressed {text or 'enter'}, {u}."

        elif action == "hotkey":
            keys = [k.strip() for k in str(text).replace("+", " ").split() if k.strip()]
            if keys:
                pyautogui.hotkey(*keys)
            msg = f"Sent {'+'.join(keys)}, {u}."

        elif action == "click":
            pyautogui.click()
            msg = f"Clicked, {u}."

        elif action == "scroll":
            amount = int(params.get("value", -500) or -500)
            pyautogui.scroll(amount)
            msg = f"Scrolled, {u}."

        elif action == "screenshot":
            from pathlib import Path
            out = Path.home() / "Desktop" / "jarvis_screenshot.png"
            pyautogui.screenshot(str(out))
            msg = f"Screenshot saved to your Desktop, {u}."

        elif action in ("copy", "paste"):
            import pyperclip
            if action == "copy" and text:
                pyperclip.copy(str(text))
                msg = f"Copied to the clipboard, {u}."
            else:
                msg = pyperclip.paste()

        else:
            msg = f"I don't recognise the control action '{action}', {u}."

        log(f"[Control] {action}", player)
        say(speak, msg if len(msg) < 150 else f"Done, {u}.")
        return msg

    except Exception as e:
        msg = f"That control action failed, {u}: {str(e)[:100]}"
        log(f"[Control] error: {e}", player)
        return msg
