# actions/screen_process.py — JARVIS: analyse the screen or camera with vision AI

import io
import time
from pathlib import Path

from ._common import user_name, api_key, log, say


def screen_process(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    question = (params.get("text") or params.get("question") or "Describe what you see.").strip()
    angle    = (params.get("angle") or "screen").strip().lower()
    u = user_name()

    img_bytes = _grab_camera() if angle == "camera" else _grab_screen()
    if img_bytes is None:
        return f"I couldn't capture the {angle}, {u}. The relevant module may not be installed."

    answer = _vision(img_bytes, question)
    if not answer:
        return f"I captured the {angle} but my vision core is offline, {u}. Add a Gemini API key."

    log(f"[Vision] {angle}: {question[:40]}", player)
    say(speak, answer)
    return answer


def _grab_screen():
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as e:
        print(f"[Vision] screen grab failed: {e}")
        return None


def _grab_camera():
    try:
        import cv2
        from ._common import load_config
        idx = int(load_config().get("camera_index", 0))
        cap = cv2.VideoCapture(idx)
        time.sleep(0.4)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        ok, buf = cv2.imencode(".png", frame)
        return buf.tobytes() if ok else None
    except Exception as e:
        print(f"[Vision] camera grab failed: {e}")
        return None


def _vision(img_bytes: bytes, question: str) -> str | None:
    key = api_key()
    if not key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content([
            question,
            {"mime_type": "image/png", "data": img_bytes},
        ])
        return (resp.text or "").strip()
    except Exception as e:
        print(f"[Vision] gemini failed: {e}")
        return None
