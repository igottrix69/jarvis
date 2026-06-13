"""
setup.py — JARVIS Installation & First-Run Setup
=================================================
Run this once to install dependencies and configure JARVIS.

Usage:
    python setup.py
"""

import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

REQUIREMENTS = [
    "google-genai",
    "google-generativeai",
    "pyaudio",
    "playwright",
    "pyautogui",
    "pyperclip",
    "psutil",
    "mss",
    "opencv-python",
    "Pillow",
    "requests",
    "beautifulsoup4",
    "youtube-transcript-api",
    "send2trash",
    "flask",
    "flask-cors",
    "numpy",
    "win10toast ; sys_platform == 'win32'",
]

CONFIG_TEMPLATE = {
    "gemini_api_key": "",
    "user_name": "sir",
    "voice": "Charon",
    "wake_word": "jarvis",
    "camera_index": 0
}

VOICES = ["Charon", "Fenrir", "Aoede", "Kore", "Puck", "Schedar"]


def banner():
    print("\n" + "="*60)
    print("   J.A.R.V.I.S  —  Setup")
    print("   Just A Rather Very Intelligent System")
    print("="*60 + "\n")


def install_packages():
    print("[Setup] Installing Python packages...")
    for pkg in REQUIREMENTS:
        name = pkg.split(";")[0].strip().split(">=")[0].split("==")[0]
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                check=True
            )
            print(f"  ✓ {name}")
        except subprocess.CalledProcessError:
            print(f"  ✗ {name} — failed (may need manual install)")

    print("\n[Setup] Installing Playwright browsers...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        print("  ✓ Chromium installed")
    except Exception as e:
        print(f"  ✗ Playwright install failed: {e}")


def configure():
    print("\n[Setup] Configuration\n")

    cfg_path = BASE_DIR / "config" / "config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or use template
    cfg = CONFIG_TEMPLATE.copy()
    if cfg_path.exists():
        try:
            existing = json.loads(cfg_path.read_text())
            cfg.update(existing)
        except Exception:
            pass

    # API Key
    if not cfg.get("gemini_api_key"):
        key = input("Enter your Gemini API key: ").strip()
        if key:
            cfg["gemini_api_key"] = key
        else:
            print("⚠️  No API key entered. You can add it later to config/config.json")

    # User name
    name = input(f"How should JARVIS address you? [{cfg.get('user_name', 'sir')}]: ").strip()
    if name:
        cfg["user_name"] = name

    # Voice selection
    print(f"\nAvailable voices: {', '.join(VOICES)}")
    voice = input(f"Choose voice [{cfg.get('voice', 'Charon')}]: ").strip()
    if voice and voice in VOICES:
        cfg["voice"] = voice
    elif voice:
        print(f"  Unknown voice '{voice}', keeping {cfg['voice']}")

    cfg_path.write_text(json.dumps(cfg, indent=4))
    print(f"\n✓ Config saved to {cfg_path}")


def create_dirs():
    for d in ["actions", "config", "memory", "ui"]:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

    # Create __init__.py for actions package
    init = BASE_DIR / "actions" / "__init__.py"
    if not init.exists():
        init.write_text("# JARVIS action modules\n")


def show_launch_instructions():
    print("\n" + "="*60)
    print("  Setup complete!\n")
    print("  To start JARVIS:\n")
    print("  1. Voice mode (recommended):")
    print("     python main.py\n")
    print("  2. Text + UI mode:")
    print("     python api_server.py")
    print("     Then open ui/index.html in Chrome\n")
    print("  3. Both together:")
    print("     python main.py &")
    print("     python api_server.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    banner()

    install = input("Install Python dependencies? [Y/n]: ").strip().lower()
    if install != "n":
        install_packages()

    create_dirs()
    configure()
    show_launch_instructions()
