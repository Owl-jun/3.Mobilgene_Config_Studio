import { Api } from "./api.js";
import { FileTreePanel } from "./file-tree.js";
import { ConfigViewPanel } from "./config-view.js";
import { PropertyPanel } from "./property-panel.js";
import { initPanelSplitters } from "./panel-splitter.js";
import { navigateToRef } from "./ref-nav.js";
import { getProfileMeta } from "./profiles/registry.js";

const WORKSPACE_KEY = "mcs_last_workspace";

const els = {
  workspaceInput: document.getElementById("workspace-path"),
  openBtn: document.getElementById("btn-open"),
  themeBtn: document.getElementById("btn-theme"),
  fileFilter: document.getElementById("file-filter"),
  fileTree: document.getElementById("file-tree-panel"),
  configToolbar: document.getElementById("config-toolbar"),
  configContent: document.getElementById("config-content"),
  propertyPanel: document.getElementById("property-panel"),
  centerModeTabs: document.getElementById("center-mode-tabs"),
  status: document.getElementById("status-bar"),
};

let workspaceData = null;

function setStatus(msg) {
  els.status.textContent = msg;
}

function setCenterMode(mode) {
  document.querySelectorAll(".center-mode-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
  configView.setCenterMode(mode);
}

async function handleRefClick(ref, fromFile) {
  await navigateToRef(ref, {
    fromFile,
    workspaceFiles: workspaceData?.files || [],
    fileTree,
    configView,
    propertyPanel,
    setStatus,
  });
}

const fileTree = new FileTreePanel(els.fileTree, {
  onSelect: onFileSelect,
  scrollEl: document.getElementById("file-tree-panel"),
});

const configView = new ConfigViewPanel(els.configContent, els.configToolbar, {
  onNodeSelect: onNodeSelect,
  onRowSelect: onRowSelect,
  onRefClick: handleRefClick,
  scrollEl: document.getElementById("config-content"),
});
configView.onModuleClick = onModuleClick;

const propertyPanel = new PropertyPanel(els.propertyPanel, {
  onRefClick: handleRefClick,
});

async function openWorkspace(path) {
  if (!path) return;
  setStatus("워크스페이스 스캔 중…");
  try {
    workspaceData = await Api.openWorkspace(path);
    localStorage.setItem(WORKSPACE_KEY, path);
    fileTree.setFiles(workspaceData.files);
    const ri = workspaceData.ref_index;
    setStatus(
      `${workspaceData.arxml_count} ARXML · 구조 맵 ${workspaceData.module_graph ?? "?"} 모듈`
    );
    propertyPanel.clear();
    setCenterMode("structure");
    await configView.showStructureGraph();
  } catch (e) {
    setStatus(`오류: ${e.message}`);
  }
}

async function onFileSelect({ file }) {
  propertyPanel.currentFile = file;
  propertyPanel.showFileInfo(file);

  if (configView.centerMode === "structure") {
    setStatus(`${file.name} — 구조 맵에서 강조`);
    await configView.showStructureGraph(file);
    // 상세 뷰 데이터는 백그라운드로 준비
    configView.currentFile = file;
    configView.currentProfile = file.profile || "generic";
    return;
  }

  setStatus(`로딩: ${file.name}`);
  await configView.loadFile(file);
  setStatus(`${file.profile} · ${file.name}`);
}

async function onModuleClick({ module, file }) {
  if (!workspaceData?.files) return;
  const f =
    workspaceData.files.find((x) => x.path === file) ||
    workspaceData.files.find((x) => x.name === `Ecud_${module}.arxml`) ||
    workspaceData.files.find((x) => x.relative.includes(`Ecud_${module}`)) ||
    workspaceData.files.find((x) => x.name === "Gateway.arxml" && module === "Gateway");

  if (!f) {
    setStatus(`모듈 파일 없음: ${module}`);
    return;
  }

  fileTree.selectedPath = f.path;
  fileTree.render({ preserveScroll: true });
  propertyPanel.showFileInfo(f);

  if (configView.centerMode === "structure") {
    await configView.showStructureGraph(f);
    configView.currentFile = f;
    configView.currentProfile = f.profile || "generic";
    setStatus(`구조 맵 · ${module}`);
    return;
  }

  await configView.loadFile(f);
  setStatus(`${f.profile} · ${module}`);
}

async function onNodeSelect({ path, node }) {
  const file = configView.currentFile;
  if (!file) return;
  propertyPanel.currentFile = file;
  try {
    const data = await Api.properties(file.path, path || node.path);
    propertyPanel.showProperties(data, {
      editable: file.editable,
      fromFile: file.path,
    });
  } catch {
    propertyPanel.showProperties({
      tag: node.tag,
      path: node.path,
      properties: [
        { key: "SHORT-NAME", value: node.name || "", readonly: false },
        ...(node.text
          ? [
              {
                key: node.tag,
                value: node.text,
                readonly: true,
                is_ref:
                  node.tag?.endsWith("-REF") || node.tag === "DEFINITION-REF",
              },
            ]
          : []),
      ],
    }, { fromFile: file.path });
  }
}

function onRowSelect(payload) {
  const file = configView.currentFile;
  propertyPanel.currentFile = file;
  if (payload.type === "gateway_mapping") {
    propertyPanel.showMappingRow(payload.row, {
      editable: file?.editable,
      fromFile: file?.path,
    });
  } else if (payload.type === "ecuc_container") {
    propertyPanel.showContainer(payload.row, {
      editable: file?.editable,
      fromFile: file?.path,
    });
  }
}

function initTheme() {
  const saved = localStorage.getItem("mcs_theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  els.themeBtn.textContent = saved === "dark" ? "☀" : "☾";
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("mcs_theme", next);
  els.themeBtn.textContent = next === "dark" ? "☀" : "☾";
}

els.openBtn.addEventListener("click", () => {
  openWorkspace(els.workspaceInput.value.trim());
});

els.workspaceInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") openWorkspace(els.workspaceInput.value.trim());
});

els.fileFilter?.addEventListener("input", (e) => {
  fileTree.setFilter(e.target.value);
});

els.centerModeTabs?.querySelectorAll(".center-mode-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const mode = btn.dataset.mode;
    setCenterMode(mode);
    if (mode === "detail" && configView.currentFile) {
      configView.loadFile(configView.currentFile);
    }
  });
});

document.getElementById("file-tree-expand-all")?.addEventListener("click", () => {
  fileTree.expandAll();
});
document.getElementById("file-tree-collapse-all")?.addEventListener("click", () => {
  fileTree.collapseAll();
});

els.themeBtn.addEventListener("click", toggleTheme);

initTheme();
initPanelSplitters(document.getElementById("main-panels"));

const last = localStorage.getItem(WORKSPACE_KEY);
if (last) {
  els.workspaceInput.value = last;
  openWorkspace(last);
} else {
  const defaultWs = "c:\\MyJob\\2.AD_Gateway\\AD_Gateway\\rgw_working";
  els.workspaceInput.value = defaultWs;
  setStatus("워크스페이스 경로를 입력하고 열기를 누르세요.");
}

Api.health()
  .then((h) => {
    if (!h.features?.includes("module_graph")) {
      setStatus("서버 구버전 — run-dev.ps1 재시작 필요");
    }
    if (h.workspace) openWorkspace(h.workspace);
  })
  .catch(() => {
    setStatus("개발 서버 미실행 — run-dev.ps1 실행");
  });
