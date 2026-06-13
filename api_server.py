"""
api_server.py — JARVIS REST API Bridge
=======================================
Lightweight Flask server that bridges the HTML UI to the Python backend.
The UI sends text commands here; this server routes them through the
ToolRouter + ActionDispatcher and returns JSON responses.

Run alongside main.py for the full experience, or standalone for text-only mode.

Usage:
    python api_server.py
    # Then open ui/index.html in browser
"""

import json
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:
    from flask import Flask, jsonify, request
    from flask_cors import CORS
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False
    print("[API] ⚠️ Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

from main import (
    SessionMemory, LongTermMemory, Player,
    ToolRouter, ActionDispatcher, CONFIG, USERNAME
)

# ── Setup ─────────────────────────────────────────────────────────────────────
app            = Flask(__name__)
CORS(app, origins=["*"])

session_memory = SessionMemory()
long_memory    = LongTermMemory()
player         = Player(session_memory)
router         = ToolRouter()
dispatcher     = ActionDispatcher(player, session_memory, long_memory)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({
        "status": "online",
        "user":   USERNAME,
        "voice":  CONFIG.get("voice", "Charon"),
        "turns":  len(session_memory.recent_turns(100)),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data     = request.get_json(force=True)
    text     = (data.get("text") or "").strip()

    if not text:
        return jsonify({"response": "No input received.", "tool": None}), 400

    player.write_log(f"[API] User: {text}")
    session_memory.add_turn("user", text)

    # Route to tool
    routed = router.route(text, session_memory)

    tool     = None
    response = ""

    if routed:
        tool, parameters = routed
        player.write_log(f"[API] Tool: {tool}")
        result   = dispatcher.dispatch(tool, parameters)
        response = _format_response(tool, parameters, result)
    else:
        # Pure conversation — use Gemini directly
        response = _conversation_reply(text)

    session_memory.add_turn("jarvis", response)
    player.write_log(f"[API] JARVIS: {response[:80]}")

    return jsonify({
        "response": response,
        "tool":     tool,
    })


@app.route("/api/log", methods=["GET"])
def get_log():
    """Returns recent session log entries."""
    log_path = BASE_DIR / "memory" / "session.log"
    if not log_path.exists():
        return jsonify({"lines": []})
    lines = log_path.read_text(encoding="utf-8").splitlines()[-50:]
    return jsonify({"lines": lines})


@app.route("/api/memory", methods=["GET"])
def get_memory():
    return jsonify(long_memory.get_all())


@app.route("/api/clear", methods=["POST"])
def clear_session():
    global session_memory
    session_memory = SessionMemory()
    return jsonify({"status": "cleared"})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_response(tool: str, params: dict, result: str) -> str:
    """Turn a raw tool result into a natural JARVIS response."""
    try:
        from pathlib import Path
        import google.generativeai as genai

        cfg = json.loads((BASE_DIR / "config" / "config.json").read_text())
        genai.configure(api_key=cfg["gemini_api_key"])
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        prompt = (
            f"You are JARVIS. Summarize this tool result in 1-2 natural sentences "
            f"as if speaking to '{USERNAME}'. Be concise and helpful.\n\n"
            f"Tool: {tool}\n"
            f"Result: {result[:800]}\n\n"
            f"Response:"
        )
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception:
        return result[:400] if result else f"Done, {USERNAME}."


def _conversation_reply(text: str) -> str:
    """Direct Gemini reply for non-tool conversation."""
    try:
        import google.generativeai as genai
        cfg = json.loads((BASE_DIR / "config" / "config.json").read_text())
        genai.configure(api_key=cfg["gemini_api_key"])
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        recent = session_memory.recent_turns(4)
        ctx    = "\n".join(f"{t['role']}: {t['text']}" for t in recent)

        prompt = (
            f"You are JARVIS. Recent conversation:\n{ctx}\n\n"
            f"User: {text}\n\n"
            f"Respond in 1-2 sentences max. Address user as '{USERNAME}'. "
            f"Be precise and intelligent, like Tony Stark's AI."
        )
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        return f"I encountered a slight issue with that request, {USERNAME}: {str(e)[:80]}"


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("  JARVIS API Server")
    print(f"  http://localhost:5001")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
