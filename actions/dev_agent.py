# actions/dev_agent.py — JARVIS: build a complete multi-file project
# Plans a file tree with Gemini, writes every file, and reports the result.

import json
import re
import time
from pathlib import Path

from ._common import user_name, ask_gemini, log, say

PROJECTS = Path.home() / "Desktop" / "JARVIS_projects"


def dev_agent(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    desc = (params.get("description") or params.get("task") or "").strip()
    lang = (params.get("language") or "python").strip()
    name = (params.get("project_name") or "").strip()
    u = user_name()

    if not desc:
        return f"What should I build, {u}?"

    say(speak, f"Starting the build, {u}. This may take a moment.")
    log(f"[DevAgent] building: {desc}", player)

    plan_raw = ask_gemini(
        f"You are a senior engineer. Design a small but complete {lang} project for this request:\n"
        f"\"{desc}\"\n\n"
        f"Return ONLY JSON of this shape (no markdown):\n"
        f'{{"project_name":"short_slug","files":[{{"path":"relative/path.ext","content":"FULL file content"}}]}}\n'
        f"Include a README.md and any run/config files. Keep it under 8 files. "
        f"Make every file complete and runnable."
    )
    if not plan_raw:
        return f"My build engine is offline, {u}. Add a Gemini API key to config.json."

    try:
        plan = json.loads(_strip_fences(plan_raw))
    except Exception:
        m = re.search(r"\{.*\}", plan_raw, re.DOTALL)
        if not m:
            return f"I couldn't parse a build plan, {u}. Try rephrasing the request."
        plan = json.loads(m.group(0))

    slug = name or plan.get("project_name") or "project"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)[:40]
    root = PROJECTS / f"{slug}_{int(time.time())}"
    root.mkdir(parents=True, exist_ok=True)

    files = plan.get("files", [])
    written = 0
    for f in files:
        rel = str(f.get("path", "")).lstrip("/\\")
        if not rel:
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_strip_fences(f.get("content", "")), encoding="utf-8")
        written += 1

    log(f"[DevAgent] wrote {written} files → {root}", player)
    msg = (f"Build complete, {u}. I created {written} files for '{slug}' at {root}. "
           f"Files: {', '.join(f.get('path','?') for f in files[:8])}.")
    say(speak, f"Project '{slug}' is ready, {u}.")
    return msg


def _strip_fences(s: str) -> str:
    s = re.sub(r"^```[a-zA-Z]*\n?", "", s.strip())
    s = re.sub(r"\n?```$", "", s.strip())
    return s.strip()
