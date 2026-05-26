import { profileBadge } from "./profiles/registry.js";
import { captureScroll, restoreScroll } from "./scroll-state.js";

export class FileTreePanel {
  constructor(container, { onSelect, scrollEl } = {}) {
    this.container = container;
    this.scrollEl = scrollEl || container;
    this.onSelect = onSelect;
    this.files = [];
    this.filter = "";
    this.selectedPath = null;
    this.expandedFolders = new Set();
    this.allFoldersExpanded = true;
  }

  setFiles(files) {
    this.files = files || [];
    this._initExpandedFolders();
    this.render({ preserveScroll: false });
  }

  setFilter(text) {
    this.filter = (text || "").toLowerCase();
    this.render({ preserveScroll: true });
  }

  expandAll() {
    const folders = this._collectFolderPaths(this._filteredFiles());
    this.expandedFolders = new Set(folders);
    this.allFoldersExpanded = true;
    this.render({ preserveScroll: true });
  }

  collapseAll() {
    this.expandedFolders.clear();
    this.allFoldersExpanded = false;
    this.render({ preserveScroll: true });
  }

  _filteredFiles() {
    return this.files.filter((f) => {
      if (!this.filter) return true;
      return f.relative.toLowerCase().includes(this.filter);
    });
  }

  _initExpandedFolders() {
    const folders = this._collectFolderPaths(this.files);
    if (this.expandedFolders.size === 0 || this.allFoldersExpanded) {
      this.expandedFolders = new Set(folders);
      this.allFoldersExpanded = true;
    }
  }

  _collectFolderPaths(files) {
    const paths = new Set();
    for (const f of files) {
      const parts = f.relative.split("/");
      let acc = "";
      for (let i = 0; i < parts.length - 1; i++) {
        acc = acc ? `${acc}/${parts[i]}` : parts[i];
        paths.add(acc);
      }
    }
    return [...paths].sort();
  }

  _buildTree(files) {
    const root = { name: "", path: "", folders: new Map(), files: [] };
    for (const f of files) {
      const parts = f.relative.split("/");
      let node = root;
      let acc = "";
      for (let i = 0; i < parts.length - 1; i++) {
        acc = acc ? `${acc}/${parts[i]}` : parts[i];
        if (!node.folders.has(parts[i])) {
          node.folders.set(parts[i], {
            name: parts[i],
            path: acc,
            folders: new Map(),
            files: [],
          });
        }
        node = node.folders.get(parts[i]);
      }
      node.files.push(f);
    }
    return root;
  }

  render({ preserveScroll = true } = {}) {
    const scrollState = preserveScroll
      ? captureScroll(this.scrollEl, { anchorSelector: ".tree-row.selected" })
      : null;

    const filtered = this._filteredFiles();
    const tree = this._buildTree(filtered);

    let html = '<ul class="file-tree">';
    if (filtered.length === 0) {
      html += `<li class="empty-state"><p>ARXML 파일 없음</p></li>`;
    } else {
      html += this._renderNode(tree, 0);
    }
    html += "</ul>";
    this.container.innerHTML = html;
    this._bindEvents();

    if (scrollState) {
      restoreScroll(this.scrollEl, scrollState);
    }
  }

  _renderNode(node, depth) {
    let html = "";
    const folderEntries = [...node.folders.entries()].sort((a, b) =>
      a[0].localeCompare(b[0])
    );
    for (const [, folder] of folderEntries) {
      const expanded = this.expandedFolders.has(folder.path);
      const indent = depth * 14;
      html += `<li class="folder-node" data-folder-li="${escapeAttr(folder.path)}">`;
      html += `<div class="tree-row folder-row" data-folder="${escapeAttr(folder.path)}" style="padding-left:${8 + indent}px">
        <button type="button" class="expand-btn" aria-label="toggle">${expanded ? "▼" : "▶"}</button>
        <span class="tree-icon">📁</span>
        <span class="tree-label">${escapeHtml(folder.name)}</span>
      </div>`;
      if (expanded) {
        html += '<ul class="file-tree">';
        html += this._renderNode(folder, depth + 1);
        for (const f of folder.files.sort((a, b) => a.name.localeCompare(b.name))) {
          html += this._renderFileRow(f, depth + 1);
        }
        html += "</ul>";
      }
      html += "</li>";
    }
    if (depth === 0) {
      for (const f of node.files.sort((a, b) => a.name.localeCompare(b.name))) {
        html += this._renderFileRow(f, 0);
      }
    }
    return html;
  }

  _renderFileRow(f, depth) {
    const sel = f.path === this.selectedPath ? " selected" : "";
    const indent = depth * 14;
    const badge = f.editable
      ? '<span class="badge badge-ed">편집</span>'
      : '<span class="badge badge-ro">읽기</span>';
    const prof = `<span class="badge badge-profile">${escapeHtml(profileBadge(f.profile))}</span>`;
    return `<li><div class="tree-row${sel}" data-path="${escapeAttr(f.path)}" data-profile="${escapeAttr(f.profile)}" style="padding-left:${8 + indent}px">
      <span class="tree-indent"></span>
      <span class="tree-icon">📄</span>
      <span class="tree-label" title="${escapeAttr(f.relative)}">${escapeHtml(f.name)}</span>
      ${prof}${badge}
    </div></li>`;
  }

  _bindEvents() {
    this.container.querySelectorAll(".folder-row").forEach((row) => {
      row.addEventListener("click", (ev) => {
        if (ev.target.closest(".expand-btn") || ev.target.classList.contains("expand-btn")) {
          ev.stopPropagation();
        }
        const folderPath = row.dataset.folder;
        if (this.expandedFolders.has(folderPath)) {
          this.expandedFolders.delete(folderPath);
        } else {
          this.expandedFolders.add(folderPath);
        }
        this.render({ preserveScroll: true });
      });
    });

    this.container.querySelectorAll(".tree-row[data-path]").forEach((row) => {
      row.addEventListener("click", () => {
        const path = row.dataset.path;
        const profile = row.dataset.profile;
        this.selectedPath = path;
        this.container
          .querySelectorAll(".tree-row.selected")
          .forEach((r) => r.classList.remove("selected"));
        row.classList.add("selected");
        const file = this.files.find((f) => f.path === path);
        this.onSelect?.({ file, profile });
      });
    });
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s);
}
