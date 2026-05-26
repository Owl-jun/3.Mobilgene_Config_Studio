# -*- coding: utf-8 -*-
"""Resolve app root / UI paths for dev and PyInstaller bundles."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_install_dir() -> Path:
    """Directory containing the running executable (portable install folder)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resource_root() -> Path:
    """Bundled read-only resources (ui, schemas) — _MEIPASS when frozen."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def get_ui_dir() -> Path:
    root = get_resource_root()
    ui = root / "ui"
    if ui.is_dir():
        return ui
    # onedir layout: ui next to exe
    alt = get_install_dir() / "ui"
    return alt if alt.is_dir() else ui


def get_schemas_dir() -> Path:
    root = get_resource_root()
    schemas = root / "schemas"
    if schemas.is_dir():
        return schemas
    alt = get_install_dir() / "schemas"
    return alt if alt.is_dir() else schemas
