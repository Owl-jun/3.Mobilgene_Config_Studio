# -*- coding: utf-8 -*-
"""
ARXML streaming parser for Mobilgene Config Studio.
Lightweight index + lazy subtree loading (no full DOM for large Ecud_*.arxml).
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

NS = {"a": "http://autosar.org/schema/r4.0"}
NS_URI = "http://autosar.org/schema/r4.0"

# Tags treated as tool metadata (read-only in UI)
# Tool / vendor metadata — hidden in analysis tree (params shown on container select)
META_TAGS = frozenset(
    {
        "ADMIN-DATA",
        "SDG",
        "SDGS",
        "SD",
        "ANNOTATIONS",
        "ANNOTATION",
        "INTRODUCTION",
        "DESC",
        "LONG-NAME",
    }
)

# Structural wrappers — hoisted or skipped in tree (not analysis targets)
TREE_SKIP_TAGS = frozenset(
    {
        "PARAMETER-VALUES",
        "REFERENCE-VALUES",
        "SUB-CONTAINERS",
        "CONTAINERS",
        "SHORT-NAME",
        "DEFINITION-REF",
        "VALUE",
        "VALUE-REF",
    }
)

READONLY_SEGMENTS = (
    "Generated",
    os.path.join("Static_Code", "delivery"),
    "Build",
)

EDITABLE_ROOT = "Configuration"


class ProfileId(str, Enum):
    GATEWAY = "gateway"
    ECUC = "ecuc"
    SWC_APP = "swc_app"
    SWC_BSW = "swc_bsw"
    DBC_CLUSTER = "dbc_cluster"
    GENERIC = "generic"


@dataclass
class FileEntry:
    path: str
    name: str
    relative: str
    profile: str
    editable: bool
    readonly_reason: Optional[str] = None
    size_bytes: int = 0


@dataclass
class TreeNode:
    id: str
    tag: str
    name: Optional[str]
    path: str
    depth: int
    child_count: int
    has_children: bool
    is_meta: bool = False
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["TreeNode"] = field(default_factory=list)
    # Leaf value for simple elements
    text: Optional[str] = None
    ref_dest: Optional[str] = None


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _qname(local: str) -> str:
    return f"{{{NS_URI}}}{local}"


def is_readonly_path(rel_path: str) -> tuple[bool, Optional[str]]:
    norm = rel_path.replace("\\", "/")
    if "_ECU_Configuration_PDF.arxml" in norm:
        return True, "schema_definition"
    for seg in READONLY_SEGMENTS:
        if f"/{seg}/" in f"/{norm}/" or norm.startswith(f"{seg}/"):
            return True, "readonly_segment"
    if not norm.startswith(EDITABLE_ROOT + "/") and not norm.startswith(EDITABLE_ROOT + "\\"):
        if norm.startswith("Generated") or "Generated/" in norm:
            return True, "generated"
    return False, None


def is_editable(rel_path: str) -> bool:
    ro, _ = is_readonly_path(rel_path)
    if ro:
        return False
    norm = rel_path.replace("\\", "/")
    return norm.startswith(EDITABLE_ROOT + "/") and norm.lower().endswith(".arxml")


def detect_profile(rel_path: str, sample_text: str = "") -> ProfileId:
    norm = rel_path.replace("\\", "/").lower()
    if norm.endswith("gateway.arxml"):
        return ProfileId.GATEWAY
    if "ecud_" in norm and "/ecu/" in norm:
        return ProfileId.ECUC
    if "/swcd_app/" in norm:
        return ProfileId.SWC_APP
    if "/swcd_bsw/" in norm:
        return ProfileId.SWC_BSW
    if "/dbimport/" in norm:
        return ProfileId.DBC_CLUSTER
    if sample_text:
        if "<GATEWAY" in sample_text or "I-PDU-MAPPING" in sample_text:
            return ProfileId.GATEWAY
        if "ECUC-MODULE-CONFIGURATION-VALUES" in sample_text:
            return ProfileId.ECUC
        if "APPLICATION-SW-COMPONENT-TYPE" in sample_text:
            return ProfileId.SWC_APP
        if "SERVICE-SW-COMPONENT-TYPE" in sample_text:
            return ProfileId.SWC_BSW
        if "DBCImport" in sample_text or "CAN-CLUSTER" in sample_text:
            return ProfileId.DBC_CLUSTER
    return ProfileId.GENERIC


def _read_sample(path: Path, max_bytes: int = 8192) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(max_bytes)


def scan_workspace(root: Path) -> dict[str, Any]:
    root = root.resolve()
    arxml_files: list[FileEntry] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip heavy dirs
        parts = Path(dirpath).relative_to(root).parts
        skip = {"Generated", ".git", ".metadata", "node_modules"}
        if any(p in skip for p in parts):
            dirnames.clear()
            continue
        for fn in sorted(filenames):
            if not fn.lower().endswith(".arxml"):
                continue
            full = Path(dirpath) / fn
            rel = str(full.relative_to(root)).replace("\\", "/")
            ro, reason = is_readonly_path(rel)
            profile = detect_profile(rel)
            if profile == ProfileId.GENERIC:
                sample = _read_sample(full)
                profile = detect_profile(rel, sample)
            arxml_files.append(
                FileEntry(
                    path=str(full),
                    name=fn,
                    relative=rel,
                    profile=profile.value,
                    editable=is_editable(rel) and not ro,
                    readonly_reason=reason,
                    size_bytes=full.stat().st_size,
                )
            )

    def file_to_dict(f: FileEntry) -> dict[str, Any]:
        return {
            "path": f.path,
            "name": f.name,
            "relative": f.relative,
            "profile": f.profile,
            "editable": f.editable,
            "readonly_reason": f.readonly_reason,
            "size_bytes": f.size_bytes,
        }

    return {
        "root": str(root),
        "arxml_count": len(arxml_files),
        "files": [
            file_to_dict(f)
            for f in sorted(arxml_files, key=lambda x: x.relative)
        ],
    }


def build_index(file_path: Path, max_depth: int = 2) -> dict[str, Any]:
    """Build shallow index tree (depth-limited) for navigation."""
    file_path = file_path.resolve()
    rel_hint = file_path.name
    sample = _read_sample(file_path)
    profile = detect_profile(rel_hint, sample)

    root_node = _parse_shallow(file_path, max_depth=max_depth)
    return {
        "file": str(file_path),
        "profile": profile.value,
        "root": _node_to_dict(root_node),
        "stats": _count_nodes(root_node),
    }


def _count_nodes(node: Optional[TreeNode]) -> dict[str, int]:
    if not node:
        return {"nodes": 0, "max_depth": 0}

    def walk(n: TreeNode, d: int) -> tuple[int, int]:
        cnt = 1
        md = d
        for c in n.children:
            sub, sd = walk(c, d + 1)
            cnt += sub
            md = max(md, sd)
        return cnt, md

    n, md = walk(node, 0)
    return {"nodes": n, "max_depth": md}


def _node_to_dict(node: TreeNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "tag": node.tag,
        "name": node.name,
        "path": node.path,
        "depth": node.depth,
        "child_count": node.child_count,
        "has_children": node.has_children,
        "is_meta": node.is_meta,
        "attrs": node.attrs,
        "text": node.text,
        "ref_dest": node.ref_dest,
        "children": [_node_to_dict(c) for c in node.children],
    }


def _parse_shallow(file_path: Path, max_depth: int = 3) -> TreeNode:
    """iterparse-based shallow tree for large files."""
    root_holder: list[TreeNode] = []
    stack: list[tuple[ET.Element, TreeNode, int]] = []
    node_counter = 0

    for event, elem in ET.iterparse(str(file_path), events=("start", "end")):
        tag = _local(elem.tag)
        if event == "start":
            node_counter += 1
            name = None
            sn = elem.find(_qname("SHORT-NAME"))
            if sn is not None and sn.text:
                name = sn.text.strip()
            path = _element_path(stack, tag, name)
            is_meta = tag in META_TAGS
            attrs = {k: v for k, v in elem.attrib.items() if k in ("UUID", "DEST")}
            ref_dest = attrs.get("DEST")
            child_count = 0
            has_children = len(list(elem)) > 0 if event == "start" else False
            # Estimate children on start
            if event == "start":
                child_count = sum(1 for _ in elem)

            node = TreeNode(
                id=f"n{node_counter}",
                tag=tag,
                name=name,
                path=path,
                depth=len(stack),
                child_count=child_count,
                has_children=child_count > 0,
                is_meta=is_meta,
                attrs=attrs,
                ref_dest=ref_dest,
            )
            if stack:
                parent = stack[-1][1]
                if parent.depth < max_depth:
                    parent.children.append(node)
            else:
                root_holder.append(node)
            stack.append((elem, node, len(stack)))
            if len(stack) > max_depth + 1:
                continue
        elif event == "end":
            if stack and stack[-1][0] is elem:
                cur = stack[-1][1]
                # Capture text value for leaf REF/VALUE tags
                if tag.endswith("-REF") and elem.text:
                    cur.text = elem.text.strip()
                elif tag == "VALUE" and elem.text:
                    cur.text = elem.text.strip()
                elif elem.text and elem.text.strip() and not list(elem):
                    cur.text = elem.text.strip()
                if tag == "SHORT-NAME" and elem.text and len(stack) >= 2:
                    _apply_short_name_to_container(elem, stack)
                if _is_ecuc_param_value_tag(tag) or tag == "ECUC-REFERENCE-VALUE":
                    _finalize_ecuc_value_node(elem, cur, stack)
                if tag == "ECUC-CONTAINER-VALUE":
                    sn = elem.find(_qname("SHORT-NAME"))
                    if sn is not None and sn.text and not cur.name:
                        cur.name = sn.text.strip()
                        if len(stack) >= 2:
                            cur.path = f"{stack[-2][1].path}/{cur.name}"
                    _repath_subtree(cur, cur.path)
                    cur.has_children = _has_visible_tree_children(elem)
                elif tag in (
                    "ECUC-MODULE-CONFIGURATION-VALUES",
                    "ECUC-VALUES",
                    "AR-PACKAGE",
                    "AR-PACKAGES",
                    "AUTOSAR",
                ):
                    cur.has_children = _has_visible_tree_children(elem)
                stack.pop()
            if _should_clear_after_end(tag):
                elem.clear()

    if root_holder:
        return root_holder[0]
    return TreeNode(
        id="n0",
        tag="AUTOSAR",
        name=None,
        path="/AUTOSAR",
        depth=0,
        child_count=0,
        has_children=False,
    )


def _is_ecuc_param_value_tag(tag: str) -> bool:
    return tag.startswith("ECUC-") and tag.endswith("-PARAM-VALUE")


def _has_visible_tree_children(elem: ET.Element) -> bool:
    """True only if the node has sub-containers or meaningful ARXML children to show."""
    for wrapper in ("SUB-CONTAINERS", "CONTAINERS"):
        parent = elem.find(_qname(wrapper))
        if parent is not None:
            for child in parent:
                if _local(child.tag) == "ECUC-CONTAINER-VALUE":
                    return True
    for child in elem:
        lt = _local(child.tag)
        if lt in META_TAGS or lt in TREE_SKIP_TAGS:
            continue
        if _is_ecuc_param_value_tag(lt):
            continue
        if lt in (
            "ECUC-CONTAINER-VALUE",
            "ECUC-MODULE-CONFIGURATION-VALUES",
            "AR-PACKAGE",
            "ELEMENTS",
            "ECUC-VALUES",
        ):
            return True
        if lt.endswith("REF") and lt != "DEFINITION-REF":
            return True
    return False


def _apply_short_name_to_container(
    elem: ET.Element,
    stack: list[tuple[Any, TreeNode, int]],
) -> None:
    """SHORT-NAME is usually parsed before siblings; fix container path early."""
    if len(stack) < 2:
        return
    container_node = stack[-2][1]
    short = elem.text.strip() if elem.text else ""
    if not short:
        return
    container_node.name = short
    if len(stack) >= 3:
        container_node.path = f"{stack[-3][1].path}/{short}"
    else:
        container_node.path = f"/{short}"


def _repath_subtree(node: TreeNode, base_path: str) -> None:
    for child in node.children:
        seg = child.name or child.tag
        child.path = f"{base_path}/{seg}"
        _repath_subtree(child, child.path)


def _should_clear_after_end(tag: str) -> bool:
    """Defer clear so parent SHORT-NAME survives until container closes."""
    return tag in (
        "ECUC-CONTAINER-VALUE",
        "ECUC-MODULE-CONFIGURATION-VALUES",
        "ECUC-VALUES",
        "AR-PACKAGE",
        "AR-PACKAGES",
        "AUTOSAR",
    )


def _finalize_ecuc_value_node(
    elem: ET.Element,
    node: TreeNode,
    stack: list[tuple[Any, TreeNode, int]],
) -> None:
    """
    ECUC param/ref value nodes often lack SHORT-NAME — use DEFINITION-REF leaf
    so sibling paths stay unique (fixes duplicate PduRCancelReceive in tree).
    """
    if len(stack) < 2:
        return
    parent_path = stack[-2][1].path
    tag = _local(elem.tag)
    leaf: Optional[str] = None

    if _is_ecuc_param_value_tag(tag):
        def_ref = elem.find(_qname("DEFINITION-REF"))
        if def_ref is not None and def_ref.text:
            leaf = def_ref.text.strip().split("/")[-1]
    elif tag == "ECUC-REFERENCE-VALUE":
        def_ref = elem.find(_qname("DEFINITION-REF"))
        if def_ref is not None and def_ref.text:
            leaf = _ref_label(def_ref)

    if leaf:
        node.name = leaf
        node.path = f"{parent_path}/{leaf}"


def _element_path(
    stack: list[tuple[Any, TreeNode, int]], tag: str, name: Optional[str]
) -> str:
    parts = []
    for _, node, _ in stack:
        seg = node.name or node.tag
        parts.append(seg)
    seg = name or tag
    parts.append(seg)
    return "/" + "/".join(parts)


def _flatten_tree_children_dict(children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hoist SUB-CONTAINERS; hide PARAMETER/REFERENCE-VALUES and param value leaves."""
    out: list[dict[str, Any]] = []
    for ch in children:
        if ch.get("is_meta"):
            continue
        tag = ch.get("tag") or ""
        if tag == "SUB-CONTAINERS" or tag == "CONTAINERS":
            out.extend(_flatten_tree_children_dict(ch.get("children") or []))
            continue
        if tag in TREE_SKIP_TAGS:
            continue
        if _is_ecuc_param_value_tag(tag):
            continue
        item = dict(ch)
        item["children"] = _flatten_tree_children_dict(ch.get("children") or [])
        out.append(item)
    return out


