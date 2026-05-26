# -*- coding: utf-8 -*-
"""
Development HTTP server for Mobilgene Config Studio UI.
Serves static UI and REST API mirroring future Tauri IPC commands.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Allow import from same directory
sys.path.insert(0, str(Path(__file__).parent))
import app_paths  # noqa: E402
import arxml_parser as ap  # noqa: E402
import ref_index as ri  # noqa: E402
import related_context as rc  # noqa: E402
import module_graph as mg  # noqa: E402
import workspace_browser as wb  # noqa: E402

ROOT = app_paths.get_resource_root()
UI_DIR = app_paths.get_ui_dir()
DEFAULT_PORT = 8765

_workspace: Path | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(path))
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _resolve_file(self, file_param: str) -> Path | None:
        p = Path(file_param)
        if not p.is_absolute() and _workspace:
            p = _workspace / file_param
        p = p.resolve()
        if _workspace:
            try:
                p.relative_to(_workspace.resolve())
            except ValueError:
                return None
        return p if p.is_file() else None

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            self._api_get(path, qs)
            return

        # Static UI
        rel = path.lstrip("/") or "index.html"
        target = UI_DIR / rel
        if target.is_dir():
            target = target / "index.html"
        if not str(target.resolve()).startswith(str(UI_DIR.resolve())):
            self.send_error(403)
            return
        self._send_file(target)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(404)
            return
        body = self._read_body()
        self._api_post(parsed.path, body)

    def _api_get(self, path: str, qs: dict) -> None:
        global _workspace

        if path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "workspace": str(_workspace) if _workspace else None,
                    "api_version": 2,
                    "features": [
                        "module_graph",
                        "resolve_ref",
                        "ref_index",
                        "browse",
                        "search",
                        "related",
                        "resolve_tree",
                    ],
                }
            )
            return

        if path == "/api/workspace":
            if not _workspace:
                self._send_json({"error": "no_workspace"}, 400)
                return
            self._send_json(ap.scan_workspace(_workspace))
            return

        if path == "/api/index":
            file_p = qs.get("file", [None])[0]
            if not file_p:
                self._send_json({"error": "file_required"}, 400)
                return
            fp = self._resolve_file(file_p)
            if not fp:
                self._send_json({"error": "invalid_file"}, 403)
                return
            depth = int(qs.get("depth", ["2"])[0])
            self._send_json(ap.build_index(fp, max_depth=depth))
            return

        if path == "/api/subtree":
            file_p = qs.get("file", [None])[0]
            node_path = qs.get("path", ["/"])[0]
            depth = int(qs.get("depth", ["2"])[0])
            fp = self._resolve_file(file_p) if file_p else None
            if not fp:
                self._send_json({"error": "invalid_file"}, 403)
                return
            self._send_json(ap.load_subtree(fp, node_path, depth=depth))
            return

        if path == "/api/gateway":
            file_p = qs.get("file", [None])[0]
            fp = self._resolve_file(file_p) if file_p else None
            if not fp:
                self._send_json({"error": "invalid_file"}, 403)
                return
            self._send_json(ap.extract_gateway_mappings(fp))
            return

        if path == "/api/ecuc":
            file_p = qs.get("file", [None])[0]
            fp = self._resolve_file(file_p) if file_p else None
            if not fp:
                self._send_json({"error": "invalid_file"}, 403)
                return
            limit = int(qs.get("limit", ["200"])[0])
            self._send_json(ap.extract_ecuc_summary(fp, max_containers=limit))
            return

        if path == "/api/properties":
            file_p = qs.get("file", [None])[0]
            node_path = qs.get("path", ["/"])[0]
            fp = self._resolve_file(file_p) if file_p else None
            if not fp:
                self._send_json({"error": "invalid_file"}, 403)
                return
            self._send_json(ap.get_node_properties(fp, node_path))
            return

        if path == "/api/ref_index":
            if not _workspace:
                self._send_json({"error": "no_workspace"}, 400)
                return
            rebuild = qs.get("rebuild", ["0"])[0] == "1"
            idx = ri.get_index(_workspace, rebuild=rebuild)
            self._send_json(idx.stats())
            return

        if path == "/api/resolve_ref":
            if not _workspace:
                self._send_json({"error": "no_workspace"}, 400)
                return
            ref = qs.get("ref", [""])[0]
            from_file = qs.get("from_file", [None])[0]
            rebuild = qs.get("rebuild", ["0"])[0] == "1"
            self._send_json(
                ri.resolve_ref(_workspace, ref, from_file=from_file, rebuild=rebuild)
            )
            return

        if path == "/api/search":
            if not _workspace:
                self._send_json({"error": "no_workspace"}, 400)
                return
            q = qs.get("q", [""])[0]
            limit = int(qs.get("limit", ["40"])[0])
            rebuild = qs.get("rebuild", ["0"])[0] == "1"
            if rebuild:
                ri.get_index(_workspace, rebuild=True)
            self._send_json(rc.search_workspace(_workspace, q, limit=limit))
            return

        if path == "/api/resolve_tree":
            if not _workspace:
                self._send_json({"error": "no_workspace"}, 400)
                return
            file_p = qs.get("file", [""])[0]
            node_path = qs.get("path", [""])[0]
            node_name = qs.get("name", [None])[0]
            fp = self._resolve_file(file_p) if file_p else None
            if not fp:
                self._send_json({"error": "invalid_file"}, 403)
                return
            tree_path = rc.resolve_tree_path(fp, node_path, node_name=node_name)
            self._send_json(
                {
                    "file": file_p,
                    "path": node_path,
                    "name": node_name,
                    "tree_path": tree_path,
                    "resolved": tree_path is not None,
                }
            )
            return

        if path == "/api/related":
            if not _workspace:
                self._send_json({"error": "no_workspace"}, 400)
                return
            file_p = qs.get("file", [""])[0]
            node_path = qs.get("path", [""])[0]
            node_name = qs.get("name", [None])[0]
            limit = int(qs.get("limit", ["35"])[0])
            rebuild = qs.get("rebuild", ["0"])[0] == "1"
            if rebuild:
                ri.get_index(_workspace, rebuild=True)
            self._send_json(
                rc.find_related(
                    _workspace,
                    file_p,
                    node_path,
                    node_name=node_name,
                    limit=limit,
                )
            )
            return

        if path in ("/api/graph", "/api/module_graph"):
            self._api_module_graph(qs)
            return

        if path == "/api/browse":
            path_arg = qs.get("path", [None])[0]
            if path_arg:
                path_arg = urllib.parse.unquote(path_arg)
            self._send_json(wb.list_directory(path_arg))
            return

        self._send_json({"error": "not_found"}, 404)

    def _api_module_graph(self, qs: dict) -> None:
        global _workspace
        if not _workspace:
            self._send_json({"error": "no_workspace"}, 400)
            return
        file_p = qs.get("file", [None])[0]
        module = qs.get("module", [None])[0]
        sel_mod = module
        sel_file = file_p
        if file_p:
            fp = self._resolve_file(file_p)
            if fp:
                sel_file = str(fp)
            else:
                # 그래프는 파일 경로 검증 실패해도 모듈명으로 하이라이트 가능
                sel_file = file_p.replace("\\", "/")
        if not sel_mod and sel_file:
            sel_mod = mg.module_from_file(_workspace, sel_file)
        self._send_json(
            mg.build_module_graph(
                _workspace,
                selected_module=sel_mod,
                selected_file=sel_file,
            )
        )

    def _api_post(self, path: str, body: dict) -> None:
        global _workspace

        if path == "/api/open_workspace":
            ws = body.get("path", "")
            if not ws:
                self._send_json({"error": "path_required"}, 400)
                return
            p = Path(ws).resolve()
            if not p.is_dir():
                self._send_json({"error": "not_a_directory"}, 400)
                return
            _workspace = p
            data = ap.scan_workspace(p)
            data["opened"] = True
            # REF 인덱스: 동일 워크스페이스 재오픈 시 캐시 재사용 (첫 오픈만 전체 스캔)
            ref_stats = ri.get_index(p, rebuild=False).stats()
            data["ref_index"] = ref_stats
            mg._graph_cache.pop(str(p.resolve()), None)
            mg._file_text_cache.clear()
            data["module_graph"] = len(mg.discover_modules(p))
            self._send_json(data)
            return

        if path == "/api/browse_pick":
            initial = body.get("path") or (
                str(_workspace) if _workspace else None
            )
            chosen = wb.pick_folder_native(initial)
            if not chosen:
                self._send_json({"cancelled": True})
                return
            self._send_json({"path": chosen})
            return

        self._send_json({"error": "not_found"}, 404)


def main() -> None:
    port = int(os.environ.get("MCS_PORT", DEFAULT_PORT))
    ws = os.environ.get("MCS_WORKSPACE")
    global _workspace
    if ws:
        _workspace = Path(ws).resolve()

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Mobilgene Config Studio dev server: http://127.0.0.1:{port}")
    if _workspace:
        print(f"Workspace: {_workspace}")
    print(f"UI root: {UI_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()
