# -*- coding: utf-8 -*-
"""
Mobilgene Config Studio — portable launcher (PyInstaller entry).
Starts embedded HTTP server and opens the UI in an app window.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.client import HTTPConnection
from pathlib import Path

# Ensure scripts package imports work when frozen
_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))


def _pick_port(preferred: int) -> int:
    for port in (preferred, preferred + 1, preferred + 2, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port if port else 0))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferred


def _wait_health(port: int, timeout_sec: float = 45.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=0.8)
            conn.request("GET", "/api/health")
            res = conn.getresponse()
            if res.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def _edge_paths() -> list[Path]:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    return [
        Path(pf) / "Microsoft/Edge/Application/msedge.exe",
        Path(pfx86) / "Microsoft/Edge/Application/msedge.exe",
        Path(pf) / "Google/Chrome/Application/chrome.exe",
        Path(pfx86) / "Google/Chrome/Application/chrome.exe",
    ]


def _open_app_window(url: str) -> None:
    if sys.platform == "win32":
        for browser in _edge_paths():
            if browser.is_file():
                subprocess.Popen(
                    [
                        str(browser),
                        f"--app={url}",
                        "--new-window",
                        "--disable-features=Translate",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                return
    webbrowser.open(url, new=1)


def main() -> int:
    preferred = int(os.environ.get("MCS_PORT", "8765"))
    port = _pick_port(preferred)
    os.environ["MCS_PORT"] = str(port)

    from dev_server import main as run_server  # noqa: WPS433

    server_thread = threading.Thread(target=run_server, name="mcs-http", daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{port}"
    if not _wait_health(port):
        print("Mobilgene Config Studio: 서버 기동 실패", file=sys.stderr)
        return 1

    if os.environ.get("MCS_HEADLESS") != "1":
        _open_app_window(url)

    # Console / frozen exe: keep process alive while server thread runs
    try:
        while server_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
