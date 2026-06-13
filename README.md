# J.A.R.V.I.S
### Just A Rather Very Intelligent System

An Iron Man-style AI assistant: a live mission-control **HUD** in the browser, **voice in / voice out** (free, browser-native), **Groq-powered reasoning** in the cloud, and an optional **local backend** that lets JARVIS actually control your PC.

> **Live demo:** _deployed on Vercel_ — open the URL, click ⚙ Settings, and you're talking to JARVIS.

---

## Two ways to run it

| | What you get | Needs |
|---|---|---|
| **☁️ Cloud (hosted)** | Full HUD, voice in/out, Groq (Llama 3.3 70B) reasoning. Works on any device, nothing to install. | Just a browser. A Groq key is configured server-side (or bring your own in Settings). |
| **🖥️ Local backend** | Everything above **plus** real desktop control — open apps, manage files, take screenshots, run code, set reminders, control the browser. | Python 3.11+ on your machine. |

The web HUD automatically uses whichever is available and falls back to an offline **demo mode** if neither is reachable, so it always responds.

---

## ☁️ The hosted web app

Pure HTML/CSS/JS HUD + two Vercel serverless functions:

```
index.html        ← the HUD (boot sequence, arc reactor, waveform, radar, chat)
api/chat.js       ← reasoning core — proxies to Groq (key stays server-side)
api/status.js     ← health check
vercel.json       ← config
```

### Features
- 🎙️ **Voice input** (Web Speech API) and 🔊 **voice replies** (Speech Synthesis) with a selectable JARVIS-style voice
- ⚡ **Fast reasoning** via Groq (Llama 3.3 70B) — near-instant responses
- 🧠 **Conversation memory** — context is sent with each turn and persisted in `localStorage`
- ⚙️ **Settings panel** — name, reasoning link (Cloud / Local / Demo), your own API key, voice on/off + voice picker, export chat
- 🟢 **Live connection indicator** — shows whether you're on `CLOUD`, `LOCAL`, or `DEMO`
- 📱 Responsive layout, full boot animation, animated system diagnostics

### Deploy your own
```bash
npm i -g vercel
vercel --prod
# then add the env var:
vercel env add GROQ_API_KEY
```
The key is read from `process.env.GROQ_API_KEY`. Get a free key (no credit card) at
[console.groq.com/keys](https://console.groq.com/keys) (it should start with `gsk_`).

No env var? No problem — visitors can paste their own key in **Settings** (stored only in their browser).

---

## 🖥️ The local backend (full PC control)

```
main.py              ← voice session (Gemini Live API — mic in / audio out)
api_server.py        ← REST bridge on :5001 (text in / JSON out, powers the HUD)
setup.py             ← one-time installer + configurator
requirements.txt

actions/             ← capability plugins (auto-routed by intent)
  open_app.py            launch apps / sites
  web_search.py          Gemini grounded search + DuckDuckGo fallback
  browser_control.py     Playwright browser automation
  computer_control.py    mouse / keyboard / clipboard (PyAutoGUI)
  computer_settings.py   volume / brightness / windows
  file_controller.py     create / move / delete / find files (recycle-bin safe)
  code_helper.py         write / edit / explain / run code
  dev_agent.py           build a full multi-file project from a prompt
  desktop_control.py     organise desktop, wallpaper, stats
  cmd_control.py         natural-language → safe shell command
  screen_process.py      screenshot / camera + vision analysis
  youtube_video.py       play / search / summarise videos
  reminder.py            timed reminders + popup
  weather_report.py      weather lookup with natural summary
  flight_finder.py       Google Flights search

config/config.json    ← API key + preferences (gitignored)
memory/               ← session log + long-term JSON memory
```

### Quick start
```bash
python setup.py          # installs deps, Playwright, creates config/config.json
# add your Gemini key to config/config.json
python api_server.py     # starts the REST bridge on http://localhost:5001
```
Then open the hosted site (or `index.html`), go to **Settings → Reasoning link → Local backend**. JARVIS now controls your machine.

For full **voice** mode (speak and hear JARVIS):
```bash
python main.py
```

### Voice commands — examples
| You say | JARVIS does |
|---|---|
| "Open Chrome" | Launches Chrome |
| "Search for SpaceX news" | Live grounded web search |
| "What's the weather in London?" | Scrape + summarise |
| "Write a Python script that…" | Generates, saves, runs code |
| "Build me a Flask todo app" | Full multi-file project |
| "Set a reminder for 3pm to call mum" | Timed reminder + popup |
| "What do you see on my screen?" | Screenshot + vision |
| "Turn the volume up" | System control |
| "Summarise this YouTube video …" | Transcript + summary |
| "Organize my desktop" | Sorts files by type |

---

## Configuration (`config/config.json`)
```json
{
  "gemini_api_key": "AIza...",
  "user_name": "sir",
  "voice": "Charon",
  "wake_word": "jarvis",
  "camera_index": 0
}
```
**Live-API voices:** Charon, Fenrir, Aoede, Kore, Puck, Schedar.

## Adding a new capability
Create `actions/my_tool.py` with a function named `my_tool`:
```python
def my_tool(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    return "Done."
```
Add it to `TOOLS_SCHEMA` in `main.py` — JARVIS auto-routes to it by intent.

---

## Requirements
- **Cloud:** any modern browser (Chrome/Edge for voice input).
- **Local:** Python 3.11+, microphone/speakers for voice mode, Gemini API key. Windows 10/11 best supported; macOS/Linux partial.

## Security notes
- `config/config.json` and `.env` are gitignored — your key is never committed.
- The serverless function keeps the server key out of the browser; user-supplied keys live only in that browser's `localStorage`.
- `cmd_control` refuses obviously destructive commands unless explicitly confirmed; file deletes go to the recycle bin.

---
*Cloud brain: Groq · Local voice + tools: Gemini · "Sometimes you gotta run before you can walk."*