def load_subtree(
    file_path: Path, node_path: str, depth: int = 2
) -> dict[str, Any]:
    """Load children under a logical path (lazy expand)."""
    file_path = file_path.resolve()
    segs = len(node_path.replace("\\", "/").strip("/").split("/"))
    parse_depth = min(max(segs + int(depth) + 4, 10), 96)
    full = _parse_shallow(file_path, max_depth=parse_depth)
    found = _find_by_path(full, node_path)
    if not found:
        return {"path": node_path, "node": None, "error": "path_not_found"}
    _trim_depth(found, depth)
    node_dict = _node_to_dict(found)
    node_dict["children"] = _flatten_tree_children_dict(node_dict.get("children") or [])
    return {"path": node_path, "node": node_dict}


def _find_by_path(node: TreeNode, path: str) -> Optional[TreeNode]:
    if node.path == path or node.path.rstrip("/") == path.rstrip("/"):
        return node
    for c in node.children:
        hit = _find_by_path(c, path)
        if hit:
            return hit
    return None


def _trim_depth(node: TreeNode, max_depth: int, current: int = 0) -> None:
    if current >= max_depth:
        node.children = []
        node.has_children = node.child_count > 0
        return
    for c in node.children:
        _trim_depth(c, max_depth, current + 1)


def _parse_dbc_pdu_ref(ref: str) -> dict[str, str]:
    """/DBCImport/CLUSTERS/R_CAN1/R_CAN1/PT_... → cluster + PDU label."""
    ref = (ref or "").strip()
    parts = ref.strip("/").split("/")
    pdu = parts[-1] if parts else ref
    cluster = ""
    if "CLUSTERS" in parts:
        i = parts.index("CLUSTERS")
        if i + 1 < len(parts):
            cluster = parts[i + 1]
    return {"cluster": cluster, "pdu": pdu, "ref": ref}


