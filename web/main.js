const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");

let backend = null;
let backendInfo = null;
let mainWindow = null;

function startBackend() {
  return new Promise((resolve, reject) => {
    const root = path.resolve(__dirname, "..");
    const python = process.env.TAFEL_PYTHON || "python";
    backend = spawn(python, ["src/web/backend.py", "--port", "0"], {
      cwd: root,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });

    let settled = false;
    backend.stdout.on("data", (chunk) => {
      const lines = chunk.toString("utf8").split(/\r?\n/).filter(Boolean);
      for (const line of lines) {
        try {
          const payload = JSON.parse(line);
          if (payload.event === "TAFEL_WEB_BACKEND") {
            backendInfo = payload;
            settled = true;
            resolve(payload);
          }
        } catch (_error) {
          // Keep stdout quiet unless it is the startup JSON line.
        }
      }
    });
    backend.stderr.on("data", (chunk) => {
      console.error(chunk.toString("utf8"));
    });
    backend.on("exit", (code) => {
      if (!settled) {
        reject(new Error(`Python backend exited before startup, code=${code}`));
      }
    });
  });
}

async function createWindow() {
  const info = backendInfo || await startBackend();
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 900,
    minWidth: 1180,
    minHeight: 720,
    title: "Tafel Analyzer",
    backgroundColor: "#f8fafc",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--tafel-backend=http://${info.host}:${info.port}`],
    },
  });
  await mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

ipcMain.handle("dialog:open-data", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "选择数据文件",
    properties: ["openFile", "multiSelections"],
    filters: [
      { name: "Data files", extensions: ["tdms", "csv", "xlsx", "xls", "cor", "txt"] },
      { name: "All files", extensions: ["*"] },
    ],
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle("dialog:open-cache", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "导入缓存项目",
    properties: ["openFile", "openDirectory"],
    filters: [
      { name: "Cache", extensions: ["json"] },
      { name: "All files", extensions: ["*"] },
    ],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("dialog:save-file", async (_event, options = {}) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: options.title || "保存文件",
    defaultPath: options.defaultPath || "",
    filters: options.filters || [{ name: "All files", extensions: ["*"] }],
  });
  return result.canceled ? null : result.filePath;
});

ipcMain.handle("dialog:save-directory", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "选择缓存项目保存目录",
    properties: ["openDirectory", "createDirectory"],
  });
  return result.canceled ? null : result.filePaths[0];
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (backend && !backend.killed) {
    backend.kill();
  }
});

