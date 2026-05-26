import { Api } from "./api.js";
import { getProfileMeta } from "./profiles/registry.js";
import { captureScroll, restoreScroll } from "./scroll-state.js";
import { refLinkHtml } from "./ref-nav.js";
import { GraphView } from "./graph-view.js";

/**
 * Center panel — profile-specific views with shared tree fallback.
 */
export class ConfigViewPanel {
  constructor(container, toolbarEl, { onNodeSelect, onRowSelect, onRefClick, scrollEl } = {}) {
    this.container = container;
    this.scrollEl = scrollEl || container;
    this.toolbarEl = toolbarEl;
    this.onNodeSelect = onNodeSelect;
    this.onRowSelect = onRowSelect;
    this.onRefClick = onRefClick;
    this._graphView = new GraphView(this.container, {
      onModuleClick: (info) => this.onModuleClick?.(info),
    });
    this.onModuleClick = null;
    this.currentFile = null;
    this.currentProfile = "generic";
    this.centerMode = "structure"; // structure | detail
    this.activeView = "tree";
    this.expandedPaths = new Set();
    this.treeRoot = null;
    this.selectedNodePath = null;
    this._treeUl = null;
  }

  async loadFile(file) {
    this.currentFile = file;
    this.currentProfile = file.profile || "generic";
    this.expandedPaths.clear();
    this.treeRoot = null;
    this.selectedNodePath = null;
    const meta = getProfileMeta(this.currentProfile);
    if (this.centerMode === "detail") {
      if (!meta.views.includes(this.activeView)) {
        this.activeView = meta.defaultView;
      }
    }
    this._renderToolbar(meta);
    await this._renderView({ preserveScroll: false });
  }

  setCenterMode(mode) {
    this.centerMode = mode;
    if (mode === "structure") {
      this.toolbarEl.innerHTML = "";
      this.showStructureGraph();
    } else if (this.currentFile) {
      this._renderToolbar(getProfileMeta(this.currentProfile));
      this._renderView({ preserveScroll: false });
    } else {
      this.toolbarEl.innerHTML = "";
      this.container.innerHTML =
        '<div class="empty-state"><h3>파일 상세</h3><p>왼쪽에서 ARXML 파일을 선택하세요.</p></div>';
    }
  }

  async showStructureGraph(file = null) {
    this.centerMode = "structure";
    this.toolbarEl.innerHTML = "";
    const f = file || this.currentFile;
    await this._graphView.render(f);
  }

  clear() {
    this.currentFile = null;
    this.treeRoot = null;
    this.centerMode = "structure";
    this.toolbarEl.innerHTML = "";
    this.container.innerHTML =
      '<div class="empty-state"><h3>구조 맵</h3><p>워크스페이스를 연면 BSW 모듈 결합 구조가 표시됩니다.</p></div>';
  }

  expandAllTree() {
    if (!this.treeRoot || this.activeView !== "tree") return;
    for (const path of this._collectExpandablePaths(this.treeRoot)) {
      this.expandedPaths.add(path);
    }
    this._refreshTree({ preserveScroll: true });
  }

  collapseAllTree() {
    this.expandedPaths.clear();
    this._refreshTree({ preserveScroll: true });
  }

  _collectExpandablePaths(node, paths = []) {
    if (!node || node.is_meta) return paths;
    const hasKids =
      node.has_children || (node.children && node.children.length > 0);
    if (hasKids && node.path) {
      paths.push(node.path);
    }
    for (const c of node.children || []) {
      this._collectExpandablePaths(c, paths);
    }
    return paths;
  }

  _renderToolbar(meta) {
    if (this.centerMode !== "detail") {
      this.toolbarEl.innerHTML = "";
      return;
    }
    const views = meta.views || ["tree"];
    const hasTree = views.includes("tree");
    const showTreeActions = hasTree && this.activeView === "tree";
    let tabs = "";
    for (const v of views) {
      const active = v === this.activeView ? " active" : "";
      const label =
        v === "matrix"
          ? "매핑 테이블"
          : v === "containers"
            ? "컨테이너"
            : "XML 트리";
      tabs += `<button type="button" class="view-tab${active}" data-view="${v}">${label}</button>`;
    }
    const treeActions = showTreeActions
      ? `<div class="tree-actions">
          <button type="button" class="btn-tree-action" data-action="expand-all" title="전체 펼치기">펼치기</button>
          <button type="button" class="btn-tree-action" data-action="collapse-all" title="전체 접기">접기</button>
        </div>`
      : "";

    this.toolbarEl.innerHTML = `
      <span class="profile-tag">${meta.label}</span>
      <span class="toolbar-filename">${esc(this.currentFile?.name || "")}</span>
      ${treeActions}
      <div class="view-tabs">${tabs}</div>`;

    this.toolbarEl.querySelectorAll(".view-tab").forEach((btn) => {
      btn.addEventListener("click", async () => {
        this.activeView = btn.dataset.view;
        this.toolbarEl
          .querySelectorAll(".view-tab")
          .forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        await this._renderView({ preserveScroll: false });
        this._renderToolbar(getProfileMeta(this.currentProfile));
      });
    });

    this.toolbarEl.querySelector('[data-action="expand-all"]')?.addEventListener(
      "click",
      () => this.expandAllTree()
    );
    this.toolbarEl.querySelector('[data-action="collapse-all"]')?.addEventListener(
      "click",
      () => this.collapseAllTree()
    );
  }

