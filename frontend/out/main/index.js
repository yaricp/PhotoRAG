"use strict";
const electron = require("electron");
const path = require("path");
function registerIpcHandlers(backendPort) {
  console.log("[IPC] registering handlers, port =", backendPort);
  electron.ipcMain.handle("select-folder", async () => {
    const result = await electron.dialog.showOpenDialog({
      properties: ["openDirectory"],
      title: "Select Photos Folder"
    });
    return result.canceled ? null : result.filePaths[0];
  });
  console.log("[IPC] registering get-backend-port");
  electron.ipcMain.handle("get-backend-port", () => backendPort);
  console.log("[IPC] done");
}
function registerAppProtocol() {
  electron.protocol.handle("app", (request) => {
    const url = new URL(request.url);
    const filePath = url.searchParams.get("path") ?? "";
    return electron.net.fetch(`file://${filePath}`);
  });
}
let mainWindow = null;
async function createWindow() {
  registerIpcHandlers(8e3);
  mainWindow = new electron.BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  if (!electron.app.isPackaged) {
    await mainWindow.loadURL("http://127.0.0.1:5173");
    mainWindow.webContents.openDevTools();
  } else {
    await mainWindow.loadFile("dist/index.html");
  }
}
electron.app.whenReady().then(() => {
  registerAppProtocol();
  createWindow();
});
electron.app.on("window-all-closed", () => {
  if (process.platform !== "darwin") electron.app.quit();
});
