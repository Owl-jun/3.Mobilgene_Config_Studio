import { Api } from "./api.js";

/**
 * REF click → resolve → open file & focus node.
 */
export async function navigateToRef(ref, { fromFile, workspaceFiles, fileTree, configView, propertyPanel, setStatus }) {
  if (!ref || !ref.startsWith("/")) {
    setStatus?.("외부 REF 경로만 지원합니다");
    return false;
  }
  setStatus?.(`REF 탐색: ${ref.split("/").pop()}…`);
  try {
    const resolved = await Api.resolveRef(ref, fromFile);
    if (!resolved.resolved) {
      setStatus?.(resolved.message || "REF 대상 없음");
      return false;
    }

    const file = workspaceFiles.find(
      (f) => f.path === resolved.file || f.relative === resolved.relative
    );
    if (!file) {
      setStatus?.(`파일 없음: ${resolved.relative}`);
      return false;
    }

    fileTree.selectedPath = file.path;
    fileTree.render({ preserveScroll: true });

    await configView.loadFile(file);
    if (resolved.autosar_path) {
      await configView.focusPath(resolved.autosar_path, {
        name: resolved.name,
      });
    }

    setStatus?.(`↗ ${resolved.relative} · ${resolved.match}`);
    return true;
  } catch (e) {
    setStatus?.(`REF 오류: ${e.message}`);
    return false;
  }
}

/** Bind delegated clicks on ref-link elements */
export function bindRefLinks(container, handler) {
  container.addEventListener("click", (e) => {
    const link = e.target.closest(".ref-link[data-ref]");
    if (!link) return;
    e.preventDefault();
    e.stopPropagation();
    handler(link.dataset.ref, link.dataset.fromFile || null);
  });
}

export function refLinkHtml(value, { fromFile } = {}) {
  if (!value || typeof value !== "string") return "";
  const v = value.trim();
  if (!v.startsWith("/")) return escapeHtml(v);
  return `<button type="button" class="ref-link" data-ref="${escapeAttr(v)}" data-from-file="${escapeAttr(fromFile || "")}" title="정의로 이동">${escapeHtml(v)}</button>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}