  async _renderView({ preserveScroll = false } = {}) {
    if (this.centerMode === "structure") {
      await this.showStructureGraph();
      return;
    }
    if (!this.currentFile) return;
    const scrollState = preserveScroll
      ? captureScroll(this.scrollEl, { anchorSelector: ".xml-tree .tree-row.selected" })
      : null;

    const loading = document.createElement("div");
    loading.className = "empty-state";
    loading.innerHTML = "<p>로딩 중...</p>";
    if (!preserveScroll) {
      this.container.innerHTML = "";
      this.container.appendChild(loading);
    }

    try {
      if (this.currentProfile === "gateway" && this.activeView === "matrix") {
        await this._renderGatewayMatrix({ preserveScroll, scrollState });
      } else if (
        this.currentProfile === "ecuc" &&
        this.activeView === "containers"
      ) {
        await this._renderEcucContainers({ preserveScroll, scrollState });
      } else {
        await this._renderXmlTree({ preserveScroll, scrollState });
      }
    } catch (e) {
      this.container.innerHTML = `<div class="empty-state"><h3>오류</h3><p>${esc(e.message)}</p></div>`;
    }
  }

  async _renderGatewayMatrix({ preserveScroll, scrollState } = {}) {
    const data = await Api.gateway(this.currentFile.path);
    const gateways = data.gateways || [];
    if (!gateways.length) {
      this.container.innerHTML =
        '<div class="empty-state"><p>Gateway 매핑이 없습니다.</p></div>';
      return;
    }

    let html = `<div class="stats-grid" style="margin-bottom:0">
      <div class="stat-card"><div class="label">Gateways</div><div class="value">${gateways.length}</div></div>
      <div class="stat-card"><div class="label">Mappings</div><div class="value">${data.total_mappings}</div></div>
    </div>`;

    for (const gw of gateways) {
      html += `<div class="section-title" style="margin-top:12px">${esc(gw.name)} (${gw.mapping_count})</div>`;
      html += `<table class="data-table"><thead><tr>
        <th>Source I-PDU</th><th>Target I-PDU</th></tr></thead><tbody>`;
      const from = this.currentFile.path;
      for (const m of gw.mappings) {
        const src = m.source_ref
          ? refLinkHtml(m.source_ref, { fromFile: from })
          : esc(m.source);
        const tgt = m.target_ref
          ? refLinkHtml(m.target_ref, { fromFile: from })
          : esc(m.target);
        html += `<tr data-mapping='${escAttr(JSON.stringify(m))}'>
          <td>${src}</td>
          <td>${tgt}</td></tr>`;
      }
      html += "</tbody></table>";
    }
    this._setContainerHtml(html, { preserveScroll, scrollState });
    this._bindMatrixRows();
    this._bindRefLinks();
  }

  _bindMatrixRows() {
    this.container.querySelectorAll("tr[data-mapping]").forEach((tr) => {
      tr.addEventListener("click", () => {
        this.container
          .querySelectorAll("tr.selected")
          .forEach((r) => r.classList.remove("selected"));
        tr.classList.add("selected");
        const row = JSON.parse(tr.dataset.mapping);
        this.onRowSelect?.({ type: "gateway_mapping", row });
      });
    });
  }

  async _renderEcucContainers({ preserveScroll, scrollState } = {}) {
    const data = await Api.ecuc(this.currentFile.path);
    const containers = data.containers || [];
    let html = `<div class="stats-grid">
      <div class="stat-card"><div class="label">Module</div><div class="value stat-value-sm">${esc(data.module || "-")}</div></div>
      <div class="stat-card"><div class="label">Containers</div><div class="value">${data.container_count}${data.truncated ? "+" : ""}</div></div>
    </div>`;
    if (data.truncated) {
      html += `<p class="tree-hint">대용량 파일 — 상위 ${containers.length}개 컨테이너만 표시</p>`;
    }
    html += `<table class="data-table"><thead><tr>
      <th>Container</th><th>Parameters</th><th>Sub</th></tr></thead><tbody>`;
    for (const c of containers) {
      html += `<tr data-container='${escAttr(JSON.stringify(c))}'>
        <td>${esc(c.name)}</td>
        <td>${c.parameter_count}</td>
        <td>${c.has_sub_containers ? "Y" : "-"}</td></tr>`;
    }
    html += "</tbody></table>";
    this._setContainerHtml(html, { preserveScroll, scrollState });
    this.container.querySelectorAll("tr[data-container]").forEach((tr) => {
      tr.addEventListener("click", () => {
        this.container
          .querySelectorAll("tr.selected")
          .forEach((r) => r.classList.remove("selected"));
        tr.classList.add("selected");
        const row = JSON.parse(tr.dataset.container);
        this.onRowSelect?.({ type: "ecuc_container", row });
      });
    });
  }

