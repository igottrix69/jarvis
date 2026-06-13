"""
J.A.R.V.I.S — Just A Rather Very Intelligent System
=====================================================
Main orchestrator. Voice-in, voice-out, tool-dispatched.

Architecture:
  - Gemini Live API  : real-time voice session (speech in / audio out)
  - Gemini Flash     : intent parsing + tool routing
  - Action modules   : modular capability plugins
  - Session memory   : short-term context across turns
  - Long-term memory : persistent JSON store
"""

import asyncio
import base64
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import pyaudio
from google import genai
from google.genai import types

# ── Path Setup ──────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent
CONFIG_PATH     = BASE_DIR / "config" / "config.json"
MEMORY_PATH     = BASE_DIR / "memory" / "long_term.json"
SESSION_LOG     = BASE_DIR / "memory" / "session.log"

# ── Audio Constants ──────────────────────────────────────────────────────────
FORMAT              = pyaudio.paInt16
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

LIVE_MODEL   = "models/gemini-2.5-flash-native-audio-preview-12-2025"
ROUTER_MODEL = "gemini-2.5-flash"

# ── Load Config ──────────────────────────────────────────────────────────────
def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        default = {
            "gemini_api_key": "",
            "user_name": "sir",
            "voice": "Charon",
            "wake_word": "jarvis",
            "camera_index": 0
        }
        CONFIG_PATH.write_text(json.dumps(default, indent=4))
        print(f"[JARVIS] ⚙️  Config created at {CONFIG_PATH}")
        print("[JARVIS] ⚠️  Please add your Gemini API key to config/config.json")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())

CONFIG   = load_config()
API_KEY  = CONFIG.get("gemini_api_key", "")
USERNAME = CONFIG.get("user_name", "sir")
VOICE    = CONFIG.get("voice", "Charon")

if not API_KEY:
    print("[JARVIS] ❌ No API key found. Set gemini_api_key in config/config.json")
    sys.exit(1)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are J.A.R.V.I.S — Just A Rather Very Intelligent System.
You are the AI assistant of the user. Address them as '{USERNAME}'.

Personality:
- Precise, intelligent, and slightly witty — like Tony Stark's JARVIS
- Proactive: anticipate needs, offer insights the user didn't ask for
- Concise: no filler. Get to the point fast.
- Loyal and adaptive: remember preferences, adapt to the user's style

