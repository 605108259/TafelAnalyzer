const { contextBridge, ipcRenderer } = require("electron");

const backendArg = process.argv.find((arg) => arg.startsWith("--tafel-backend="));
const backendUrl = backendArg ? backendArg.slice("--tafel-backend=".length) : "http://127.0.0.1:8765";

contextBridge.exposeInMainWorld("tafel", {
  backendUrl,
  openDataFiles: () => ipcRenderer.invoke("dialog:open-data"),
  openCache: () => ipcRenderer.invoke("dialog:open-cache"),
  saveFile: (options) => ipcRenderer.invoke("dialog:save-file", options),
  saveDirectory: () => ipcRenderer.invoke("dialog:save-directory"),
});

