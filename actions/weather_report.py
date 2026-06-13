# actions/weather_report.py
# JARVIS — Weather Report
#
# Uses browser_control to open Google Weather and scrapes the result.
# Falls back to webbrowser.open if browser_control is unavailable.
# Speaks a natural summary via the speak callback.

import re
import time
import webbrowser
from urllib.parse import quote_plus
from pathlib import Path


def weather_report(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    Gets weather for a city and speaks a natural summary.

    parameters:
        city  (str, required) — city name
        time  (str, optional) — 'today', 'tomorrow', 'this week', etc.
        units (str, optional) — 'metric' (default) or 'imperial'
    """
    params = parameters or {}
    city   = (params.get("city") or "").strip()
    when   = (params.get("time") or "today").strip()
    units  = params.get("units", "metric")

    if not city:
        msg = f"I need a city name to check the weather, {_user()}."
        _log(msg, player)
        return msg

    if player:
        player.write_log(f"[Weather] {city} / {when}")

    # Build search query
    search_query  = f"weather in {city} {when}"
    encoded_query = quote_plus(search_query)
    url           = f"https://www.google.com/search?q={encoded_query}"

    # Try browser_control first (gives us scrapeable text)
    raw_text = _try_browser_scrape(url)

    if raw_text:
        summary = _parse_weather(raw_text, city, when)
    else:
        # Fallback: just open browser
        try:
            webbrowser.open(url)
        except Exception as e:
            msg = f"I couldn't open the browser for the weather report, {_user()}: {e}"
            _log(msg, player)
            return msg
        summary = f"I've opened the weather for {city} in your browser, {_user()}."

    _log(summary, player)

    if speak:
        speak(summary)

    if session_memory:
        try:
            session_memory.set_last_search(query=search_query, response=summary)
        except Exception:
            pass

    return summary


def _try_browser_scrape(url: str) -> str | None:
    """Attempt to use browser_control to get page text."""
    try:
        from actions.browser_control import browser_control

        browser_control({"action": "go_to", "url": url})
        time.sleep(3)
        text = browser_control({"action": "get_text"})
        return text if text and len(text) > 50 else None
    except Exception as e:
        print(f"[Weather] ⚠️ Browser scrape failed: {e}")
        return None


def _parse_weather(raw_text: str, city: str, when: str) -> str:
    """
    Uses Gemini to extract a natural weather summary from raw page text.
    Falls back to a simple regex parse.
    """
    try:
        from pathlib import Path
        import json, sys

        base = Path(__file__).resolve().parent.parent
        cfg  = json.loads((base / "config" / "config.json").read_text())
        key  = cfg.get("gemini_api_key", "")

        if not key:
            raise ValueError("No API key")

        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        prompt = (
            f"Extract the weather summary for {city} ({when}) from this page text.\n"
            f"Return ONE sentence like: 'It is currently 22°C and partly cloudy in {city}, "
            f"with a high of 25°C and a low of 18°C.'\n"
            f"If no data found, return: NO_DATA\n\n"
            f"Page text:\n{raw_text[:3000]}\n\nSummary:"
        )

        response = model.generate_content(prompt)
        result   = response.text.strip()

        if result and result != "NO_DATA" and len(result) > 10:
            return result

    except Exception as e:
        print(f"[Weather] ⚠️ Gemini parse failed: {e}")

    # Regex fallback — look for temperature patterns
    temp_match = re.search(r"(\d{1,3})[°º]?\s*[CF]", raw_text)
    if temp_match:
        return f"The current temperature in {city} is around {temp_match.group(0)}, {_user()}."

    return f"I've pulled up the weather for {city} in your browser, {_user()}."


def _user() -> str:
    try:
        from pathlib import Path
        import json
        cfg = json.loads((Path(__file__).resolve().parent.parent / "config" / "config.json").read_text())
        return cfg.get("user_name", "sir")
    except Exception:
        return "sir"


def _log(message: str, player=None):
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
