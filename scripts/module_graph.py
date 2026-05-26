# -*- coding: utf-8 -*-
"""
Workspace BSW module coupling graph.
Combines Ecud module discovery, REF/routing hints, and generic AUTOSAR stack templates.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

NS_URI = "http://autosar.org/schema/r4.0"

# Generic AUTOSAR communication / diagnostic stacks (ECU-agnostic)
STACK_CHAINS: list[list[str]] = [
    ["CanTrcv", "CanIf", "CanTp", "PduR", "Com"],
    ["CanTrcv", "CanIf", "CanTp", "PduR", "Dcm"],
    ["CanTrcv", "CanIf", "PduR", "Dcm"],
    ["CanTrcv", "CanIf", "PduR", "Com"],
    ["CanIf", "CanSM", "ComM"],
    ["CanSM", "ComM"],
    ["ComM", "Com"],
    ["PduR", "IpduM", "Com"],
    ["Gateway", "PduR"],
    ["Gateway", "Com"],
    ["Com", "Rte"],
    ["Dcm", "Rte"],
    ["PduR", "Rte"],
    ["IpduM", "PduR"],
    ["EcuC", "PduR"],
    ["EcuC", "Com"],
    ["EcuC", "Dcm"],
    ["EcuM", "BswM"],
    ["BswM", "ComM"],
    ["Dem", "Dcm"],
    ["NvM", "MemIf"],
]

# Left-to-right layout tier (lower = closer to bus)
LAYER_TIER: dict[str, int] = {
    "Can": 0,
    "CanTrcv": 0,
    "CanCM": 0,
    "CanIf": 1,
    "CanTp": 2,
    "CanSM": 2,
    "CanNm": 2,
    "LinIf": 1,
    "LinTp": 2,
    "PduR": 3,
    "IpduM": 3,
    "CDD_Router": 3,
    "Gateway": 3,
    "Com": 4,
    "Dcm": 4,
    "EcuC": 4,
    "ComM": 5,
    "Rte": 6,
    "Swcd": 6,
    "BswM": 7,
    "EcuM": 7,
    "Os": 7,
    "Dem": 8,
    "Det": 8,
    "NvM": 8,
    "MemIf": 8,
    "Fee": 8,
    "Fls": 8,
}

MODULE_IN_PATH = re.compile(r"/(?:AUTRON|AUTOSAR)/([A-Za-z][A-Za-z0-9_]*)/")
PDU_ROUTING_HINT = re.compile(
    r"PduR_([A-Za-z][A-Za-z0-9_]*)IPdu|IN_.*?_(?:RoutingPath|RP)",
    re.IGNORECASE,
)
ECUD_NAME = re.compile(r"Ecud_([A-Za-z0-9_]+)\.arxml$", re.IGNORECASE)

_graph_cache: dict[str, Any] = {}

# Swimlane groups (viewer-oriented, not Mobilgene clone)
VIEW_LANES: list[dict[str, Any]] = [
    {"id": "bus", "label": "Bus · Transceiver", "members": ["CanTrcv", "Can", "CanCM", "LinIf"]},
    {"id": "comm", "label": "CAN / LIN IF", "members": ["CanIf", "CanTp", "CanSM", "CanNm", "LinTp"]},
    {"id": "pdu", "label": "PDU Router · Gateway", "members": ["PduR", "IpduM", "Gateway", "CDD_Router"]},
    {"id": "service", "label": "Com · Diag", "members": ["Com", "Dcm", "EcuC", "ComM"]},
    {"id": "rte", "label": "RTE", "members": ["Rte"]},
    {"id": "system", "label": "System · OS", "members": ["Os", "EcuM", "BswM", "WdgM", "WdgIf", "Det", "OsImp", "OsProfiler"]},
    {"id": "mem", "label": "NvM · Mem", "members": ["NvM", "MemIf", "Fee", "Fls", "Dem", "FiM", "KeyM", "Csm", "CryIf"]},
]

# Communication path discovery (from workspace scan — not fixed templates)
COMM_SINKS = frozenset({"Com", "Dcm", "Rte", "Dem", "IpduM"})
COMM_SOURCE_MAX_TIER = 2
PATH_MAX_LEN = 12
PATH_MAX_COUNT = 24

CAN_BUS = frozenset({"CanTrcv", "Can", "CanIf", "CanTp", "CanSM", "CanNm", "CanCM"})
LIN_BUS = frozenset({"LinIf", "LinTp"})
ETH_BUS = frozenset({"SoAd", "DoIP"})

# Legacy spine / neighbor hints only (not used for path pills)
SPINE_REFERENCE_CHAINS: list[list[str]] = [
    ["CanTrcv", "Can", "CanIf", "CanTp", "PduR", "Dcm", "Rte"],
    ["CanTrcv", "Can", "CanIf", "PduR", "Com", "Rte"],
    ["Gateway", "PduR", "Com"],
]

# AUTOSAR layered model (stacks = vertical columns, bottom → top within column)
AUTOSAR_STACKS: list[dict[str, Any]] = [
    {
        "id": "os",
        "label": "OS / Mode",
        "service": ["Os", "OsImp", "OsProfiler", "EcuM", "BswM", "ComM", "WdgM"],
        "ecu_abs": ["WdgIf"],
        "mcal": [],
    },
    {
        "id": "can",
        "label": "CAN",
        "service": ["CanTp", "CanSM", "CanNm", "CanCM"],
        "ecu_abs": ["CanIf"],
        "mcal": ["CanTrcv", "Can"],
    },
    {
        "id": "com",
        "label": "COM / PDU",
        "service": ["Com", "PduR", "IpduM", "Gateway", "CDD_Router", "EcuC"],
        "ecu_abs": [],
        "mcal": [],
    },
    {
        "id": "diag",
        "label": "Diagnostic",
        "service": ["Dcm", "Dem", "FiM", "Det"],
        "ecu_abs": [],
        "mcal": [],
    },
    {
        "id": "mem",
        "label": "Memory",
        "service": ["NvM", "Crc"],
        "ecu_abs": ["MemIf"],
        "mcal": ["Fee", "Fls"],
    },
    {
        "id": "crypto",
        "label": "Crypto",
        "service": ["Csm", "CryIf", "KeyM"],
        "ecu_abs": [],
        "mcal": [],
    },
    {
        "id": "io",
        "label": "I/O",
        "service": ["IoHwAb"],
        "ecu_abs": [],
        "mcal": ["Port", "Dio", "Adc", "Pwm", "Icu", "Spi"],
    },
    {
        "id": "mcu",
        "label": "MCU",
        "service": ["McalLib"],
        "ecu_abs": [],
        "mcal": ["Mcu", "ResourceM", "Gpt", "Irq"],
    },
]

RTE_LAYER = {"id": "rte", "label": "Runtime Environment (RTE)", "modules": ["Rte"]}

LAYER_BANDS = [
    {"id": "service", "label": "Service Layer"},
    {"id": "ecu_abs", "label": "ECU Abstraction Layer"},
    {"id": "mcal", "label": "Microcontroller Abstraction Layer (MCAL)"},
]


def _qname(local: str) -> str:
    return f"{{{NS_URI}}}{local}"


def _module_from_ecud_filename(name: str) -> Optional[str]:
    m = ECUD_NAME.match(name)
    if not m:
        return None
    mod = m.group(1)
    if mod.startswith("Ecud_"):
        mod = mod[5:]
    return mod


def discover_modules(workspace: Path) -> dict[str, dict[str, Any]]:
    """Map module name -> {file, relative, profile, tier}."""
    workspace = workspace.resolve()
    modules: dict[str, dict[str, Any]] = {}

    gw = workspace / "Configuration" / "System" / "DBImport" / "Gateway.arxml"
    if gw.is_file():
        modules["Gateway"] = {
            "name": "Gateway",
            "file": str(gw),
            "relative": str(gw.relative_to(workspace)).replace("\\", "/"),
            "profile": "gateway",
            "tier": LAYER_TIER.get("Gateway", 3),
        }

    ecu_dir = workspace / "Configuration" / "Ecu"
    if ecu_dir.is_dir():
        for p in ecu_dir.rglob("Ecud_*.arxml"):
            if "_ECU_Configuration_PDF" in p.name:
                continue
            mod = _module_from_ecud_filename(p.name)
            if not mod:
                continue
            rel = str(p.relative_to(workspace)).replace("\\", "/")
            modules[mod] = {
                "name": mod,
                "file": str(p.resolve()),
                "relative": rel,
                "profile": "ecuc",
                "tier": LAYER_TIER.get(mod, 9),
            }

    # EcuC is central — ensure present
    ecuc = workspace / "Configuration" / "Ecu" / "Ecud_EcuC.arxml"
    if ecuc.is_file() and "EcuC" not in modules:
        modules["EcuC"] = {
            "name": "EcuC",
            "file": str(ecuc.resolve()),
            "relative": str(ecuc.relative_to(workspace)).replace("\\", "/"),
            "profile": "ecuc",
            "tier": LAYER_TIER.get("EcuC", 4),
        }

    return modules


# 통신 경로 분석에 필요한 모듈만 ARXML 전문 스캔 (나머지는 STACK_CHAINS만)
_ROUTING_SCAN_MODULES = frozenset(
    {
        "PduR",
        "Gateway",
        "Com",
        "CanIf",
        "CanTp",
        "Dcm",
        "LinIf",
        "LinTp",
        "IpduM",
        "SoAd",
        "DoIP",
        "CDD_Router",
        "EcuC",
    }
)

_file_text_cache: dict[str, tuple[float, str]] = {}


def _read_arxml_text(path: Path) -> str:
    key = str(path.resolve())
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return ""
    cached = _file_text_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    _file_text_cache[key] = (mtime, text)
    return text


def _scan_file_links(path: Path, source_module: str) -> set[tuple[str, str, str]]:
    """Return set of (from, to, kind) edges."""
    edges: set[tuple[str, str, str]] = set()
    if source_module not in _ROUTING_SCAN_MODULES:
        return edges

    text = _read_arxml_text(path)
    if not text:
        return edges

    if source_module == "PduR":
        for hint in (
            "Dcm",
            "Com",
            "CanIf",
            "CanTp",
            "IpduM",
            "LinIf",
            "SoAd",
            "DoIP",
            "Gateway",
            "CDD_Router",
        ):
            if f"PduR_{hint}IPdu" in text or f"_{hint}IPdu" in text:
                edges.add(("PduR", hint, "routing"))
        return edges

    for m in MODULE_IN_PATH.finditer(text):
        target = m.group(1)
        if target != source_module and target not in ("AUTRON", "AUTOSAR", "EcucConfigSet"):
            edges.add((source_module, target, "ref"))

    for m in PDU_ROUTING_HINT.finditer(text):
        hint = m.group(1)
        if hint and hint != source_module:
            edges.add((source_module, hint, "routing"))

    return edges


def _build_base_graph(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    modules = discover_modules(workspace)
    edge_set: set[tuple[str, str, str]] = set()

    # Template stack edges (only if both modules exist in workspace)
    names = set(modules.keys())
    for chain in STACK_CHAINS:
        for i in range(len(chain) - 1):
            a, b = chain[i], chain[i + 1]
            if a in names and b in names:
                edge_set.add((a, b, "stack"))

    # Detected edges from Ecud / Gateway files
    for mod, info in modules.items():
        p = Path(info["file"])
        if p.is_file():
            edge_set.update(_scan_file_links(p, mod))

    # Normalize targets that exist; map aliases
    alias = {"Can": "CanIf"}
    normalized: set[tuple[str, str, str]] = set()
    for fr, to, kind in edge_set:
        to = alias.get(to, to)
        fr = alias.get(fr, fr)
        if to in names and fr in names and fr != to:
            normalized.add((fr, to, kind))

    # Group nodes by tier for layout
    nodes = []
    for name, info in sorted(modules.items(), key=lambda x: (x[1]["tier"], x[0])):
        nodes.append(
            {
                "id": f"mod:{name}",
                "label": name,
                "type": "module",
                "module": name,
                "tier": info["tier"],
                "file": info["file"],
                "relative": info["relative"],
                "profile": info["profile"],
            }
        )

    edges = [
        {
            "from": f"mod:{fr}",
            "to": f"mod:{to}",
            "kind": kind,
            "label": "→" if kind == "stack" else "ref",
        }
        for fr, to, kind in sorted(normalized)
    ]

    lanes, spine, other_count = _build_lane_view(modules, names)
    autosar = _build_autosar_layer_view(modules, names, workspace, normalized)

    return {
        "workspace": str(workspace),
        "module_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "layers": _layer_groups(nodes),
        "graph_type": "autosar_layers",
        "lanes": lanes,
        "spine": spine,
        "other_count": other_count,
        "autosar": autosar,
    }


def _build_adjacency(
    names: set[str], edges: set[tuple[str, str, str]]
) -> dict[str, set[str]]:
    """Path walking uses stack + routing only (REF edges create unrealistic jumps)."""
    adj: dict[str, set[str]] = {n: set() for n in names}
    for fr, to, kind in edges:
        if kind in ("stack", "routing"):
            adj.setdefault(fr, set()).add(to)
    return adj


def _is_valid_comm_chain(chain: list[str]) -> bool:
    if len(chain) < 2:
        return False
    service = [m for m in chain if m in ("Com", "Dcm", "IpduM")]
    if len(service) > 1:
        if not ("Dem" in chain and "Dcm" in chain and "Com" not in chain):
            return False
    return True


def _is_subsequence(short: tuple[str, ...], long: tuple[str, ...]) -> bool:
    if len(short) >= len(long):
        return False
    it = iter(long)
    return all(any(x == y for y in it) for x in short)


def _dedupe_comm_paths(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep longest path per label; drop strict subpaths."""
    by_label: dict[str, list[dict[str, Any]]] = {}
    for p in paths:
        label = p["title"].split(":", 1)[0]
        by_label.setdefault(label, []).append(p)

    out: list[dict[str, Any]] = []
    for label, group in by_label.items():
        group.sort(key=lambda p: len(p["modules"]), reverse=True)
        kept: list[tuple[str, ...]] = []
        for p in group:
            mods = tuple(p["modules"])
            if any(_is_subsequence(mods, k) for k in kept):
                continue
            kept.append(mods)
            out.append(p)
    out.sort(key=_path_sort_key)
    return out


