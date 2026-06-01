const apiBase = window.tafel.backendUrl;
let state = null;

const $ = (id) => document.getElementById(id);

async function api(path, data) {
  const init = data === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
  const response = await fetch(`${apiBase}${path}`, init);
  const payload = await response.json();
  if (!payload.ok) {
    state = payload.state || state;
    render();
    throw new Error(payload.error || "请求失败");
  }
  state = payload.state;
  render();
  return payload.state;
}

function showError(error) {
  $("status").textContent = error.message || String(error);
  $("status").classList.add("danger");
}

function clearError() {
  $("status").classList.remove("danger");
}

async function run(action) {
  clearError();
  try {
    await action();
  } catch (error) {
    showError(error);
  }
}

function setPanel(name) {
  document.querySelectorAll(".rail-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.panel === name);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${name}`);
  });
}

function render() {
  if (!state) {
    return;
  }
  renderFiles();
  renderSegments();
  renderComparison();
  renderHistory();
  renderToolbar();
  renderSummary();
  $("chart").src = state.chart_png || "";
  $("status").textContent = state.status || "";
}

function renderFiles() {
  $("file-list").innerHTML = "";
  for (const file of state.files || []) {
    const row = document.createElement("div");
    row.className = `row${file.path === state.current_path ? " active" : ""}`;
    row.innerHTML = `
      <div class="row-title"><strong title="${escapeAttr(file.path)}">${escapeHtml(file.name)}</strong></div>
      <div class="row-meta">${escapeHtml(file.path)}</div>
      <div class="actions">
        <button data-act="select">选择</button>
        <button data-act="remove">移除</button>
      </div>
    `;
    row.querySelector('[data-act="select"]').onclick = () => run(() => api("/api/select-file", { path: file.path }));
    row.querySelector('[data-act="remove"]').onclick = () => run(() => api("/api/remove-file", { path: file.path }));
    $("file-list").appendChild(row);
  }
}

function renderSegments() {
  $("segment-list").innerHTML = "";
  for (const segment of state.segments || []) {
    const row = document.createElement("div");
    row.className = `row${segment.index === state.active_segment_index ? " active" : ""}`;
    row.innerHTML = `
      <input type="checkbox" ${segment.selected ? "checked" : ""} />
      <div>
        <div class="row-title">
          <span class="swatch" style="background:${segment.color}"></span>
          <strong>${escapeHtml(segment.label)}</strong>
        </div>
        <div class="row-meta">${segment.has_fit ? "已拟合" : "未拟合"}${segment.error ? ` · ${escapeHtml(segment.error)}` : ""}</div>
      </div>
      <input type="color" value="${segment.color}" title="颜色" />
    `;
    row.onclick = (event) => {
      if (event.target.tagName !== "INPUT") {
        run(() => api("/api/set-segment", { index: segment.index }));
      }
    };
    row.querySelector('input[type="checkbox"]').onchange = (event) => {
      run(() => api("/api/set-segment", { index: segment.index, selected: event.target.checked }));
    };
    row.querySelector('input[type="color"]').onchange = (event) => {
      run(() => api("/api/set-segment", { index: segment.index, color: event.target.value }));
    };
    $("segment-list").appendChild(row);
  }
}

function renderComparison() {
  $("comparison-list").innerHTML = "";
  $("lsv-style").value = state.comparison_lsv_style || "line_marker";
  $("fit-window").checked = Boolean(state.comparison_tafel_fit_window);
  for (const item of state.comparison_items || []) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="row-title">
        <input type="checkbox" ${item.visible ? "checked" : ""} />
        <span class="swatch" style="background:${item.color}"></span>
        <strong>${escapeHtml(item.label)}</strong>
      </div>
      <div class="row-meta">${escapeHtml(item.file_name)} · Segment ${item.segment_index + 1}${item.slope_mv_per_dec === null ? "" : ` · ${item.slope_mv_per_dec.toFixed(2)} mV/dec`}</div>
      <div class="actions">
        <input type="color" value="${item.color}" />
        <button data-act="remove">移除</button>
      </div>
    `;
    row.querySelector('input[type="checkbox"]').onchange = (event) => {
      run(() => api("/api/update-comparison", { item_id: item.item_id, visible: event.target.checked }));
    };
    row.querySelector('input[type="color"]').onchange = (event) => {
      run(() => api("/api/update-comparison", { item_id: item.item_id, color: event.target.value }));
    };
    row.querySelector('[data-act="remove"]').onclick = () => {
      run(() => api("/api/update-comparison", { item_id: item.item_id, remove: true }));
    };
    $("comparison-list").appendChild(row);
  }
}

function renderHistory() {
  $("history-list").innerHTML = "";
  for (const item of state.history || []) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="row-title"><strong>${escapeHtml(item.title)}</strong></div>
      <div class="row-meta">${escapeHtml(item.updated_at || "")}</div>
      <div class="row-meta">${escapeHtml(item.cache_path || "")}</div>
      <button>恢复</button>
    `;
    row.querySelector("button").onclick = () => run(() => api("/api/cache/import", { path: item.cache_path }));
    $("history-list").appendChild(row);
  }
}

