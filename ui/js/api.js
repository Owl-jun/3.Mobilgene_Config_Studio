/**
 * API layer — dev server fetch today, Tauri invoke later.
 */
export const Api = {
  base: "",

  async _fetch(path, options = {}) {
    const url = `${this.base}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || res.statusText);
    }
    return res.json();
  },

  health() {
    return this._fetch("/api/health");
  },

  openWorkspace(path) {
    return this._fetch("/api/open_workspace", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
  },

  workspace() {
    return this._fetch("/api/workspace");
  },

  index(file, depth = 2) {
    return this._fetch(
      `/api/index?file=${encodeURIComponent(file)}&depth=${depth}`
    );
  },

  subtree(file, nodePath, depth = 2) {
    return this._fetch(
      `/api/subtree?file=${encodeURIComponent(file)}&path=${encodeURIComponent(nodePath)}&depth=${depth}`
    );
  },

  gateway(file) {
    return this._fetch(`/api/gateway?file=${encodeURIComponent(file)}`);
  },

  ecuc(file, limit = 200) {
    return this._fetch(
      `/api/ecuc?file=${encodeURIComponent(file)}&limit=${limit}`
    );
  },

  properties(file, nodePath) {
    return this._fetch(
      `/api/properties?file=${encodeURIComponent(file)}&path=${encodeURIComponent(nodePath)}`
    );
  },

  resolveRef(ref, fromFile = null) {
    let q = `/api/resolve_ref?ref=${encodeURIComponent(ref)}`;
    if (fromFile) q += `&from_file=${encodeURIComponent(fromFile)}`;
    return this._fetch(q);
  },

  refIndex(rebuild = false) {
    return this._fetch(`/api/ref_index?rebuild=${rebuild ? "1" : "0"}`);
  },

  graph(file, focus = null, limit = 80) {
    let q = `/api/graph?file=${encodeURIComponent(file)}&limit=${limit}`;
    if (focus) q += `&focus=${encodeURIComponent(focus)}`;
    return this._fetch(q);
  },

  moduleGraph(filePath = null, module = null) {
    const params = new URLSearchParams();
    if (filePath) {
      params.set("file", String(filePath).replace(/\\/g, "/"));
    }
    if (module) params.set("module", module);
    const qs = params.toString();
    return this._fetch(`/api/module_graph${qs ? `?${qs}` : ""}`);
  },
};

/** Tauri bridge stub — swap Api.base calls to invoke when packaged */
export function isTauri() {
  return typeof window !== "undefined" && "__TAURI__" in window;
}