def extract_gateway_mappings(file_path: Path) -> dict[str, Any]:
    """Extract I-PDU mapping rows for gateway profile view."""
    file_path = file_path.resolve()
    gateways: list[dict[str, Any]] = []

    for event, elem in ET.iterparse(str(file_path), events=("end",)):
        tag = _local(elem.tag)
        if tag == "GATEWAY":
            gw_name = _short_name(elem)
            mappings = []
            for mapping in elem.findall(f".//{_qname('I-PDU-MAPPING')}"):
                src = mapping.find(_qname("SOURCE-I-PDU-REF"))
                tgt_container = mapping.find(_qname("TARGET-I-PDU"))
                tgt = None
                if tgt_container is not None:
                    tgt = tgt_container.find(_qname("TARGET-I-PDU-REF"))
                src_ref = src.text.strip() if src is not None and src.text else ""
                tgt_ref = tgt.text.strip() if tgt is not None and tgt.text else ""
                src_p = _parse_dbc_pdu_ref(src_ref)
                tgt_p = _parse_dbc_pdu_ref(tgt_ref)
                mappings.append(
                    {
                        "id": f"{gw_name}_{len(mappings)}",
                        "source": _ref_label(src),
                        "source_ref": src_ref,
                        "source_dest": src.attrib.get("DEST") if src is not None else None,
                        "source_cluster": src_p["cluster"],
                        "source_pdu": src_p["pdu"],
                        "target": _ref_label(tgt),
                        "target_ref": tgt_ref,
                        "target_dest": tgt.attrib.get("DEST") if tgt is not None else None,
                        "target_cluster": tgt_p["cluster"],
                        "target_pdu": tgt_p["pdu"],
                    }
                )
            gateways.append(
                {
                    "name": gw_name,
                    "mapping_count": len(mappings),
                    "mappings": mappings,
                }
            )
            elem.clear()
        elif tag == "I-PDU-MAPPING" and not gateways:
            pass

    return {
        "file": str(file_path),
        "profile": ProfileId.GATEWAY.value,
        "gateways": gateways,
        "total_mappings": sum(g["mapping_count"] for g in gateways),
    }