def _path_sources(names: set[str], adj: dict[str, set[str]]) -> list[str]:
    """Entry modules for comm paths (bus / gateway / orphan PduR)."""
    sources: set[str] = set()
    for n in names:
        if LAYER_TIER.get(n, 9) <= COMM_SOURCE_MAX_TIER:
            sources.add(n)
        if n == "Gateway":
            sources.add(n)
    pdu_tier = LAYER_TIER.get("PduR", 3)
    for n in ("PduR", "IpduM"):
        if n not in names:
            continue
        has_lower_in = any(
            LAYER_TIER.get(pred, 9) < pdu_tier and n in adj.get(pred, set())
            for pred in names
        )
        if not has_lower_in:
            sources.add(n)
    for n in ("NvM", "Dem", "ComM", "CanNm"):
        if n in names and not any(n in adj.get(pred, set()) for pred in names):
            sources.add(n)
    return sorted(sources, key=lambda x: (LAYER_TIER.get(x, 0), x))


def _label_comm_path(chain: list[str]) -> str:
    has_can = any(m in chain for m in CAN_BUS)
    has_lin = any(m in chain for m in LIN_BUS)
    has_eth = any(m in chain for m in ETH_BUS)

    if chain and chain[0] == "Gateway":
        return "Gateway"
    if "Dcm" in chain:
        if has_lin:
            return "LIN 진단"
        if has_eth:
            return "진단 (DoIP/Eth)"
        if "CanTp" in chain:
            return "진단 (UDS/CAN)"
        if has_can:
            return "진단 (CAN)"
        return "진단"
    if "Com" in chain:
        if has_lin:
            return "LIN (COM)"
        if has_eth:
            return "Ethernet (COM)"
        if has_can:
            return "신호 (COM)"
        return "COM"
    if "IpduM" in chain:
        return "IpduM"
    if "Dem" in chain:
        return "Dem · Dcm"
    if set(chain) <= {"NvM", "MemIf", "Fee", "Fls", "Ea"}:
        return "NvM · Flash"
    if "ComM" in chain:
        return "ComM"
    return "통신 경로"