function renderToolbar() {
  $("potential-formula").value = state.formulas?.potential || "";
  $("current-formula").value = state.formulas?.current || "";
  $("e-eq").value = state.params?.e_eq || "0";
  $("window-range").value = state.params?.window_range || "12-15";
  $("eta-range").value = state.params?.eta_range || "";
  $("logj-range").value = state.params?.logj_range || "";
  $("min-r2").value = state.params?.min_r2 || "0.95";
  $("fit-priority").value = normalizePriority(state.params?.fit_priority);
}

function renderSummary() {
  const summary = $("fit-summary");
  summary.innerHTML = "";
  for (const [segment, fit] of Object.entries(state.fits || {})) {
    const item = document.createElement("span");
    item.className = "pill";
    item.textContent = `S${Number(segment) + 1}: ${fit.slope_mv_per_dec.toFixed(2)} mV/dec, R²=${fit.r2.toFixed(4)}`;
    summary.appendChild(item);
  }
}

function normalizePriority(value) {
  return value === "r2" ? "r2" : "slope";
}

function collectParams() {
  return {
    e_eq: $("e-eq").value,
    window_range: $("window-range").value,
    eta_range: $("eta-range").value,
    logj_range: $("logj-range").value,
    min_r2: $("min-r2").value,
    fit_priority: $("fit-priority").value,
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

document.querySelectorAll(".rail-btn").forEach((button) => {
  button.onclick = () => setPanel(button.dataset.panel);
});

$("open-files").onclick = () => run(async () => {
  const paths = await window.tafel.openDataFiles();
  if (paths.length) {
    await api("/api/load-files", { paths });
  }
});

$("import-cache").onclick = () => run(async () => {
  const path = await window.tafel.openCache();
  if (path) {
    await api("/api/cache/import", { path });
  }
});

$("export-cache").onclick = () => run(async () => {
  const path = await window.tafel.saveDirectory();
  if (path) {
    await api("/api/cache/export", { path });
  }
});

$("export-cache-v2").onclick = () => run(async () => {
  const path = await window.tafel.saveFile({
    title: "导出 v2 缓存 JSON",
    defaultPath: "tafel-cache.json",
    filters: [{ name: "JSON", extensions: ["json"] }],
  });
  if (path) {
    await api("/api/cache/export", { path, v2: true });
  }
});

$("apply-formulas").onclick = () => run(async () => {
  await api("/api/set-params", collectParams());
  await api("/api/set-formulas", {
    potential: $("potential-formula").value,
    current: $("current-formula").value,
  });
});

for (const id of ["e-eq", "window-range", "eta-range", "logj-range", "min-r2", "fit-priority"]) {
  $(id).addEventListener("change", () => run(() => api("/api/set-params", collectParams())));
}

$("run-fit").onclick = () => run(async () => {
  await api("/api/set-params", collectParams());
  await api("/api/fit", { force: true });
});

$("manual-fit").onclick = () => run(() => api("/api/manual-fit", {
  x_min: $("manual-x-min").value,
  x_max: $("manual-x-max").value,
  y_min: $("manual-y-min").value,
  y_max: $("manual-y-max").value,
}));

$("select-all").onclick = () => run(() => api("/api/select-all-segments", { selected: true }));
$("select-none").onclick = () => run(() => api("/api/select-all-segments", { selected: false }));
$("add-comparison").onclick = () => run(() => api("/api/add-comparison", {}));
$("show-comparison").onclick = () => run(() => api("/api/chart-mode", { mode: "comparison" }));
$("clear-comparison").onclick = () => run(() => api("/api/update-comparison", { clear: true }));
$("lsv-style").onchange = () => run(() => api("/api/update-comparison", { comparison_lsv_style: $("lsv-style").value }));
$("fit-window").onchange = () => run(() => api("/api/update-comparison", { comparison_tafel_fit_window: $("fit-window").checked }));

$("save-raw").onclick = () => exportCurrent("raw_txt", "raw.txt", [{ name: "Text", extensions: ["txt"] }]);
$("save-processed").onclick = () => exportCurrent("processed_txt", "processed.txt", [{ name: "Text", extensions: ["txt"] }]);
$("save-npz").onclick = () => exportCurrent("npz", "fit.npz", [{ name: "NPZ", extensions: ["npz"] }]);
$("save-chart").onclick = () => exportCurrent("png", "tafel_chart.png", [
  { name: "Images", extensions: ["png", "pdf", "svg"] },
]);

function exportCurrent(kind, defaultPath, filters) {
  run(async () => {
    const path = await window.tafel.saveFile({ title: "导出", defaultPath, filters });
    if (path) {
      const ext = path.split(".").pop().toLowerCase();
      await api("/api/export/current", { kind: kind === "png" ? ext : kind, path });
    }
  });
}

api("/api/state").catch(showError);