def _short_name(elem: ET.Element) -> str:
    sn = elem.find(_qname("SHORT-NAME"))
    return sn.text.strip() if sn is not None and sn.text else "unnamed"


def _ref_label(ref_elem: Optional[ET.Element]) -> str:
    if ref_elem is None or not ref_elem.text:
        return ""
    text = ref_elem.text.strip()
    return text.split("/")[-1] if "/" in text else text


def extract_ecuc_summary(file_path: Path, max_containers: int = 200) -> dict[str, Any]:
    """Extract ECUC module summary: containers and parameters (bounded)."""
    file_path = file_path.resolve()
    module_name = None
    containers: list[dict[str, Any]] = []
    count = 0

    for event, elem in ET.iterparse(str(file_path), events=("end",)):
        tag = _local(elem.tag)
        if tag == "ECUC-MODULE-CONFIGURATION-VALUES" and module_name is None:
            module_name = _short_name(elem)
        if tag == "ECUC-CONTAINER-VALUE" and count < max_containers:
            cname = _short_name(elem)
            params = []
            for pv in elem.findall(f".//{_qname('ECUC-NUMERICAL-PARAM-VALUE')}"):
                def_ref = pv.find(_qname("DEFINITION-REF"))
                val = pv.find(_qname("VALUE"))
                if def_ref is not None and val is not None:
                    params.append(
                        {
                            "definition": _ref_label(def_ref),
                            "definition_path": def_ref.text.strip() if def_ref.text else "",
                            "value": val.text.strip() if val.text else "",
                        }
                    )
            for pv in elem.findall(f".//{_qname('ECUC-TEXTUAL-PARAM-VALUE')}"):
                def_ref = pv.find(_qname("DEFINITION-REF"))
                val = pv.find(_qname("VALUE"))
                if def_ref is not None:
                    params.append(
                        {
                            "definition": _ref_label(def_ref),
                            "definition_path": def_ref.text.strip() if def_ref.text else "",
                            "value": val.text.strip() if val is not None and val.text else "",
                        }
                    )
            sub_count = len(elem.findall(_qname("SUB-CONTAINERS")))
            containers.append(
                {
                    "name": cname,
                    "path": f"/{module_name}/{cname}" if module_name else cname,
                    "parameter_count": len(params),
                    "parameters": params[:50],
                    "has_sub_containers": sub_count > 0,
                }
            )
            count += 1
            elem.clear()

    return {
        "file": str(file_path),
        "profile": ProfileId.ECUC.value,
        "module": module_name,
        "container_count": count,
        "containers": containers,
        "truncated": count >= max_containers,
    }