def _path_sort_key(path: dict[str, Any]) -> tuple[int, int, str]:
    title = path.get("title", "")
    for i, prefix in enumerate(
        ("진단", "신호", "Gateway", "LIN", "Ethernet", "IpduM", "Dem", "NvM", "ComM")
    ):
        if title.startswith(prefix):
            return (i, -len(path.get("modules", [])), title)
    return (99, -len(path.get("modules", [])), title)


def _discover_comm_paths(
    names: set[str],
    edges: set[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    """
    Discover communication paths by walking edges from workspace ARXML scan.
    Edges come from STACK_CHAINS (present modules only) + REF/routing hints in Ecud files.
    """
    adj = _build_adjacency(names, edges)
    sources = _path_sources(names, adj)
    paths: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()

    def register(chain: list[str]) -> None:
        if not _is_valid_comm_chain(chain):
            return
        key = tuple(chain)
        if key in seen:
            return
        seen.add(key)
        label = _label_comm_path(chain)
        arrow = " → ".join(chain)
        paths.append(
            {
                "id": f"path_{len(paths)}",
                "title": f"{label}: {arrow}",
                "modules": list(chain),
                "source": "workspace_scan",
            }
        )

    def dfs(node: str, chain: list[str], visited: set[str]) -> None:
        if len(chain) > PATH_MAX_LEN:
            return
        nexts = [
            nxt
            for nxt in sorted(adj.get(node, ()), key=lambda x: (LAYER_TIER.get(x, 0), x))
            if nxt not in visited
            and LAYER_TIER.get(nxt, 5) >= LAYER_TIER.get(node, 5)
        ]
        if node == "Rte":
            if len(chain) >= 2:
                register(chain)
            return
        if node in ("Com", "Dcm", "Dem", "IpduM") and len(chain) >= 2 and not nexts:
            register(chain)
        if node in ("Com", "Dcm") and len(chain) >= 2:
            if "Rte" not in adj.get(node, set()) and not nexts:
                register(chain)
        for nxt in nexts:
            dfs(nxt, chain + [nxt], visited | {nxt})
        if node in ("Com", "Dcm") and "Rte" in adj.get(node, set()) and "Rte" not in visited:
            dfs("Rte", chain + ["Rte"], visited | {"Rte"})

    for src in sources:
        dfs(src, [src], {src})

    return _dedupe_comm_paths(paths)[:PATH_MAX_COUNT]


def _build_autosar_layer_view(
    modules: dict[str, dict[str, Any]],
    names: set[str],
    workspace: Path,
    edges: set[tuple[str, str, str]],
) -> dict[str, Any]:
    assigned: set[str] = set()
    stacks_out: list[dict[str, Any]] = []

    for stack_def in AUTOSAR_STACKS:
        bands: dict[str, list[dict[str, Any]]] = {}
        for band in ("service", "ecu_abs", "mcal"):
            mods = []
            for m in stack_def.get(band, []):
                if m in modules:
                    mods.append(_module_chip(m, modules[m]))
                    assigned.add(m)
            if mods:
                bands[band] = mods
        if bands:
            stacks_out.append(
                {
                    "id": stack_def["id"],
                    "label": stack_def["label"],
                    "bands": bands,
                }
            )

    rte_mods = []
    for m in RTE_LAYER["modules"]:
        if m in modules:
            rte_mods.append(_module_chip(m, modules[m]))
            assigned.add(m)

    other = sorted(n for n in names if n not in assigned)
    other_mods = [_module_chip(m, modules[m]) for m in other]

    paths = _discover_comm_paths(names, edges)

    app_mods = _discover_app_components(workspace)

    return {
        "application": app_mods,
        "rte": rte_mods,
        "stacks": stacks_out,
        "bands": LAYER_BANDS,
        "paths": paths,
        "paths_source": "workspace_scan",
        "other": other_mods,
        "other_count": len(other_mods),
    }


def _discover_app_components(workspace: Path) -> list[dict[str, Any]]:
    app_dir = workspace / "Configuration" / "System" / "Swcd_App"
    if not app_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(app_dir.glob("*.arxml")):
        label = p.stem[4:] if p.stem.startswith("App_") else p.stem
        out.append(
            {
                "module": f"APP:{label}",
                "label": label,
                "file": str(p.resolve()),
                "relative": str(p.relative_to(workspace)).replace("\\", "/"),
                "profile": "swc_app",
                "is_app": True,
            }
        )
    return out


def _build_lane_view(
    modules: dict[str, dict[str, Any]], names: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    lanes_out: list[dict[str, Any]] = []
    assigned: set[str] = set()

    for lane_def in VIEW_LANES:
        present: list[dict[str, Any]] = []
        for m in lane_def["members"]:
            if m in modules:
                present.append(_module_chip(m, modules[m]))
                assigned.add(m)
        if present:
            lanes_out.append(
                {
                    "id": lane_def["id"],
                    "label": lane_def["label"],
                    "modules": present,
                }
            )

    other_names = sorted(n for n in names if n not in assigned)
    other_count = len(other_names)
    if other_names:
        lanes_out.append(
            {
                "id": "other",
                "label": f"기타 모듈 ({other_count})",
                "modules": [_module_chip(m, modules[m]) for m in other_names],
                "collapsed_default": True,
            }
        )

    spine = _pick_spine(names)
    return lanes_out, spine, other_count


def _module_chip(name: str, info: dict[str, Any]) -> dict[str, Any]:
    return {
        "module": name,
        "label": name,
        "file": info["file"],
        "relative": info["relative"],
        "profile": info["profile"],
        "on_spine": False,
    }


def _pick_spine(names: set[str]) -> list[dict[str, Any]]:
    for chain in SPINE_REFERENCE_CHAINS:
        present = [m for m in chain if m in names]
        if len(present) >= 3:
            return [{"module": m, "label": m} for m in present]
    return []


def build_module_graph(
    workspace: Path,
    selected_module: Optional[str] = None,
    selected_file: Optional[str] = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    cache_key = str(workspace)
    if cache_key not in _graph_cache:
        _graph_cache[cache_key] = _build_base_graph(workspace)

    sel = selected_module
    if not sel and selected_file:
        sel = _module_from_path(selected_file, discover_modules(workspace))
    return _highlight(_graph_cache[cache_key], sel, workspace)


def _layer_groups(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_tier: dict[int, list[str]] = {}
    for n in nodes:
        t = n.get("tier", 9)
        by_tier.setdefault(t, []).append(n["label"])
    return [{"tier": t, "modules": sorted(by_tier[t])} for t in sorted(by_tier)]


def _module_from_path(
    file_path: Optional[str], modules: dict[str, dict[str, Any]]
) -> Optional[str]:
    if not file_path:
        return None
    p = Path(file_path)
    if p.name.lower() == "gateway.arxml":
        return "Gateway"
    mod = _module_from_ecud_filename(p.name)
    if mod and mod in modules:
        return mod
    for name, info in modules.items():
        if info["file"] == str(p.resolve()):
            return name
    return mod


def _highlight(
    graph: dict[str, Any],
    selected_module: Optional[str],
    workspace: Path,
) -> dict[str, Any]:
    import copy

    g = copy.deepcopy(graph)
    sel = selected_module
    g["selected_module"] = sel
    spine_mods = {s["module"] for s in g.get("spine", [])}
    for n in g["nodes"]:
        n["selected"] = n["module"] == sel
        n["dimmed"] = bool(sel) and n["module"] != sel and not _is_neighbor(g, sel, n["module"])
        n["on_spine"] = n["module"] in spine_mods
    path_mods = _path_modules_for_selection(g, sel)

    for lane in g.get("lanes", []):
        for m in lane.get("modules", []):
            _apply_chip_highlight(m, sel, spine_mods, path_mods)

    autosar = g.get("autosar")
    if autosar:
        for m in autosar.get("rte", []):
            _apply_chip_highlight(m, sel, spine_mods, path_mods)
        for stack in autosar.get("stacks", []):
            for band_mods in stack.get("bands", {}).values():
                for m in band_mods:
                    _apply_chip_highlight(m, sel, spine_mods, path_mods)
        for m in autosar.get("other", []):
            _apply_chip_highlight(m, sel, spine_mods, path_mods)
        autosar["active_path"] = _pick_active_path(autosar, sel)
    return g


def _path_modules_for_selection(g: dict[str, Any], sel: Optional[str]) -> set[str]:
    if not sel:
        return set()
    autosar = g.get("autosar") or {}
    for p in autosar.get("paths", []):
        if sel in p.get("modules", []):
            return set(p["modules"])
    return set()


def _pick_active_path(autosar: dict[str, Any], sel: Optional[str]) -> Optional[str]:
    if not sel:
        return "diag"
    for p in autosar.get("paths", []):
        if sel in p.get("modules", []):
            return p["id"]
    return "diag"


def _apply_chip_highlight(
    m: dict[str, Any],
    sel: Optional[str],
    spine_mods: set[str],
    path_mods: set[str],
) -> None:
    mod = m["module"]
    m["selected"] = mod == sel
    m["on_path"] = mod in path_mods or mod in spine_mods
    m["dimmed"] = (
        bool(sel)
        and mod != sel
        and not m["on_path"]
        and not _is_neighbor_simple(sel, mod)
    )


def _is_neighbor_simple(sel: str, name: str) -> bool:
    """Loose neighbor for layer view."""
    for chain in SPINE_REFERENCE_CHAINS:
        if sel in chain and name in chain:
            return True
    return False


def _is_neighbor(g: dict[str, Any], sel: str, name: str) -> bool:
    for e in g["edges"]:
        fr = e["from"].replace("mod:", "")
        to = e["to"].replace("mod:", "")
        if fr == sel and to == name:
            return True
        if to == sel and fr == name:
            return True
    return False


def module_from_file(workspace: Path, file_path: str) -> Optional[str]:
    modules = discover_modules(workspace)
    return _module_from_path(file_path, modules)