Capabilities you can invoke (say what you're doing naturally):
- Open applications, search the web, control the browser
- Manage files and the desktop
- Write, edit, run, and debug code
- Control computer settings (volume, brightness, windows)
- Set reminders and manage tasks
- Analyze the screen or camera
- Search for flights, summarize YouTube videos

When you need to take an action, you'll receive tool results and should 
narrate them naturally. Keep responses under 3 sentences unless detail is needed.
Never say "As an AI" or "I'm just a language model". You ARE JARVIS."""

# ── Session Memory ────────────────────────────────────────────────────────────
class SessionMemory:
    def __init__(self):
        self._data: dict = {
            "turns": [],
            "context": {},
            "last_action": None,
        }

    def add_turn(self, role: str, text: str):
        self._data["turns"].append({
            "role": role,
            "text": text,
            "time": time.strftime("%H:%M:%S")
        })
        if len(self._data["turns"]) > 40:
            self._data["turns"] = self._data["turns"][-40:]

    def set_context(self, key: str, value):
        self._data["context"][key] = value

    def get_context(self, key: str, default=None):
        return self._data["context"].get(key, default)

    def set_last_action(self, action: str, result: str):
        self._data["last_action"] = {"action": action, "result": result}

    def recent_turns(self, n: int = 6) -> list:
        return self._data["turns"][-n:]

    def set_last_search(self, query: str, response: str):
        self.set_context("last_search", {"query": query, "response": response})

# ── Long-Term Memory ──────────────────────────────────────────────────────────
class LongTermMemory:
    def __init__(self):
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if MEMORY_PATH.exists():
            try:
                self._data = json.loads(MEMORY_PATH.read_text())
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def remember(self, key: str, value):
        self._data[key] = value
        self._save()

    def recall(self, key: str, default=None):
        return self._data.get(key, default)

    def _save(self):
        MEMORY_PATH.write_text(json.dumps(self._data, indent=2))

    def get_all(self) -> dict:
        return dict(self._data)

# ── Player (logging + TTS bridge) ─────────────────────────────────────────────
class Player:
    def __init__(self, session_memory: SessionMemory):
        self.memory = session_memory
        SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)

    def write_log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        print(line.strip())
        try:
            with open(SESSION_LOG, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

# ── Tool Router ───────────────────────────────────────────────────────────────
class ToolRouter:
    """Routes natural language intents to action modules via Gemini."""

    TOOLS_SCHEMA = [
        {
            "name": "open_app",
            "description": "Open an application on the computer",
            "parameters": {"app_name": "string — name of the app to open"}
        },
        {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {"query": "string — search query", "mode": "search|compare"}
        },
        {
            "name": "browser_control",
            "description": "Control the browser — navigate, click, type, search",
            "parameters": {
                "action": "go_to|search|click|type|scroll|get_text|close",
                "url": "optional URL",
                "query": "optional search query",
                "text": "optional text to click or type"
            }
        },
        {
            "name": "computer_settings",
            "description": "Control system settings — volume, brightness, windows",
            "parameters": {"description": "string — what to do", "value": "optional numeric value"}
        },
        {
            "name": "computer_control",
            "description": "Low-level computer control — mouse, keyboard, clipboard",
            "parameters": {"action": "type|click|hotkey|press|scroll|screenshot", "text": "optional"}
        },
        {
            "name": "file_controller",
            "description": "Manage files and folders — create, delete, move, read, find",
            "parameters": {
                "action": "list|create_file|create_folder|delete|move|copy|rename|read|write|find",
                "path": "optional path",
                "name": "optional filename"
            }
        },
        {
            "name": "code_helper",
            "description": "Write, edit, explain, run, build, debug, or optimize code",
            "parameters": {
                "action": "write|edit|explain|run|build|optimize|auto",
                "description": "what to build or change",
                "language": "programming language",
                "file_path": "optional path to existing file"
            }
        },
        {
            "name": "dev_agent",
            "description": "Build a complete multi-file software project from scratch",
            "parameters": {
                "description": "what the project should do",
                "language": "programming language",
                "project_name": "optional project name"
            }
        },
        {
            "name": "desktop_control",
            "description": "Manage the desktop — wallpaper, organize files, desktop cleanup",
            "parameters": {"action": "wallpaper|organize|clean|list|stats", "task": "optional natural language task"}
        },
        {
            "name": "cmd_control",
            "description": "Run terminal/command-line tasks",
            "parameters": {"task": "string — describe what to do"}
        },
        {
            "name": "screen_process",
            "description": "Analyze the screen or camera with vision AI",
            "parameters": {
                "text": "question about what you see",
                "angle": "screen|camera"
            }
        },
        {
            "name": "youtube_video",
            "description": "Play, summarize, or get info about YouTube videos",
            "parameters": {
                "action": "play|summarize|get_info|trending",
                "query": "optional search query",
                "region": "optional country code for trending"
            }
        },
        {
            "name": "reminder",
            "description": "Set a timed reminder",
            "parameters": {
                "date": "YYYY-MM-DD",
                "time": "HH:MM",
                "message": "reminder message"
            }
        },
        {
            "name": "weather_report",
            "description": "Get weather information for a city",
            "parameters": {"city": "city name", "time": "optional — today/tomorrow/etc"}
        },
        {
            "name": "flight_finder",
            "description": "Search for flights between cities",
            "parameters": {
                "origin": "departure city or airport",
                "destination": "arrival city",
                "date": "departure date",
                "cabin": "economy|business|first"
            }
        },
    ]

    def __init__(self):
        self._client = genai.Client(api_key=API_KEY)

    def route(self, user_text: str, session_memory: SessionMemory) -> tuple[str, dict] | None:
        """
        Given user speech, returns (tool_name, parameters) or None if no tool needed.
        """
        recent = session_memory.recent_turns(4)
        context = "\n".join(f"{t['role']}: {t['text']}" for t in recent)

        tools_desc = json.dumps(self.TOOLS_SCHEMA, indent=2)

        prompt = f"""You are a tool router for JARVIS, an AI assistant.

Recent conversation:
{context}

User just said: "{user_text}"

Available tools:
{tools_desc}

Decide: does this request require a tool?
- If YES: respond with JSON: {{"tool": "tool_name", "parameters": {{...}}}}
- If NO (it's casual conversation, a question you can answer directly, or a follow-up):
  respond with exactly: {{"tool": null}}

Rules:
- Extract ALL relevant parameters from the user's words
- For dates/times, convert to standard formats
- Be decisive — if in doubt about casual vs tool, pick tool
- Only return the JSON. No explanation.

JSON:"""

        try:
            response = self._client.models.generate_content(
                model=ROUTER_MODEL,
                contents=prompt
            )
            text = response.text.strip()
            text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
            parsed = json.loads(text)
            tool = parsed.get("tool")
            if not tool:
                return None
            return tool, parsed.get("parameters", {})
        except Exception as e:
            print(f"[Router] ⚠️ Routing error: {e}")
            return None

# ── Action Dispatcher ─────────────────────────────────────────────────────────
class ActionDispatcher:
    """Lazy-loads and calls action modules."""

    def __init__(self, player: Player, session_memory: SessionMemory, long_memory: LongTermMemory):
        self.player = player
        self.session = session_memory
        self.memory = long_memory
        self._modules: dict = {}

    def _load(self, name: str):
        if name in self._modules:
            return self._modules[name]
        try:
            import importlib
            mod = importlib.import_module(f"actions.{name}")
            self._modules[name] = mod
            return mod
        except ImportError as e:
            print(f"[Dispatcher] ⚠️ Module not found: {name} ({e})")
            return None

    def dispatch(self, tool: str, parameters: dict, speak=None) -> str:
        self.player.write_log(f"[Action] {tool} → {json.dumps(parameters)[:80]}")

        mod = self._load(tool)
        if mod is None:
            return f"I don't have a module for '{tool}' yet, {USERNAME}."

        fn = getattr(mod, tool, None)
        if fn is None:
            fn_names = [x for x in dir(mod) if not x.startswith("_") and callable(getattr(mod, x))]
            if fn_names:
                fn = getattr(mod, fn_names[0])
            else:
                return f"No callable found in module '{tool}'."

        try:
            kwargs = {
                "parameters": parameters,
                "player": self.player,
                "session_memory": self.session,
            }
            import inspect
            sig = inspect.signature(fn)
            if "speak" in sig.parameters and speak:
                kwargs["speak"] = speak
            if "response" in sig.parameters:
                kwargs["response"] = None

            result = fn(**kwargs)
            self.session.set_last_action(tool, str(result)[:200])
            return str(result) if result else "Done."
        except Exception as e:
            print(f"[Dispatcher] ❌ {tool} failed: {e}")
            import traceback; traceback.print_exc()
            return f"That action ran into an issue, {USERNAME}: {str(e)[:100]}"

# ── Main JARVIS Session ───────────────────────────────────────────────────────
class JarvisSession:

    def __init__(self):
        self.session_memory  = SessionMemory()
        self.long_memory     = LongTermMemory()
        self.player          = Player(self.session_memory)
        self.router          = ToolRouter()
        self.dispatcher      = ActionDispatcher(self.player, self.session_memory, self.long_memory)
        self._pya            = pyaudio.PyAudio()
        self._audio_out_q:   asyncio.Queue | None = None
        self._text_inject_q: asyncio.Queue | None = None
        self._session        = None

    async def run(self):
        client = genai.Client(
            api_key=API_KEY,
            http_options={"api_version": "v1beta"}
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=SYSTEM_PROMPT,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE
                    )
                )
            ),
        )

        print(f"\n{'='*60}")
        print(f"  J.A.R.V.I.S  —  Online")
        print(f"  Voice: {VOICE}  |  User: {USERNAME}")
        print(f"{'='*60}\n")

        while True:
            try:
                print("[JARVIS] 🔌 Connecting to Gemini Live...")
                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self._session        = session
                    self._audio_out_q    = asyncio.Queue()
                    self._text_inject_q  = asyncio.Queue()

                    print("[JARVIS] ✅ Connected. Listening...\n")
                    self.player.write_log("JARVIS online.")

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._mic_loop())
                        tg.create_task(self._recv_loop())
                        tg.create_task(self._play_loop())
                        tg.create_task(self._tool_inject_loop())

            except Exception as e:
                print(f"[JARVIS] ⚠️ Session dropped: {e} — reconnecting in 3s...")
                await asyncio.sleep(3)

    # ── Microphone ──────────────────────────────────────────────────────────
    async def _mic_loop(self):
        stream = await asyncio.to_thread(
            self._pya.open,
            format=FORMAT, channels=CHANNELS,
            rate=SEND_SAMPLE_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        try:
            while True:
                data = await asyncio.to_thread(stream.read, CHUNK_SIZE, False)
                b64  = base64.b64encode(data).decode("utf-8")
                await self._session.send_realtime_input(
                    audio=types.Blob(data=b64, mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}")
                )
        finally:
            stream.close()

    # ── Receive + Tool Routing ───────────────────────────────────────────────
    async def _recv_loop(self):
        user_transcript_buf   = []
        jarvis_transcript_buf = []

        async for response in self._session.receive():

            if response.data:
                await self._audio_out_q.put(response.data)

            sc = response.server_content
            if not sc:
                continue

            # Input transcription (what user said)
            if sc.input_transcription and sc.input_transcription.text:
                chunk = sc.input_transcription.text.strip()
                if chunk:
                    user_transcript_buf.append(chunk)

            # Output transcription (what JARVIS is saying)
            if sc.output_transcription and sc.output_transcription.text:
                chunk = sc.output_transcription.text.strip()
                if chunk:
                    jarvis_transcript_buf.append(chunk)

            if sc.turn_complete:
                if user_transcript_buf:
                    full_user = " ".join(user_transcript_buf).strip()
                    self.player.write_log(f"You: {full_user}")
                    self.session_memory.add_turn("user", full_user)

                    # Route to tools in background
                    asyncio.create_task(self._handle_tool(full_user))
                    user_transcript_buf = []

                if jarvis_transcript_buf:
                    full_jarvis = " ".join(jarvis_transcript_buf).strip()
                    self.player.write_log(f"JARVIS: {full_jarvis}")
                    self.session_memory.add_turn("jarvis", full_jarvis)
                    jarvis_transcript_buf = []

    # ── Tool Handling ────────────────────────────────────────────────────────
    async def _handle_tool(self, user_text: str):
        routed = await asyncio.to_thread(
            self.router.route, user_text, self.session_memory
        )

        if routed is None:
            return  # Pure conversation, JARVIS handles it natively

        tool, parameters = routed
        print(f"[JARVIS] 🔧 Tool: {tool}")

        # Announce action
        announce = self._tool_announcement(tool, parameters)
        if announce:
            await self._inject_text(announce)

        # Run tool in thread
        result = await asyncio.to_thread(
            self.dispatcher.dispatch, tool, parameters,
            lambda msg: asyncio.run_coroutine_threadsafe(
                self._inject_text(msg), asyncio.get_event_loop()
            )
        )

        # Feed result back to JARVIS voice
        feedback = f"Tool result for {tool}: {result[:500]}"
        await self._inject_text(f"Based on the action result: {result[:300]}")

    def _tool_announcement(self, tool: str, params: dict) -> str | None:
        announcements = {
            "web_search":        f"Searching for {params.get('query', 'that')}.",
            "open_app":          f"Opening {params.get('app_name', 'the application')}.",
            "code_helper":       f"Working on that code now.",
            "dev_agent":         f"Starting the build. This may take a moment.",
            "file_controller":   None,
            "screen_process":    f"Analyzing the {'screen' if params.get('angle') != 'camera' else 'camera feed'}.",
            "flight_finder":     f"Searching flights from {params.get('origin', '?')} to {params.get('destination', '?')}.",
            "youtube_video":     f"{'Playing' if params.get('action', 'play') == 'play' else 'Working on'} that YouTube request.",
            "reminder":          None,
            "weather_report":    f"Pulling up the weather for {params.get('city', 'that location')}.",
        }
        return announcements.get(tool)

    # ── Text Injection ───────────────────────────────────────────────────────
    async def _inject_text(self, text: str):
        """Injects text into the live session so JARVIS speaks it."""
        if self._session and text:
            try:
                await self._session.send_client_content(
                    turns={"parts": [{"text": text}]},
                    turn_complete=True
                )
            except Exception as e:
                print(f"[JARVIS] ⚠️ Inject error: {e}")

    async def _tool_inject_loop(self):
        """Processes queued text injections."""
        while True:
            text = await self._text_inject_q.get()
            await self._inject_text(text)

    # ── Audio Playback ───────────────────────────────────────────────────────
    async def _play_loop(self):
        stream = await asyncio.to_thread(
            self._pya.open,
            format=FORMAT, channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE, output=True
        )
        try:
            while True:
                chunk = await self._audio_out_q.get()
                await asyncio.to_thread(stream.write, chunk)
        finally:
            stream.close()


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    session = JarvisSession()
    try:
        asyncio.run(session.run())
    except KeyboardInterrupt:
        print("\n[JARVIS] Shutting down. Goodbye.")


if __name__ == "__main__":
    main()
