# -*- coding: utf-8 -*-
"""Workspace search and related-context (REF in/out, linked modules)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import arxml_parser as ap
import ref_index as ri

NS_URI = "http://autosar.org/schema/r4.0"


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _qname(local: str) -> str:
    return f"{{{NS_URI}}}{local}"


def module_from_autosar_ref(ref: str) -> Optional[str]:
    ref = (ref or "").strip()
    if not ref.startswith("/"):
        ref = f"/{ref}"
    parts = ref.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "AUTRON":
        return parts[1]
    if parts and parts[0] == "AUTOSAR":
        return "EcuC"
    return None


def _container_lookup_keys(node_path: str, node_name: Optional[str]) -> list[str]:
    """Keys for matching ECUC-CONTAINER-VALUE paths (XML or AUTOSAR logical)."""
    keys: list[str] = []
    seen: set[str] = set()

    def add(k: str) -> None:
        k = (k or "").replace("\\", "/").strip("/")
        if k and k not in seen:
            seen.add(k)
            keys.append(k)

    raw = (node_path or "").replace("\\", "/").strip()
    if raw.startswith("/"):
        raw = raw.strip("/")
    if raw:
        add(raw)
        parts = raw.split("/")
        if len(parts) >= 2 and parts[0] == "AUTRON":
            add("/".join(parts[2:]))
        if len(parts) >= 3 and parts[0] == "AUTRON":
            add("/".join(parts[1:]))
    if node_name:
        add(node_name)
    return keys


def _split_ref_values(text: str) -> list[str]:
    """Comma-separated VALUE-REF lists (common in Dcm session refs)."""
    out: list[str] = []
    for part in (text or "").split(","):
        p = part.strip()
        if p.startswith("/"):
            out.append(p)
    return out


def search_workspace(
    workspace: Path, query: str, limit: int = 40
) -> dict[str, Any]:
    query = (query or "").strip()
    if len(query) < 2:
        return {"query": query, "results": [], "count": 0}

    idx = ri.get_index(workspace.resolve())
    q = query.lower()
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for path, locs in idx.path_locations.items():
        for loc in locs:
            name = (loc.get("name") or "").lower()
            path_l = path.lower()
            score = 0
            if name == q:
                score = 100
            elif name.startswith(q):
                score = 80
            elif q in name:
                score = 60
            elif q in path_l:
                score = 40
            else:
                continue
            key = (loc.get("file", ""), path)
            if key in seen:
                continue
            seen.add(key)
            mod = module_from_autosar_ref(path) or ""
            results.append(
                {
                    "name": loc.get("name") or path.split("/")[-1],
                    "autosar_path": path,
                    "file": loc.get("file"),
                    "tag": loc.get("tag"),
                    "module": mod,
                    "score": score,
                }
            )

    results.sort(key=lambda r: (-r["score"], r.get("name") or ""))
    return {
        "query": query,
        "results": results[:limit],
        "count": len(results),
        "truncated": len(results) > limit,
    }


def _incoming_refs(
    idx: ri.RefIndex, autosar_paths: list[str], limit: int
) -> list[dict[str, Any]]:
    """REF edges that point exactly at this container's AUTOSAR path (no parent rollup)."""
    keys: set[str] = set()
    for p in autosar_paths:
        p = (p or "").replace("\\", "/").strip()
        if not p:
            continue
        keys.add(p if p.startswith("/") else f"/{p}")

    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for edge in idx.ref_edges:
        to_ref = (edge.get("to_ref") or "").strip()
        if not to_ref:
            continue
        to_norm = to_ref if to_ref.startswith("/") else f"/{to_ref}"
        if to_norm not in keys:
            continue
        sig = (edge.get("file", ""), edge.get("from_path", ""), to_ref)
        if sig in seen:
            continue
        seen.add(sig)
        hits.append(
            {
                "file": edge.get("file"),
                "from_path": edge.get("from_path"),
                "from_name": edge.get("from_name"),
                "from_tag": edge.get("from_tag"),
                "ref_tag": edge.get("ref_tag"),
                "target": to_ref,
                "module": module_from_autosar_ref(to_ref),
                "dest": edge.get("dest"),
            }
        )

    hits.sort(key=lambda h: (h.get("file", ""), h.get("from_path", "")))
    return hits[:limit]


def _autosar_path_from_xml(xml_path: str) -> str:
    """Best-effort AUTOSAR logical path from Ecud XML tree path."""
    skip = {
        "AUTOSAR",
        "AR-PACKAGES",
        "AUTRON",
        "ELEMENTS",
        "CONTAINERS",
        "SUB-CONTAINERS",
    }
    parts = [p for p in xml_path.replace("\\", "/").split("/") if p and p not in skip]
    if not parts:
        return ""
    if parts[0] == "Dcm":
        return "/AUTRON/" + "/".join(parts)
    return "/AUTRON/" + "/".join(parts)