PARAM_VALUE_TAGS = frozenset(
    {
        "ECUC-NUMERICAL-PARAM-VALUE",
        "ECUC-TEXTUAL-PARAM-VALUE",
        "ECUC-ENUMERATION-PARAM-VALUE",
        "ECUC-BOOLEAN-PARAM-VALUE",
    }
)
REF_VALUE_TAGS = frozenset({"ECUC-REFERENCE-VALUE"})


def _path_match_score(want: str, full: str) -> int:
    """Higher = better match. 100 = exact path."""
    want = want.replace("\\", "/").strip("/")
    full = full.replace("\\", "/").strip("/")
    if not want or not full:
        return 0
    if full == want:
        return 100
    if full.endswith("/" + want):
        return 90
    wp = want.split("/")
    fp = full.split("/")
    if len(wp) >= 3 and len(fp) >= len(wp) and fp[-len(wp) :] == wp:
        return 70
    return 0


def _paths_match(want: str, full: str) -> bool:
    return _path_match_score(want, full) > 0


def _path_from_element_stack(stack: list[ET.Element]) -> str:
    parts: list[str] = []
    for e in stack:
        tag = _local(e.tag)
        if tag == "SHORT-NAME":
            continue
        sn = e.find(_qname("SHORT-NAME"))
        if sn is not None and sn.text:
            parts.append(sn.text.strip())
        elif tag not in META_TAGS:
            parts.append(tag)
    return "/" + "/".join(parts)