  _setContainerHtml(html, { preserveScroll, scrollState }) {
    if (preserveScroll && scrollState) {
      this.container.innerHTML = html;
      restoreScroll(this.scrollEl, scrollState);
    } else {
      this.container.innerHTML = html;
    }
  }

  async _renderXmlTree({ preserveScroll = false, scrollState = null } = {}) {
    if (!this.treeRoot) {
      const data = await Api.index(this.currentFile.path, 3);
      this.treeRoot = data.root;
      this._treeStats = data.stats || {};
    }

    const stats = this._treeStats || {};
    if (!preserveScroll) {
      this.container.innerHTML = `
        <div class="config-tree-wrap">
          <div class="stats-grid">
            <div class="stat-card"><div class="label">Indexed nodes</div><div class="value">${stats.nodes || "?"}</div></div>
            <div class="stat-card"><div class="label">Depth</div><div class="value">${stats.max_depth ?? "-"}</div></div>
          </div>
          <ul class="file-tree xml-tree" id="xml-tree-root"></ul>
        </div>`;
      this._treeUl = this.container.querySelector("#xml-tree-root");
    } else if (!this._treeUl) {
      this._treeUl = this.container.querySelector("#xml-tree-root");
    }

    if (!scrollState && preserveScroll) {
      scrollState = captureScroll(this.scrollEl, {
        anchorSelector: ".xml-tree .tree-row.selected",
      });
    }

    this._refreshTree({ preserveScroll, scrollState });
  }

  _refreshTree({ preserveScroll = true, scrollState = null } = {}) {
    if (!this._treeUl) return;
    if (!scrollState && preserveScroll) {
      scrollState = captureScroll(this.scrollEl, {
        anchorSelector: ".xml-tree .tree-row.selected",
      });
    }

    this._treeUl.innerHTML = "";
    const nodes = this.treeRoot?.children || [this.treeRoot].filter(Boolean);
    this._appendTreeNodes(this._treeUl, nodes, 0);

    if (this.selectedNodePath) {
      const sel = this._treeUl.querySelector(
        `[data-path="${cssEscape(this.selectedNodePath)}"]`
      );
      sel?.classList.add("selected");
    }

    if (preserveScroll && scrollState) {
      restoreScroll(this.scrollEl, scrollState);
    }
    this._bindRefLinks();
  }

  _appendTreeNodes(parentUl, nodes, depth) {
    if (!nodes) return;
    for (const node of nodes) {
      if (!node || node.is_meta) continue;
      const li = document.createElement("li");
      const hasKids =
        node.has_children || (node.children && node.children.length > 0);
      const expanded = this.expandedPaths.has(node.path);
      const indent = depth * 14;
      const isSelected = this.selectedNodePath === node.path;

      const preview = paramPreview(node);
      li.innerHTML = `<div class="tree-row${isSelected ? " selected" : ""}" data-path="${escAttr(node.path)}" style="padding-left:${8 + indent}px">
        <button type="button" class="expand-btn" ${hasKids ? "" : "disabled"} aria-label="toggle">${hasKids ? (expanded ? "▼" : "▶") : "·"}</button>
        <span class="node-tag">${esc(node.tag)}</span>
        ${node.name ? `<span class="node-name">${esc(node.name)}</span>` : ""}
        ${preview ? `<span class="node-meta">${preview}</span>` : ""}
        ${node.text ? (node.tag?.endsWith("-REF") || node.tag === "DEFINITION-REF"
          ? `<span class="node-meta">${refLinkHtml(node.text, { fromFile: this.currentFile?.path })}</span>`
          : `<span class="node-meta">${esc(truncate(node.text, 48))}</span>`) : ""}
      </div>`;
      parentUl.appendChild(li);

      const row = li.querySelector(".tree-row");
      const expandBtn = li.querySelector(".expand-btn");

      expandBtn?.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (!hasKids) return;
        this._toggleNode(node, li, depth);
      });

      row.addEventListener("click", (ev) => {
        if (ev.target.closest(".expand-btn")) return;
        this._treeUl
          ?.querySelectorAll(".tree-row.selected")
          .forEach((r) => r.classList.remove("selected"));
        row.classList.add("selected");
        this.selectedNodePath = node.path;
        this.onNodeSelect?.({ path: node.path, node });
      });

