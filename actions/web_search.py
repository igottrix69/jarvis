# actions/web_search.py — JARVIS: web search
# Primary: Gemini with Google Search grounding. Fallback: DuckDuckGo HTML scrape.

from urllib.parse import quote_plus

from ._common import user_name, api_key, log, say


def web_search(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    query = (params.get("query") or params.get("q") or "").strip()
    mode  = (params.get("mode") or "search").strip()

    if not query:
        msg = f"What would you like me to search for, {user_name()}?"
        return msg

    log(f"[WebSearch] {mode}: {query}", player)

    summary = _gemini_grounded(query, mode) or _duckduckgo(query)

    if not summary:
        summary = f"I couldn't retrieve results for '{query}' right now, {user_name()}."

    say(speak, summary)
    if session_memory:
        try:
            session_memory.set_last_search(query=query, response=summary)
        except Exception:
            pass
    return summary


def _gemini_grounded(query: str, mode: str) -> str | None:
    """Use the new google-genai client with the Google Search tool."""
    key = api_key()
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        instruction = (
            "Compare the options and give a concise recommendation."
            if mode == "compare" else
            "Answer concisely in 2-4 sentences with the most current facts."
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{instruction}\n\nQuery: {query}",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception as e:
        print(f"[WebSearch] grounded failed: {e}")
        return None


def _duckduckgo(query: str) -> str | None:
    try:
        import requests
        from bs4 import BeautifulSoup

        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = [s.get_text(" ", strip=True) for s in soup.select(".result__snippet")[:3]]
        snippets = [s for s in snippets if s]
        if snippets:
            return "Here's what I found: " + " ".join(snippets)[:600]
    except Exception as e:
        print(f"[WebSearch] DDG failed: {e}")
    return None
