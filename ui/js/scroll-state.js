/**
 * Scroll / viewport preservation across DOM updates.
 */

export function captureScroll(scrollEl, options = {}) {
  if (!scrollEl) return null;
  const anchorSel = options.anchorSelector || ".tree-row.selected";
  const anchor = scrollEl.querySelector(anchorSel);
  let anchorPath = null;
  let anchorOffset = 0;
  if (anchor) {
    anchorPath =
      anchor.dataset.path ||
      anchor.dataset.folder ||
      anchor.getAttribute("data-path");
    const elRect = anchor.getBoundingClientRect();
    const scRect = scrollEl.getBoundingClientRect();
    anchorOffset = elRect.top - scRect.top;
  }
  return {
    scrollTop: scrollEl.scrollTop,
    scrollLeft: scrollEl.scrollLeft,
    anchorPath,
    anchorOffset,
  };
}

export function restoreScroll(scrollEl, state) {
  if (!scrollEl || !state) return;

  const apply = () => {
    if (state.anchorPath) {
      const anchor = scrollEl.querySelector(
        `[data-path="${cssEscape(state.anchorPath)}"], [data-folder="${cssEscape(state.anchorPath)}"]`
      );
      if (anchor) {
        const elRect = anchor.getBoundingClientRect();
        const scRect = scrollEl.getBoundingClientRect();
        const delta = elRect.top - scRect.top - state.anchorOffset;
        scrollEl.scrollTop += delta;
        return;
      }
    }
    scrollEl.scrollTop = state.scrollTop;
    scrollEl.scrollLeft = state.scrollLeft || 0;
  };

  requestAnimationFrame(() => {
    apply();
    requestAnimationFrame(apply);
  });
}

function cssEscape(value) {
  if (typeof CSS !== "undefined" && CSS.escape) {
    return CSS.escape(value);
  }
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}
