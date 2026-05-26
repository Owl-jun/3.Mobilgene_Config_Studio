import { refLinkHtml } from "./ref-nav.js";

/**
 * Property panel — REF links for cross-navigation.
 */

export class PropertyPanel {
  constructor(container, { onRefClick } = {}) {
    this.container = container;
    this.scrollEl = container;
    this.onRefClick = onRefClick;
    this.currentFile = null;
    this.editable = false;
  }

  clear() {
    this.container.innerHTML =
      '<div class="empty-state"><h3>속성</h3><p>트리 또는 테이블에서 항목을 선택하세요.</p></div>';
  }

  showFileInfo(file) {
    this.currentFile = file;
    this.editable = file?.editable ?? false;
    const sizeKb = file ? (file.size_bytes / 1024).toFixed(1) : "0";
    this.container.innerHTML = `
      <div class="section-title">파일 정보</div>
      <div class="prop-list">
        <div class="prop-row"><span class="prop-key">경로</span><span class="prop-value">${esc(file.relative)}</span></div>
        <div class="prop-row"><span class="prop-key">프로필</span><span class="prop-value">${esc(file.profile)}</span></div>
        <div class="prop-row"><span class="prop-key">크기</span><span class="prop-value">${sizeKb} KB</span></div>
        <div class="prop-row"><span class="prop-key">편집</span><span class="prop-value">${file.editable ? "허용" : "읽기 전용"}</span></div>
      </div>
      <p class="viewer-hint">Mobilgene 보조 뷰어 — REF 클릭으로 정의 위치로 이동, 관계 그래프 탭에서 의존성 확인</p>`;
  }

  showProperties(data, { editable = false, fromFile } = {}) {
    if (!data || !data.properties?.length) {
      this.container.innerHTML =
        '<div class="empty-state"><p>표시할 속성이 없습니다.</p></div>';
      return;
    }

    const src = fromFile || this.currentFile?.path;
    let html = `<div class="section-title">${esc(data.tag || "Node")}</div><div class="prop-list">`;
    for (const p of data.properties) {
      if (p.key === "_param_table" && Array.isArray(p.param_rows)) {
        let rows = "";
        for (const r of p.param_rows) {
          const k = esc(r.name || "");
          let v = esc(r.value || "");
          if (r.value_is_ref && r.value?.startsWith("/")) {
            v = refLinkHtml(r.value, { fromFile: src });
          }
          rows += `<tr><td>${k}</td><td>${v}</td></tr>`;
        }
        html += `</div>
          <table class="data-table">
            <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
          <div class="prop-list">`;
        continue;
      }
      const ro = p.readonly || !editable;
      let valHtml;
      if (p.is_ref && p.value?.startsWith("/")) {
        valHtml = `<span class="prop-value">${refLinkHtml(p.value, { fromFile: src })}</span>`;
      } else if (ro) {
        valHtml = `<span class="prop-value prop-readonly">${esc(p.value)}</span>`;
      } else {
        valHtml = `<span class="prop-value"><input type="text" value="${escAttr(p.value)}" disabled/></span>`;
      }
      html += `<div class="prop-row"><span class="prop-key">${esc(p.key)}</span>${valHtml}</div>`;
    }
    html += "</div>";
    if (data.path) {
      html += `<div class="section-title">경로</div><div class="prop-list"><div class="prop-row"><span class="prop-key">논리 경로</span><span class="prop-value" style="font-size:11px">${esc(data.path)}</span></div></div>`;
    }
    this.container.innerHTML = html;
    this._bindRefLinks();
  }

  showMappingRow(row, { editable = false, fromFile } = {}) {
    const src = fromFile || this.currentFile?.path;
    this.container.innerHTML = `
      <div class="section-title">I-PDU Mapping</div>
      <div class="prop-list">
        <div class="prop-row"><span class="prop-key">Source</span><span class="prop-value">${row.source_ref ? refLinkHtml(row.source_ref, { fromFile: src }) : esc(row.source)}</span></div>
        <div class="prop-row"><span class="prop-key">Target</span><span class="prop-value">${row.target_ref ? refLinkHtml(row.target_ref, { fromFile: src }) : esc(row.target)}</span></div>
        ${row.source_dest ? `<div class="prop-row"><span class="prop-key">Source DEST</span><span class="prop-value">${esc(row.source_dest)}</span></div>` : ""}
        ${row.target_dest ? `<div class="prop-row"><span class="prop-key">Target DEST</span><span class="prop-value">${esc(row.target_dest)}</span></div>` : ""}
      </div>`;
    this._bindRefLinks();
  }

  showContainer(container, { editable = false, fromFile } = {}) {
    const src = fromFile || this.currentFile?.path;
    let paramsHtml = "";
    for (const p of container.parameters || []) {
      const defRef = p.definition_path?.startsWith("/")
        ? refLinkHtml(p.definition_path, { fromFile: src })
        : "";
      paramsHtml += `<div class="prop-row">
        <span class="prop-key">${esc(p.definition)}</span>
        <span class="prop-value">${defRef}<span class="param-val">${esc(p.value)}</span></span>
      </div>`;
    }
    this.container.innerHTML = `
      <div class="section-title">${esc(container.name)}</div>
      <div class="stats-grid">
        <div class="stat-card"><div class="label">Parameters</div><div class="value">${container.parameter_count}</div></div>
        <div class="stat-card"><div class="label">Sub-containers</div><div class="value">${container.has_sub_containers ? "Yes" : "No"}</div></div>
      </div>
      <div class="section-title">Parameters</div>
      <div class="prop-list">${paramsHtml || '<p class="empty-state">없음</p>'}</div>`;
    this._bindRefLinks();
  }

  _bindRefLinks() {
    this.container.querySelectorAll(".ref-link[data-ref]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
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

function escAttr(s) {
  return esc(s).replace(/"/g, "&quot;");
}