      if (hasKids && expanded) {
        const childUl = document.createElement("ul");
        childUl.className = "file-tree";
        li.appendChild(childUl);
        if (node.children?.length) {
          this._appendTreeNodes(childUl, node.children, depth + 1);
        } else {
          this._lazyLoadChildren(childUl, node, depth + 1);
        }
      }
    }
  }

  async _toggleNode(node, li, depth) {
    const scrollState = captureScroll(this.scrollEl, {
      anchorSelector: ".xml-tree .tree-row.selected",
    });

    if (this.expandedPaths.has(node.path)) {
      this.expandedPaths.delete(node.path);
      li.querySelector(":scope > ul")?.remove();
      li.querySelector(".expand-btn").textContent = "▶";
    } else {
      this.expandedPaths.add(node.path);
      const btn = li.querySelector(".expand-btn");
      btn.textContent = "▼";
      let childUl = li.querySelector(":scope > ul");
      if (!childUl) {
        childUl = document.createElement("ul");
        childUl.className = "file-tree";
        li.appendChild(childUl);
        if (node.children?.length) {
          this._appendTreeNodes(childUl, node.children, depth + 1);
        } else {
          await this._lazyLoadChildren(childUl, node, depth + 1);
        }
      }
    }

    restoreScroll(this.scrollEl, scrollState);
  }

  async _lazyLoadChildren(childUl, node, depth) {
    childUl.innerHTML =
      '<li class="empty-state" style="padding:8px">로딩...</li>';
    const scrollState = captureScroll(this.scrollEl, {
      anchorSelector: ".xml-tree .tree-row.selected",
    });
    try {
      const sub = await Api.subtree(this.currentFile.path, node.path, 2);
      childUl.innerHTML = "";
      node.children = sub.node?.children || [];
      if (node.children.length) {
        this._appendTreeNodes(childUl, node.children, depth);
      } else {
        childUl.innerHTML =
          '<li style="padding:8px;color:var(--text-muted)">(empty)</li>';
      }
    } catch {
      childUl.innerHTML =
        '<li style="padding:8px;color:var(--danger)">로드 실패</li>';
    }
    restoreScroll(this.scrollEl, scrollState);
  }

  async focusPath(autosarPath) {
    if (!autosarPath || !this.currentFile) return;
    this.centerMode = "detail";
    const parts = autosarPath.split("/").filter(Boolean);
    let acc = "";
    for (const p of parts) {
      acc += `/${p}`;
      this.expandedPaths.add(acc);
    }
    this.selectedNodePath = autosarPath.startsWith("/")
      ? autosarPath
      : `/${autosarPath}`;

    if (this.activeView !== "tree") {
      this.activeView = "tree";
      this._renderToolbar(getProfileMeta(this.currentProfile));
    }
    await this._renderXmlTree({ preserveScroll: false });
    const row = this._treeUl?.querySelector(
      `[data-path="${cssEscape(this.selectedNodePath)}"]`
    );
    if (row) {
      row.classList.add("selected");
      row.scrollIntoView({ block: "center", behavior: "smooth" });
      const node = { path: this.selectedNodePath, tag: "", name: row.querySelector(".node-name")?.textContent };
      this.onNodeSelect?.({ path: this.selectedNodePath, node });
    }
  }

  async _selectPathInTree(path) {
    if (!path) return;
    this.centerMode = "detail";
    this.activeView = "tree";
    this._renderToolbar(getProfileMeta(this.currentProfile));
    await this.focusPath(path);
  }

  _bindRefLinks() {
    this.container.querySelectorAll(".ref-link[data-ref]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.onRefClick?.(btn.dataset.ref, btn.dataset.fromFile || this.currentFile?.path);
      });
    });
  }
}

function esc(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function paramPreview(node) {
  const tag = node?.tag || "";
  if (tag === "PARAMETER-VALUES" || tag === "REFERENCE-VALUES") {
    const n = node.children?.length || 0;
    return n > 0 ? `${n} params` : "";
  }
  if (!tag.startsWith("ECUC-") || !tag.endsWith("-PARAM-VALUE")) return "";
  const def = node.children?.find((c) => c.tag === "DEFINITION-REF" && c.text)?.text;
  const val =
    node.children?.find((c) => c.tag === "VALUE" && c.text)?.text ||
    node.children?.find((c) => c.tag === "VALUE-REF" && c.text)?.text;
  if (!def && !val) return "";
  const name = def ? def.split("/").pop() : "param";
  return `${esc(name)} = ${esc(val || "")}`;
}

function escAttr(s) {
  return esc(s).replace(/"/g, "&quot;");
}

function truncate(s, n) {
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function cssEscape(value) {
  if (typeof CSS !== "undefined" && CSS.escape) {
    return CSS.escape(value);
  }
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}
