# actions/youtube_video.py — JARVIS: play / search / summarise YouTube videos

import re
import webbrowser
from urllib.parse import quote_plus

from ._common import user_name, ask_gemini, log, say


def youtube_video(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "play").strip().lower()
    query  = (params.get("query") or params.get("text") or "").strip()
    u = user_name()

    try:
        if action == "play":
            return _play(query, u, speak, player)
        if action == "summarize":
            return _summarize(query, u, speak, player)
        if action == "trending":
            region = (params.get("region") or "US").upper()
            webbrowser.open(f"https://www.youtube.com/feed/trending?gl={region}")
            return f"Here's what's trending on YouTube, {u}."
        if action == "get_info":
            return _summarize(query, u, speak, player)
        return _play(query, u, speak, player)
    except Exception as e:
        msg = f"That YouTube request failed, {u}: {str(e)[:100]}"
        log(f"[YouTube] error: {e}", player)
        return msg


def _play(query, u, speak, player):
    if not query:
        webbrowser.open("https://youtube.com")
        return f"Opening YouTube, {u}."
    # autoplay first result trick
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    webbrowser.open(url)
    log(f"[YouTube] play: {query}", player)
    msg = f"Pulling up '{query}' on YouTube, {u}."
    say(speak, msg)
    return msg


def _video_id(text: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", text)
    return m.group(1) if m else None


def _summarize(query, u, speak, player):
    vid = _video_id(query)
    if not vid:
        return f"Give me a YouTube link to summarise, {u}."
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        chunks = YouTubeTranscriptApi.get_transcript(vid)
        transcript = " ".join(c["text"] for c in chunks)
    except Exception:
        return f"I couldn't fetch the transcript for that video, {u} — it may have captions disabled."

    summary = ask_gemini(f"Summarise this YouTube transcript in 3-4 sentences:\n\n{transcript[:6000]}")
    if not summary:
        return f"I have the transcript but my summariser is offline, {u}. Add a Gemini API key."
    log(f"[YouTube] summarised {vid}", player)
    say(speak, summary)
    return summary
