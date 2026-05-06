"use strict";
const electron = require("electron");
console.log("[PRELOAD] LOADED");
electron.contextBridge.exposeInMainWorld("electronAPI", {
  openFolder: () => electron.ipcRenderer.invoke("select-folder"),
  getBackendPort: () => electron.ipcRenderer.invoke("get-backend-port"),
  onBackendReady: (cb) => {
    electron.ipcRenderer.on("backend-ready", (_, port) => cb(port));
  },
  platform: process.platform
});
