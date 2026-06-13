# actions/cmd_control.py — JARVIS: run terminal / command-line tasks
# Uses Gemini to translate a natural-language task into a safe shell command,
# then runs it. Blocks obviously destructive commands unless explicitly confirmed.

import subprocess
import sys

from ._common import user_name, ask_gemini, log, say

DANGEROUS = ("rm -rf", "format ", "del /f", "rmdir /s", "mkfs", "dd if=",
             ":(){", "shutdown", "reg delete", "diskpart")


def cmd_control(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    task = (params.get("task") or params.get("command") or params.get("description") or "").strip()
    u = user_name()

    if not task:
        return f"What command would you like me to run, {u}?"

    # If it already looks like a raw command, use it; else ask Gemini to write one.
    command = task
    if " " in task and not _looks_like_command(task):
        shell = "PowerShell" if sys.platform.startswith("win") else "bash"
        gen = ask_gemini(
            f"Translate this request into a single safe {shell} command. "
            f"Return ONLY the command, no markdown, no explanation.\n\nRequest: {task}"
        )
        if gen:
            command = gen.strip().strip("`").splitlines()[0].strip()

    lower = command.lower()
    if any(d in lower for d in DANGEROUS) and not params.get("confirm"):
        return f"That command looks destructive, {u}. I'll hold off unless you confirm explicitly."

    try:
        log(f"[Cmd] {command}", player)
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        out = (result.stdout or result.stderr or "").strip()
        msg = out[:1200] if out else f"Command completed, {u}."
        say(speak, f"Command finished, {u}.")
        return msg
    except subprocess.TimeoutExpired:
        return f"That command took too long and was stopped, {u}."
    except Exception as e:
        msg = f"The command failed, {u}: {str(e)[:100]}"
        log(f"[Cmd] error: {e}", player)
        return msg


def _looks_like_command(text: str) -> bool:
    first = text.split()[0].lower()
    known = {"dir", "ls", "cd", "echo", "type", "cat", "ping", "ipconfig", "ifconfig",
             "git", "python", "pip", "node", "npm", "curl", "whoami", "date", "cls",
             "clear", "tasklist", "get-process", "get-childitem"}
    return first in known
