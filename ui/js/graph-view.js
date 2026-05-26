import { Api } from "./api.js";

/**
 * AUTOSAR layered architecture map (reference-style layer table).
 */
export class GraphView {
  constructor(container, { onModuleClick } = {}) {
    this.container = container;
    this.onModuleClick = onModuleClick;
    this._data = null;
    this._activePath = "diag";
    this._showOther = false;
  }

  async render(file) {
    this.container.innerHTML =
      '<div class="empty-state"><p>구조 맵 로딩…</p></div>';
    try {
      const data = await Api.moduleGraph(file?.path, null);
      this._data = data;
      if (data.autosar?.active_path) {
        this._activePath = data.autosar.active_path;
      }
      this._draw(data);
    } catch (e) {
      const hint =
        e.message === "not_found"
          ? "개발 서버를 재시작해 주세요. (run-dev.ps1)"
          : e.message === "no_workspace"
            ? "먼저 워크스페이스를 열어 주세요."
            : e.message;
      this.container.innerHTML = `<div class="empty-state"><h3>구조 맵 오류</h3><p>${esc(hint)}</p></div>`;
    }
  }

  _draw(data) {
    const ar = data.autosar;
    if (!ar?.stacks?.length) {
      this.container.innerHTML =
        '<div class="empty-state"><p>레이어 데이터 없습니다. 서버를 재시작해 주세요.</p></div>';
      return;
    }

    const sel = data.selected_module;
    const paths = ar.paths || [];

    let html = `<div class="autosar-map">
      <div class="structure-toolbar">
        <span class="structure-title">AUTOSAR Layered Architecture</span>
        <span class="structure-meta">${data.module_count} BSW 모듈</span>
      </div>`;

    html += `<div class="path-legend">`;
    for (const p of paths) {
      const active = p.id === this._activePath ? " path-pill-active" : "";
      html += `<button type="button" class="path-pill${active}" data-path-id="${escAttr(p.id)}">${esc(p.title)}</button>`;
    }
    html += `</div>`;

    if (sel) {
      html += `<p class="structure-selection">선택: <strong>${esc(sel)}</strong> · 모듈 클릭 → ARXML · 「파일 상세」에서 XML/컨테이너</p>`;
    }

    const colCount = ar.stacks.length + (ar.other_count > 0 ? 1 : 0);
    html += `<div class="autosar-diagram" style="--stack-cols:${colCount}">`;

    // Application band (full width, top)
    html += `<div class="layer-band layer-app">
      <div class="band-label">Application Layer</div>
      <div class="band-cells-full">`;
    const apps = ar.application || [];
    if (apps.length) {
      for (const m of apps) {
        html += modCell(m, sel, this._activePathModules(ar));
      }
    } else {
      html += `<span class="band-empty">Swcd_App 없음</span>`;
    }
    html += `</div></div>`;

    // RTE band (full width)
    html += `<div class="layer-band layer-rte">
      <div class="band-label">Runtime Environment (RTE)</div>
      <div class="band-cells band-cells-full">`;
    for (const m of ar.rte || []) {
      html += modCell(m, sel, this._activePathModules(ar));
    }
    if (!(ar.rte || []).length) {
      html += `<span class="band-empty">—</span>`;
    }
    html += `</div></div>`;

    // Stack columns header
    html += `<div class="stacks-header">`;
    for (const stack of ar.stacks) {
      html += `<div class="stack-col-head">${esc(stack.label)}</div>`;
    }
    if (ar.other_count > 0) {
      html += `<div class="stack-col-head stack-col-other">기타</div>`;
    }
    html += `</div>`;

    // Layer bands: Service → ECU Abstraction → MCAL
    const bandOrder = [
      { key: "service", cls: "layer-service", label: "Service Layer" },
      { key: "ecu_abs", cls: "layer-ecu", label: "ECU Abstraction Layer" },
      { key: "mcal", cls: "layer-mcal", label: "MCAL" },
    ];

    for (const band of bandOrder) {
      html += `<div class="layer-band ${band.cls}">
        <div class="band-label">${esc(band.label)}</div>
        <div class="stacks-row">`;
      for (const stack of ar.stacks) {
        const mods = stack.bands?.[band.key] || [];
        html += `<div class="stack-col">`;
        for (const m of mods) {
          html += modCell(m, sel, this._activePathModules(ar));
        }
        html += `</div>`;
      }
      if (ar.other_count > 0 && band.key === "service") {
        html += `<div class="stack-col stack-col-other">`;
        if (this._showOther) {
          for (const m of ar.other) {
            html += modCell(m, sel, this._activePathModules(ar));
          }
        } else {
          html += `<button type="button" class="btn-show-other" id="btn-show-other">+${ar.other_count} 모듈</button>`;
        }
        html += `</div>`;
      } else if (ar.other_count > 0) {
        html += `<div class="stack-col stack-col-other"></div>`;
      }
      html += `</div></div>`;
    }

    html += `</div></div>`;
    this.container.innerHTML = html;

    this.container.querySelectorAll(".path-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._activePath = btn.dataset.pathId;
        this._draw(this._data);
      });
    });

    this.container.querySelector("#btn-show-other")?.addEventListener("click", () => {
      this._showOther = true;
      this._draw(this._data);
    });

    this._bindChips();
  }

  _activePathModules(ar) {
    const p = (ar.paths || []).find((x) => x.id === this._activePath);
    return new Set(p?.modules || []);
  }

  _bindChips() {
    this.container.querySelectorAll(".layer-mod").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.onModuleClick?.({
          module: btn.dataset.module,
          file: btn.dataset.file,
        });
      });
    });
  }
}

function modCell(m, selected, pathSet) {
  const onPath = pathSet.has(m.module) || m.on_path;
  let cls = "layer-mod";
  if (m.module === selected) cls += " layer-mod-selected";
  else if (m.dimmed) cls += " layer-mod-dimmed";
  else if (onPath) cls += " layer-mod-path";
  return `<button type="button" class="${cls}" data-module="${escAttr(m.module)}" data-file="${escAttr(m.file || "")}">${esc(m.label)}</button>`;
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escAttr(s) {
  return esc(s).replace(/"/g, "&quot;");
}
