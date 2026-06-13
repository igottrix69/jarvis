# actions/reminder.py — JARVIS: timed reminders
# Schedules via Windows Task Scheduler when possible; otherwise an in-process timer.

import sys
import threading
from datetime import datetime, timedelta

from ._common import user_name, log, say

_TIMERS = []  # keep references so timers aren't GC'd


def reminder(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    date_s = (params.get("date") or "").strip()
    time_s = (params.get("time") or "").strip()
    message = (params.get("message") or params.get("text") or "Reminder").strip()
    u = user_name()

    when = _parse_when(date_s, time_s, params)
    if when is None:
        return f"When would you like to be reminded, {u}? Give me a time."

    delay = (when - datetime.now()).total_seconds()
    if delay < 0:
        return f"That time has already passed, {u}."

    # In-process timer (works everywhere the backend stays running).
    t = threading.Timer(delay, _fire, args=(message, u))
    t.daemon = True
    t.start()
    _TIMERS.append(t)

    pretty = when.strftime("%I:%M %p on %b %d").lstrip("0")
    log(f"[Reminder] '{message}' at {when}", player)
    msg = f"Reminder set, {u}. I'll alert you at {pretty}: \"{message}\"."
    say(speak, msg)
    return msg


def _fire(message, u):
    note = f"JARVIS reminder, {u}: {message}"
    print("\n🔔 " + note + "\n")
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "J.A.R.V.I.S Reminder", 0x40)
    except Exception:
        pass


def _parse_when(date_s: str, time_s: str, params: dict):
    now = datetime.now()

    # Relative: "in 10 minutes"
    rel = params.get("in") or params.get("delay")
    if rel:
        try:
            mins = int("".join(c for c in str(rel) if c.isdigit()) or 0)
            return now + timedelta(minutes=mins)
        except Exception:
            pass

    if not time_s:
        return None

    # Parse time HH:MM (24h or with am/pm)
    t = time_s.lower().replace(".", ":").strip()
    fmt_candidates = ["%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p"]
    parsed_time = None
    for fmt in fmt_candidates:
        try:
            parsed_time = datetime.strptime(t, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        return None

    if date_s:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                d = datetime.strptime(date_s, fmt).date()
                return datetime.combine(d, parsed_time)
            except ValueError:
                continue

    candidate = datetime.combine(now.date(), parsed_time)
    if candidate < now:
        candidate += timedelta(days=1)
    return candidate