def _extract_param_row(child: ET.Element) -> Optional[dict[str, Any]]:
    tag = _local(child.tag)
    def_ref = child.find(_qname("DEFINITION-REF"))
    name = _ref_label(def_ref) if def_ref is not None else tag
    def_path = def_ref.text.strip() if def_ref is not None and def_ref.text else ""

    val_el = child.find(_qname("VALUE"))
    if val_el is not None and val_el.text is not None:
        return {
            "name": name,
            "value": val_el.text.strip(),
            "definition_path": def_path,
            "kind": tag,
        }
    vref = child.find(_qname("VALUE-REF"))
    if vref is not None and vref.text:
        return {
            "name": name,
            "value": vref.text.strip(),
            "definition_path": def_path,
            "kind": tag,
            "value_is_ref": True,
            "value_dest": vref.attrib.get("DEST"),
        }
    return None


def extract_value_container_rows(
    file_path: Path, node_path: str, max_rows: int = 400
) -> list[dict[str, Any]]:
    """Direct children under PARAMETER-VALUES or REFERENCE-VALUES as flat name/value rows."""
    file_path = file_path.resolve()
    want = node_path.replace("\\", "/").strip("/")
    best_rows: list[dict[str, Any]] = []
    best_score = 0
    stack: list[ET.Element] = []

    try:
        for event, elem in ET.iterparse(str(file_path), events=("start", "end")):
            if event == "start":
                stack.append(elem)
            else:
                tag = _local(elem.tag)
                full_path = _path_from_element_stack(stack).strip("/")
                if tag in ("PARAMETER-VALUES", "REFERENCE-VALUES"):
                    score = _path_match_score(want, full_path)
                    if score > best_score:
                        rows: list[dict[str, Any]] = []
                        for child in list(elem):
                            ct = _local(child.tag)
                            if ct in PARAM_VALUE_TAGS or ct in REF_VALUE_TAGS:
                                row = _extract_param_row(child)
                                if row and len(rows) < max_rows:
                                    rows.append(row)
                        best_score = score
                        best_rows = rows
                        if score >= 100:
                            stack.pop()
                            if _should_clear_after_end(tag):
                                elem.clear()
                            break
                stack.pop()
                if _should_clear_after_end(tag):
                    elem.clear()
    except ET.ParseError:
        return []

    return best_rows


