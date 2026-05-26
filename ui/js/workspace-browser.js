import { Api } from "./api.js";

/**
 * In-app folder browser + optional native OS picker (dev server side).
 */
export class WorkspaceBrowser {
  constructor(modalEl, { onSelect } = {}) {
    this.modal = modalEl;
    this.onSelect = onSelect;
    this.currentPath = null;
    this.isWorkspace = false;

    this.pathInput = modalEl.querySelector("#ws-browse-path");
    this.dirList = modalEl.querySelector("#ws-dir-list");
    this.hintEl = modalEl.querySelector("#ws-browse-hint");
    this.selectBtn = modalEl.querySelector("#ws-browse-select");
    this.upBtn = modalEl.querySelector("#ws-browse-up");
    this.nativeBtn = modalEl.querySelector("#ws-browse-native");

    modalEl.querySelectorAll("[data-ws-close]").forEach((el) => {
      el.addEventListener("click", () => this.close());
    });

    this.selectBtn?.addEventListener("click", () => {
      if (this.currentPath) {
        this.onSelect?.(this.currentPath);
        this.close();
      }
    });

    this.upBtn?.addEventListener("click", () => {
      if (this._parentPath) this.load(this._parentPath);
      else this.load(null);
    });

    this.nativeBtn?.addEventListener("click", () => this._pickNative());

    this.dirList?.addEventListener("dblclick", (e) => {
      const row = e.target.closest("[data-dir-path]");
      if (row) this.load(row.dataset.dirPath);
    });

    this.dirList?.addEventListener("click", (e) => {
      const row = e.target.closest("[data-dir-path]");
      if (!row) return;
      this.dirList.querySelectorAll(".ws-dir-row").forEach((r) => {
        r.classList.toggle("selected", r === row);
      });
      this.currentPath = row.dataset.dirPath;
      this.isWorkspace = row.dataset.isWorkspace === "1";
      this._updateSelectionUi();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !this.modal.classList.contains("hidden")) {
        this.close();
      }
    });
  }

  open(initialPath = null) {
    this.modal.classList.remove("hidden");
    this.modal.setAttribute("aria-hidden", "false");
    const start =
      initialPath?.trim() ||
      document.getElementById("workspace-path")?.value?.trim() ||
      null;
    this.load(start || null);
  }

  close() {
    this.modal.classList.add("hidden");
    this.modal.setAttribute("aria-hidden", "true");
  }

  async load(path) {
    this.dirList.innerHTML = '<li class="ws-dir-loading">로딩 중…</li>';
    this.selectBtn.disabled = true;
    this.hintEl.textContent = "";

    try {
      const data = await Api.browse(path);
      if (data.error) {
        this.dirList.innerHTML = `<li class="ws-dir-error">${esc(data.message || data.error)}</li>`;
        return;
      }

      this._parentPath = data.parent;
      this.currentPath = data.path;
      this.isWorkspace = !!data.is_workspace;
      this.pathInput.value = data.path || "(드라이브 / 루트)";
      this.upBtn.disabled = !data.parent && !data.path;

      if (!data.entries?.length) {
        this.dirList.innerHTML = '<li class="ws-dir-empty">하위 폴더 없음</li>';
      } else {
        this.dirList.innerHTML = data.entries
          .map(
            (e) => `<li>
              <button type="button" class="ws-dir-row" data-dir-path="${escAttr(e.path)}" data-is-workspace="${e.is_workspace ? "1" : "0"}">
                <span class="ws-dir-icon">${e.is_workspace ? "📦" : "📁"}</span>
                <span class="ws-dir-name">${esc(e.name)}</span>
                ${e.is_workspace ? '<span class="ws-dir-badge">워크스페이스</span>' : ""}
              </button>
            </li>`
          )
          .join("");
      }

      this._updateSelectionUi();
    } catch (e) {
      this.dirList.innerHTML = `<li class="ws-dir-error">${esc(e.message)}</li>`;
    }
  }

  _updateSelectionUi() {
    const canOpen = !!this.currentPath;
    this.selectBtn.disabled = !canOpen;
    if (!this.currentPath) {
      this.hintEl.textContent = "폴더를 선택하거나 더블클릭해 이동하세요.";
      return;
    }
    if (this.isWorkspace) {
      this.hintEl.textContent = "Configuration 폴더가 있는 Mobilgene 워크스페이스로 보입니다.";
    } else {
      this.hintEl.textContent =
        "Configuration/Ecu 가 없어도 열 수 있습니다. 하위에 ARXML이 있으면 표시됩니다.";
    }
  }

  async _pickNative() {
    this.hintEl.textContent = "시스템 폴더 창을 여는 중…";
    try {
      const res = await Api.browsePick(this.currentPath);
      if (res.cancelled) {
        this.hintEl.textContent = "취소됨";
        return;
      }
      if (res.path) {
        this.onSelect?.(res.path);
        this.close();
      }
    } catch (e) {
      this.hintEl.textContent = `시스템 창 실패: ${e.message}`;
    }
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
