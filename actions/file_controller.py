# actions/file_controller.py — JARVIS: file & folder management
# Safe-by-default: deletes go to the recycle bin (send2trash) when available.

import os
import shutil
from pathlib import Path

from ._common import user_name, log, say

HOME = Path.home()


def _resolve(path: str | None) -> Path:
    """Resolve a path, expanding ~ and common shortcuts, defaulting to Desktop."""
    if not path:
        return HOME / "Desktop"
    p = str(path).strip().strip('"').strip("'")
    shortcuts = {
        "desktop": HOME / "Desktop",
        "documents": HOME / "Documents",
        "downloads": HOME / "Downloads",
        "home": HOME,
    }
    if p.lower() in shortcuts:
        return shortcuts[p.lower()]
    return Path(os.path.expandvars(os.path.expanduser(p)))


def file_controller(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "list").strip().lower()
    path   = params.get("path")
    name   = params.get("name")
    u = user_name()

    try:
        if action == "list":
            base = _resolve(path)
            if not base.exists():
                return f"That location doesn't exist, {u}: {base}"
            items = sorted(os.listdir(base))[:50]
            listing = ", ".join(items) if items else "nothing"
            msg = f"{base.name or base} contains {len(items)} items: {listing}"

        elif action == "create_folder":
            target = _resolve(path) / (name or "New Folder")
            target.mkdir(parents=True, exist_ok=True)
            msg = f"Created the folder {target.name}, {u}."

        elif action == "create_file":
            target = _resolve(path) / (name or "new_file.txt")
            content = params.get("content", "")
            target.write_text(content, encoding="utf-8")
            msg = f"Created {target.name}, {u}."

        elif action == "write":
            target = _resolve(path)
            target.write_text(params.get("content", ""), encoding="utf-8")
            msg = f"Wrote to {target.name}, {u}."

        elif action == "read":
            target = _resolve(path)
            text = target.read_text(encoding="utf-8", errors="replace")
            msg = text[:1500] + ("…" if len(text) > 1500 else "")

        elif action == "delete":
            target = _resolve(path)
            _delete(target)
            msg = f"Moved {target.name} to the recycle bin, {u}."

        elif action == "move":
            dst = params.get("destination") or params.get("to")
            shutil.move(str(_resolve(path)), str(_resolve(dst)))
            msg = f"Moved it, {u}."

        elif action == "copy":
            src = _resolve(path)
            dst = _resolve(params.get("destination") or params.get("to"))
            if src.is_dir():
                shutil.copytree(src, dst / src.name, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            msg = f"Copied {src.name}, {u}."

        elif action == "rename":
            src = _resolve(path)
            new = src.with_name(name or src.name)
            src.rename(new)
            msg = f"Renamed to {new.name}, {u}."

        elif action == "find":
            base = _resolve(path) if path else HOME
            term = (name or "").lower()
            hits = []
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if term in f.lower():
                        hits.append(os.path.join(root, f))
                        if len(hits) >= 15:
                            break
                if len(hits) >= 15:
                    break
            msg = (f"Found {len(hits)} matches for '{name}': " + ", ".join(Path(h).name for h in hits)) if hits \
                  else f"I found no files matching '{name}', {u}."

        else:
            msg = f"I don't recognise the file action '{action}', {u}."

        log(f"[Files] {action} → ok", player)
        say(speak, msg if len(msg) < 200 else f"Done, {u}.")
        return msg

    except Exception as e:
        msg = f"That file operation failed, {u}: {str(e)[:100]}"
        log(f"[Files] {action} error: {e}", player)
        return msg


def _delete(target: Path):
    try:
        from send2trash import send2trash
        send2trash(str(target))
    except Exception:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
