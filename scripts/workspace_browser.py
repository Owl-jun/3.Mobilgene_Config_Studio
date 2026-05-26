# -*- coding: utf-8 -*-
"""Workspace folder browse — directory listing and optional native picker."""

from __future__ import annotations

import os
import string
from pathlib import Path
from typing import Any, Optional


def _is_workspace_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    cfg = path / "Configuration"
    return (cfg / "Ecu").is_dir() or cfg.is_dir()


def get_roots() -> list[dict[str, str]]:
    """Volume / home roots for empty browse path."""
    roots: list[dict[str, str]] = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if Path(drive).exists():
                roots.append({"name": drive, "path": drive})
    else:
        home = Path.home()
        roots.append({"name": str(home), "path": str(home.resolve())})
    return roots


def list_directory(path_str: str | None) -> dict[str, Any]:
    """
    List subdirectories of path_str.
    path empty/None → roots (drives on Windows) or home.
    """
    if not path_str:
        entries = get_roots()
        return {
            "path": None,
            "parent": None,
            "entries": entries,
            "is_workspace": False,
        }

    current = Path(path_str).resolve()
    if not current.is_dir():
        return {"error": "not_a_directory", "path": str(current)}

    parent: str | None = None
    if current.parent != current:
        parent = str(current.parent)

    entries: list[dict[str, Any]] = []
    try:
        children = sorted(
            (p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: p.name.lower(),
        )
    except OSError as e:
        return {"error": "access_denied", "message": str(e), "path": str(current)}

    for p in children:
        try:
            entries.append(
                {
                    "name": p.name,
                    "path": str(p.resolve()),
                    "is_workspace": _is_workspace_root(p),
                }
            )
        except OSError:
            continue

    return {
        "path": str(current),
        "parent": parent,
        "entries": entries,
        "is_workspace": _is_workspace_root(current),
    }


def pick_folder_native(initial: str | None = None) -> Optional[str]:
    """
    Open OS folder picker on the machine running the dev server.
    Returns absolute path or None if cancelled / unavailable.
    """
    initialdir = initial
    if initialdir:
        p = Path(initialdir)
        if p.is_file():
            initialdir = str(p.parent)
        elif not p.is_dir():
            initialdir = str(Path.home())

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(
            title="Mobilgene 워크스페이스 폴더 선택",
            initialdir=initialdir or str(Path.home()),
            mustexist=True,
        )
        root.destroy()
        if chosen:
            return str(Path(chosen).resolve())
    except Exception:
        pass
    return None
