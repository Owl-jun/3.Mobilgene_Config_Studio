# -*- coding: utf-8 -*-
"""Workspace-wide AUTOSAR REF index and resolution."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

NS_URI = "http://autosar.org/schema/r4.0"


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _qname(local: str) -> str:
    return f"{{{NS_URI}}}{local}"


def _is_ref_tag(tag: str) -> bool:
    return tag.endswith("-REF") or tag == "DEFINITION-REF"


class RefIndex:
    """Session cache: AUTOSAR path -> defining locations, plus REF edges."""

    def __init__(self) -> None:
        self.path_locations: dict[str, list[dict[str, Any]]] = {}
        self.ref_edges: list[dict[str, Any]] = []
        self.files_scanned = 0
        self.workspace: Optional[str] = None

    def build(self, workspace: Path, max_files: int = 200) -> dict[str, Any]:
        workspace = workspace.resolve()
        self.path_locations.clear()
        self.ref_edges.clear()
        self.files_scanned = 0
        self.workspace = str(workspace)

        roots = []
        cfg = workspace / "Configuration"
        if cfg.is_dir():
            roots.append(cfg)
        else:
            roots.append(workspace)

        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                parts = Path(dirpath).relative_to(workspace).parts
                if any(
                    p in {"Generated", ".git", ".metadata", "node_modules", "Build"}
                    for p in parts
                ):
                    dirnames.clear()
                    continue
                for fn in sorted(filenames):
                    if self.files_scanned >= max_files:
                        return self.stats()
                    if not fn.lower().endswith(".arxml"):
                        continue
                    if "_ECU_Configuration_PDF.arxml" in fn:
                        continue
                    rel = str((Path(dirpath) / fn).relative_to(workspace)).replace(
                        "\\", "/"
                    )
                    self._index_file(Path(dirpath) / fn, rel)
                    self.files_scanned += 1

        return self.stats()

    def stats(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "files_scanned": self.files_scanned,
            "paths_indexed": len(self.path_locations),
            "ref_edges": len(self.ref_edges),
        }

    def _add_path(self, autosar_path: str, rel: str, name: str, tag: str) -> None:
        if not autosar_path:
            return
        key = autosar_path if autosar_path.startswith("/") else f"/{autosar_path}"
        loc = {
            "file": rel,
            "name": name,
            "tag": tag,
            "autosar_path": key,
        }
        self.path_locations.setdefault(key, []).append(loc)
        # suffix index for partial match
        parts = key.split("/")
        for i in range(2, len(parts) + 1):
            suffix = "/" + "/".join(parts[-i:])
            if suffix != key:
                self.path_locations.setdefault(suffix, []).append(loc)

    def _index_file(self, full: Path, rel: str) -> None:
        stack: list[str] = []
        try:
            for event, elem in ET.iterparse(str(full), events=("start", "end")):
                tag = _local(elem.tag)
                if event == "start":
                    sn = elem.find(_qname("SHORT-NAME"))
                    if sn is not None and sn.text:
                        stack.append(sn.text.strip())
                elif event == "end":
                    path = "/" + "/".join(stack) if stack else ""
                    if stack:
                        self._add_path(path, rel, stack[-1], tag)
                    for child in elem:
                        ct = _local(child.tag)
                        if _is_ref_tag(ct) and child.text:
                            self.ref_edges.append(
                                {
                                    "from_path": path,
                                    "from_name": stack[-1] if stack else "",
                                    "from_tag": tag,
                                    "to_ref": child.text.strip(),
                                    "ref_tag": ct,
                                    "dest": child.attrib.get("DEST"),
                                    "file": rel,
                                }
                            )
                    sn = elem.find(_qname("SHORT-NAME"))
                    if sn is not None and sn.text and stack:
                        stack.pop()
        except ET.ParseError:
            return


_index_cache: Optional[RefIndex] = None
_index_workspace: Optional[str] = None


def get_index(workspace: Path, rebuild: bool = False) -> RefIndex:
    global _index_cache, _index_workspace
    ws = str(workspace.resolve())
    if rebuild or _index_cache is None or _index_workspace != ws:
        _index_cache = RefIndex()
        _index_cache.build(workspace)
        _index_workspace = ws
    return _index_cache


def resolve_ref(
    workspace: Path,
    ref: str,
    from_file: Optional[str] = None,
    rebuild: bool = False,
) -> dict[str, Any]:
    ref = (ref or "").strip()
    if not ref:
        return {"resolved": False, "error": "empty_ref"}

    idx = get_index(workspace, rebuild=rebuild)
    ws = workspace.resolve()

    candidates: list[dict[str, Any]] = []

    # Exact and normalized paths
    for key in (ref, ref if ref.startswith("/") else f"/{ref}"):
        if key in idx.path_locations:
            for loc in idx.path_locations[key]:
                candidates.append({**loc, "match": "exact", "score": 100})

    if not candidates:
        # Longest suffix match
        ref_parts = ref.strip("/").split("/")
        for n in range(len(ref_parts), 0, -1):
            suffix = "/" + "/".join(ref_parts[-n:])
            if suffix in idx.path_locations:
                for loc in idx.path_locations[suffix]:
                    candidates.append({**loc, "match": "suffix", "score": 50 + n})
                break

    if not candidates and "/" in ref:
        leaf = ref.split("/")[-1]
        for path, locs in idx.path_locations.items():
            if path.endswith("/" + leaf) or path == f"/{leaf}":
                for loc in locs:
                    candidates.append({**loc, "match": "leaf", "score": 30})

    # Heuristic: DBC / ECUC path hints
    if not candidates:
        hint = _guess_files_for_ref(ref, ws)
        for rel in hint:
            candidates.append(
                {
                    "file": rel,
                    "name": ref.split("/")[-1],
                    "tag": "?",
                    "autosar_path": ref,
                    "match": "hint",
                    "score": 10,
                }
            )

    if not candidates:
        return {
            "resolved": False,
            "ref": ref,
            "from_file": from_file,
            "message": "워크스페이스에서 대상을 찾지 못했습니다",
        }

    # Prefer same-area files, then Configuration
    def rank(c: dict[str, Any]) -> tuple[int, int, str]:
        score = c.get("score", 0)
        f = c.get("file", "")
        if from_file and f in from_file:
            score += 20
        if f.startswith("Configuration/"):
            score += 5
        return (-score, 0 if f.startswith("Configuration/") else 1, f)

    best = sorted(candidates, key=rank)[0]
    full_path = str((ws / best["file"]).resolve())

    return {
        "resolved": True,
        "ref": ref,
        "from_file": from_file,
        "file": full_path,
        "relative": best["file"],
        "autosar_path": best.get("autosar_path", ref),
        "name": best.get("name"),
        "tag": best.get("tag"),
        "match": best.get("match"),
    }


def _guess_files_for_ref(ref: str, workspace: Path) -> list[str]:
    rels: list[str] = []
    ref_l = ref.lower()
    if "dbcimport" in ref_l or "cluster" in ref_l:
        base = workspace / "Configuration" / "System" / "DBImport"
        if base.is_dir():
            rels.extend(
                str(p.relative_to(workspace)).replace("\\", "/")
                for p in base.glob("*.arxml")
            )
    if "ecuc" in ref_l or ref.startswith("/AUTRON"):
        base = workspace / "Configuration" / "Ecu"
        if base.is_dir():
            rels.extend(
                str(p.relative_to(workspace)).replace("\\", "/")
                for p in base.glob("Ecud_*.arxml")
            )
    return rels[:8]


def extract_graph(
    file_path: Path,
    focus_path: Optional[str] = None,
    limit: int = 80,
) -> dict[str, Any]:
    """Build nodes/edges for relationship graph (REF-centric)."""
    file_path = file_path.resolve()
    rel = file_path.name
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def node_id(kind: str, key: str) -> str:
        return f"{kind}:{key}"

    def add_node(nid: str, label: str, ntype: str, extra: dict | None = None) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "type": ntype, **(extra or {})}

    idx_edges: list[dict[str, Any]] = []
    stack: list[str] = []

    for event, elem in ET.iterparse(str(file_path), events=("start", "end")):
        tag = _local(elem.tag)
        if event == "start":
            sn = elem.find(_qname("SHORT-NAME"))
            if sn is not None and sn.text:
                stack.append(sn.text.strip())
        elif event == "end":
            path = "/" + "/".join(stack) if stack else ""
            if path and (
                not focus_path
                or path.startswith(focus_path)
                or focus_path in path
            ):
                if stack:
                    nid = node_id("elem", path)
                    add_node(nid, stack[-1], "element", {"path": path, "tag": tag})
                for child in elem:
                    ct = _local(child.tag)
                    if _is_ref_tag(ct) and child.text:
                        ref = child.text.strip()
                        idx_edges.append({"from": path, "to": ref, "tag": ct})
            sn = elem.find(_qname("SHORT-NAME"))
            if sn is not None and sn.text and stack:
                stack.pop()

    # External index edges from same file in workspace cache optional — use local only first
    for e in idx_edges[:limit]:
        from_path = e["from"]
        to_ref = e["to"]
        fn = node_id("elem", from_path)
        tn = node_id("ref", to_ref)
        add_node(fn, from_path.split("/")[-1] or from_path, "element", {"path": from_path})
        add_node(tn, to_ref.split("/")[-1] or to_ref, "ref", {"ref": to_ref})
        edges.append(
            {
                "from": fn,
                "to": tn,
                "kind": "REF",
                "label": _local(e["tag"]) if "/" not in e["tag"] else e["tag"],
            }
        )
        if len(nodes) >= limit:
            break

    return {
        "file": str(file_path),
        "focus": focus_path,
        "nodes": list(nodes.values())[:limit],
        "edges": edges[:limit],
        "truncated": len(idx_edges) > limit,
    }
