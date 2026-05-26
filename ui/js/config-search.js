import { Api } from "./api.js";

/**
 * Workspace symbol search in file-detail toolbar.
 */
export function initConfigSearch({ inputEl, resultsEl, onPick, setStatus }) {
  if (!inputEl) return;

  let timer = null;

  inputEl.addEventListener("input", () => {
    clearTimeout(timer);
    const q = inputEl.value.trim();
    if (q.length < 2) {
      hideResults(resultsEl);
      return;
    }
    timer = setTimeout(() => runSearch(q, resultsEl, onPick, setStatus), 280);
  });

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      hideResults(resultsEl);
      inputEl.blur();
    }
  });

  document.addEventListener("click", (e) => {
    if (!resultsEl?.contains(e.target) && e.target !== inputEl) {
      hideResults(resultsEl);
    }
  });
}

async function runSearch(q, resultsEl, onPick, setStatus) {
  if (!resultsEl) return;
  resultsEl.innerHTML = '<div class="search-hint">검색 중…</div>';
  resultsEl.classList.remove("hidden");
  try {
    const data = await Api.search(q, 30);
    const rows = data.results || [];
    if (!rows.length) {
      resultsEl.innerHTML = '<div class="search-hint">결과 없음</div>';
      return;
    }
    let html = "";
    for (const r of rows) {
      html += `<button type="button" class="search-hit" data-file="${escAttr(
        r.file
      )}" data-path="${escAttr(r.autosar_path)}">
        <span class="search-hit-name">${esc(r.name)}</span>
        <span class="search-hit-meta">${esc(r.module || "")} · ${esc(
          r.file || ""
        )}</span>
      </button>`;
    }
    resultsEl.innerHTML = html;
    resultsEl.querySelectorAll(".search-hit").forEach((btn) => {
      btn.addEventListener("click", () => {
        hideResults(resultsEl);
        onPick?.({
          file: btn.dataset.file,
          path: btn.dataset.path,
          name: btn.querySelector(".search-hit-name")?.textContent,
        });
      });
    });
    setStatus?.(`검색: ${rows.length}건`);
  } catch (e) {
    resultsEl.innerHTML = `<div class="search-hint">${esc(e.message)}</div>`;
  }
}

function hideResults(el) {
  if (!el) return;
  el.classList.add("hidden");
  el.innerHTML = "";
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
