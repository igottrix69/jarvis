# actions/_common.py
# Shared helpers for JARVIS action modules: config, Gemini, logging, speech.

import json
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def user_name() -> str:
    return load_config().get("user_name", "sir")


def api_key() -> str:
    return load_config().get("gemini_api_key", "")


def gemini(model_name: str = "gemini-2.5-flash"):
    """Return a configured google.generativeai model, or None if unavailable."""
    key = api_key()
    if not key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        print(f"[Gemini] init failed: {e}")
        return None


def ask_gemini(prompt: str, model_name: str = "gemini-2.5-flash") -> str | None:
    model = gemini(model_name)
    if model is None:
        return None
    try:
        resp = model.generate_content(prompt)
        return (resp.text or "").strip()
    except Exception as e:
        print(f"[Gemini] generate failed: {e}")
        return None


def log(message: str, player=None):
    if player:
        try:
            player.write_log(message)
            return
        except Exception:
            pass
    print(message)


def say(speak, message: str):
    """Push a message to the live voice channel if a speak callback exists."""
    if speak:
        try:
            speak(message)
        except Exception:
            pass