def _bundle_from_container_elem(
    elem: ET.Element, logical_path: str
) -> dict[str, Any]:
    props: list[dict[str, Any]] = []
    sn = elem.find(_qname("SHORT-NAME"))
    name = sn.text.strip() if sn is not None and sn.text else ""
    if name:
        props.append({"key": "SHORT-NAME", "value": name, "readonly": False})
    uuid = elem.attrib.get("UUID")
    if uuid:
        props.append({"key": "UUID", "value": uuid, "readonly": True})
    def_ref = elem.find(_qname("DEFINITION-REF"))
    if def_ref is not None and def_ref.text:
        props.append(
            {
                "key": "DEFINITION-REF",
                "value": def_ref.text.strip(),
                "readonly": True,
                "is_ref": True,
                "dest": def_ref.attrib.get("DEST"),
            }
        )

    param_rows: list[dict[str, Any]] = []
    pv_parent = elem.find(_qname("PARAMETER-VALUES"))
    if pv_parent is not None:
        for child in pv_parent:
            ct = _local(child.tag)
            if ct in PARAM_VALUE_TAGS:
                row = _extract_param_row(child)
                if row:
                    param_rows.append(row)

    ref_rows: list[dict[str, Any]] = []
    rv_parent = elem.find(_qname("REFERENCE-VALUES"))
    if rv_parent is not None:
        for child in rv_parent:
            if _local(child.tag) in REF_VALUE_TAGS:
                row = _extract_param_row(child)
                if row:
                    ref_rows.append(row)

    sub = elem.find(_qname("SUB-CONTAINERS"))
    if sub is not None:
        sub_n = sum(1 for c in sub if _local(c.tag) == "ECUC-CONTAINER-VALUE")
        if sub_n:
            props.append(
                {"key": "하위 컨테이너", "value": str(sub_n), "readonly": True}
            )

    if param_rows:
        props.append(
            {"key": "_param_table", "param_rows": param_rows, "readonly": True}
        )
    if ref_rows:
        props.append(
            {"key": "_ref_table", "ref_rows": ref_rows, "readonly": True}
        )

    path = logical_path if logical_path.startswith("/") else f"/{logical_path}"
    return {
        "path": path,
        "tag": "ECUC-CONTAINER-VALUE",
        "properties": props,
        "node": {"name": name, "tag": "ECUC-CONTAINER-VALUE"},
        "param_row_count": len(param_rows),
        "ref_row_count": len(ref_rows),
    }


