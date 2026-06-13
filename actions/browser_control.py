# actions/browser_control.py — JARVIS: browser automation via Playwright
# Maintains one persistent browser across calls. Degrades to webbrowser.open
# if Playwright isn't installed.

import webbrowser
from urllib.parse import quote_plus

from ._common import user_name, log, say

_PW = None        # playwright instance
_BROWSER = None   # browser
_PAGE = None      # current page


def _ensure_page():
    """Lazily start Playwright Chromium and return a page, or None on failure."""
    global _PW, _BROWSER, _PAGE
    if _PAGE is not None:
        return _PAGE
    try:
        from playwright.sync_api import sync_playwright
        _PW = sync_playwright().start()
        _BROWSER = _PW.chromium.launch(headless=False)
        _PAGE = _BROWSER.new_page()
        return _PAGE
    except Exception as e:
        print(f"[Browser] Playwright unavailable: {e}")
        return None


def browser_control(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "go_to").strip().lower()
    url    = params.get("url")
    query  = params.get("query")
    text   = params.get("text")
    u = user_name()

    page = _ensure_page()

    # ── Fallback path (no Playwright) ─────────────────────────────
    if page is None:
        if action in ("go_to", "open") and url:
            webbrowser.open(url)
            return f"Opened {url} in your browser, {u}."
        if action == "search" and query:
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
            return f"Searching the web for {query}, {u}."
        return f"Browser automation needs Playwright installed, {u}. Run setup.py."

    # ── Playwright path ───────────────────────────────────────────
    try:
        if action in ("go_to", "open"):
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            msg = f"Navigated to {url}, {u}."
        elif action == "search":
            page.goto(f"https://www.google.com/search?q={quote_plus(query or '')}",
                      wait_until="domcontentloaded", timeout=20000)
            msg = f"Searching for {query}, {u}."
        elif action == "click":
            page.click(f"text={text}", timeout=8000)
            msg = f"Clicked '{text}', {u}."
        elif action == "type":
            page.keyboard.type(text or "")
            msg = f"Typed it, {u}."
        elif action == "scroll":
            page.mouse.wheel(0, 800)
            msg = f"Scrolled, {u}."
        elif action == "get_text":
            return (page.inner_text("body") or "")[:4000]
        elif action == "close":
            _shutdown()
            msg = f"Closed the browser, {u}."
        else:
            msg = f"I don't recognise the browser action '{action}', {u}."

        log(f"[Browser] {action}", player)
        say(speak, msg)
        return msg

    except Exception as e:
        msg = f"The browser action failed, {u}: {str(e)[:100]}"
        log(f"[Browser] error: {e}", player)
        return msg


def _shutdown():
    global _PW, _BROWSER, _PAGE
    try:
        if _BROWSER: _BROWSER.close()
        if _PW: _PW.stop()
    except Exception:
        pass
    _PW = _BROWSER = _PAGE = None
