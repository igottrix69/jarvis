# actions/flight_finder.py — JARVIS: search flights via Google Flights

import webbrowser
from urllib.parse import quote_plus

from ._common import user_name, log, say


def flight_finder(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    origin = (params.get("origin") or "").strip()
    dest   = (params.get("destination") or params.get("dest") or "").strip()
    date   = (params.get("date") or "").strip()
    cabin  = (params.get("cabin") or "economy").strip()
    u = user_name()

    if not origin or not dest:
        return f"I need both a departure and arrival city to search flights, {u}."

    # Google Flights opens to a query-built search.
    query = f"flights from {origin} to {dest}"
    if date:
        query += f" on {date}"
    if cabin and cabin != "economy":
        query += f" {cabin} class"

    url = f"https://www.google.com/travel/flights?q={quote_plus(query)}"

    try:
        # Try to scrape a quick summary via browser_control; else just open.
        summary = _scrape(url)
    except Exception:
        summary = None

    if not summary:
        webbrowser.open(url)
        summary = f"I've opened Google Flights for {origin} to {dest}{' on ' + date if date else ''}, {u}."

    log(f"[Flights] {origin} → {dest} {date}", player)
    say(speak, summary)
    return summary


def _scrape(url: str) -> str | None:
    try:
        from actions.browser_control import browser_control
        browser_control({"action": "go_to", "url": url})
        import time
        time.sleep(4)
        text = browser_control({"action": "get_text"})
        if text and len(text) > 80:
            from ._common import ask_gemini
            return ask_gemini(
                "From this Google Flights page text, summarise the cheapest 1-2 options "
                f"(airline, price, times) in 2 sentences. If none found, reply NO_DATA.\n\n{text[:3500]}"
            )
    except Exception:
        return None
    return None
