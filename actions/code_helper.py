# actions/code_helper.py — JARVIS: write / edit / explain / run code
# Uses Gemini to generate code, saves it to the workspace, and can run it.

import re
import subprocess
import sys
import time
from pathlib import Path

from ._common import user_name, ask_gemini, log, say

WORKSPACE = Path.home() / "Desktop" / "JARVIS_workspace"

EXT = {
    "python": "py", "py": "py", "javascript": "js", "js": "js", "typescript": "ts",
    "html": "html", "css": "css", "bash": "sh", "shell": "sh", "c": "c",
    "cpp": "cpp", "c++": "cpp", "java": "java", "go": "go", "rust": "rs",
}


def code_helper(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "auto").strip().lower()
    desc   = (params.get("description") or params.get("task") or "").strip()
    lang   = (params.get("language") or "python").strip().lower()
    file_path = params.get("file_path")
    u = user_name()

    WORKSPACE.mkdir(parents=True, exist_ok=True)

    if action == "explain":
        return _explain(file_path, desc, u)
    if action == "run":
        return _run(file_path, u, speak, player)

    if not desc and action in ("write", "auto", "build", "optimize", "edit"):
        return f"What would you like me to code, {u}?"

    # ── Generate / edit code ─────────────────────────────────────
    existing = ""
    if file_path and Path(file_path).exists():
        existing = Path(file_path).read_text(encoding="utf-8", errors="replace")

    if action == "edit" and existing:
        prompt = (f"Edit this {lang} code as requested. Return ONLY the full updated code, "
                  f"no markdown fences.\n\nRequest: {desc}\n\nCurrent code:\n{existing}")
    else:
        prompt = (f"Write clean, complete, runnable {lang} code for this request. "
                  f"Return ONLY the code, no markdown fences, no commentary.\n\nRequest: {desc}")

    code = ask_gemini(prompt)
    if not code:
        return f"My code engine is offline, {u}. Add a Gemini API key to config.json."

    code = _strip_fences(code)

    ext = EXT.get(lang, "txt")
    if file_path:
        out = Path(file_path)
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", desc.lower())[:30].strip("_") or "snippet"
        out = WORKSPACE / f"{slug}_{int(time.time())}.{ext}"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code, encoding="utf-8")
    log(f"[Code] wrote {out}", player)

    msg = f"I've written the {lang} code to {out.name}, {u}."
    if action in ("auto", "build") and lang in ("python", "py"):
        run_out = _run(str(out), u, speak, player)
        msg += f" Running it now — {run_out}"
    say(speak, f"Code ready, {u}.")
    return msg


def _strip_fences(code: str) -> str:
    code = re.sub(r"^```[a-zA-Z]*\n?", "", code.strip())
    code = re.sub(r"\n?```$", "", code.strip())
    return code.strip()


def _explain(file_path, desc, u):
    code = desc
    if file_path and Path(file_path).exists():
        code = Path(file_path).read_text(encoding="utf-8", errors="replace")
    if not code:
        return f"Point me at some code to explain, {u}."
    out = ask_gemini(f"Explain this code clearly in 3-5 sentences:\n\n{code[:4000]}")
    return out or f"My reasoning core is offline, {u}."


def _run(file_path, u, speak, player):
    if not file_path or not Path(file_path).exists():
        return f"I don't have a file to run, {u}."
    p = Path(file_path)
    runner = {"py": [sys.executable], "js": ["node"]}.get(p.suffix.lstrip("."))
    if not runner:
        return f"I can only auto-run Python and JavaScript, {u}."
    try:
        r = subprocess.run(runner + [str(p)], capture_output=True, text=True, timeout=30, cwd=p.parent)
        out = (r.stdout or r.stderr or "").strip()
        log(f"[Code] ran {p.name}", player)
        return (out[:800] or "it ran with no output.") if out else "it ran successfully."
    except Exception as e:
        return f"it hit an error: {str(e)[:120]}"