def _exact_container_bundle(
    file_path: Path, want_path: str
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Bundle only when XML path matches exactly (score 100)."""
    want = (want_path or "").replace("\\", "/").strip("/")
    if not want:
        return None, None

    file_path = file_path.resolve()
    best: Optional[dict[str, Any]] = None
    best_full: Optional[str] = None
    stack: list[ET.Element] = []

    try:
        for event, elem in ET.iterparse(str(file_path), events=("start", "end")):
            if event == "start":
                stack.append(elem)
            else:
                tag = _local(elem.tag)
                if tag == "ECUC-CONTAINER-VALUE":
                    full = ap._path_from_element_stack(stack).strip("/")
                    if ap._path_match_score(want, full) == 100:
                        best = ap._bundle_from_container_elem(elem, full)
                        best_full = full
                        stack.pop()
                        break
                stack.pop()
    except ET.ParseError:
        return None, None

    return best, best_full


def _outgoing_refs_from_container(
    file_path: Path,
    xml_path: str,
    limit: int = 35,
) -> list[dict[str, Any]]:
    """Outgoing VALUE-REF on the selected container only (same as property REF table)."""
    bundle, _ = _exact_container_bundle(file_path, xml_path)
    if not bundle:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for prop in bundle.get("properties", []):
        if prop.get("key") != "_ref_table":
            continue
        for r in prop.get("ref_rows") or []:
            tgt = (r.get("value") or "").strip()
            if not tgt.startswith("/") or tgt in seen:
                continue
            seen.add(tgt)
            out.append(
                {
                    "target": tgt,
                    "label": r.get("name") or tgt.split("/")[-1],
                    "ref_tag": "VALUE-REF",
                    "kind": "reference",
                    "module": module_from_autosar_ref(tgt),
                }
            )
            if len(out) >= limit:
                break
    return out[:limit]


def resolve_tree_path(
    file_path: Path, node_path: str, node_name: Optional[str] = None
) -> Optional[str]:
    """Map AUTOSAR logical path to XML tree path; tree paths pass through unchanged."""
    raw = (node_path or "").replace("\\", "/").strip("/")
    if raw.startswith("AUTOSAR/"):
        _, matched = _exact_container_bundle(file_path, raw)
        return matched or raw

    lookup_keys = _container_lookup_keys(node_path, node_name)
    if not lookup_keys:
        return None

    best_full: Optional[str] = None
    best_score = 0
    stack: list[ET.Element] = []

    try:
        for event, elem in ET.iterparse(str(file_path.resolve()), events=("start", "end")):
            if event == "start":
                stack.append(elem)
            else:
                tag = _local(elem.tag)
                if tag == "ECUC-CONTAINER-VALUE":
                    full = ap._path_from_element_stack(stack).strip("/")
                    score = 0
                    for key in lookup_keys:
                        score = max(score, ap._path_match_score(key, full))
                    if score > best_score:
                        best_score = score
                        best_full = full
                stack.pop()
    except ET.ParseError:
        return None

    if best_score < 90:
        return None
    return best_full


def find_related(
    workspace: Path,
    file_path: str,
    node_path: str,
    node_name: Optional[str] = None,
    limit: int = 35,
) -> dict[str, Any]:
    """
    Related context for analysis: outgoing REFs, incoming REFs, linked BSW modules.
    """
    workspace = workspace.resolve()
    fp = Path(file_path)
    if not fp.is_file():
        fp = workspace / file_path.replace("\\", "/")
    rel_file = str(fp.relative_to(workspace)).replace("\\", "/") if fp.is_file() else file_path

    tree_path = resolve_tree_path(fp, node_path, node_name=node_name)
    xml_path = tree_path or (node_path or "").replace("\\", "/").strip("/")

    bundle, _matched_xml = _exact_container_bundle(fp, xml_path) if xml_path else (None, None)
    autosar_paths: list[str] = []
    if (node_path or "").startswith("/AUTRON"):
        autosar_paths.append(node_path)
    elif xml_path:
        autosar_paths.append(_autosar_path_from_xml(xml_path))

    idx = ri.get_index(workspace)
    incoming = _incoming_refs(idx, autosar_paths, limit=limit)
    outgoing = _outgoing_refs_from_container(fp, xml_path, limit=limit) if xml_path else []

    current_mod: Optional[str] = None
    if rel_file.startswith("Configuration/Ecu/Ecud_"):
        current_mod = Path(rel_file).stem.replace("Ecud_", "", 1)

    return {
        "file": rel_file,
        "path": node_path,
        "tree_path": tree_path,
        "autosar_path": autosar_paths[0] if autosar_paths else None,
        "name": node_name,
        "current_module": current_mod,
        "outgoing": outgoing,
        "incoming": incoming,
        "outgoing_count": len(outgoing),
        "incoming_count": len(incoming),
    }
