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

  showProperties(data, { editable = false, fromFile, related = null } = {}) {
    const hasProps = data?.properties?.length;
    const hasRefTable = data?.properties?.some((p) => p.key === "_ref_table");
    const incomingOnly =
      related?.incoming?.length > 0 ? related.incoming : [];
    const hasIncoming = incomingOnly.length > 0;
    if (!hasProps && !hasIncoming) {
      this.container.innerHTML =
        '<div class="empty-state"><p>표시할 속성이 없습니다.</p></div>';
      return;
    }

    const src = fromFile || this.currentFile?.path;
    const title =
      data?.node?.name ||
      data?.properties?.find((p) => p.key === "SHORT-NAME")?.value ||
      data?.tag ||
      related?.name ||
      "Node";
    let html = `<div class="section-title">${esc(title)}</div>`;
    html += `<div class="prop-list">`;
    for (const p of data?.properties || []) {
      if (p.key === "_param_table" && Array.isArray(p.param_rows)) {
        html += `</div>${renderKeyValueTable("Parameter", "Value", p.param_rows, src)}<div class="prop-list">`;
        continue;
      }
      if (p.key === "_ref_table" && Array.isArray(p.ref_rows)) {
        html += `</div>${renderKeyValueTable("이 컨테이너 → 연결", "대상", p.ref_rows, src)}<div class="prop-list">`;
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
    if (data?.path) {
      html += `<div class="section-title">경로</div><div class="prop-list"><div class="prop-row"><span class="prop-key">논리 경로</span><span class="prop-value" style="font-size:11px">${esc(data.path)}</span></div></div>`;
    }
    if (hasIncoming) {
      html += renderIncomingSection(incomingOnly, src, {
        autosarPath: related?.autosar_path,
      });
    } else if (
      related &&
      !hasRefTable &&
      related.outgoing_count === 0 &&
      data?.node?.tag === "ECUC-CONTAINER-VALUE"
    ) {
      html += `<p class="viewer-hint">이 컨테이너에는 직접 REF가 없습니다. 연결은 하위 컨테이너(예: defaultSession)를 선택하세요.</p>`;
    }
    this.container.innerHTML = html;
    this._bindRefLinks();
    this._bindIncomingHits();
  }

  _bindIncomingHits() {
    this.container.querySelectorAll(".incoming-hit[data-file]").forEach((row) => {
      row.style.cursor = "pointer";
      row.addEventListener("click", (e) => {
        if (e.target.closest(".ref-link")) return;
        e.preventDefault();
        this.onIncomingOpen?.({
          file: row.dataset.file,
          path: row.dataset.path,
          name: row.dataset.name,
        });
      });
    });
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

function renderIncomingSection(rows, fromFile, { autosarPath } = {}) {
  const pathHint = autosarPath
    ? `<p class="viewer-hint muted">대상 경로: ${esc(autosarPath)}</p>`
    : "";
  let body = "";
  for (const r of rows) {
    const fromLabel = esc(r.from_name || r.from_path?.split("/").pop() || "?");
    const fromFileLabel = esc((r.file || "").split("/").pop() || r.file || "");
    body += `<tr class="incoming-hit" data-file="${escAttr(
      r.file || ""
    )}" data-path="${escAttr(r.from_path || "")}" data-name="${escAttr(
      r.from_name || ""
    )}">
      <td><span class="incoming-from">${fromLabel}</span><br/><span class="muted">${fromFileLabel}</span></td>
      <td>${esc(r.ref_tag || "REF")}</td>
    </tr>`;
  }
  return `${pathHint}
    <div class="section-title section-sub">← 이 컨테이너를 참조 (${rows.length})</div>
    <table class="data-table data-table-compact">
      <thead><tr><th>출처 컨테이너</th><th>REF 종류</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
    <p class="viewer-hint">행 클릭 시 참조한 쪽으로 이동</p>`;
}

function renderKeyValueTable(colA, colB, rows, fromFile) {
  let body = "";
  for (const r of rows) {
    const k = esc(r.name || "");
    let v = esc(r.value || "");
    if (r.value_is_ref && r.value?.startsWith("/")) {
      v = refLinkHtml(r.value, { fromFile });
    }
    body += `<tr><td>${k}</td><td>${v}</td></tr>`;
  }
  return `<table class="data-table">
    <thead><tr><th>${esc(colA)}</th><th>${esc(colB)}</th></tr></thead>
    <tbody>${body}</tbody>
  </table>`;
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