def extract_ecuc_container_bundle(
    file_path: Path, node_path: str
) -> Optional[dict[str, Any]]:
    """Read PARAMETER/REFERENCE-VALUES for an ECUC-CONTAINER-VALUE by path."""
    file_path = file_path.resolve()
    want = node_path.replace("\\", "/").strip("/")
    best: Optional[dict[str, Any]] = None
    best_score = 0
    stack: list[ET.Element] = []

    try:
        for event, elem in ET.iterparse(str(file_path), events=("start", "end")):
            if event == "start":
                stack.append(elem)
            else:
                tag = _local(elem.tag)
                if tag == "ECUC-CONTAINER-VALUE":
                    full = _path_from_element_stack(stack).strip("/")
                    score = _path_match_score(want, full)
                    if score > best_score:
                        best_score = score
                        best = _bundle_from_container_elem(elem, full)
                        if score >= 100:
                            stack.pop()
                            if _should_clear_after_end(tag):
                                elem.clear()
                            break
                stack.pop()
                if _should_clear_after_end(tag):
                    elem.clear()
    except ET.ParseError:
        return None

    if best_score < 70:
        return None
    return best


def get_node_properties(file_path: Path, node_path: str) -> dict[str, Any]:
    """Return property bag for selected node (for property panel)."""
    tail = node_path.replace("\\", "/").rstrip("/").split("/")[-1]

    if tail not in ("PARAMETER-VALUES", "REFERENCE-VALUES"):
        bundle = extract_ecuc_container_bundle(file_path, node_path)
        if bundle and bundle.get("properties"):
            return bundle

    sub = load_subtree(file_path, node_path, depth=1)
    node = sub.get("node")
    if not node and tail in ("PARAMETER-VALUES", "REFERENCE-VALUES"):
        rows = extract_value_container_rows(file_path, node_path)
        if not rows:
            parts = node_path.replace("\\", "/").strip("/").split("/")
            if len(parts) >= 2:
                rows = extract_value_container_rows(file_path, f"{parts[-2]}/{parts[-1]}")
        if rows:
            return {
                "path": node_path,
                "tag": tail,
                "properties": [
                    {"key": "_param_table", "param_rows": rows, "readonly": True},
                    {"key": "개수", "value": str(len(rows)), "readonly": True},
                ],
                "node": None,
                "param_row_count": len(rows),
            }
    if not node:
        return {"properties": [], "node": None}
    tag = node.get("tag") or ""
    props: list[dict[str, Any]] = []
    if tag in ("PARAMETER-VALUES", "REFERENCE-VALUES") or tail in (
        "PARAMETER-VALUES",
        "REFERENCE-VALUES",
    ):
        rows = extract_value_container_rows(file_path, node_path)
        if not rows:
            parts = node_path.replace("\\", "/").strip("/").split("/")
            if len(parts) >= 2:
                fallback = f"{parts[-2]}/{parts[-1]}"
                rows = extract_value_container_rows(file_path, fallback)
        if rows:
            props.append(
                {
                    "key": "_param_table",
                    "param_rows": rows,
                    "readonly": True,
                }
            )
            props.append(
                {
                    "key": "개수",
                    "value": str(len(rows)),
                    "readonly": True,
                }
            )
            return {
                "path": node_path,
                "tag": tag,
                "properties": props,
                "node": node,
                "param_row_count": len(rows),
            }

    if node.get("name"):
        props.append({"key": "SHORT-NAME", "value": node["name"], "readonly": False})
    if node.get("text"):
        props.append({"key": node["tag"], "value": node["text"], "readonly": True})
    for k, v in (node.get("attrs") or {}).items():
        props.append({"key": k, "value": v, "readonly": True})
    for ch in node.get("children") or []:
        if ch.get("text"):
            ctag = ch.get("tag", "")
            is_ref = ctag.endswith("-REF") or ctag == "DEFINITION-REF"
            props.append(
                {
                    "key": ctag,
                    "value": ch["text"],
                    "readonly": ch.get("is_meta", False),
                    "is_ref": is_ref,
                    "dest": (ch.get("attrs") or {}).get("DEST"),
                }
            )
    return {"path": node_path, "tag": tag, "properties": props, "node": node}
