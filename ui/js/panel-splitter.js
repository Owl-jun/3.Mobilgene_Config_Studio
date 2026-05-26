/**
 * Resizable 3-column layout with persisted widths.
 */

const STORAGE_KEY = "mcs_panel_widths";
const DEFAULTS = [260, null, 300]; // center = flex
const MIN = [160, 320, 200];

export function initPanelSplitters(rootEl) {
  const panels = rootEl.querySelectorAll(".panel-col");
  if (panels.length !== 3) return;

  const saved = loadWidths();
  applyWidths(panels, saved);

  const splitters = rootEl.querySelectorAll(".panel-splitter");
  splitters.forEach((splitter, i) => {
    splitter.addEventListener("mousedown", (e) => startDrag(e, i, panels, rootEl));
  });
}

function loadWidths() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return [...DEFAULTS];
}

function saveWidths(left, right) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([left, null, right]));
}

function applyWidths(panels, widths) {
  const [left, , right] = widths;
  if (left) panels[0].style.width = `${left}px`;
  if (right) panels[2].style.width = `${right}px`;
}

function startDrag(e, splitterIndex, panels, rootEl) {
  e.preventDefault();
  const leftPanel = panels[0];
  const rightPanel = panels[2];
  const startX = e.clientX;
  const startLeft = leftPanel.offsetWidth;
  const startRight = rightPanel.offsetWidth;

  document.body.classList.add("is-resizing");

  const onMove = (ev) => {
    const dx = ev.clientX - startX;
    if (splitterIndex === 0) {
      const newLeft = clamp(startLeft + dx, MIN[0], rootEl.clientWidth - MIN[1] - startRight - 80);
      leftPanel.style.width = `${newLeft}px`;
    } else {
      const newRight = clamp(startRight - dx, MIN[2], rootEl.clientWidth - MIN[0] - startLeft - 80);
      rightPanel.style.width = `${newRight}px`;
    }
  };

  const onUp = () => {
    document.body.classList.remove("is-resizing");
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    saveWidths(leftPanel.offsetWidth, rightPanel.offsetWidth);
  };

  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}
